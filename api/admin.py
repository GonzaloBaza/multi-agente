"""
Endpoints de administración (protegidos con API key interna):
- GET  /admin/status   → estado del sistema
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_key(x_admin_key: str = Header(...)):
    settings = get_settings()
    if x_admin_key != settings.app_secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return x_admin_key


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
