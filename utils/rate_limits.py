"""
Config centralizada de rate limiting por endpoint.

`main.py` inicializa un `Limiter` global con default 60/min por IP. Este
módulo exporta el mismo limiter + helpers para key-by-user (cuota por
sesión autenticada, no por IP) y los decoradores específicos con límites
custom.

Valores calibrados para el tamaño actual (5-50 agentes humanos + un par
de miles de conversaciones del bot/día). Si se escala agregá una capa
Cloudflare / AWS WAF antes de tocar estos.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def user_or_ip(request: Request) -> str:
    """Key func: usuario autenticado si hay session token, si no IP.

    Previene que un agente rogue consuma la cuota global compartida con
    usuarios anónimos (que suele ser más laxa por IP). Si dos usuarios
    comparten IP (NAT corporativo), cada uno tiene su quota.
    """
    session = request.headers.get("x-session-token")
    if session:
        # Prefijo para que no colisione con una IP que sea "abc123".
        return f"session:{session[:16]}"
    return get_remote_address(request)


# Limiter global — mismo instance que main.py registra en app.state.
# Se re-exporta para que los routers puedan decorar endpoints.
limiter = Limiter(key_func=user_or_ip, default_limits=["120/minute"])


# ─── Límites nombrados ──────────────────────────────────────────────────────
# Documentar el "por qué" de cada uno acá evita que alguien los toque sin
# entender. Ajustalos si observás 429 reales en prod.

# LLM calls — costosas en tokens. Un agente pidiendo 1000 spell-checks
# en 1 min = USD 5-10. Límite protege wallet.
LLM_PER_USER = "30/minute"

# Test agent sandbox — corre un full LangGraph run. 10/min = 1 run cada
# 6 seg, suficiente para debugging manual.
TEST_AGENT_PER_USER = "10/minute"

# Bulk ops del inbox — operaciones destructivas en N convs.
BULK_OPS_PER_USER = "20/minute"

# Redis admin destructivo. Algo del estilo "did you MEAN to click that?".
REDIS_FLUSH_PER_USER = "2/hour"
REDIS_NUKE_PER_USER = "1/day"

# Widget público — el endpoint /widget/chat lo pega el browser del
# visitante. 30/min por session_id (cookie) es razonable — un humano
# escribe <10 mensajes/min normal.
WIDGET_CHAT_PER_SESSION = "30/minute"

# Uploads de media — file upload puede consumir bandwith. 20/min alcanza
# para un agente mandando audios/docs a un cliente.
UPLOAD_PER_USER = "20/minute"
