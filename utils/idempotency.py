"""
Idempotency keys para webhooks y operaciones sensibles.

Meta, MercadoPago, Rebill, Zoho re-envían webhooks si no respondés 200 en
<20s. Sin idempotency keys, el mismo pago se procesa 2 veces → duplicado
en Zoho, doble mensaje al cliente, doble alta. Este módulo provee un lock
atómico en Redis para marcar "este event_id ya se procesó" con TTL.

Patrón de uso:

    from utils.idempotency import idempotency_guard

    @router.post("/webhook/mercadopago")
    async def mercadopago_webhook(...):
        event_id = body.get("id") or body.get("data", {}).get("id")
        async with idempotency_guard("mp", event_id) as first_time:
            if not first_time:
                return {"status": "duplicate_ignored"}
            # procesamiento real (solo la primera vez)
            ...

TTL default 24h — suficiente para retries de los principales proveedores
(Meta re-intenta hasta 24h). Si el event_id es vacío (no viene), el guard
es no-op — no bloqueamos porque no tenemos cómo deduplicar.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog

logger = structlog.get_logger(__name__)

_KEY = "idempotency:{scope}:{event_id}"
_DEFAULT_TTL = 86400  # 24h


@asynccontextmanager
async def idempotency_guard(scope: str, event_id: str | None, ttl: int = _DEFAULT_TTL):
    """Retorna True si es la primera vez que vemos este event_id; False si es duplicado.

    Si `event_id` vacío/None → retorna True (sin dedup, procesar normal).
    Usa SET NX con TTL — atómico, sin race conditions entre workers.
    """
    if not event_id:
        yield True
        return

    from memory.conversation_store import get_conversation_store

    key = _KEY.format(scope=scope, event_id=event_id)
    store = await get_conversation_store()
    try:
        # NX = solo set si no existe. Atómico.
        set_ok = await store._redis.set(key, "1", ex=ttl, nx=True)
    except Exception as e:
        # Si Redis falla, no bloqueamos el webhook — preferimos procesar 2
        # veces antes que perder un pago. Log el fallo para seguimiento.
        logger.warning("idempotency_redis_failed", scope=scope, event_id=event_id, error=str(e))
        yield True
        return

    if not set_ok:
        logger.info("idempotency_duplicate", scope=scope, event_id=event_id)
        yield False
        return
    yield True
