"""
Job horario: marca `convertido` en el kanban con la señal REAL de compra.

El bot no crea sales orders — solo comparte links de checkout. La única
señal verdadera de que una conversación terminó en venta es que el checkout
haya escrito `Contacts.IDLEAD = <lead_id>` en Zoho (el link viaja con
`?idlead=` — ver utils/idlead_links.py).

Este job cierra el loop del lado del kanban:
  1. Candidatas: conversaciones recientes con label `caliente` o
     `esperando_pago` y `zoho_lead_id` persistido en el perfil.
  2. Una consulta batch a Zoho (COQL, chunks de 20): ¿qué lead_ids ya
     tienen Contacto con ese IDLEAD?
  3. Match → `conv_label = convertido` (con TTL, igual que el classifier)
     + broadcast SSE.

El LLM del classifier ya no puede emitir `convertido` — a esa columna solo
se llega por este job o por drag manual del supervisor.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Cuántas conversaciones candidatas revisar por corrida (techo defensivo).
MAX_CANDIDATAS = 200

# Labels desde los que una conversación puede pasar a convertido.
LABELS_CANDIDATOS = ("caliente", "esperando_pago")

# Ventana de actividad: no revisar conversaciones muertas hace meses.
VENTANA_DIAS = 45


async def run_conversion_check() -> dict:
    from agents.classifier import LABEL_TTL_SECONDS
    from integrations.zoho.contacts import ZohoContacts
    from memory import postgres_store
    from memory.conversation_store import get_conversation_store

    pool = await postgres_store.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            select c.external_id as sid,
                   (c.user_profile)::jsonb ->> 'zoho_lead_id' as lead_id
            from public.conversations c
            where c.updated_at > now() - interval '{VENTANA_DIAS} days'
              and (c.user_profile)::jsonb ->> 'zoho_lead_id' is not null
            order by c.updated_at desc
            limit {MAX_CANDIDATAS}
            """
        )
    if not rows:
        return {"candidatas": 0, "convertidas": 0}

    store = await get_conversation_store()
    r = store._redis
    keys = [f"conv_label:{row['sid']}" for row in rows]
    labels_raw = await r.mget(keys)

    def _dec(v):
        return v.decode() if isinstance(v, bytes) else v

    candidatas = [
        (row["sid"], row["lead_id"])
        for row, lab in zip(rows, labels_raw, strict=False)
        if _dec(lab) in LABELS_CANDIDATOS and row["lead_id"]
    ]
    if not candidatas:
        return {"candidatas": 0, "convertidas": 0}

    lead_ids = [lid for _, lid in candidatas]
    try:
        convertidos = await ZohoContacts().idleads_convertidos(lead_ids)
    except Exception as e:
        logger.warning("conversion_check_zoho_failed", error=str(e))
        return {"candidatas": len(candidatas), "convertidas": 0, "error": str(e)}

    marcadas = 0
    for sid, lid in candidatas:
        if lid not in convertidos:
            continue
        await r.set(f"conv_label:{sid}", "convertido", ex=LABEL_TTL_SECONDS)
        marcadas += 1
        try:
            from utils.realtime import broadcast_event

            broadcast_event({"type": "label_updated", "session_id": sid, "label": "convertido"})
        except Exception:
            pass
        logger.info("conversion_check_convertido", session_id=sid, lead_id=lid)

    logger.info(
        "conversion_check_done",
        candidatas=len(candidatas),
        convertidas=marcadas,
    )
    return {"candidatas": len(candidatas), "convertidas": marcadas}
