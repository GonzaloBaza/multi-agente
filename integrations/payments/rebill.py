"""
Rebill — suscripciones y planes de pago recurrente.
Documentación: https://docs.rebill.to/
"""
import httpx
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


class RebillClient:
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.rebill_api_key
        self._base = settings.rebill_base_url
        self._org_id = settings.rebill_organization_id
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def create_subscription_link(
        self,
        plan_id: str,
        customer: dict,
        external_reference: str | None = None,
    ) -> dict:
        """
        Genera un link de suscripción a un plan Rebill.
        customer: {email, first_name, last_name, phone}
        """
        payload = {
            "plan_id": plan_id,
            "organization_id": self._org_id,
            "customer": {
                "email": customer.get("email", ""),
                "first_name": customer.get("first_name", ""),
                "last_name": customer.get("last_name", ""),
                "phone": customer.get("phone", ""),
            },
        }
        if external_reference:
            payload["external_id"] = external_reference

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/subscriptions/checkout",
                json=payload,
                headers=self._headers,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

        logger.info("rebill_checkout_created", plan_id=plan_id, external_ref=external_reference)
        return {
            "checkout_url": data.get("checkout_url", data.get("url", "")),
            "subscription_id": data.get("id", ""),
        }

    async def get_subscription(self, subscription_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/subscriptions/{subscription_id}",
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()

    async def pause_subscription(self, subscription_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/subscriptions/{subscription_id}/pause",
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()

    async def resume_subscription(self, subscription_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/subscriptions/{subscription_id}/resume",
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
        return resp.json()

    async def create_instant_link(
        self,
        amount: float,
        currency: str,
        description: str,
        external_reference: str | None = None,
    ) -> dict:
        """Genera un link de pago instantáneo por monto específico (sin plan)."""
        payload = {
            "organization_id": self._org_id,
            "amount": amount,
            "currency": currency,
            "description": description,
        }
        if external_reference:
            payload["external_id"] = external_reference

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/payment-links",
                json=payload,
                headers=self._headers,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "checkout_url": data.get("checkout_url", data.get("url", "")),
            "link_id": data.get("id", ""),
        }

    async def get_active_subscription_link(self, customer_id: str) -> dict:
        """Obtiene el link de pago de la suscripción activa de un cliente."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/subscriptions",
                params={"customer_id": customer_id, "status": "active"},
                headers=self._headers,
                timeout=15,
            )
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            data = resp.json()

        subscriptions = data.get("data", data if isinstance(data, list) else [])
        if not subscriptions:
            return {}

        sub_id = subscriptions[0].get("id", "")
        if not sub_id:
            return {}

        return await self.get_payment_link_for_overdue(sub_id)

    async def get_payment_link_for_overdue(self, subscription_id: str) -> dict:
        """Genera un link de pago para regularizar una suscripción con mora."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/subscriptions/{subscription_id}/retry-payment-link",
                headers=self._headers,
                timeout=15,
            )
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
        return resp.json()
