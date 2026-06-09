"""
Admin de promos/cupones por país y canal.

Permite al admin editar desde el panel `/promos` qué cupón está activo en
cada (país, canal) sin tocar código. Los cambios se aplican en vivo —
cada request al endpoint sales lee el config fresh de Redis.

Storage: Redis key `campaign_configs:{COUNTRY}:{channel}` con JSON del config.
Si no hay key → se usa el hardcoded de `agents/sales/channel_configs.py`.

Endpoints (todos bajo `/api/v1/admin`):
  - GET    /promos                        → lista todos (país × canal)
  - GET    /promos/presets                → presets disponibles + países/canales soportados
  - PUT    /promos/{country}/{channel}    → guardar override (body: config dict)
  - DELETE /promos/{country}/{channel}    → borrar override (vuelve al default)

Auth: `verify_admin_or_session` + role admin/supervisor.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from agents.sales.channel_configs import (
    PROMO_PRESETS,
    SUPPORTED_CHANNELS,
    SUPPORTED_COUNTRIES,
    delete_campaign_config_override,
    list_campaign_configs,
    save_campaign_config_override,
)
from api.admin import require_role_or_admin, verify_admin_or_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin-promos"])


# ── Schemas ─────────────────────────────────────────────────────────────────


class PromoConfig(BaseModel):
    """Config de promo. Forma libre según `promo_type`."""

    promo_type: str = Field(..., description="'none' | 'scaled_coupons' | 'hot_sale_block'")
    # Campos opcionales (presentes según promo_type)
    code: str | None = None
    pct: int | None = None
    factor: float | None = None
    until: str | None = None
    name: str | None = None
    country_name: str | None = None
    # `scaled_coupons` usa levels en vez de los campos planos
    levels: list[Any] | None = None

    def to_dict(self) -> dict:
        out = {"promo_type": self.promo_type}
        for k in ("code", "pct", "factor", "until", "name", "country_name", "levels"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        return out


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get(
    "/promos",
    dependencies=[Depends(verify_admin_or_session), Depends(require_role_or_admin("admin", "supervisor"))],
)
async def list_promos() -> dict:
    """Lista TODOS los configs activos (país × canal).
    Cada item indica si viene del hardcoded (`source='default'`) o de un
    override Redis (`source='override'`)."""
    items = await list_campaign_configs()
    return {"items": items, "count": len(items)}


@router.get(
    "/promos/presets",
    dependencies=[Depends(verify_admin_or_session), Depends(require_role_or_admin("admin", "supervisor"))],
)
async def get_promo_presets() -> dict:
    """Devuelve los presets disponibles (lo que el dropdown muestra) +
    países/canales soportados. Lo usa la UI para popular el dropdown."""
    return {
        "presets": [
            {"key": "none",            "label": "Sin promo",                "config": PROMO_PRESETS["none"]},
            {"key": "scaled_coupons",  "label": "BOT15/BOT20 escalado",      "config": PROMO_PRESETS["scaled_coupons"]},
            {"key": "custom",          "label": "Hot Sale custom (editar)",  "config": PROMO_PRESETS["hot_sale_template"]},
        ],
        "countries": [{"iso": iso, "name": name} for iso, name in SUPPORTED_COUNTRIES],
        "channels": SUPPORTED_CHANNELS,
    }


@router.put(
    "/promos/{country}/{channel}",
    dependencies=[Depends(verify_admin_or_session), Depends(require_role_or_admin("admin", "supervisor"))],
)
async def update_promo(
    country: str = Path(..., min_length=2, max_length=3),
    channel: str = Path(..., min_length=2),
    config: PromoConfig = Body(...),
) -> dict:
    """Guarda override en Redis para (country, channel)."""
    iso = country.upper().strip()
    ch = channel.lower().strip()
    if iso not in {c[0] for c in SUPPORTED_COUNTRIES}:
        raise HTTPException(400, f"País no soportado: {iso}")
    if ch not in SUPPORTED_CHANNELS:
        raise HTTPException(400, f"Canal no soportado: {ch}")
    if config.promo_type not in ("none", "scaled_coupons", "hot_sale_block"):
        raise HTTPException(400, f"promo_type inválido: {config.promo_type}")
    try:
        await save_campaign_config_override(iso, ch, config.to_dict())
    except Exception as e:
        logger.error("promo_save_failed", country=iso, channel=ch, error=str(e))
        raise HTTPException(500, f"Error guardando override: {e}")
    return {"ok": True, "country": iso, "channel": ch, "config": config.to_dict()}


@router.delete(
    "/promos/{country}/{channel}",
    dependencies=[Depends(verify_admin_or_session), Depends(require_role_or_admin("admin", "supervisor"))],
)
async def reset_promo(
    country: str = Path(..., min_length=2, max_length=3),
    channel: str = Path(..., min_length=2),
) -> dict:
    """Borra el override Redis. Vuelve al config hardcoded del .py."""
    iso = country.upper().strip()
    ch = channel.lower().strip()
    deleted = await delete_campaign_config_override(iso, ch)
    return {"ok": True, "country": iso, "channel": ch, "deleted": deleted}
