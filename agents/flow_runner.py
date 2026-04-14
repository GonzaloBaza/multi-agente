"""
Ejecuta el flujo activo para una conversación.
"""
import json
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)

ACTIVE_KEY = "flow:active"
FLOW_KEY_TPL = "flow:{name}"


async def _get_active_flow() -> Optional[dict]:
    """Carga el flujo activo desde Redis."""
    from memory.conversation_store import get_conversation_store
    store = await get_conversation_store()
    r = store._redis
    active_name = await r.get(ACTIVE_KEY)
    if not active_name:
        return None
    if isinstance(active_name, bytes):
        active_name = active_name.decode()
    raw = await r.get(FLOW_KEY_TPL.format(name=active_name))
    if not raw:
        return None
    return json.loads(raw)


def _nodes(drawflow_data: dict) -> dict:
    return drawflow_data.get("drawflow", {}).get("Home", {}).get("data", {})


def _find_start_node(drawflow_data: dict) -> tuple:
    for node_id, node in _nodes(drawflow_data).items():
        if node.get("name") == "inicio":
            return node_id, node
    return None, None


def _find_node(drawflow_data: dict, node_id: str) -> Optional[dict]:
    return _nodes(drawflow_data).get(str(node_id))


def _follow_output(drawflow_data: dict, node_id: str, output_name: str) -> Optional[str]:
    node = _find_node(drawflow_data, node_id)
    if not node:
        return None
    conns = node.get("outputs", {}).get(output_name, {}).get("connections", [])
    return str(conns[0]["node"]) if conns else None


def _match_output(node: dict, user_message: str) -> str:
    """Match user message to an output by button label. Returns output name or 'output_1'."""
    data = node.get("data", {})
    button_outputs = data.get("button_outputs", {})  # {"output_1": "Cursos online 💻", ...}
    user_lower = user_message.lower().strip()
    for out_name, label in button_outputs.items():
        label_lower = label.lower()
        # Strip emoji and extra spaces for comparison
        label_clean = "".join(c for c in label_lower if c.isalpha() or c.isspace()).strip()
        user_clean = "".join(c for c in user_lower if c.isalpha() or c.isspace()).strip()
        if label_clean and (label_clean in user_clean or user_clean in label_clean):
            return out_name
    # default: first output
    outputs = node.get("outputs", {})
    return list(outputs.keys())[0] if outputs else "output_1"


def _node_to_response(node: dict) -> str:
    data = node.get("data", {})
    msg = data.get("message", "")
    buttons = [b.strip() for b in data.get("buttons", []) if b.strip()]
    if buttons:
        return f"{msg} [BUTTONS: {' | '.join(buttons)}]"
    return msg


FLOW_STATE_TTL = 86400  # 24h


async def _mark_done(store, state_key: str):
    """Marca el flujo como completado para esta sesión (no se reinicia)."""
    await store._redis.setex(state_key, FLOW_STATE_TTL, json.dumps({"done": True}))


async def run_flow_step(session_id: str, user_message: str) -> Optional[dict]:
    """
    Try to advance the conversation flow.
    Returns:
      {"response": str, "agent": None, "handoff": False} — flow sent message, continue flow
      {"response": None, "agent": "ventas"|..., "handoff": False} — delegate to AI agent
      {"response": str, "agent": None, "handoff": True} — handoff to human
      None — no active flow, or flow already done for this session
    """
    flow_data = await _get_active_flow()
    if not flow_data:
        return None

    drawflow = flow_data.get("drawflow")
    if not drawflow:
        return None

    from memory.conversation_store import get_conversation_store
    store = await get_conversation_store()

    state_key = f"flow_state:{session_id}"
    state_raw = await store._redis.get(state_key)

    # ── Flujo ya completado para esta sesión — no reiniciar ──
    if state_raw is not None:
        state = json.loads(state_raw)
        if state.get("done"):
            return None

    # ── Primera vez: iniciar flujo ──
    if state_raw is None:
        node_id, start_node = _find_start_node(drawflow)
        if not node_id:
            return None
        response = _node_to_response(start_node)
        await store._redis.setex(state_key, FLOW_STATE_TTL, json.dumps({"node": node_id}))
        logger.info("flow_started", session=session_id, node=node_id)
        return {"response": response, "agent": None, "handoff": False}

    # ── Avanzar flujo ──
    state = json.loads(state_raw)
    current_node_id = state.get("node")
    current_node = _find_node(drawflow, current_node_id)

    if not current_node:
        await _mark_done(store, state_key)
        return None

    out_name = _match_output(current_node, user_message)
    next_node_id = _follow_output(drawflow, current_node_id, out_name)

    if not next_node_id:
        # Sin conexión → pasar al AI (no reiniciar más)
        await _mark_done(store, state_key)
        return None

    next_node = _find_node(drawflow, next_node_id)
    if not next_node:
        await _mark_done(store, state_key)
        return None

    next_name = next_node.get("name", "")
    next_data = next_node.get("data", {})

    if next_name in ("mensaje", "botones", "inicio"):
        response = _node_to_response(next_node)
        await store._redis.setex(state_key, FLOW_STATE_TTL, json.dumps({"node": next_node_id}))
        logger.info("flow_step", session=session_id, node=next_node_id, type=next_name)
        return {"response": response, "agent": None, "handoff": False}

    elif next_name == "agente_ia":
        agent = next_data.get("agent", "ventas")
        await _mark_done(store, state_key)
        logger.info("flow_to_agent", session=session_id, agent=agent)
        return {"response": None, "agent": agent, "handoff": False}

    elif next_name == "humano":
        msg = next_data.get("message", "Te voy a conectar con un asesor. 🙏")
        await _mark_done(store, state_key)
        logger.info("flow_to_human", session=session_id)
        return {"response": msg, "agent": None, "handoff": True}

    await _mark_done(store, state_key)
    return None
