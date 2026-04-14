"""
API para gestionar flujos de conversación.
Almacena en Redis (persistente) en vez de archivos locales.
"""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from api.auth import require_role

router = APIRouter(prefix="/admin/flows", tags=["flows"])

FLOW_KEY   = "flow:{name}"          # hash con data del flujo
FLOWS_LIST = "flows:index"           # set con nombres de flujos
ACTIVE_KEY = "flow:active"           # string con el nombre del flujo activo


async def _redis():
    from memory.conversation_store import get_conversation_store
    store = await get_conversation_store()
    return store._redis


class FlowSave(BaseModel):
    name: str
    drawflow: dict
    active: bool = False


@router.get("/list")
async def list_flows(user: dict = Depends(require_role("admin", "supervisor"))):
    r = await _redis()
    names = await r.smembers(FLOWS_LIST)
    flows = []
    active_name = await r.get(ACTIVE_KEY)
    if isinstance(active_name, bytes):
        active_name = active_name.decode()
    for n in sorted(names):
        name = n.decode() if isinstance(n, bytes) else n
        flows.append({"name": name, "active": name == active_name})
    return flows


@router.get("/{name}")
async def get_flow(name: str, user: dict = Depends(require_role("admin", "supervisor"))):
    r = await _redis()
    raw = await r.get(FLOW_KEY.format(name=name))
    if not raw:
        return {"name": name, "drawflow": None, "active": False}
    data = json.loads(raw)
    active_name = await r.get(ACTIVE_KEY)
    if isinstance(active_name, bytes):
        active_name = active_name.decode()
    data["active"] = (name == active_name)
    return data


@router.post("/save")
async def save_flow(flow: FlowSave, user: dict = Depends(require_role("admin"))):
    r = await _redis()
    payload = json.dumps({"name": flow.name, "drawflow": flow.drawflow}, ensure_ascii=False)
    await r.set(FLOW_KEY.format(name=flow.name), payload)
    await r.sadd(FLOWS_LIST, flow.name)
    if flow.active:
        await r.set(ACTIVE_KEY, flow.name)
    return {"ok": True}


@router.post("/{name}/activate")
async def activate_flow(name: str, user: dict = Depends(require_role("admin"))):
    r = await _redis()
    # Verify flow exists
    raw = await r.get(FLOW_KEY.format(name=name))
    if not raw:
        raise HTTPException(status_code=404, detail="Flujo no encontrado")
    await r.set(ACTIVE_KEY, name)
    return {"ok": True}


@router.post("/{name}/deactivate")
async def deactivate_flow(name: str, user: dict = Depends(require_role("admin"))):
    r = await _redis()
    active_name = await r.get(ACTIVE_KEY)
    if isinstance(active_name, bytes):
        active_name = active_name.decode()
    if active_name == name:
        await r.delete(ACTIVE_KEY)
    return {"ok": True}


@router.delete("/{name}")
async def delete_flow(name: str, user: dict = Depends(require_role("admin"))):
    r = await _redis()
    await r.delete(FLOW_KEY.format(name=name))
    await r.srem(FLOWS_LIST, name)
    active_name = await r.get(ACTIVE_KEY)
    if isinstance(active_name, bytes):
        active_name = active_name.decode()
    if active_name == name:
        await r.delete(ACTIVE_KEY)
    return {"ok": True}


# ── Widget Config ──────────────────────────────────────────────
WIDGET_CONFIG_KEY = "widget:config"


class WidgetConfig(BaseModel):
    title: str = "Asesor de Cursos"
    color: str = "#1a73e8"
    greeting: str = ""
    avatar: str = ""
    bubble_icon: str = ""
    position: str = "right"
    quick_replies: str = ""


@router.get("/widget-config/public")
async def get_widget_config_public():
    """Public endpoint for the embeddable widget to load its config."""
    r = await _redis()
    raw = await r.get(WIDGET_CONFIG_KEY)
    if not raw:
        return WidgetConfig().model_dump()
    return json.loads(raw)


@router.get("/widget-config")
async def get_widget_config(user: dict = Depends(require_role("admin", "supervisor"))):
    r = await _redis()
    raw = await r.get(WIDGET_CONFIG_KEY)
    if not raw:
        return WidgetConfig().model_dump()
    return json.loads(raw)


@router.post("/widget-config")
async def save_widget_config(config: WidgetConfig, user: dict = Depends(require_role("admin"))):
    r = await _redis()
    await r.set(WIDGET_CONFIG_KEY, json.dumps(config.model_dump(), ensure_ascii=False))
    return {"ok": True}
