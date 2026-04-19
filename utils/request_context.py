"""
Middleware de request context + logging estructurado.

Por cada HTTP request:
  - Asigna un `request_id` (UUID corto) si el cliente no mandó uno en
    header `X-Request-ID`. Se propaga en la respuesta (misma header) y
    en cada log emitido durante el ciclo del request via structlog
    contextvars.
  - Captura `user_id` / `user_role` si hay session token válido (best-effort
    — no bloquea si falla).
  - Loguea `http_request_start` y `http_request_done` con duración y
    status. Sirve como audit trail + debug de latencias.

Sin este middleware, los logs de un request quedan dispersos sin clave
común para correlacionarlos. Con él, basta filtrar `request_id` en
Sentry/Grafana/Loki para ver TODO lo que pasó en esa llamada.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Endpoints que NO se loguean (healthchecks de Docker/k8s generan mucho ruido).
_LOG_EXCLUDED_PATHS = {"/health"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]

        # Intentamos resolver quién está haciendo el request (sin bloquear
        # si el token es inválido — eso lo maneja el endpoint).
        user_id: str = ""
        user_role: str = ""
        session_token = request.headers.get("x-session-token")
        if session_token:
            try:
                from memory.conversation_store import get_conversation_store
                import json as _json
                store = await get_conversation_store()
                raw = await store._redis.get(f"session:{session_token}")
                if raw:
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    info = _json.loads(raw)
                    user_id = info.get("id", "")
                    user_role = info.get("role", "")
            except Exception:
                pass

        # Bindea contexto para que cualquier logger.info() dentro del
        # request cycle incluya estos campos automáticamente.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
            user_id=user_id,
            user_role=user_role,
        )

        skip_log = request.url.path in _LOG_EXCLUDED_PATHS
        started = time.perf_counter()
        if not skip_log:
            logger.info("http_request_start")

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            dur_ms = round((time.perf_counter() - started) * 1000)
            logger.exception("http_request_error", duration_ms=dur_ms, error=str(exc))
            raise

        dur_ms = round((time.perf_counter() - started) * 1000)
        response.headers["x-request-id"] = req_id
        if not skip_log:
            logger.info(
                "http_request_done",
                status=response.status_code,
                duration_ms=dur_ms,
            )
        return response
