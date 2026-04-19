"""
Sistema de eventos por conversación — equivalente a "Obtener eventos" de Botmaker.
Loguea agente usado, acciones tomadas, errores, etc.
Almacena en Redis como lista JSON, últimos 100 eventos por conversación.
"""

import datetime
import json

import structlog

logger = structlog.get_logger(__name__)

MAX_EVENTS = 100


async def log_event(session_id: str, event_type: str, data: dict):
    """
    Registra un evento para una conversación.

    event_type: "intent", "action", "error", "info"
    data: dict con los detalles del evento
    """
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()

        event = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "type": event_type,
            **data,
        }

        key = f"conv_events:{session_id}"
        pipe = store._redis.pipeline()
        pipe.rpush(key, json.dumps(event, ensure_ascii=False))
        pipe.ltrim(key, -MAX_EVENTS, -1)  # mantener solo los últimos 100
        pipe.expire(key, 60 * 60 * 24 * 30)  # 30 días
        await pipe.execute()

        # Broadcast SSE para que el inbox se actualice en tiempo real
        try:
            from utils.realtime import broadcast_event

            broadcast_event(
                {
                    "type": "conv_event",
                    "session_id": session_id,
                    "event": event,
                }
            )
        except Exception:
            pass

    except Exception as e:
        logger.warning("conv_event_log_failed", session_id=session_id, error=str(e))


async def get_events(session_id: str, limit: int = 50) -> list[dict]:
    """Devuelve los últimos eventos de una conversación."""
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        raw = await store._redis.lrange(f"conv_events:{session_id}", -limit, -1)
        return [json.loads(r) for r in raw]
    except Exception:
        return []


# ─── Helpers para tipos comunes ───────────────────────────────────────────────


async def log_intent(session_id: str, intent: str, agent: str, message_preview: str = ""):
    await log_event(
        session_id,
        "intent",
        {
            "intent": intent,
            "agent": agent,
            "msg": message_preview[:80] if message_preview else "",
        },
    )


async def log_action(session_id: str, action: str, detail: str = "", success: bool = True):
    await log_event(
        session_id,
        "action" if success else "error",
        {
            "action": action,
            "detail": detail[:200] if detail else "",
        },
    )


async def log_error(session_id: str, source: str, error: str):
    await log_event(
        session_id,
        "error",
        {
            "source": source,
            "error": error[:300] if error else "",
        },
    )
