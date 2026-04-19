"""
Audit logging — registro inmutable de acciones administrativas.
Almacena en Redis list 'audit:log' con max 10k entradas.
"""

import datetime
import json

import structlog

logger = structlog.get_logger(__name__)

AUDIT_KEY = "audit:log"
AUDIT_MAX = 10000
AUDIT_TTL = 86400 * 180  # 6 meses


async def audit_log(
    user_id: str,
    user_name: str,
    action: str,
    target: str,
    details: dict | None = None,
):
    """Registra una accion administrativa en el audit log."""
    from memory.conversation_store import get_conversation_store

    store = await get_conversation_store()

    entry = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "user_name": user_name,
        "action": action,
        "target": target,
        "details": details or {},
    }

    await store._redis.lpush(AUDIT_KEY, json.dumps(entry, ensure_ascii=False))
    await store._redis.ltrim(AUDIT_KEY, 0, AUDIT_MAX - 1)
    await store._redis.expire(AUDIT_KEY, AUDIT_TTL)

    logger.info("audit", **{k: v for k, v in entry.items() if k != "details"})


async def get_audit_log(limit: int = 100, offset: int = 0) -> list[dict]:
    """Retorna las ultimas entradas del audit log."""
    from memory.conversation_store import get_conversation_store

    store = await get_conversation_store()

    raw = await store._redis.lrange(AUDIT_KEY, offset, offset + limit - 1)
    entries = []
    for item in raw:
        try:
            data = item.decode("utf-8") if isinstance(item, bytes) else item
            entries.append(json.loads(data))
        except Exception:
            pass
    return entries
