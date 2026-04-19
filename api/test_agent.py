"""
Test AI Agent — sandbox para probar el pipeline multi-agente sin persistir nada.

Útil para QA de prompts, debugging del router, ver qué tools invoca cada agente,
y medir latencia/tokens consumidos.
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import structlog

from api.auth import require_role

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin/test-agent", tags=["test-agent"])


class TestMessageRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{role: "user"|"assistant", content: "..."}]
    country: str = "AR"
    channel: str = "widget"
    forced_agent: Optional[str] = None  # sales|collections|post_sales|closer|None
    skip_flow: bool = True  # saltea flow runner en tests


@router.post("")
async def test_agent(
    req: TestMessageRequest,
    user: dict = Depends(require_role("admin", "supervisor")),
):
    """Invoca el supervisor multi-agente con un prompt de test.
    NO persiste nada en Redis/Postgres. Retorna respuesta + metadata."""
    if not req.message.strip():
        raise HTTPException(400, "Mensaje vacío")

    from agents.router import route_message

    conversation_id = f"test_{int(time.time())}"
    t0 = time.monotonic()
    try:
        result = await route_message(
            user_message=req.message,
            history=req.history,
            country=req.country,
            channel=req.channel,
            conversation_id=conversation_id,
            phone="test",
            skip_flow=req.skip_flow,
        )
    except Exception as e:
        logger.error("test_agent_failed", error=str(e))
        raise HTTPException(500, f"Error en agente: {e}")
    latency_ms = int((time.monotonic() - t0) * 1000)

    return {
        "response": result.get("response", ""),
        "agent_used": result.get("agent_used", ""),
        "handoff_requested": bool(result.get("handoff_requested")),
        "handoff_reason": result.get("handoff_reason", ""),
        "link_rebill_enviado": bool(result.get("link_rebill_enviado")),
        "latency_ms": latency_ms,
    }
