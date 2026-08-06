"""
Módulo Zoho Area_de_cobranzas — ficha completa del alumno en mora.
Campos reales del CRM: Dias_de_atraso_cal, Saldo_Vencido_2, etc.
"""

import httpx
import structlog

from config.settings import get_settings

from .auth import ZohoAuth

logger = structlog.get_logger(__name__)


# Prefijo de la cache de fichas en Redis (widget.py escribe, router.py lee).
# ⚠️ SUBIR LA VERSIÓN cada vez que cambie la forma del dict de `_normalizar`.
# Sin eso, tras un deploy conviven fichas viejas sin los campos nuevos y el
# veredicto de estado de cuenta sale mal hasta que expira el TTL (2 h).
# v2 = se agregó `importePagado`, que es lo que valida la identidad contable.
FICHA_CACHE_PREFIX = "datos_deudor:v2:"


class ZohoAreaCobranzas:
    def __init__(self):
        self._auth = ZohoAuth()
        self._base = get_settings().zoho_base_url.replace("/crm/v6", "/crm/v3")

    async def get_by_id(self, cobranza_id: str) -> dict:
        """Obtiene la ficha completa de un registro de Area_de_cobranzas."""
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Area_de_cobranzas/{cobranza_id}",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
        data = resp.json()
        records = data.get("data", [data])
        return self._normalizar(records[0]) if records else {}

    async def search_by_email(self, email: str) -> dict:
        """Busca un registro en Area_de_cobranzas por email del alumno."""
        headers = await self._auth.auth_headers()
        params = {"criteria": f"(Email:equals:{email})"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Area_de_cobranzas/search",
                params=params,
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 204:
                return {}
            resp.raise_for_status()
        data = resp.json()
        records = data.get("data", [])
        return self._normalizar(records[0]) if records else {}

    async def search_by_phone(self, phone: str) -> dict:
        """Busca un registro en Area_de_cobranzas por teléfono."""
        headers = await self._auth.auth_headers()
        params = {"criteria": f"(Tel_fono:equals:{phone})"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Area_de_cobranzas/search",
                params=params,
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 204:
                return {}
            resp.raise_for_status()
        data = resp.json()
        records = data.get("data", [])
        return self._normalizar(records[0]) if records else {}

    async def set_tag(self, cobranza_id: str, tag_name: str) -> None:
        """Actualiza el tag de cobranzas del registro (reemplaza el anterior)."""
        headers = await self._auth.auth_headers()
        payload = {"data": [{"Tag": [{"name": tag_name}]}]}
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base}/Area_de_cobranzas/{cobranza_id}",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                logger.warning("zoho_tag_update_failed", status=resp.status_code, tag=tag_name)

    def _normalizar(self, raw: dict) -> dict:
        """
        Normaliza el registro crudo de Zoho a la ficha estándar del agente.

        ⚠️ Zoho devuelve las claves presentes con valor `null` cuando el campo
        está vacío, así que `raw.get(k, "default")` NO alcanza — devuelve None y
        ese None termina renderizado como el string "None" en el prompt. Por eso
        todos los textos usan `or` en vez del default de `.get()`.
        """

        def _txt(key: str, default: str = "") -> str:
            return str(raw.get(key) or default)

        def _num(key: str) -> float:
            try:
                return float(raw.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0

        def _ent(key: str) -> int:
            # Vía float: Zoho devuelve algunos numéricos como "35.0" y un
            # `int("35.0")` directo tira ValueError. Antes eso caía al 0 del
            # except y un moroso con 35 días de atraso aparecía al día.
            try:
                return int(float(raw.get(key) or 0))
            except (TypeError, ValueError):
                return 0

        return {
            "cobranzaId": _txt("id"),
            "ID_Cliente": _txt("ID_Cliente"),
            "alumno": _txt("Nombre_del_alumno", "Alumno"),
            "email": _txt("Email"),
            "telefono": _txt("Tel_fono"),
            "pais": _txt("Pa_s"),
            "importeContrato": _num("Importe_de_contrato"),
            # Cuánto pagó realmente. Permite la identidad contable
            # `contrato - pagado = saldoTotal`, que es lo único que habilita a
            # afirmar si un contrato está saldado. Ver utils/account_state.py.
            "importePagado": _num("Importe_de_pagos_a_la_fecha_2"),
            "moneda": _txt("Currency", "ARS"),
            "modoPago": _txt("Modo_de_pago"),
            "metodoPago": _txt("M_todo_de_pago"),
            "valorCuota": _num("Monto_de_cada_pago_restantes"),
            # OJO: `saldoPendiente` es la deuda VENCIDA exigible hoy
            # (Zoho `Saldo_Vencido_2`), NO lo que falta del contrato. Lo que
            # falta en total es `saldoTotal` (Zoho `Saldo_pendiente`).
            "saldoPendiente": _num("Saldo_Vencido_2"),
            "saldoTotal": _num("Saldo_pendiente"),
            "diasAtraso": _ent("Dias_de_atraso_cal"),
            "estadoGestion": _txt("Estado_de_la_gesti_n", "Desconocido"),
            "estadoMora": _txt("Estado_de_mora", "Al día"),
            "cuotasTotales": _ent("Cuotas_totales_2"),
            "cuotasPagas": _ent("Cuotas_pagas_2"),
            "cuotasVencidas": _ent("Cuotas_vencidas_2"),
            "cuotasPendientes": _ent("Cuotas_pendientes_2"),
            "importeUltimoPago": _num("Importe_ultimo_pago"),
            "fechaUltimoPago": _txt("Fecha_de_ultimo_pago", "No registrado"),
            "fechaContratoEfectivo": _txt("Fecha_de_contrato_efectivo", "No registrada"),
            "fechaProximoPago": _txt("Fecha_de_proximo_pago", "No registra"),
            # Fecha a la que corresponde la próxima cuota del plan. Zoho la
            # mantiene aunque `Fecha_de_proximo_pago` venga vacía.
            "fechaProximaCuota": _txt("Cuota_corresponde_a", "No registra"),
            "fechaPromesaPago": _txt("Fecha_de_promesa_de_pago", "No registra"),
            "linkFactura": _txt("Comprobante_Factura", "No disponible"),
            "baja": bool(raw.get("Baja")),
            "refinanciamiento": bool(raw.get("Refinanciamiento")),
            # ⚠️ Esto es "no tiene deuda VENCIDA", NO "canceló el contrato".
            # Antes se llamaba `pagado` y ese nombre causó que el bot le dijera
            # a un alumno con 10 cuotas por delante que ya había pagado todo.
            # Para saber si el contrato está saldado usá clasificar_estado_cuenta().
            "sinDeudaVencida": _ent("Dias_de_atraso_cal") == 0 and _num("Saldo_Vencido_2") == 0,
        }
