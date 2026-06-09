"""
Configuraciones de campaña/cupón por canal+país.

Cada config define cómo se renderiza el bloque de promo dentro del system
prompt de ventas. Permite que el mismo prompt base sirva para múltiples
canales (widget, whatsapp, email digest, etc.) y campañas (Hot Sale,
Black Friday, cupones permanentes del bot, etc.) **sin duplicar el prompt**.

Cómo se usa:
    from agents.sales.channel_configs import get_campaign_config
    config = get_campaign_config(country="AR", channel="whatsapp")
    prompt = build_sales_prompt(country="AR", channel="whatsapp",
                                campaign_config=config)

Tipos de promo soportados (`promo_type`):
    - "hot_sale_block": promo única tipo Hot Sale (1 código, %, vigencia).
      Se MENCIONA en apertura. Usado en widget de campaña pública.
    - "scaled_coupons": 2 niveles de cupón con escalado por objeción.
      NO se menciona en apertura — aparece solo si hay objeción real
      de precio. Usado en WhatsApp (lead ya calificado, mejor margen).
    - "none": sin promo. El bot no menciona descuentos ni cupones
      en absoluto. Usado para canales/países sin campaña activa.

Para agregar un canal/campaña nuevo:
    1. Sumá el config al dict `_CONFIGS` con key (country.upper(), channel).
    2. (Opcional) Si es un `promo_type` nuevo, agregá un renderer en
       `agents/sales/prompts.py` → `_render_promo_block(config)`.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Prefijo de las keys Redis donde se persisten los overrides editables
# desde el panel admin (`/promos`). El valor es el JSON del config dict.
# Cuando NO hay key en Redis para (country, channel), se cae al hardcoded
# de `_CONFIGS` / `_DEFAULTS_BY_CHANNEL` definido más abajo.
_REDIS_PREFIX = "campaign_configs"


def _redis_key(country: str, channel: str) -> str:
    return f"{_REDIS_PREFIX}:{(country or '').upper().strip()}:{(channel or '').lower().strip()}"


# ── PROMO ACTIVA — editar acá cuando cambie ─────────────────────────────────
# Widget AR — Hot Sale pública del sitio msklatam.com
WIDGET_AR: dict[str, Any] = {
    "promo_type": "hot_sale_block",
    "code": "HOY30",
    "pct": 30,
    "factor": 0.70,  # cuota × 0.70 = post-descuento
    "until": "17 de mayo 2026",
    "name": "Hot Sale",
}

# Cyber CL/UY — Semana de ciber (1 al 7 de junio 2026), 30% off con HOY30.
# 🛑 FINALIZADA el 7/6/2026 — CL/UY vuelven a BOT15/BOT20 (WHATSAPP_DEFAULT).
# Los configs se preservan para reactivación rápida en próxima campaña.
CYBER_CL: dict[str, Any] = {
    "promo_type": "hot_sale_block",
    "code": "HOY30",
    "pct": 30,
    "factor": 0.70,
    "until": "7 de junio",
    "name": "CyberDay",
    "country_name": "Chile",
}
CYBER_UY: dict[str, Any] = {
    "promo_type": "hot_sale_block",
    "code": "HOY30",
    "pct": 30,
    "factor": 0.70,
    "until": "7 de junio",
    "name": "CiberLunes",
    "country_name": "Uruguay",
}

# WhatsApp AR/LATAM — cupones permanentes del bot vendedor, escalado por objeción
WHATSAPP_DEFAULT: dict[str, Any] = {
    "promo_type": "scaled_coupons",
    "levels": [
        # (código, % descuento, factor cuota original, descripción nivel)
        ("BOT15", 15, 0.85, "Nivel 1 — primera objeción real de precio"),
        ("BOT20", 20, 0.80, "Nivel 2 — segunda objeción. Techo absoluto."),
    ],
}

# Países/canales sin campaña activa.
NO_PROMO: dict[str, Any] = {"promo_type": "none"}


# Mapa principal: (country_uppercase, channel_lowercase) → config.
# Si una combinación no está, se usa el default por canal (ver get_campaign_config).
_CONFIGS: dict[tuple[str, str], dict[str, Any]] = {
    # Widget
    ("AR", "widget"): WHATSAPP_DEFAULT,  # Hot Sale finalizado 17/5/2026 — vuelve a BOT15/BOT20
    # 🛑 Cyber CL/UY (1-7 jun 2026) — FINALIZADA. Vuelven a BOT15/BOT20 en ambos canales.
    # Para reactivar: cambiar `WHATSAPP_DEFAULT` → `CYBER_CL` / `CYBER_UY` y ajustar `until`.
    ("CL", "widget"): WHATSAPP_DEFAULT,
    ("CL", "whatsapp"): WHATSAPP_DEFAULT,
    ("UY", "widget"): WHATSAPP_DEFAULT,
    ("UY", "whatsapp"): WHATSAPP_DEFAULT,
    # WhatsApp (resto de países usan el BOT15/BOT20 escalado por objeción)
    ("AR", "whatsapp"): WHATSAPP_DEFAULT,
    ("MX", "whatsapp"): WHATSAPP_DEFAULT,
    ("CO", "whatsapp"): WHATSAPP_DEFAULT,
    ("PE", "whatsapp"): WHATSAPP_DEFAULT,
    ("BO", "whatsapp"): WHATSAPP_DEFAULT,
    ("PY", "whatsapp"): WHATSAPP_DEFAULT,
    ("EC", "whatsapp"): WHATSAPP_DEFAULT,
    ("VE", "whatsapp"): WHATSAPP_DEFAULT,
    ("CR", "whatsapp"): WHATSAPP_DEFAULT,
    ("GT", "whatsapp"): WHATSAPP_DEFAULT,
    ("HN", "whatsapp"): WHATSAPP_DEFAULT,
    ("NI", "whatsapp"): WHATSAPP_DEFAULT,
    ("PA", "whatsapp"): WHATSAPP_DEFAULT,
    ("SV", "whatsapp"): WHATSAPP_DEFAULT,
    ("ES", "whatsapp"): WHATSAPP_DEFAULT,
    ("INT", "whatsapp"): WHATSAPP_DEFAULT,
}


# Fallbacks por canal (cuando no hay match exacto país+canal).
_DEFAULTS_BY_CHANNEL: dict[str, dict[str, Any]] = {
    "widget": NO_PROMO,  # widget sin Hot Sale activa → sin promo
    "whatsapp": WHATSAPP_DEFAULT,  # cualquier país en WA → BOT15/BOT20
}


def get_campaign_config(country: str, channel: str) -> dict[str, Any]:
    """
    Devuelve el config HARDCODED de campaña/cupón para (country, channel).
    NO consulta Redis — solo lo definido en este archivo.

    Para incluir overrides editables desde el panel admin, usar
    `get_campaign_config_async`.

    Resolución:
        1. Match exacto (country.upper(), channel.lower()) en _CONFIGS.
        2. Fallback por canal en _DEFAULTS_BY_CHANNEL.
        3. NO_PROMO (sin promo) si ninguno aplica.
    """
    key = ((country or "").upper().strip(), (channel or "").lower().strip())
    if key in _CONFIGS:
        return _CONFIGS[key]
    return _DEFAULTS_BY_CHANNEL.get(key[1], NO_PROMO)


# ── PRESETS para la UI (lo que el admin elige en el dropdown) ──────────────
# Cada preset tiene una key estable y un config dict. La UI muestra los names
# en el dropdown; al guardar, persiste el config en Redis.
# Para "custom" la UI abre un mini-form donde el admin define los campos.
PROMO_PRESETS: dict[str, dict[str, Any]] = {
    "none": NO_PROMO,
    "scaled_coupons": WHATSAPP_DEFAULT,
    # Los Hot Sale custom se editan campo por campo desde la UI; no hay
    # preset fijo — el usuario define code, pct, factor, until, name,
    # country_name. Igualmente listamos uno de referencia:
    "hot_sale_template": {
        "promo_type": "hot_sale_block",
        "code": "PROMO",
        "pct": 20,
        "factor": 0.80,
        "until": "31 dic 2030",
        "name": "Promo",
        "country_name": "",
    },
}


def get_preset_key_for_config(cfg: dict[str, Any]) -> str:
    """Devuelve la key del preset que matchea exactamente el config dado.
    Si no matchea ninguno, devuelve "custom". Lo usa la UI para preseleccionar
    el dropdown.
    """
    if cfg == NO_PROMO:
        return "none"
    if cfg == WHATSAPP_DEFAULT:
        return "scaled_coupons"
    if cfg.get("promo_type") == "hot_sale_block":
        return "custom"
    return "custom"


# ── Versión async con override Redis ────────────────────────────────────────


async def get_campaign_config_async(country: str, channel: str) -> dict[str, Any]:
    """
    Como `get_campaign_config` pero CON override desde Redis.

    Resolución:
        1. Si Redis tiene un override para (country, channel) → usar ese.
        2. Sino, usar el hardcoded `get_campaign_config`.

    Pensado para llamarse desde el endpoint del canal (widget/whatsapp)
    al inicio del request, y pasar el resultado como `campaign_config=`
    a `build_sales_agent`.
    """
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        raw = await store._redis.get(_redis_key(country, channel))
        if raw:
            data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            if isinstance(data, dict) and data.get("promo_type"):
                return data
    except Exception as e:
        logger.debug("campaign_config_redis_get_failed", country=country, channel=channel, error=str(e))
    return get_campaign_config(country, channel)


async def save_campaign_config_override(country: str, channel: str, config: dict[str, Any]) -> None:
    """
    Guarda un override en Redis. El admin puede:
      - Setear NO_PROMO para desactivar.
      - Setear WHATSAPP_DEFAULT para activar BOT15/BOT20.
      - Setear un hot_sale_block custom (code, pct, factor, until, name, country_name).
    """
    if not isinstance(config, dict) or not config.get("promo_type"):
        raise ValueError("config debe tener 'promo_type'")
    from memory.conversation_store import get_conversation_store

    store = await get_conversation_store()
    # Sin TTL — el override persiste hasta que el admin lo borre.
    await store._redis.set(_redis_key(country, channel), json.dumps(config, ensure_ascii=False))
    logger.info(
        "campaign_config_override_saved",
        country=country,
        channel=channel,
        promo_type=config.get("promo_type"),
    )


async def delete_campaign_config_override(country: str, channel: str) -> bool:
    """Borra el override Redis. Vuelve al config hardcoded del .py.
    Retorna True si había algo para borrar, False si no."""
    from memory.conversation_store import get_conversation_store

    store = await get_conversation_store()
    deleted = await store._redis.delete(_redis_key(country, channel))
    if deleted:
        logger.info("campaign_config_override_deleted", country=country, channel=channel)
    return bool(deleted)


# Países soportados — los mismos del payload de WhatsApp (ver
# _COUNTRY_TO_ISO2 en api/sales_whatsapp.py). Plus INT como fallback genérico.
SUPPORTED_COUNTRIES: list[tuple[str, str]] = [
    ("AR", "Argentina"),
    ("BO", "Bolivia"),
    ("BR", "Brasil"),
    ("CL", "Chile"),
    ("CO", "Colombia"),
    ("CR", "Costa Rica"),
    ("EC", "Ecuador"),
    ("ES", "España"),
    ("GT", "Guatemala"),
    ("HN", "Honduras"),
    ("MX", "México"),
    ("NI", "Nicaragua"),
    ("PA", "Panamá"),
    ("PE", "Perú"),
    ("PY", "Paraguay"),
    ("SV", "El Salvador"),
    ("UY", "Uruguay"),
    ("VE", "Venezuela"),
    ("INT", "Otros / Internacional"),
]
SUPPORTED_CHANNELS: list[str] = ["widget", "whatsapp"]


async def list_campaign_configs() -> list[dict[str, Any]]:
    """
    Lista TODOS los configs activos (countries × channels), indicando para
    cada uno si el config viene del hardcoded (`source="default"`) o de un
    override Redis (`source="override"`).

    Retorna una lista de:
      {
        "country": "AR",
        "country_name": "Argentina",
        "channel": "widget",
        "config": {...promo_type...},
        "preset": "scaled_coupons" | "none" | "custom",
        "source": "default" | "override",
      }
    """
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        redis = store._redis
    except Exception:
        redis = None

    out: list[dict[str, Any]] = []
    for iso, name in SUPPORTED_COUNTRIES:
        for ch in SUPPORTED_CHANNELS:
            cfg = get_campaign_config(iso, ch)
            source = "default"
            if redis is not None:
                try:
                    raw = await redis.get(_redis_key(iso, ch))
                    if raw:
                        data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
                        if isinstance(data, dict) and data.get("promo_type"):
                            cfg = data
                            source = "override"
                except Exception:
                    pass
            out.append({
                "country": iso,
                "country_name": name,
                "channel": ch,
                "config": cfg,
                "preset": get_preset_key_for_config(cfg),
                "source": source,
            })
    return out
