import httpx
from .auth import ZohoAuth
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


class ZohoLeads:
    def __init__(self):
        self._auth = ZohoAuth()
        self._base = get_settings().zoho_base_url

    async def create(self, data: dict) -> dict:
        """
        Crea un Lead en Zoho CRM.
        data: {last_name, first_name, phone, email, country, curso_de_interes,
               canal_origen, estado_pago, notas}
        """
        payload = {
            "data": [{
                "Last_Name": data.get("last_name", data.get("name", "Sin nombre")),
                "First_Name": data.get("first_name", ""),
                "Phone": data.get("phone", ""),
                "Email": data.get("email", ""),
                "Country": data.get("country", "Argentina"),
                "Lead_Source": data.get("canal_origen", "WhatsApp"),
                # Campos personalizados
                "Curso_de_Interes": data.get("curso_de_interes", ""),
                "Canal_Origen": data.get("canal_origen", ""),
                "Estado_Pago": data.get("estado_pago", "Pendiente"),
                "Notas_Bot": data.get("notas", ""),
            }]
        }
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/Leads",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()

        lead_id = result["data"][0]["details"]["id"]
        logger.info("zoho_lead_created", lead_id=lead_id)
        return {"id": lead_id, **result["data"][0]}

    async def update(self, lead_id: str, data: dict) -> dict:
        payload = {"data": [{"id": lead_id, **data}]}
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base}/Leads",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()

    async def search_by_phone(self, phone: str) -> dict | None:
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Leads/search",
                params={"phone": phone},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", [None])[0]

    async def search_by_email(self, email: str) -> dict | None:
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Leads/search",
                params={"email": email},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", [None])[0]
