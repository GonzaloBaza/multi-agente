"""
Bus de eventos en tiempo real (SSE + Redis Pub/Sub).

El endpoint SSE del inbox (`GET /api/inbox/stream`) abre una cola local por
cliente y entrega eventos. `broadcast_event()` publica al canal Redis
`inbox:events`; un listener single-worker redistribuye al set local de
colas de CADA worker uvicorn. Así cualquier cambio (asignación, mensaje
nuevo, takeover...) llega a todos los browsers conectados sin importar a
qué worker pegue su SSE.

Antes vivía en `api/inbox.py` junto con los endpoints HTTP legacy. Se
extrajo cuando borramos ese router para no seguir acarreando un archivo
de 1700 líneas dead-mixed-with-alive.
"""

from __future__ import annotations

import asyncio
import json

import structlog

logger = structlog.get_logger(__name__)

# Set de colas de clientes SSE conectados a ESTE worker. `inbox_api.stream`
# agrega y remueve entradas; `_local_broadcast` itera para distribuir.
_sse_clients: set[asyncio.Queue] = set()

_PUBSUB_CHANNEL = "inbox:events"


def broadcast_event(event: dict) -> None:
    """Publica un evento al bus. No-op silencioso si no hay event loop.

    Normalmente se llama desde código async del request cycle. Si se llama
    fuera de un loop (tests, scripts), cae al broadcast local directo
    — útil para evitar explotar llamadas sincrónicas desde handlers legacy.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_redis_publish(event))
    except RuntimeError:
        _local_broadcast(event)


def _local_broadcast(event: dict) -> None:
    """Distribuye el evento a las colas SSE de este worker."""
    dead = set()
    for q in _sse_clients:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # Cliente lento — lo descartamos, nueva conexión repondrá estado.
            dead.add(q)
    _sse_clients.difference_update(dead)


async def _redis_publish(event: dict) -> None:
    """Publica al canal Redis. El listener de cada worker hace fan-out local."""
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        await store._redis.publish(_PUBSUB_CHANNEL, json.dumps(event))
    except Exception as e:
        logger.debug("redis_publish_failed", error=str(e))


async def start_pubsub_listener() -> None:
    """Background task del startup: suscribe a `inbox:events` y distribuye.

    Llamado desde `main.py` lifespan. Nunca retorna — corre hasta shutdown.
    Si el pubsub falla silencioso, el SSE del worker solo recibe eventos
    publicados desde el mismo worker (degradado pero funcional).
    """
    import redis.asyncio as aioredis

    from config.settings import get_settings

    try:
        settings = get_settings()
        sub_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = sub_client.pubsub()
        await pubsub.subscribe(_PUBSUB_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    _local_broadcast(event)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("pubsub_listener_error", error=str(e))
