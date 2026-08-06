"""
Tests del veredicto de estado de cuenta.

El caso 1 es el bug real que originó todo: Raúl Pereyra preguntó si su curso
estaba pagado, el bot le dijo que sí, y en realidad estaba al día con cuotas
por delante. Después canceló el total por adelantado y el registro quedó
diciendo dos cosas a la vez (saldo casi 0 pero 10 cuotas pendientes).
"""

from __future__ import annotations

import pytest

from utils.account_state import EstadoCuenta, bloque_estado_cuenta, clasificar_estado_cuenta

# Ficha real de Area_de_cobranzas al 06-ago-2026 (cancelación por adelantado).
FICHA_RAUL = {
    "cobranzaId": "5344455000505805809",
    "alumno": "Raul Pereyra",
    "moneda": "ARS",
    "modoPago": "Cobro recurrente",
    "importeContrato": 212881.0,
    "importePagado": 212880.08,
    "saldoTotal": 0.92,
    "saldoPendiente": 0.0,  # deuda VENCIDA
    "valorCuota": 17740.08,
    "cuotasTotales": 12,
    "cuotasPagas": 2,
    "cuotasPendientes": 10,  # ← desactualizado: ya pagó todo
    "cuotasVencidas": 0,
    "diasAtraso": 0,
}


def _ficha(**over) -> dict:
    base = {
        "cobranzaId": "abc123",
        "moneda": "ARS",
        "importeContrato": 120000.0,
        "importePagado": 40000.0,
        "saldoTotal": 80000.0,
        "saldoPendiente": 0.0,
        "valorCuota": 10000.0,
        "cuotasTotales": 12,
        "cuotasPagas": 4,
        "cuotasPendientes": 8,
        "cuotasVencidas": 0,
        "diasAtraso": 0,
    }
    base.update(over)
    return base


# ── El bug original ────────────────────────────────────────────────────────


def test_raul_contrato_saldado_pese_a_cuotas_desactualizadas():
    """La plata cierra y da 0 → saldado, aunque el registro diga 10 cuotas."""
    r = clasificar_estado_cuenta(FICHA_RAUL)
    assert r["estado"] == EstadoCuenta.SALDADO
    assert r["confiable"] is True
    # Las cuotas no coinciden con el saldo → no se citan. Pero eso NO es un
    # dato roto: son acumuladores distintos (pagó 11 cuotas en un solo pago),
    # así que no puede figurar como inconsistencia a corregir.
    assert r["cuotasConfiables"] is False
    assert "cuotas_no_coinciden_con_saldo" in r["notasCuotas"]
    assert r["inconsistencias"] == []


def test_raul_no_le_ofrecemos_cuotas_al_alumno():
    """El render no puede presentar las 10 cuotas como deuda real."""
    render = clasificar_estado_cuenta(FICHA_RAUL)["render"]
    assert "SALDADO" in render
    # Si menciona el número, es sólo para aclarar que NO se mencione.
    if "10" in render:
        assert "NO se lo menciones" in render


def test_raul_el_3_de_agosto_tenia_deuda():
    """Mismo alumno ANTES de cancelar: el veredicto tiene que ser el opuesto."""
    antes = dict(
        FICHA_RAUL,
        importePagado=17740.08,
        saldoTotal=195140.0,
        cuotasPagas=1,
        cuotasPendientes=11,
    )
    r = clasificar_estado_cuenta(antes)
    assert r["estado"] != EstadoCuenta.SALDADO
    assert "SALDADO" not in r["render"]


# ── Casos sanos ────────────────────────────────────────────────────────────


def test_al_dia_informa_cuotas_y_saldo():
    r = clasificar_estado_cuenta(_ficha())
    assert r["estado"] == EstadoCuenta.AL_DIA
    assert r["cuotasConfiables"] is True
    assert "8 cuota" in r["render"]
    assert "NO está saldado" in r["render"]


def test_saldado_de_verdad():
    r = clasificar_estado_cuenta(
        _ficha(importePagado=120000.0, saldoTotal=0.0, cuotasPagas=12, cuotasPendientes=0)
    )
    assert r["estado"] == EstadoCuenta.SALDADO
    assert r["cuotasConfiables"] is True


def test_con_deuda_vencida():
    r = clasificar_estado_cuenta(_ficha(saldoPendiente=20000.0, cuotasVencidas=2, diasAtraso=35))
    assert r["estado"] == EstadoCuenta.CON_DEUDA_VENCIDA
    assert "2 cuota" in r["render"]
    assert "35" in r["render"]


def test_dias_de_atraso_solos_ya_son_deuda_vencida():
    r = clasificar_estado_cuenta(_ficha(diasAtraso=5))
    assert r["estado"] == EstadoCuenta.CON_DEUDA_VENCIDA


# ── Datos rotos → el bot no afirma nada ────────────────────────────────────


def test_importes_que_no_cierran_no_permiten_veredicto():
    """contrato − pagado ≠ saldo → nada es confiable."""
    r = clasificar_estado_cuenta(_ficha(importePagado=40000.0, saldoTotal=5.0))
    assert r["estado"] == EstadoCuenta.DATO_INSUFICIENTE
    assert r["confiable"] is False
    assert "importes_no_cierran" in r["inconsistencias"]
    assert "PROHIBIDO" in r["render"]


def test_sin_ficha():
    for vacio in (None, {}, {"alumno": "X"}):
        r = clasificar_estado_cuenta(vacio)
        assert r["estado"] == EstadoCuenta.DATO_INSUFICIENTE
        assert "PROHIBIDO" in r["render"]


def test_contrato_en_cero():
    r = clasificar_estado_cuenta(_ficha(importeContrato=0.0))
    assert r["estado"] == EstadoCuenta.DATO_INSUFICIENTE
    assert "contrato_en_cero" in r["inconsistencias"]


def test_sin_pagos_todavia_es_coherente():
    """Caso real: 11 de 600 registros no tienen importePagado porque nunca
    pagaron. Ahí saldoTotal == contrato y el veredicto es válido."""
    r = clasificar_estado_cuenta(
        _ficha(
            importeContrato=693000.0,
            importePagado=0.0,
            saldoTotal=693000.0,
            saldoPendiente=86625.0,
            valorCuota=86625.0,
            cuotasTotales=8,
            cuotasPagas=0,
            cuotasPendientes=8,
            cuotasVencidas=1,
            diasAtraso=12,
        )
    )
    assert r["estado"] == EstadoCuenta.CON_DEUDA_VENCIDA
    assert r["confiable"] is True


def test_sin_pagos_pero_saldo_en_cero_no_es_saldado():
    """El caso peligroso: nunca pagó pero el saldo quedó en 0 por dato viejo.
    Sin la validación contable esto se leería como 'contrato saldado'."""
    r = clasificar_estado_cuenta(
        _ficha(importeContrato=120000.0, importePagado=0.0, saldoTotal=0.0, cuotasPagas=0)
    )
    assert r["estado"] == EstadoCuenta.DATO_INSUFICIENTE
    assert "importes_no_cierran" in r["inconsistencias"]
    assert "SALDADO" not in r["render"]


def test_cuotas_que_no_suman():
    r = clasificar_estado_cuenta(_ficha(cuotasPagas=4, cuotasPendientes=3, cuotasTotales=12))
    assert r["cuotasConfiables"] is False
    assert "cuotas_no_suman" in r["notasCuotas"]


def test_desfasaje_de_cuotas_no_es_dato_a_corregir():
    """Definición de Cobranzas: cuotas y saldo son acumuladores distintos. Que
    no coincidan es esperable (pagos parciales / varias cuotas juntas) y no
    debe reportarse como registro a revisar."""
    r = clasificar_estado_cuenta(_ficha(cuotasPendientes=2))  # saldo dice 8 cuotas
    assert r["cuotasConfiables"] is False
    assert r["inconsistencias"] == []
    assert "desactualizado" not in r["render"]


def test_valores_none_de_zoho_no_rompen():
    """Zoho manda claves presentes con null; no pueden reventar el cálculo."""
    r = clasificar_estado_cuenta(
        {
            "cobranzaId": "x",
            "importeContrato": None,
            "importePagado": None,
            "saldoTotal": None,
            "valorCuota": None,
            "cuotasPendientes": None,
            "diasAtraso": None,
        }
    )
    assert r["estado"] == EstadoCuenta.DATO_INSUFICIENTE
    assert "None" not in r["render"]


# ── Invariantes ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "over",
    [
        {},
        {"saldoTotal": 0.0, "importePagado": 120000.0, "cuotasPendientes": 0, "cuotasPagas": 12},
        {"saldoPendiente": 5000.0, "cuotasVencidas": 1},
        {"diasAtraso": 90, "saldoPendiente": 30000.0},
        {"importeContrato": 0.0},
        {"valorCuota": 0.0},
    ],
)
def test_saldado_implica_saldo_cero(over):
    """Invariante: nunca decimos SALDADO si queda plata por pagar.

    El umbral se compara contra el piso ABSOLUTO de la moneda. Antes esto
    asertaba contra `valorCuota * 0.01`, que era la propia tolerancia
    buggeada — el test pasaba mientras el bot regalaba deuda real.
    """
    from utils.account_state import _PISO_DEFAULT, _PISO_REDONDEO

    r = clasificar_estado_cuenta(_ficha(**over))
    if r["estado"] == EstadoCuenta.SALDADO:
        piso = _PISO_REDONDEO.get((r["moneda"] or "").upper(), _PISO_DEFAULT)
        assert r["saldoTotal"] <= piso


# ── Regresiones de la revisión adversarial ─────────────────────────────────


@pytest.mark.parametrize(
    "moneda,contrato,cuotas,deuda_real",
    [
        ("COP", 12_000_000.0, 1, 119_000.0),  # pago único: la cuota ES el contrato
        ("COP", 12_000_000.0, 3, 39_000.0),
        ("PYG", 9_000_000.0, 1, 80_000.0),
        ("CLP", 1_200_000.0, 1, 11_000.0),
        ("ARS", 212_881.0, 1, 1_200.0),
    ],
)
def test_pocas_cuotas_no_esconden_deuda_real(moneda, contrato, cuotas, deuda_real):
    """Con planes de pocas cuotas, `valorCuota` ≈ contrato. Si la tolerancia
    fuera un % de la cuota, sería un % del contrato y una deuda real quedaría
    bajo el umbral. Peor en monedas sin decimales."""
    r = clasificar_estado_cuenta(
        _ficha(
            moneda=moneda,
            importeContrato=contrato,
            importePagado=contrato - deuda_real,
            saldoTotal=deuda_real,
            saldoPendiente=0.0,
            valorCuota=contrato / cuotas,
            cuotasTotales=cuotas,
            cuotasPagas=0,
            cuotasPendientes=cuotas,
        )
    )
    assert r["estado"] != EstadoCuenta.SALDADO, f"{moneda} {deuda_real} quedó invisible"
    assert "SALDADO" not in r["render"]


def test_residuo_de_redondeo_si_es_saldado():
    """Contracara: un resto chico de verdad sí tiene que dar saldado."""
    r = clasificar_estado_cuenta(
        _ficha(
            moneda="COP",
            importeContrato=12_000_000.0,
            importePagado=11_998_800.0,
            saldoTotal=1_200.0,
            valorCuota=1_000_000.0,
            cuotasTotales=12,
            cuotasPagas=12,
            cuotasPendientes=0,
        )
    )
    assert r["estado"] == EstadoCuenta.SALDADO


@pytest.mark.parametrize("mora", [{"diasAtraso": 3}, {"cuotasVencidas": 1}, {"diasAtraso": 1}])
def test_mora_desactualizada_no_le_reclama_a_quien_pago_todo(mora):
    """Zoho recalcula la mora por lotes: puede quedar vieja tras un pago. La
    identidad contable manda — si no queda saldo, está saldado."""
    r = clasificar_estado_cuenta(dict(FICHA_RAUL, **mora))
    assert r["estado"] == EstadoCuenta.SALDADO
    assert "DEUDA VENCIDA" not in r["render"]
    assert "mora_con_contrato_saldado" in r["inconsistencias"]


def test_deuda_vencida_real_sigue_detectandose():
    """El fix anterior no puede tapar mora legítima: si queda saldo, se cobra."""
    r = clasificar_estado_cuenta(_ficha(saldoPendiente=20000.0, cuotasVencidas=2, diasAtraso=30))
    assert r["estado"] == EstadoCuenta.CON_DEUDA_VENCIDA


@pytest.mark.parametrize(
    "over",
    [{}, {"saldoTotal": 0.0, "importePagado": 120000.0, "cuotasPendientes": 0}, {"diasAtraso": 9}],
)
def test_solo_saldado_habilita_la_palabra_pagado(over):
    """Ningún otro estado puede sugerir que terminó de pagar."""
    r = clasificar_estado_cuenta(_ficha(**over))
    if r["estado"] != EstadoCuenta.SALDADO:
        assert "SALDADO" not in r["render"]


def test_bloque_para_el_prompt_trae_la_regla_dura():
    bloque = bloque_estado_cuenta(FICHA_RAUL)
    assert "ESTADO DE CUENTA" in bloque
    assert "al día" in bloque.lower()
    assert "NO que terminó de pagar" in bloque


# ── "¿Cuántas cuotas me faltan?" ───────────────────────────────────────────


def test_cuotas_restantes_se_derivan_del_saldo():
    """El contador de Zoho dice 10, pero ya pagó todo: la respuesta es 0."""
    r = clasificar_estado_cuenta(FICHA_RAUL)
    assert r["cuotasPendientes"] == 10  # lo que dice el registro
    assert r["cuotasRestantes"] == 0  # lo que hay que contestarle


@pytest.mark.parametrize(
    "saldo,cuota,esperado",
    [
        (80000.0, 10000.0, 8),
        (35000.0, 10000.0, 4),  # 3.5 → se redondea para arriba
        (30500.0, 10000.0, 4),  # el resto supera el piso ARS (100) → 1 más
        (30050.0, 10000.0, 3),  # resto por debajo del piso = redondeo
        (0.92, 17740.08, 0),  # Raúl
    ],
)
def test_calculo_de_cuotas_restantes(saldo, cuota, esperado):
    r = clasificar_estado_cuenta(
        _ficha(
            importeContrato=120000.0,
            importePagado=120000.0 - saldo,
            saldoTotal=saldo,
            valorCuota=cuota,
        )
    )
    assert r["cuotasRestantes"] == esperado


def test_render_contesta_cuantas_cuotas_faltan():
    """Si el contador no sirve, el render igual trae el número derivado."""
    r = clasificar_estado_cuenta(_ficha(cuotasPendientes=2))  # desfasado
    assert r["cuotasConfiables"] is False
    assert "cuántas cuotas le faltan: 8" in r["render"]
