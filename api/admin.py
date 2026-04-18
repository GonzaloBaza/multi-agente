"""
Endpoints de administración (protegidos con API key interna):
- GET  /admin/status   → estado del sistema
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_key(x_admin_key: str = Header(...)):
    """Solo admin key — para scripts/cron/webhooks internos.

    Endpoints que sirven al UI logueado deben usar `verify_admin_or_session`
    para que el browser no necesite mandar el admin key (que sería expuesto
    en el bundle JS).
    """
    settings = get_settings()
    if x_admin_key != settings.app_secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return x_admin_key


async def verify_admin_or_session(
    x_admin_key: Optional[str] = Header(None),
    x_session_token: Optional[str] = Header(None),
) -> dict:
    """Acepta cualquiera de:
      - `X-Admin-Key: <secret>` → para scripts internos / cron / curl manual.
      - `X-Session-Token: <jwt>` → para el browser autenticado vía /auth/login.

    Retorna dict con `{auth: "admin"}` o `{auth: "session", user: {...}}`.

    Esto reemplaza a `verify_admin_key` en endpoints que el UI consume:
    sin esto, el frontend tendría que mandar el admin key embebido en el
    bundle JS (que se descarga en claro), bypaseando todo el sistema de
    sesiones. Con esto el browser solo necesita su JWT.
    """
    settings = get_settings()

    # 1. Admin key (preferido si viene — backward-compat con scripts).
    if x_admin_key:
        if x_admin_key == settings.app_secret_key:
            return {"auth": "admin"}
        raise HTTPException(status_code=403, detail="Invalid admin key")

    # 2. Session token vía Redis (mismo storage que get_current_user).
    if x_session_token:
        from memory.conversation_store import get_conversation_store
        import json as _json
        store = await get_conversation_store()
        data = await store._redis.get(f"session:{x_session_token}")
        if not data:
            raise HTTPException(status_code=401, detail="Sesión expirada")
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return {"auth": "session", "user": _json.loads(data)}

    raise HTTPException(status_code=401, detail="No autenticado")


def require_role_or_admin(*roles: str):
    """Dependencia: acepta admin key (pasa siempre) o sesión con role en roles.

    Pensada para endpoints que ya dependen de `verify_admin_or_session` a
    nivel de router pero necesitan gate adicional por rol (bulk ops,
    administración de templates, etc).

    Uso:
        @router.post("/bulk/assign")
        async def bulk_assign(..., auth: dict = Depends(require_role_or_admin("admin", "supervisor"))):
            ...
    """
    async def _check(auth: dict = Depends(verify_admin_or_session)) -> dict:
        # Admin key ≡ rol admin (scripts internos, cron)
        if auth.get("auth") == "admin":
            return auth
        user = auth.get("user") or {}
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Sin permisos para esta acción")
        return auth
    return _check


@router.get("/status")
async def get_status(key: str = Depends(verify_admin_key)):
    """Estado general del sistema."""
    import redis.asyncio as aioredis
    settings = get_settings()

    redis_ok = False
    try:
        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        redis_ok = True
        await client.aclose()
    except Exception:
        pass

    # Postgres (Supabase)
    pg_ok = False
    try:
        from memory import postgres_store
        pool = await postgres_store.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        pg_ok = True
    except Exception:
        pass

    # Circuit breakers status
    from utils.circuit_breaker import CircuitBreaker
    breakers = CircuitBreaker.get_all_status()

    return {
        "status": "ok",
        "redis": "connected" if redis_ok else "error",
        "postgres": "connected" if pg_ok else "error",
        "model": settings.openai_model,
        "env": settings.app_env,
        "circuit_breakers": breakers,
    }
