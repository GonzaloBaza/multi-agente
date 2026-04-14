import httpx
from .auth import ZohoAuth
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


class ZohoSalesOrders:
    def __init__(self):
        self._auth = ZohoAuth()
        self._base = get_settings().zoho_base_url

    async def create(self, data: dict) -> dict:
        """
        Crea una Sales Order (inscripción) en Zoho.
        data: {contact_id, curso_nombre, precio, moneda, payment_link,
               payment_provider, pais, notas}
        """
        payload = {
            "data": [{
                "Subject": f"Inscripción: {data.get('curso_nombre', 'Curso')}",
                "Contact_Name": {"id": data["contact_id"]},
                "Status": "Pendiente de pago",
                "Grand_Total": data.get("precio", 0),
                "Currency": data.get("moneda", "ARS"),
                "Curso_Nombre": data.get("curso_nombre", ""),
                "Link_de_Pago": data.get("payment_link", ""),
                "Proveedor_Pago": data.get("payment_provider", ""),
                "Pais": data.get("pais", "Argentina"),
                "Notas_Inscripcion": data.get("notas", ""),
                "Product_Details": [{
                    "product": {"name": data.get("curso_nombre", "")},
                    "quantity": 1,
                    "unit_price": data.get("precio", 0),
                    "total": data.get("precio", 0),
                }],
            }]
        }
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/Sales_Orders",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()

        order_id = result["data"][0]["details"]["id"]
        logger.info("zoho_sales_order_created", order_id=order_id)
        return {"id": order_id}

    async def update_payment_status(self, order_id: str, status: str, transaction_id: str = "") -> dict:
        payload = {
            "data": [{
                "id": order_id,
                "Status": status,
                "Transaction_ID": transaction_id,
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

    async def list_by_contact(self, contact_id: str) -> list[dict]:
        headers = await self._auth.auth_headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/Sales_Orders/search",
                params={"criteria": f"Contact_Name:equals:{contact_id}"},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 204:
                return []
            resp.raise_for_status()
        return resp.json().get("data", [])
