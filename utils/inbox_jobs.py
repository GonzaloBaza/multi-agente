"""
Background jobs del inbox:
  - wake_snoozed: cada 5 min, despierta conversaciones snoozeadas vencidas
                  y notifica al agente asignado vía Slack.
  - notify_new_human_request: dispara Slack cuando una conv escala a humano.

Se arranca con `start_inbox_jobs()` desde main.py al levantar la app.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import httpx
import structlog

from memory import conversation_meta as cm
from memory.postgres_store import get_pool
from config.settings import get_settings
from api.inbox import broadcast_event

logger = structlog.get_logger(__name__)

_task_handle: Optional[asyncio.Task] = None
_running = False


# ─── Notifs Slack ────────────────────────────────────────────────────────────

async def slack_notify(text: str, blocks: list | None = None) -> None:
    """Manda mensaje al webhook Slack del workspace (si está configurado)."""
    settings = get_settings()
    url = settings.slack_webhook_url
    if not url:
        return
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.warning("slack_notify_failed", error=str(e))


async def notify_human_request(conv_id: str, contact_name: str, last_msg: str) -> None:
    """Llama a Slack cuando una conv requiere atención humana."""
    text = f"⚠️ *{contact_name}* necesita atención humana"
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f">{last_msg[:200]}"}},
        {
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Abrir conversación"},
                "url": f"https://agentes.msklatam.com/inbox?conv={conv_id}",
            }],
        },
    ]
    await slack_notify(text, blocks)


# ─── Cron loop ───────────────────────────────────────────────────────────────

async def _cron_loop():
    global _running
    _running = True
    logger.info("inbox_jobs_started")
    while _running:
        try:
            # 1) Despertar snoozeados vencidos
            woken = await cm.wake_expired_snoozed()
            for conv_id in woken:
                logger.info("snooze_woken", conv_id=conv_id)
                broadcast_event({
                    "type": "snooze_woken",
                    "conversation_id": conv_id,
                })

            if woken:
                await slack_notify(
                    f"⏰ {len(woken)} conversaciones despertaron del snooze "
                    f"y vuelven al inbox activo."
                )

        except Exception as e:
            logger.error("cron_loop_error", error=str(e))

        # Esperar 5 min entre corridas
        try:
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            break

    logger.info("inbox_jobs_stopped")


def start_inbox_jobs():
    """Arranca el loop en background. Idempotente."""
    global _task_handle
    if _task_handle and not _task_handle.done():
        return
    loop = asyncio.get_event_loop()
    _task_handle = loop.create_task(_cron_loop())


def stop_inbox_jobs():
    global _running, _task_handle
    _running = False
    if _task_handle:
        _task_handle.cancel()


# ─── Audit log ───────────────────────────────────────────────────────────────

async def log_action(
    actor_id: str,
    action: str,
    conversation_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Persiste una acción humana al audit log."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                insert into public.inbox_audit_log
                  (actor_id, action, conversation_id, detail, created_at)
                values ($1, $2, $3, $4::jsonb, now())
                """,
                actor_id, action, conversation_id,
                json.dumps(detail or {}),
            )
        except Exception as e:
            logger.warning("audit_log_failed", error=str(e))


async def list_audit_log(
    limit: int = 100,
    conversation_id: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> list[dict]:
    pool = await get_pool()
    where_parts = []
    params: list = []
    idx = 1
    if conversation_id:
        where_parts.append(f"conversation_id = ${idx}")
        params.append(conversation_id); idx += 1
    if actor_id:
        where_parts.append(f"actor_id = ${idx}")
        params.append(actor_id); idx += 1
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    params.append(limit)
    sql = f"""
        select id, actor_id, action, conversation_id, detail, created_at
        from public.inbox_audit_log
        {where}
        order by created_at desc
        limit ${idx}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [
        {
            "id": str(r["id"]),
            "actor_id": r["actor_id"],
            "action": r["action"],
            "conversation_id": str(r["conversation_id"]) if r["conversation_id"] else None,
            "detail": r["detail"] if isinstance(r["detail"], dict) else (json.loads(r["detail"]) if r["detail"] else {}),
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]
