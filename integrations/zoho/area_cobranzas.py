"""
Módulo Zoho Area_de_cobranzas — ficha completa del alumno en mora.
Campos reales del CRM: Dias_de_atraso_cal, Saldo_Vencido_2, etc.
"""
import httpx
from .auth import ZohoAuth
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


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
        """Normaliza el registro crudo de Zoho a la ficha estándar del agente."""
        return {
            "cobranzaId": raw.get("id", ""),
            "ID_Cliente": raw.get("ID_Cliente", ""),
            "alumno": raw.get("Nombre_del_alumno", "Alumno"),
            "email": raw.get("Email", ""),
            "telefono": raw.get("Tel_fono", ""),
            "pais": raw.get("Pa_s", ""),
            "importeContrato": float(raw.get("Importe_de_contrato") or 0),
            "moneda": raw.get("Currency", "ARS"),
            "modoPago": raw.get("Modo_de_pago", ""),
            "metodoPago": raw.get("M_todo_de_pago", ""),
            "valorCuota": float(raw.get("Monto_de_cada_pago_restantes") or 0),
            "saldoPendiente": float(raw.get("Saldo_Vencido_2") or 0),
            "saldoTotal": float(raw.get("Saldo_pendiente") or 0),
            "diasAtraso": int(raw.get("Dias_de_atraso_cal") or 0),
            "estadoGestion": raw.get("Estado_de_la_gesti_n", "Desconocido"),
            "estadoMora": raw.get("Estado_de_mora", "Al día"),
            "cuotasTotales": int(raw.get("Cuotas_totales_2") or 0),
            "cuotasPagas": int(raw.get("Cuotas_pagas_2") or 0),
            "cuotasVencidas": int(raw.get("Cuotas_vencidas_2") or 0),
            "cuotasPendientes": int(raw.get("Cuotas_pendientes_2") or 0),
            "importeUltimoPago": float(raw.get("Importe_ultimo_pago") or 0),
            "fechaUltimoPago": raw.get("Fecha_de_ultimo_pago", "No registrado"),
            "fechaContratoEfectivo": raw.get("Fecha_de_contrato_efectivo", "No registrada"),
            "fechaProximoPago": raw.get("Fecha_de_proximo_pago", "No registra"),
            "fechaPromesaPago": raw.get("Fecha_de_promesa_de_pago", "No registra"),
            "linkFactura": raw.get("Comprobante_Factura", "No disponible"),
            "pagado": int(raw.get("Dias_de_atraso_cal") or 0) == 0
                     and float(raw.get("Saldo_Vencido_2") or 0) == 0,
        }
