"""
MercadoPago — generación de Preference (checkout link de pago único).
Para suscripciones usar Rebill.
"""

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

MP_API_BASE = "https://api.mercadopago.com"


class MercadoPagoClient:
    def __init__(self):
        self._token = get_settings().mp_access_token
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def create_payment_link(
        self,
        title: str,
        price: float,
        currency: str,
        quantity: int = 1,
        payer_email: str | None = None,
        external_reference: str | None = None,
        notification_url: str | None = None,
    ) -> dict:
        """
        Crea una Preference de pago y retorna init_point (link de checkout).
        """
        settings = get_settings()
        item = {
            "title": title,
            "unit_price": price,
            "currency_id": currency,
            "quantity": quantity,
        }

        payload: dict = {
            "items": [item],
            "back_urls": {
                "success": f"{settings.app_base_url}/payment/success",
                "failure": f"{settings.app_base_url}/payment/failure",
                "pending": f"{settings.app_base_url}/payment/pending",
            },
            "auto_return": "approved",
        }

        if payer_email:
            payload["payer"] = {"email": payer_email}
        if external_reference:
            payload["external_reference"] = external_reference
        if notification_url:
            payload["notification_url"] = notification_url
        else:
            payload["notification_url"] = f"{settings.app_base_url}/webhook/mercadopago"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MP_API_BASE}/checkout/preferences",
                json=payload,
                headers=self._headers,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

        logger.info("mp_preference_created", preference_id=data.get("id"))
        return {
            "preference_id": data["id"],
            "checkout_url": data["init_point"],
            "sandbox_url": data.get("sandbox_init_point", ""),
        }

    async def verify_webhook(self, payment_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{MP_API_BASE}/v1/payments/{payment_id}",
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()
