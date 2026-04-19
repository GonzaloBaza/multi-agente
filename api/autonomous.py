"""
Endpoints para el monitor del sistema autónomo (sales closer).

GET  /admin/autonomous/status      — jobs activos, próximos runs, last stats
GET  /admin/autonomous/recent      — últimas acciones del retargeting (qué se envió, a quién)
POST /admin/autonomous/run-now     — fuerza un ciclo de retargeting manualmente
POST /admin/autonomous/retry-now   — fuerza el ciclo de auto-retry ahora
"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends

from api.auth import require_role
from memory.conversation_store import get_conversation_store

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin/autonomous", tags=["autonomous"])


@router.get("/status")
async def status(user: dict = Depends(require_role("admin", "supervisor"))):
    """Estado actual del scheduler + última run del retargeting."""
    try:
        from utils.scheduler import get_scheduler

        s = get_scheduler()
        jobs = [
            {
                "id": j.id,
                "name": j.name,
                "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
                "trigger": str(j.trigger),
            }
            for j in s.get_jobs()
        ]
        running = s.running
    except Exception:
        jobs, running = [], False

    store = await get_conversation_store()
    r = store._redis
    stats_raw = await r.get("retargeting:stats")
    stats = (
        json.loads(stats_raw.decode() if isinstance(stats_raw, bytes) else stats_raw) if stats_raw else None
    )

    cfg_raw = await r.get("retargeting:config")
    cfg = (
        json.loads(cfg_raw.decode() if isinstance(cfg_raw, bytes) else cfg_raw)
        if cfg_raw
        else {"enabled": True}
    )

    return {
        "scheduler_running": running,
        "jobs": jobs,
        "last_run_stats": stats,
        "config": cfg,
    }


@router.get("/recent")
async def recent_actions(user: dict = Depends(require_role("admin", "supervisor"))):
    """Últimas acciones del retargeting (basadas en keys retarget_sent:* con TTL)."""
    store = await get_conversation_store()
    r = store._redis
    results = []
    async for raw_key in r.scan_iter(match="retarget_sent:*", count=100):
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        value = await r.get(key)
        ttl = await r.ttl(key)
        parts = key.split(":")
        # formato: retarget_sent:{phone}:day{N}
        phone = parts[1] if len(parts) > 2 else ""
        day = parts[2] if len(parts) > 2 else ""
        results.append(
            {
                "phone": phone,
                "day": day,
                "action": (value.decode() if isinstance(value, bytes) else value) or "",
                "ttl_seconds": ttl,
            }
        )
    results.sort(key=lambda x: x["ttl_seconds"] or 0, reverse=True)
    return {"recent": results[:200]}


@router.post("/run-now")
async def run_now(user: dict = Depends(require_role("admin", "supervisor"))):
    """Dispara un ciclo de retargeting manualmente."""
    import asyncio

    from utils.autonomous_tasks import run_retargeting_cycle

    asyncio.create_task(run_retargeting_cycle())
    return {"ok": True, "message": "Ciclo de retargeting disparado"}


@router.post("/retry-now")
async def retry_now(user: dict = Depends(require_role("admin", "supervisor"))):
    """Dispara el ciclo de auto-retry de descartados manualmente."""
    import asyncio

    from utils.autonomous_tasks import run_auto_retry_cycle

    asyncio.create_task(run_auto_retry_cycle())
    return {"ok": True, "message": "Ciclo de auto-retry disparado"}


class ConfigUpdate:
    pass


@router.post("/toggle")
async def toggle(user: dict = Depends(require_role("admin", "supervisor"))):
    """Toggle on/off del sistema autónomo."""
    store = await get_conversation_store()
    r = store._redis
    raw = await r.get("retargeting:config")
    cfg = {"enabled": True}
    if raw:
        try:
            cfg = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        except Exception:
            pass
    cfg["enabled"] = not cfg.get("enabled", True)
    await r.set("retargeting:config", json.dumps(cfg))
    return {"enabled": cfg["enabled"]}
