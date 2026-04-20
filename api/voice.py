"""
API de voice — por ahora solo lectura de call logs de Zoho Voice.

Recordatorio arquitectónico: el INICIO de llamadas (click-to-call) lo
resuelve la extensión ZDialer en el browser del agente, fuera de este
backend. Zoho Voice no expone una API REST pública para iniciar llamadas
a un número arbitrario — solo Power Dialer (campañas masivas), que no es
lo que queremos.

Lo que sí hacemos desde el backend:
  - GET /api/v1/voice/logs?phone=...  → historial de llamadas del cliente
    para mostrar en la timeline de cada conversación.

Auth: cookie de sesión (`verify_admin_or_session`). Disponible a todo agente
logueado — los agentes ven las llamadas de los clientes que atienden.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.admin import verify_admin_or_session
from integrations.zoho.voice import ZohoVoice

router = APIRouter(
    prefix="/api/v1/voice",
    tags=["voice"],
    dependencies=[Depends(verify_admin_or_session)],
)


@router.get("/logs")
async def list_call_logs(
    phone: str | None = Query(
        None,
        description=(
            "Número del cliente para filtrar. Acepta cualquier formato "
            "(+549..., 549..., con/sin guiones) — el cliente compara por "
            "los últimos 10 dígitos."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """Trae los call logs de Zoho Voice, opcionalmente filtrados por cliente.

    Sin `phone`: devuelve los últimos N globales (útil para debugging).
    Con `phone`: trae las llamadas asociadas a ese número.

    Shape de cada log:
        { logid, direction, start, end, duration, from_number, to_number,
          customer_number, did_number, agent_name, hangup_cause, ... }
    """
    client = ZohoVoice()
    logs = await client.list_logs(phone=phone, limit=limit)
    return {"logs": logs, "count": len(logs)}
