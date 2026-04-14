"""
Módulo de cobranzas en Zoho — trabaja con Sales Orders y un módulo custom de Cobranzas.
"""
import httpx
from datetime import date
from .auth import ZohoAuth
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


class ZohoCollections:
    def __init__(self):
        self._auth = ZohoAuth()
        self._base = get_settings().zoho_base_url

    async def get_overdue(self, days_overdue: int = 0) -> list[dict]:
        """Retorna Sales Orders con pagos vencidos."""
        today = date.today().isoformat()
        headers = await self._auth.auth_headers()
        # Busca órdenes con estado pendiente y fecha de vencimiento pasada
        params = {
            "criteria": f"(Status:equals:Pendiente de pago)AND(Fecha_Vencimiento:less_than:{today})"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Sales_Orders/search",
                params=params,
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 204:
                return []
            resp.raise_for_status()
        return resp.json().get("data", [])

    async def log_interaction(self, contact_id: str, notes: str, interaction_type: str = "Gestión bot") -> dict:
        """Registra una interacción de cobranzas en el módulo custom."""
        payload = {
            "data": [{
                "Name": f"Gestión {date.today().isoformat()}",
                "Contacto": {"id": contact_id},
                "Tipo_Gestion": interaction_type,
                "Notas": notes,
                "Fecha_Gestion": date.today().isoformat(),
                "Canal": "WhatsApp Bot",
            }]
        }
        headers = await self._auth.auth_headers()
        # Módulo custom "Cobranzas" — ajustar API name si cambia
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/Cobranzas",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            # Si el módulo no existe aún, logueamos sin fallar
            logger.warning("cobranzas_module_not_found", status=resp.status_code)
            return {}

    async def mark_regularized(self, order_id: str, notes: str = "") -> dict:
        """Marca una orden como regularizada tras acuerdo de pago."""
        payload = {
            "data": [{
                "id": order_id,
                "Status": "En regularización",
                "Notas_Cobranza": notes,
            }]
        }
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base}/Sales_Orders",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()

    async def escalate_dispute(self, order_id: str, reason: str) -> dict:
        """Escala disputa de cobro a revisión humana."""
        payload = {
            "data": [{
                "id": order_id,
                "Status": "Disputa - Requiere revisión",
                "Motivo_Disputa": reason,
            }]
        }
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base}/Sales_Orders",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()
