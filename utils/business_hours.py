"""
Horario de atención por país — fuente de verdad única para todos los agentes.

Horario: **Lunes a Viernes, 9 a 18 hs, hora local del país del usuario**.
Fuera de ese rango (noches, fines de semana) = fuera de horario.

Usa `zoneinfo` (timezones IANA reales, DST-correcto todo el año) en vez de
offsets UTC fijos. Depende del paquete `tzdata` (ya instalado como dep de
APScheduler/tzlocal) para que funcione igual en el container Linux, que no
trae la base de zonas del sistema.

Acepta el país como ISO-2 (AR/MX/...) o como nombre completo en español
("Argentina", "México") — este último es el formato que usa la ficha de
cobranzas.
"""

from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

# País ISO-2 → timezone IANA. DST resuelto por zoneinfo.
_COUNTRY_TZ: dict[str, str] = {
    "AR": "America/Argentina/Buenos_Aires",
    "UY": "America/Montevideo",
    "BR": "America/Sao_Paulo",
    "CL": "America/Santiago",
    "BO": "America/La_Paz",
    "VE": "America/Caracas",
    "PY": "America/Asuncion",
    "CO": "America/Bogota",
    "PE": "America/Lima",
    "EC": "America/Guayaquil",
    "MX": "America/Mexico_City",
    "CR": "America/Costa_Rica",
    "GT": "America/Guatemala",
    "HN": "America/Tegucigalpa",
    "NI": "America/Managua",
    "SV": "America/El_Salvador",
    "PA": "America/Panama",
    "ES": "Europe/Madrid",
    "INT": "America/Argentina/Buenos_Aires",
}

# Nombre completo (como viene en la ficha de cobranzas) → ISO-2.
_NAME_TO_ISO: dict[str, str] = {
    "argentina": "AR",
    "uruguay": "UY",
    "brasil": "BR",
    "chile": "CL",
    "bolivia": "BO",
    "venezuela": "VE",
    "paraguay": "PY",
    "colombia": "CO",
    "peru": "PE",
    "perú": "PE",
    "ecuador": "EC",
    "mexico": "MX",
    "méxico": "MX",
    "costa rica": "CR",
    "guatemala": "GT",
    "honduras": "HN",
    "nicaragua": "NI",
    "el salvador": "SV",
    "panama": "PA",
    "panamá": "PA",
    "espana": "ES",
    "españa": "ES",
}

_DEFAULT_ISO = "AR"

# Horario de atención (hora local del país).
_BIZ_START_HOUR = 9
_BIZ_END_HOUR = 18  # exclusivo: 18:00 ya cuenta como fuera de horario.

_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Aviso reutilizable para cuando el bot deriva estando fuera de horario.
# Registra el caso, setea expectativa de contacto, y — clave — invita a la
# persona a seguir con el bot mientras tanto, para que no quede colgada.
OUT_OF_HOURS_LINE = (
    "Ahora estamos fuera del horario de atención (lunes a viernes de 9 a 18 hs), "
    "así que un asesor te va a contactar apenas volvamos. Igual dejo tu caso "
    "registrado — y si querés, mientras tanto seguimos por acá y te ayudo en lo "
    "que pueda. 🙏"
)


def _resolve_iso(country: str | None) -> str:
    """Normaliza ISO-2 o nombre completo a un ISO-2 conocido (default AR)."""
    raw = (country or "").strip()
    if not raw:
        return _DEFAULT_ISO
    up = raw.upper()
    if len(up) == 2 and up in _COUNTRY_TZ:
        return up
    iso = _NAME_TO_ISO.get(raw.lower())
    return iso or _DEFAULT_ISO


def _now_local(country: str | None = "AR") -> _dt.datetime:
    iso = _resolve_iso(country)
    tzname = _COUNTRY_TZ.get(iso, _COUNTRY_TZ[_DEFAULT_ISO])
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(_COUNTRY_TZ[_DEFAULT_ISO])
    return _dt.datetime.now(tz)


def is_business_hours(country: str | None = "AR") -> bool:
    """True si AHORA es horario de atención (L-V 9-18) en la hora local del país."""
    now = _now_local(country)
    return now.weekday() < 5 and _BIZ_START_HOUR <= now.hour < _BIZ_END_HOUR


def business_hours_note(country: str | None = "AR") -> str:
    """Línea de referencia para el prompt: hora local actual + estado in/out."""
    now = _now_local(country)
    iso = _resolve_iso(country)
    dia = _DIAS_ES[now.weekday()]
    estado = (
        "✅ dentro del horario laboral (L-V 9-18 hs)."
        if is_business_hours(country)
        else "⚠️ FUERA del horario laboral (L-V 9-18 hs)."
    )
    return f"Hora local {iso} ahora: {dia} {now.strftime('%d/%m %H:%M')} → {estado}"


def business_hours_block(country: str | None = "AR") -> str:
    """
    Sección lista para inyectar en el system prompt de cualquier agente.
    Le dice al bot si está dentro o fuera de horario y qué hacer al derivar.
    """
    note = business_hours_note(country)
    if is_business_hours(country):
        rule = (
            "Estás DENTRO del horario de atención: derivá, pasá el portal de "
            "tickets o dejá los datos con normalidad, SIN aclarar nada de horario."
        )
    else:
        rule = (
            "Estás FUERA del horario de atención. Esto SOLO afecta el contacto de "
            "un asesor humano — vos (el bot) seguís disponible 24/7 y NO cortás la "
            "conversación por el horario. Reglas:\n"
            "• Si el usuario simplemente sigue preguntando o charlando, atendelo "
            "con total normalidad, SIN mencionar el horario.\n"
            "• **Solo cuando estés por derivar a un asesor humano, pasar el portal "
            "de tickets o dejar sus datos para que lo contacten**: avisá primero "
            "— con tus palabras y tu tono — que ahora estamos fuera del horario de "
            "atención (L-V 9-18 hs), que el caso igual queda registrado, y OFRECELE "
            "seguir ayudándolo vos mientras tanto (que no quede colgado). Recién "
            "después completás la derivación como siempre.\n"
            f'Idea del mensaje (adaptalo, no lo copies literal): "{OUT_OF_HOURS_LINE}"'
        )
    return (
        "## ⏰ HORARIO DE ATENCIÓN\n"
        f"{note}\n"
        f"{rule}\n"
        "El horario es lunes a viernes de 9 a 18 hs en la hora local del país del "
        "usuario. No inventes ni prometas un horario distinto."
    )
