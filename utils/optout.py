"""
Opt-out (baja de contacto) para el bot de WhatsApp/Botmaker.

Cuando una persona pide que no la contacten más ("no me escriban más",
"no quiero recibir más info", etc.), el lead en Zoho pasa a Estado
"No habilitado". Las reglas del lifecycle de Enfermería llevan ese estado
excluido en sus criterios, así que los envíos programados pendientes
(t12/t24/pasa_fase2, mails 48/96hs, cierre t144) se descartan solos al
reevaluar criterios — mismo mecanismo que el freno de "Convertido Enfermeria".

Dos capas de detección:
- `es_optout_explicito()`: regex de frases duras. Corre determinista en el
  webhook de WhatsApp ANTES del LLM — cero riesgo de que el agente siga
  vendiendo. Solo frases inequívocas de "no me contacten": un "no me
  interesa" a secas NO corta acá (es una objeción que el agente puede
  manejar una vez; los grises los decide el LLM con la tool).
- Tool `marcar_no_contactar` (agents/sales/tools.py): el agente la llama
  ante pedidos de baja que el regex no matchea.
"""

import re

import structlog

logger = structlog.get_logger(__name__)

# Estado de baja en Zoho (display del picklist Lead_Status). La API v8 habla
# display values para este picklist (lee "Convertido Enfermeria", no su
# actual "Convertido"), pero por si el write exige el actual value del
# estado estándar renombrado, hay fallback a "Not Qualified".
OPTOUT_STATUS_DISPLAY = "No habilitado"
OPTOUT_STATUS_ACTUAL = "Not Qualified"

# Flag Redis por teléfono — evita re-updates a Zoho si la persona repite el
# pedido. NO bloquea mensajes entrantes: si vuelve a escribir, el bot
# responde normal (lo que muere es nuestra automatización saliente).
_OPTOUT_FLAG_PREFIX = "optout_wa:"
_OPTOUT_FLAG_TTL = 60 * 60 * 24 * 180  # 180 días

# Frases DURAS de opt-out. Criterio: tienen que ser inequívocas.
# "no me manden el link todavía" NO debe matchear → los verbos de envío
# exigen "más/nunca" inmediatamente después.
_OPTOUT_PATTERNS = [
    # "no me escriban más", "no me contacten nunca", "no me llames más"
    r"\bno\s+me\s+(escriba[sn]?|manden?|mandes|env[ií]e[sn]?|contacten?|contactes|llamen?|llames)\s+(m[aá]s|nunca)\b",
    # "no me molesten" / "no molesten más" — inequívoco incluso sin "más"
    r"\bno\s+(me\s+)?molesten?\b",
    # "dejen de escribirme/mandarme/insistir"
    r"\bdej[ae]n?\s+de\s+(escribir|mandar|enviar|molestar|contactar|insistir|joder)",
    # "no quiero recibir más", "no quiero saber más/nada"
    r"\bno\s+quiero\s+(recibir|saber)\s+(m[aá]s|nada)\b",
    # "no quiero más info/mensajes/correos"
    r"\bno\s+quiero\s+m[aá]s\s+(info|informaci[oó]n|mensajes?|correos?|mails?|publicidad|promos?|promociones)\b",
    # "no quiero que me escriban/contacten/llamen"
    r"\bno\s+quiero\s+que\s+me\s+(escriban|contacten|llamen|molesten|manden)\b",
    # "borrame/eliminame" (solos ya son claros), "sacame/quitame de la lista/base"
    r"\b(b[oó]rr[ae]n?me|elim[ií]n[ae]n?me)\b",
    r"\b(s[aá]c[ae]me|s[aá]quenme|qu[ií]t[ae]me|qu[ií]tenme)\s+de\s+(la\s+|tu\s+|su\s+)?(lista|base|contactos|grupo)\b",
    # "basta de mensajes/spam"
    r"\bbasta\s+de\s+(mensajes|escribirme|mandarme|spam|insistir)\b",
    r"\bno\s+insistan?\s+m[aá]s\b|\bno\s+insistan\b",
    # mensaje que es SOLO "stop" o "baja" (estilo unsubscribe)
    r"^\s*(stop|baja)\s*[.!]*\s*$",
]
_OPTOUT_RE = [re.compile(p, re.IGNORECASE) for p in _OPTOUT_PATTERNS]

# Respuesta fija del bot ante opt-out — no pasa por el LLM.
OPTOUT_REPLY = (
    "Listo, no te vamos a escribir más. Gracias por avisarnos 🙏 "
    "Si más adelante querés retomar la consulta, escribinos por acá y con gusto te ayudamos."
)


def es_optout_explicito(texto: str) -> bool:
    """True si el texto contiene un pedido inequívoco de no ser contactado."""
    t = (texto or "").strip()
    if not t:
        return False
    return any(rx.search(t) for rx in _OPTOUT_RE)


async def _flag_ya_marcado(phone: str) -> bool:
    if not phone:
        return False
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        return bool(await store._redis.get(f"{_OPTOUT_FLAG_PREFIX}{phone}"))
    except Exception:
        return False


async def _flag_marcar(phone: str, lead_id: str) -> None:
    if not phone:
        return
    try:
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        await store._redis.set(
            f"{_OPTOUT_FLAG_PREFIX}{phone}", lead_id or "1", ex=_OPTOUT_FLAG_TTL
        )
    except Exception as e:
        logger.debug("optout_flag_set_failed", phone=phone, error=str(e))


async def marcar_no_habilitado(lead_id: str | None, phone: str | None = None) -> str | None:
    """
    Pasa el lead a Estado "No habilitado" en Zoho. Si no hay lead_id, intenta
    resolverlo por teléfono. Devuelve el lead_id afectado, o None si no se
    pudo (sin lead conocido o error de Zoho — nunca levanta excepción).
    """
    from integrations.zoho.leads import ZohoLeads

    phone = (phone or "").strip()
    lid = (lead_id or "").strip()
    try:
        zl = ZohoLeads()
        if not lid and phone:
            found = await zl.search_by_phone(phone)
            if found:
                lid = str(found.get("id") or "")
        if not lid:
            logger.warning("optout_sin_lead", phone=phone)
            return None

        try:
            await zl.update(lid, {"Lead_Status": OPTOUT_STATUS_DISPLAY})
        except Exception:
            # Picklist estándar renombrado: si Zoho rechazó el display value,
            # reintentar con el actual value del picklist.
            await zl.update(lid, {"Lead_Status": OPTOUT_STATUS_ACTUAL})

        await _flag_marcar(phone, lid)
        logger.info("optout_lead_marcado", lead_id=lid, phone=phone)
        return lid
    except Exception as e:
        logger.error("optout_update_failed", lead_id=lid, phone=phone, error=str(e))
        return None


async def procesar_optout_whatsapp(lead_id: str | None, phone: str, texto: str) -> str | None:
    """
    Punto de entrada del webhook: si `texto` es un opt-out explícito, marca el
    lead y devuelve la respuesta fija para el usuario. Si no, devuelve None
    (el flujo sigue normal hacia el agente).
    """
    if not es_optout_explicito(texto):
        return None

    ya = await _flag_ya_marcado(phone)
    if ya:
        logger.info("optout_repetido", phone=phone)
        return OPTOUT_REPLY

    marcado = await marcar_no_habilitado(lead_id, phone)
    logger.info(
        "optout_whatsapp",
        phone=phone,
        lead_id=marcado or lead_id or "",
        resuelto=bool(marcado),
        msg=texto[:120],
    )
    return OPTOUT_REPLY
