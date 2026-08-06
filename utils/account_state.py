"""
Estado de cuenta del alumno — única fuente autorizada del veredicto financiero.

Motivo: un alumno preguntó si su curso estaba pagado y el bot le respondió que
sí, cuando en realidad estaba **al día** pero con 10 cuotas por delante. La
causa fue que el sistema deducía "pagado" de un solo campo (`Saldo_Vencido_2`),
que significa "no tiene deuda vencida" — no "canceló el contrato".

La regla de acá en adelante: **ningún agente concluye estado financiero por su
cuenta**. Esta función lo calcula y devuelve un texto (`render`) que los prompts
usan tal cual.

DEFINICIÓN DE COBRANZAS (ago-2026, acuerdo con Roberto — no cambiar sin él):

    El estado de cuenta es el SALDO PENDIENTE, no las cuotas pendientes.

Las cuotas y el saldo son acumuladores DISTINTOS: `Cuotas_pendientes_2` suma
cuotas acumuladas y `Saldo_pendiente` suma saldo acumulado. Con pagos parciales
o varias cuotas abonadas en un solo pago los dos se despegan, y eso es correcto
por diseño — no es un dato roto y no se puede "arreglar" sin romper el otro caso.

Por eso acá:
  · El veredicto sale del SALDO (`saldoTotal` y `saldoPendiente`/vencido).
  · Las cuotas solo se mencionan si coinciden con el saldo; si no, se callan.
  · Se valida la identidad contable `importeContrato - importePagado = saldoTotal`.
    Si NO cierra, no se afirma nada y se deriva a una persona.
"""

from __future__ import annotations

import datetime as _dt
from enum import StrEnum


class EstadoCuenta(StrEnum):
    SALDADO = "SALDADO"
    AL_DIA = "AL_DIA"
    CON_DEUDA_VENCIDA = "CON_DEUDA_VENCIDA"
    DATO_INSUFICIENTE = "DATO_INSUFICIENTE"


_TOL_V1 = 0.005  # 0.5% del contrato — redondeos y diferencias de cambio
_TOL_CUOTAS = 0.5  # media cuota de diferencia entre saldo y cuotas × valor

# Piso absoluto por moneda para considerar un saldo "cero" (residuo de
# redondeo). ⚠️ Tiene que ser ABSOLUTO, no un % de la cuota: `valorCuota` es
# contrato/cuotasTotales, así que en planes de pocas cuotas (o pago único) un
# porcentaje de la cuota es un porcentaje del contrato entero — y ahí una deuda
# real se vuelve invisible. En monedas sin decimales (COP, PYG, CLP) el efecto
# se multiplica.
_PISO_REDONDEO = {
    "ARS": 100.0,
    "BOB": 10.0,
    "CLP": 500.0,
    "COP": 5000.0,
    "CRC": 500.0,
    "DOP": 60.0,
    "EUR": 1.0,
    "GTQ": 10.0,
    "HNL": 30.0,
    "MXN": 20.0,
    "NIO": 40.0,
    "PEN": 4.0,
    "PYG": 5000.0,
    "USD": 1.0,
    "UYU": 40.0,
}
_PISO_DEFAULT = 1.0  # moneda desconocida → exigimos saldo casi exacto

_TEXTO_SIN_DATOS = (
    "SIN DATOS CONFIABLES DE FINANCIACIÓN — PROHIBIDO afirmar si el curso está "
    "pagado, saldado o al día. Decile que estás verificando su situación y "
    "derivá al portal de tickets."
)


def _money(monto: float, moneda: str = "") -> str:
    """Formatea 212881.0 → 'ARS 212.881,00' (convención en español)."""
    entero, _, dec = f"{monto:,.2f}".partition(".")
    return f"{moneda} {entero.replace(',', '.')},{dec}".strip()


def _plural(n: int, singular: str, plural: str) -> str:
    """'1 cuota vencida' / '3 cuotas vencidas' — sin los '(s)' que el LLM copia."""
    return f"{n} {singular if n == 1 else plural}"


def _cuotas_equivalentes(saldo: float, valor_cuota: float, moneda: str = "") -> int | None:
    """
    Cuántas cuotas faltan, DERIVADO del saldo (`saldo ÷ valor de cuota`).

    No se usa el contador `Cuotas_pendientes_2` de Zoho porque acumula distinto
    que el saldo (ver docstring del módulo). Este número, en cambio, siempre es
    coherente con la plata: si el alumno abonó 11 cuotas de un saque, el saldo
    baja y acá dan 0 — que es lo que hay que contestarle.

    El sobrante se cuenta como una cuota más solo si supera el piso de redondeo
    de la moneda: un resto de centavos es ruido del contrato, no un pago.
    """
    if valor_cuota <= 0 or saldo <= 0:
        return None
    piso = _PISO_REDONDEO.get(moneda.strip().upper(), _PISO_DEFAULT)
    enteras = int(saldo / valor_cuota)
    resto = saldo - enteras * valor_cuota
    return enteras + 1 if resto > piso else enteras


def _pago_reciente(fecha: str | None, dias: int = 5) -> bool:
    """True si `fecha` (YYYY-MM-DD de Zoho) cae dentro de los últimos N días."""
    if not fecha:
        return False
    try:
        d = _dt.date.fromisoformat(str(fecha)[:10])
    except ValueError:
        return False
    delta = (_dt.date.today() - d).days
    return 0 <= delta <= dias


def _num(ficha: dict, key: str) -> float:
    try:
        return float(ficha.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _ent(ficha: dict, key: str) -> int:
    try:
        return int(ficha.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def clasificar_estado_cuenta(ficha: dict | None) -> dict:
    """
    Determina el estado de cuenta a partir de la ficha normalizada de
    `integrations/zoho/area_cobranzas.py`.

    Devuelve un dict con:
        estado            EstadoCuenta
        confiable         bool — False si los importes no cierran
        cuotasConfiables  bool — False si las cuotas contradicen al saldo
        inconsistencias   list[str] — qué chequeo falló (para logs / limpieza)
        render            str — texto listo para inyectar en el prompt
        (+ los números crudos que el agente puede citar)
    """
    inconsistencias: list[str] = []

    def _insuficiente(motivo: str, f: dict | None = None) -> dict:
        f = f or {}
        inconsistencias.append(motivo)
        return {
            "estado": EstadoCuenta.DATO_INSUFICIENTE,
            "confiable": False,
            "cuotasConfiables": False,
            "inconsistencias": inconsistencias,
            "moneda": str(f.get("moneda") or ""),
            "saldoTotal": _num(f, "saldoTotal"),
            "saldoVencido": _num(f, "saldoPendiente"),
            "cuotasPendientes": _ent(f, "cuotasPendientes"),
            "valorCuota": _num(f, "valorCuota"),
            "render": _TEXTO_SIN_DATOS,
        }

    if not ficha or not ficha.get("cobranzaId"):
        return _insuficiente("sin_ficha")

    # Ficha cacheada con el formato viejo (Redis `datos_deudor:*`, TTL 2h):
    # no trae `importePagado`, así que la identidad contable daría falso
    # negativo y TODO alumno caería en DATO_INSUFICIENTE hasta que expire. Se
    # detecta por ausencia de la clave (≠ presente en 0, que es "no pagó nada")
    # y se releen los datos en vez de emitir un veredicto a ciegas.
    if "importePagado" not in ficha:
        return _insuficiente("ficha_formato_viejo", ficha)

    moneda = str(ficha.get("moneda") or "")
    contrato = _num(ficha, "importeContrato")
    pagado = _num(ficha, "importePagado")
    saldo_total = _num(ficha, "saldoTotal")
    saldo_vencido = _num(ficha, "saldoPendiente")  # ⚠️ es la deuda VENCIDA
    valor_cuota = _num(ficha, "valorCuota")
    c_tot = _ent(ficha, "cuotasTotales")
    c_pag = _ent(ficha, "cuotasPagas")
    c_pend = _ent(ficha, "cuotasPendientes")
    c_venc = _ent(ficha, "cuotasVencidas")
    dias = _ent(ficha, "diasAtraso")
    prox = str(ficha.get("fechaProximaCuota") or "").strip()

    # ── V1 · identidad contable: contrato − pagado = saldo ──────────────────
    # Si no cierra, ningún número del registro es confiable: cortamos acá.
    #
    # Vale también cuando el alumno no pagó nada (`importePagado` vacío en Zoho
    # llega como 0): ahí la cuenta exige `saldoTotal == contrato`. Eso atrapa
    # justamente el caso peligroso — un registro sin pagos donde el saldo quedó
    # en 0 por dato viejo, que sin esta validación se leería como "saldado".
    if contrato <= 0:
        # Sin monto de contrato no hay contra qué validar.
        return _insuficiente("contrato_en_cero", ficha)

    if abs((contrato - pagado) - saldo_total) > max(1.0, contrato * _TOL_V1):
        return _insuficiente("importes_no_cierran", ficha)

    # ── Coherencia de las cuotas ───────────────────────────────────────────
    # OJO: que las cuotas no coincidan con el saldo NO es un error de dato.
    # Los contadores de cuotas y el saldo son acumuladores distintos (definición
    # de Cobranzas, ago-2026): si alguien abona varias cuotas en un solo pago o
    # hace un pago parcial, se despegan entre sí. Es esperable e inamovible.
    # Por eso esto NO va a `inconsistencias` (que significa "dato a revisar"):
    # solo baja la bandera para que el bot no cite cuotas, y hable de plata.
    cuotas_confiables = True
    notas_cuotas: list[str] = []
    if c_tot > 0 and (c_pag + c_pend) != c_tot:
        notas_cuotas.append("cuotas_no_suman")
        cuotas_confiables = False
    if valor_cuota > 0:
        esperado = c_pend * valor_cuota
        if abs(esperado - saldo_total) > max(valor_cuota * _TOL_CUOTAS, 1.0):
            notas_cuotas.append("cuotas_no_coinciden_con_saldo")
            cuotas_confiables = False
    elif c_pend > 0:
        notas_cuotas.append("sin_valor_de_cuota")
        cuotas_confiables = False

    # ── Veredicto ──────────────────────────────────────────────────────────
    # El orden importa: la identidad contable (V1, ya validada) manda sobre los
    # campos de mora, que Zoho recalcula por lotes y quedan viejos. Si primero
    # se preguntara por la mora, un `diasAtraso` desactualizado le reclamaría
    # plata a alguien que ya canceló todo — el daño inverso al bug original.
    tol_saldado = _PISO_REDONDEO.get(moneda.strip().upper(), _PISO_DEFAULT)
    hay_deuda_vencida = saldo_vencido > tol_saldado or c_venc > 0 or dias > 0

    if saldo_total <= tol_saldado:
        if hay_deuda_vencida:
            inconsistencias.append("mora_con_contrato_saldado")
        estado = EstadoCuenta.SALDADO
        render = (
            "CONTRATO SALDADO — no tiene deuda vencida y no le queda saldo por "
            "pagar. Podés confirmarle que terminó de abonar el curso."
        )
        if not cuotas_confiables and c_pend > 0:
            render += (
                " (El registro muestra cuotas pendientes porque ese contador se "
                "acumula distinto que el saldo — ej. cuando se abonan varias "
                "cuotas juntas. NO menciones cuotas.)"
            )
    elif hay_deuda_vencida:
        estado = EstadoCuenta.CON_DEUDA_VENCIDA
        # Lo vencido no puede superar lo que falta del contrato entero.
        vencido = min(saldo_vencido, saldo_total) if saldo_total > 0 else saldo_vencido
        detalle = []
        if vencido > tol_saldado:
            detalle.append(f"deuda vencida exigible hoy: {_money(vencido, moneda)}")
        if c_venc > 0:
            detalle.append(_plural(c_venc, "cuota vencida", "cuotas vencidas"))
        if dias > 0:
            detalle.append(_plural(dias, "día de atraso", "días de atraso"))
        if not detalle:
            # El disparador fue mora sin importe: no inventamos un "ARS 0,00".
            detalle.append(f"saldo pendiente de {_money(saldo_total, moneda)}")
        render = "TIENE DEUDA VENCIDA — " + ", ".join(detalle) + "."
        # OJO: no se suma "y además le quedan N cuotas por vencer" — el
        # contador de pendientes ya incluye las vencidas, así que sería contar
        # la misma plata dos veces. El saldo total lo dice sin ambigüedad.
        if saldo_total > vencido:
            render += f" Saldo total del contrato: {_money(saldo_total, moneda)}."
    else:
        estado = EstadoCuenta.AL_DIA
        if cuotas_confiables and c_pend > 0:
            render = (
                f"AL DÍA — no tiene deuda vencida, pero el curso NO está saldado: "
                f"le {'queda' if c_pend == 1 else 'quedan'} "
                f"{_plural(c_pend, 'cuota', 'cuotas')} de {_money(valor_cuota, moneda)}, "
                f"saldo total {_money(saldo_total, moneda)}."
            )
            if prox and prox != "No registra":
                render += f" Próxima cuota: {prox}."
        else:
            # El contador de cuotas de Zoho no sirve acá, pero el alumno igual
            # puede preguntar cuántas le faltan: se lo derivamos del saldo.
            render = (
                f"AL DÍA — no tiene deuda vencida, pero el curso NO está saldado: "
                f"le queda un saldo de {_money(saldo_total, moneda)}."
            )
            eq = _cuotas_equivalentes(saldo_total, valor_cuota, moneda)
            if eq:
                render += (
                    f" Si pregunta cuántas cuotas le faltan: {eq}, "
                    f"de {_money(valor_cuota, moneda)} cada una "
                    "(calculado sobre el saldo — NO uses el contador de cuotas "
                    "del registro, que acumula distinto)."
                )

    # Pago reciente todavía sin imputar: si quedó saldo pero cobró hace poco,
    # el bot tiene que dejar la puerta abierta en vez de afirmar la deuda a
    # secas (la imputación en Zoho no es instantánea).
    if estado in (EstadoCuenta.AL_DIA, EstadoCuenta.CON_DEUDA_VENCIDA) and _pago_reciente(
        ficha.get("fechaUltimoPago")
    ):
        render += (
            f" ⚠️ Registra un pago el {ficha.get('fechaUltimoPago')}: si menciona "
            "haber pagado, puede que todavía no esté imputado. No lo contradigas "
            "— decile que lo verificás y derivá."
        )

    return {
        "estado": estado,
        "confiable": True,
        "cuotasConfiables": cuotas_confiables,
        "inconsistencias": inconsistencias,
        "notasCuotas": notas_cuotas,
        "moneda": moneda,
        "saldoTotal": saldo_total,
        "saldoVencido": saldo_vencido,
        "cuotasPendientes": c_pend,
        # Cuotas derivadas del saldo — es el número que hay que contestarle al
        # alumno si pregunta cuántas le faltan.
        "cuotasRestantes": _cuotas_equivalentes(saldo_total, valor_cuota, moneda) or 0,
        "valorCuota": valor_cuota,
        "render": render,
    }


def bloque_estado_cuenta(ficha: dict | None) -> str:
    """Sección lista para inyectar en el system prompt de cualquier agente."""
    r = clasificar_estado_cuenta(ficha)
    return (
        "## 💳 ESTADO DE CUENTA (veredicto del sistema — NO lo recalcules)\n"
        f"{r['render']}\n"
        "Regla dura: no digas *pagado*, *saldado*, *completo* ni *no debe nada* "
        "salvo que arriba diga CONTRATO SALDADO. Estar **al día** significa que "
        "no tiene deuda vencida, NO que terminó de pagar."
    )
