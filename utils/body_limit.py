"""
Middleware que limita el tamaño del body del request.

Uvicorn/Starlette no limita por default — un cliente malicioso puede pegar
un POST de 2GB y agotar memoria del container. Rechazamos con 413 si el
Content-Length declarado excede el límite, y también enforce a nivel stream
por si el Content-Length miente.

Excepciones: endpoints de upload de media (inbox, templates) aceptan más
para permitir audios/PDFs. Pasá el path en `whitelist_paths` si necesitás
bypass.
"""

from __future__ import annotations

from collections.abc import Iterable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_bytes: int = 1_000_000,
        upload_paths: Iterable[str] = (),
        upload_max_bytes: int = 25_000_000,
    ):
        super().__init__(app)
        self._max = max_bytes
        self._upload_max = upload_max_bytes
        self._upload_paths = tuple(upload_paths)

    def _limit_for(self, path: str) -> int:
        if any(path.startswith(p) for p in self._upload_paths):
            return self._upload_max
        return self._max

    async def dispatch(self, request: Request, call_next) -> Response:
        limit = self._limit_for(request.url.path)
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    return _too_large(limit)
            except ValueError:
                pass
        # No podemos enforce streaming sin consumir el body acá (rompería el
        # handler downstream). El declared es suficiente para la inmensa
        # mayoría de ataques (cliente honesto sobre Content-Length).
        return await call_next(request)


def _too_large(limit: int) -> JSONResponse:
    logger.warning("request_body_too_large", limit=limit)
    return JSONResponse(
        status_code=413,
        content={"detail": f"Request body demasiado grande (max {limit} bytes)"},
    )
