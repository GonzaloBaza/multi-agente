"""
Retry con exponential backoff para llamadas a LLMs (OpenAI, Anthropic).

OpenAI tira regularmente 429 (rate limit) y 500/503 (overloaded) bajo carga.
Hoy un fail transitorio = respuesta vacía al usuario. Un wrapper con 3
reintentos (500ms, 2s, 5s) evita el 80% de esos casos.

Uso:

    from utils.llm_retry import with_retry

    @with_retry(attempts=3)
    async def call_openai(...):
        return await client.chat.completions.create(...)

O inline:

    resp = await with_retry(lambda: client.chat.completions.create(...))

No usamos `tenacity` para mantener requirements mínimos — la lógica es
simple (3 líneas) y así no agregamos una dep transitiva.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")

# Backoff exponencial clásico con jitter implícito (suma fija al attempt).
# Total worst-case: 0.5 + 2 + 5 = 7.5s antes de rendirse.
_DEFAULT_DELAYS = (0.5, 2.0, 5.0)

# Solo reintentamos estos errores. Los 4xx "lógicos" (auth, bad request,
# content filter) no se reintentan — son errores del caller.
_RETRYABLE_SUBSTRINGS = (
    "rate limit",
    "rate_limit",
    "timeout",
    "timed out",
    "overloaded",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
)


def _is_retryable(exc: BaseException) -> bool:
    # Excepciones HTTP conocidas de openai / httpx que tienen .status_code
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in (408, 429, 500, 502, 503, 504):
        return True
    msg = str(exc).lower()
    return any(s in msg for s in _RETRYABLE_SUBSTRINGS)


async def call_with_retry[T](  # noqa: UP047 — generic explícito por claridad
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delays: tuple[float, ...] = _DEFAULT_DELAYS,
    label: str = "llm_call",
) -> T:
    """Ejecuta `fn()` con reintentos. Re-raisa si agota intentos o error no-retryable."""
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or i == attempts - 1:
                break
            delay = delays[min(i, len(delays) - 1)]
            logger.warning(
                "llm_retry",
                label=label,
                attempt=i + 1,
                delay_s=delay,
                error=str(e)[:200],
            )
            await asyncio.sleep(delay)
    assert last_exc is not None  # noqa: S101 — defensive
    raise last_exc


def with_retry(
    *,
    attempts: int = 3,
    delays: tuple[float, ...] = _DEFAULT_DELAYS,
    label: str | None = None,
):
    """Decorator para funciones async que devuelven una promise del LLM."""

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        lbl = label or fn.__name__

        @wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            return await call_with_retry(
                lambda: fn(*args, **kwargs),
                attempts=attempts,
                delays=delays,
                label=lbl,
            )

        return wrapper

    return decorator
