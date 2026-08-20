"""
Post-procesador de atribución: agrega `idlead={lead_id}` a las URLs de
msklatam.com que el agente emite en sus respuestas.

El esquema de atribución (checkout → Contacts.IDLEAD → lead convertido)
depende de que TODO link al sitio viaje con el id del lead. Los links que
vienen de los campos del lead (Link_web, Link_checkout, Link_bot_*) ya lo
traen desde Zoho; este módulo cubre los que el LLM compone solo — p.ej. el
patrón `https://msklatam.com/checkout/{slug}/?utm_source=bot` que enseñan
los prompts de ventas y closer.

Solo toca el host principal (msklatam.com / www.msklatam.com). Los
subdominios (ayuda., agentes., etc.) quedan intactos.
"""

from __future__ import annotations

import re

# URL del host principal; corta antes de espacios, comillas, cierre de
# markdown/paréntesis. La puntuación final de prosa se recorta aparte.
_MSK_URL = re.compile(
    r"https?://(?:www\.)?msklatam\.com(?:/[^\s<>\"'\)\]]*)?",
    re.IGNORECASE,
)
_TRAILING_PUNCT = ".,;:!?…"


def con_idlead(text: str, lead_id: str | None) -> str:
    """Devuelve `text` con `idlead={lead_id}` agregado a cada URL de
    msklatam.com que no lo tenga. Si no hay lead_id, no toca nada."""
    if not text or not lead_id:
        return text
    lid = str(lead_id).strip()
    if not lid:
        return text

    def _sub(m: re.Match) -> str:
        url = m.group(0)
        # No arrastrar la puntuación final de la frase adentro de la URL.
        stripped = url.rstrip(_TRAILING_PUNCT)
        tail = url[len(stripped) :]
        if "idlead=" in stripped.lower():
            return url
        base, _, frag = stripped.partition("#")
        sep = "&" if "?" in base else "?"
        nuevo = f"{base}{sep}idlead={lid}"
        if frag:
            nuevo += "#" + frag
        return nuevo + tail

    return _MSK_URL.sub(_sub, text)
