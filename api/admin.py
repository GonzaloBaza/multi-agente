"""
Endpoints de administración (protegidos con API key interna):
- POST /admin/reindex  → re-indexa todos los cursos en Pinecone
- GET  /admin/status   → estado del sistema
- POST /admin/reindex/{country} → re-indexa un país específico
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header
from rag.indexer import CourseIndexer
from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_key(x_admin_key: str = Header(...)):
    settings = get_settings()
    if x_admin_key != settings.app_secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return x_admin_key


@router.post("/reindex")
async def reindex_all(key: str = Depends(verify_admin_key)):
    """Re-indexa todos los JSONs de cursos en Pinecone."""
    indexer = CourseIndexer()
    data_dir = Path(__file__).parent.parent / "rag" / "data"
    try:
        results = await indexer.index_all_countries(data_dir)
        logger.info("reindex_complete", results=results)
        return {"status": "ok", "indexed": results}
    except Exception as e:
        logger.error("reindex_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/{country}")
async def reindex_country(country: str, key: str = Depends(verify_admin_key)):
    """Re-indexa los cursos de un país específico (AR, MX, CO, PE, CL, UY)."""
    country = country.upper()
    data_dir = Path(__file__).parent.parent / "rag" / "data"
    json_file = data_dir / f"courses_{country.lower()}.json"

    if not json_file.exists():
        raise HTTPException(status_code=404, detail=f"No data file for country {country}")

    indexer = CourseIndexer()
    try:
        count = await indexer.index_from_file(json_file, country)
        return {"status": "ok", "country": country, "indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    pinecone_ok = False
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=settings.pinecone_api_key)
        indexes = [i.name for i in pc.list_indexes()]
        pinecone_ok = settings.pinecone_index_name in indexes
    except Exception:
        pass

    # Circuit breakers status
    from utils.circuit_breaker import CircuitBreaker
    breakers = CircuitBreaker.get_all_status()

    return {
        "status": "ok",
        "redis": "connected" if redis_ok else "error",
        "pinecone": "connected" if pinecone_ok else "error",
        "model": settings.openai_model,
        "env": settings.app_env,
        "circuit_breakers": breakers,
    }
