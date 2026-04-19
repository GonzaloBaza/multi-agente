"""
Flag en Redis: está el bot respondiendo esta conversación o la tomó un humano.

Redis keys:
  bot_disabled:{session_id}     — widget (session_id es hash interno)
  bot_disabled_wa:{session_id}  — WhatsApp (session_id es número de teléfono)

Un humano "toma" una conversación → `set(True)` → el webhook entrante deja de
rutearla al agente IA. El humano "libera" → `set(False)` → el bot vuelve a
responder.
"""

from __future__ import annotations

from memory.conversation_store import get_conversation_store


def bot_disabled_key(session_id: str) -> str:
    """Clave Redis del flag, distinta según canal (WhatsApp vs widget).

    WhatsApp session_ids son números de teléfono (solo dígitos + `+`). El
    widget usa hashes alfanuméricos. Se separan para evitar colisiones si
    un número de teléfono coincide accidentalmente con un hash de widget.
    """
    if session_id.lstrip("+").isdigit():
        return f"bot_disabled_wa:{session_id}"
    return f"bot_disabled:{session_id}"


async def is_bot_disabled(session_id: str) -> bool:
    store = await get_conversation_store()
    val = await store._redis.get(bot_disabled_key(session_id))
    return bool(val)


async def set_bot_disabled(session_id: str, disabled: bool) -> None:
    store = await get_conversation_store()
    key = bot_disabled_key(session_id)
    if disabled:
        await store._redis.set(key, "1")
    else:
        await store._redis.delete(key)
