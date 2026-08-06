"""
Test AI Agent — sandbox para probar el pipeline multi-agente sin persistir nada.

Útil para QA de prompts, debugging del router, ver qué tools invoca cada agente,
y medir latencia/tokens consumidos.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import require_role
from utils.rate_limits import TEST_AGENT_PER_USER, limiter

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin/test-agent", tags=["test-agent"])


class TestMessageRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{role: "user"|"assistant", content: "..."}]
    country: str = "AR"
    channel: str = "widget"
    # Acepta ambos vocabularios (ver `_agent_name_map` en agents/router.py):
    # ventas|cobranzas|post_venta|closer o sales|collections|post_sales|closer.
    forced_agent: str | None = None
    skip_flow: bool = True  # no-op, se conserva por compat de callers

    # Contexto del usuario simulado. Sin esto es imposible reproducir en el
    # sandbox los bugs que dependen de la ficha del alumno (ej. estado de
    # cuenta), porque los agentes resuelven la ficha a partir del email/phone.
    email: str = ""
    user_name: str = ""
    phone: str = ""
    page_slug: str = ""
    has_debt: bool = False
    is_student: bool = False


@router.post("")
@limiter.limit(TEST_AGENT_PER_USER)
async def test_agent(
    request: Request,
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
            phone=req.phone or "test",
            email=req.email,
            user_name=req.user_name,
            page_slug=req.page_slug,
            has_debt=req.has_debt,
            is_student=req.is_student,
            skip_flow=req.skip_flow,
            # Sin esto el selector "Forzar agente" de la UI no hacía nada: el
            # mensaje siempre pasaba por el clasificador.
            forced_agent=req.forced_agent,
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
