"""
Endpoint de ventas v2 (experimental, aislado de producción).

`POST /api/v1/sales/whatsapp/webhook-v2`

Mismo shape y mismo preprocessing que el v1 (dedup + audio/imagen + debounce,
reusando los helpers de `api/sales_whatsapp.py`), pero invoca el agente con
`build_sales_agent_v2` (prompt podado + reforzado + modelo `SALES_V2_MODEL`).

Reúsa `_process_message_and_respond` de v1 vía el parámetro `agent_builder` →
garantiza paridad de orquestación; lo único distinto es prompt + modelo.

Zoho en modo TEST: los leads que cree el v2 se marcan con `[QA-V2]` en
Description (idempotente por conversación) para filtrarlos/borrarlos fácil.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from agents.sales.agent_v2 import _v2_model, build_sales_agent_v2
from api.sales_whatsapp import (
    BotmakerPayload,
    BotmakerResponse,
    _bucket_drain,
    _bucket_push,
    _bucket_release,
    _bucket_try_lock,
    _debounce_wait,
    _describe_image_url,
    _is_duplicate_msgid,
    _process_message_and_respond,
    _transcribe_audio_url,
)
from memory.conversation_store import get_conversation_store
from utils.agent_context import current_channel

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/sales/whatsapp", tags=["sales-whatsapp-v2"])


async def _mark_lead_test(lead_id: str, phone: str, headline: str) -> None:
    """Marca el lead como prueba ([QA-V2] en Description). Idempotente por phone."""
    if not lead_id:
        return
    try:
        store = await get_conversation_store()
        flag = f"qa_v2_marked:{phone}"
        if await store._redis.get(flag):
            return
        from integrations.zoho.leads import ZohoLeads

        await ZohoLeads().update(lead_id, {"Description": f"[QA-V2] {headline or 'test v2'}"})
        await store._redis.set(flag, "1", ex=7 * 24 * 3600)
        logger.info("sales_v2_lead_marked_test", lead_id=lead_id, phone=phone)
    except Exception as e:
        logger.warning("sales_v2_mark_test_failed", error=str(e))


@router.post("/webhook-v2", response_model=BotmakerResponse)
async def sales_whatsapp_webhook_v2(payload: BotmakerPayload) -> BotmakerResponse:
    """Webhook v2 — idéntico al v1 pero con agente v2 (prompt podado + modelo env)."""
    logger.info(
        "sales_v2_webhook_received",
        msg_id=payload.msgId,
        phone=payload.phone,
        lead_id=payload.leadId,
        model=_v2_model(),
    )

    if not payload.phone:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="missing phone")

    # Dedup por msgId (anti-bucle) — mismo store que v1.
    if await _is_duplicate_msgid(payload.msgId or ""):
        logger.info("sales_v2_duplicate_msgid", msg_id=payload.msgId)
        return BotmakerResponse(skip_response=True)

    current_channel.set("whatsapp")

    # Audio / imagen → texto (reusa los transcriptores de v1).
    user_msg = payload.userMessage or ""
    if payload.audioUrl or user_msg == "__audio__":
        transcribed = await _transcribe_audio_url(payload.audioUrl) if payload.audioUrl else ""
        if not transcribed:
            return BotmakerResponse(
                text="Recibí tu audio pero no logré transcribirlo. ¿Me lo escribís en texto? 🙏",
                context={},
            )
        user_msg = transcribed
    elif payload.imageUrl or user_msg == "__image__":
        description = await _describe_image_url(payload.imageUrl) if payload.imageUrl else ""
        if not description:
            return BotmakerResponse(
                text="Recibí tu imagen pero no logré procesarla. ¿Me contás por texto qué necesitás? 🙏",
                context={},
            )
        user_msg = description

    if not user_msg:
        return BotmakerResponse(skip_response=True)

    # Debounce (mismo mecanismo que v1).
    await _bucket_push(payload.phone, user_msg)
    if not await _bucket_try_lock(payload.phone):
        logger.info("sales_v2_debounce_yielded", phone=payload.phone, msg_id=payload.msgId)
        return BotmakerResponse(skip_response=True)

    try:
        await _debounce_wait(payload.phone)
        msgs = await _bucket_drain(payload.phone)
        if not msgs:
            msgs = [user_msg]
        user_msg = msgs[0] if len(msgs) == 1 else "\n".join(msgs)

        # MISMA orquestación que v1, swappeando solo el builder del agente.
        resp = await _process_message_and_respond(
            payload, user_msg, agent_builder=build_sales_agent_v2
        )

        # Marcar el lead como TEST (best-effort, idempotente).
        lead_id = (resp.context or {}).get("leadId") if resp else ""
        await _mark_lead_test(lead_id, payload.phone, payload.referralHeadline)
        return resp
    finally:
        await _bucket_release(payload.phone)


@router.get("/health-v2")
async def health_v2() -> dict:
    return {"status": "ok", "variant": "v2", "model": _v2_model()}
