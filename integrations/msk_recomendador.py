"""
Recomendador de cursos para leads de Televenta.

Reemplaza al Assistant de OpenAI (`asst_cXWTx3WREqeldCiY3RJYIqcd`) que quedó
muerto con el sunset de la Assistants API el 2026-08-26. Aquel dependía de un
vector store con JSON del catálogo subidos a mano — solo AR/MX/CO y sin
actualizar desde abril. Acá el catálogo sale de `public.courses`, que se
sincroniza del CMS todas las noches a las 3:30 para los 17 países habilitados.

Diferencia clave con el assistant viejo: el LLM NO devuelve datos del curso,
devuelve slugs. Título, precio y product_id salen siempre de la DB. Un slug que
el modelo invente no matchea y se descarta — no hay forma de que un curso
inexistente llegue al CRM.

El filtro por país, la exclusión de Másters y el descarte de cursos ya hechos
pasan en SQL/Python, no en el prompt: una regla en texto que el modelo puede
ignorar no es una regla.
"""

from __future__ import annotations

import json
import unicodedata

import structlog
from openai import AsyncOpenAI

from config.settings import get_settings
from integrations import msk_courses
from memory import postgres_store

logger = structlog.get_logger(__name__)

# Cuántos cursos pide el negocio. El flujo de Televenta siempre mostró 4.
N_RECOMENDACIONES = 4

# País no reconocido → catálogo de Colombia. Es el catch-all que ya usaba el
# prompt del assistant ("co" → Colombia y otros países no listados).
PAIS_FALLBACK = "co"

# Techo de cursos que entran al prompt. ~40 tokens por fila; el país más grande
# hoy es Chile con 166, así que 400 deja margen de sobra sin reventar contexto.
MAX_CANDIDATOS = 400


SYSTEM_PROMPT = """Eres un experto recomendador de cursos médicos para MSK Latam.

Te paso el perfil de un profesional de la salud y el catálogo de cursos activos
de su país. Tenés que elegir los 4 cursos que mejor le calcen.

REGLAS

1. Elegí EXACTAMENTE 4 cursos del catálogo.
2. Devolvé el `slug` tal cual aparece en el catálogo. No inventes slugs, no los
   edites, no los traduzcas. Un slug que no esté en el catálogo se descarta.
3. Priorizá, en este orden:
   a. Coincidencia con la profesión y la especialidad del usuario.
   b. Coincidencia con sus temas de interés.
   c. Cursos del cedente AMIR.
   d. Mayor duración en horas.
4. Si no hay 4 que coincidan con profesión y especialidad, completá con cursos
   de temas afines. Siempre devolvé 4.
5. Por cada curso escribí un `motivo` de una línea (máximo 140 caracteres)
   anclado al perfil concreto de esta persona, no genérico. Nada de "es un
   curso muy completo": decí por qué le sirve A ESTA PERSONA.

TONO DEL MOTIVO
Español neutro profesional. Prohibido el voseo (vos, tenés, podés, sos). Sin
emojis ni signos de admiración.

FORMATO
Devolvé solo este JSON, nada antes ni después:

{
  "cursos_recomendados": [
    {"slug": "<slug exacto del catálogo>", "motivo": "<una línea>"}
  ]
}"""


def _normalizar(txt: str | None) -> str:
    """Minúsculas sin acentos ni espacios de más, para comparar títulos y países."""
    if not txt:
        return ""
    sin_acentos = unicodedata.normalize("NFKD", str(txt))
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


def codigo_pais(pais: str | None) -> str:
    """
    "Argentina" → "ar". Acepta también el ISO directo ("ar", "AR").

    País desconocido o vacío → PAIS_FALLBACK. El recomendador nunca debe
    quedarse sin catálogo: es preferible recomendar con la lista de Colombia
    que devolver vacío y dejar al televendedor sin nada que ofrecer.
    """
    if not pais:
        return PAIS_FALLBACK
    p = _normalizar(pais)
    if p in msk_courses.LANG_BY_COUNTRY:
        return p
    for code, label in msk_courses.COUNTRY_LABEL.items():
        if _normalizar(label) == p:
            return code
    logger.warning("recomendador_pais_desconocido", pais=pais, fallback=PAIS_FALLBACK)
    return PAIS_FALLBACK


def _partir_cursos_hechos(cursos_realizados: str | list[str] | None) -> list[str]:
    """El webhook manda los cursos separados por ';' en un solo string."""
    if not cursos_realizados:
        return []
    if isinstance(cursos_realizados, str):
        crudos = cursos_realizados.split(";")
    else:
        crudos = list(cursos_realizados)
    return [c.strip() for c in crudos if c and c.strip()]


def _celda(valor: object) -> str:
    """Escapa un valor para meterlo en una celda de la tabla markdown."""
    return str(valor or "").replace("|", "/").replace("\n", " ").strip()


def _catalogo_para_prompt(candidatos: list[dict]) -> str:
    """Tabla markdown compacta. Mismo envoltorio XML que `get_catalog_compact`."""
    filas = [
        "| Slug | Título | Categoría | Cedente | Horas |",
        "|---|---|---|---|---|",
    ]
    for c in candidatos:
        filas.append(
            f"| {c['slug']} | {_celda(c['title'])} | {_celda(c['categoria'])} "
            f"| {_celda(c['cedente'])} | {c.get('duration_hours') or '-'} |"
        )
    return "<catalogo>\n" + "\n".join(filas) + "\n</catalogo>"


def _perfil_para_prompt(
    *,
    pais: str,
    profesion: str,
    especialidad: str,
    temas_interes: str,
    cursos_hechos: list[str],
) -> str:
    lineas = [
        f"País: {pais or '-'}",
        f"Profesión: {profesion or '-'}",
        f"Especialidad: {especialidad or '-'}",
        f"Temas de interés: {temas_interes or '-'}",
    ]
    if cursos_hechos:
        lineas.append("Cursos que YA hizo (no los recomiendes): " + "; ".join(cursos_hechos))
    else:
        lineas.append("Cursos que ya hizo: ninguno registrado")
    return "\n".join(lineas)


async def recomendar_cursos(
    *,
    pais: str | None,
    profesion: str = "",
    especialidad: str = "",
    temas_interes: str = "",
    cursos_realizados: str | list[str] | None = None,
    n: int = N_RECOMENDACIONES,
) -> dict:
    """
    Devuelve `n` cursos recomendados para el perfil, con datos traídos de la DB.

    Nunca levanta por culpa del LLM: si la llamada falla o devuelve basura, cae
    al ranking por defecto del catálogo (más horas primero). Un lead con
    recomendaciones mediocres es mucho mejor que un lead sin crear.
    """
    country = codigo_pais(pais)
    cursos_hechos = _partir_cursos_hechos(cursos_realizados)
    hechos_norm = {_normalizar(t) for t in cursos_hechos}

    candidatos = await postgres_store.list_courses_for_recommender(
        country, limit=MAX_CANDIDATOS
    )
    # Descarte de lo que ya cursó. En SQL no se puede: el título que manda
    # Analytics no siempre coincide carácter a carácter con el del CMS.
    candidatos = [c for c in candidatos if _normalizar(c["title"]) not in hechos_norm]

    if not candidatos:
        logger.warning("recomendador_sin_catalogo", country=country, pais=pais)
        return {"country": country, "cursos": [], "fallback": True}

    por_slug = {c["slug"]: c for c in candidatos}
    elegidos: list[dict] = []

    try:
        elegidos = await _elegir_con_llm(
            candidatos=candidatos,
            por_slug=por_slug,
            pais=pais or msk_courses.COUNTRY_LABEL.get(country, country),
            profesion=profesion,
            especialidad=especialidad,
            temas_interes=temas_interes,
            cursos_hechos=cursos_hechos,
            n=n,
        )
    except Exception as e:
        logger.exception("recomendador_llm_fallo", country=country, error=str(e))

    fallback = len(elegidos) < n
    # Completar con el ranking por defecto (la query ya viene ordenada por horas).
    if fallback:
        ya = {c["slug"] for c in elegidos}
        for c in candidatos:
            if len(elegidos) >= n:
                break
            if c["slug"] in ya:
                continue
            elegidos.append({**c, "motivo": ""})

    return {
        "country": country,
        "cursos": elegidos[:n],
        "fallback": fallback,
        "candidatos_evaluados": len(candidatos),
    }


async def _elegir_con_llm(
    *,
    candidatos: list[dict],
    por_slug: dict[str, dict],
    pais: str,
    profesion: str,
    especialidad: str,
    temas_interes: str,
    cursos_hechos: list[str],
    n: int,
) -> list[dict]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_msg = (
        _perfil_para_prompt(
            pais=pais,
            profesion=profesion,
            especialidad=especialidad,
            temas_interes=temas_interes,
            cursos_hechos=cursos_hechos,
        )
        + "\n\n"
        + _catalogo_para_prompt(candidatos)
        + f"\n\nElegí exactamente {n} cursos."
    )

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.3,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    data = json.loads(resp.choices[0].message.content)

    elegidos: list[dict] = []
    descartados: list[str] = []
    for item in data.get("cursos_recomendados") or []:
        slug = (item or {}).get("slug", "")
        curso = por_slug.get(slug)
        if not curso:
            # Slug inventado o de otro país. Se descarta en silencio; el
            # fallback rellena el hueco.
            descartados.append(slug)
            continue
        if any(e["slug"] == slug for e in elegidos):
            continue
        elegidos.append({**curso, "motivo": (item.get("motivo") or "").strip()})
        if len(elegidos) >= n:
            break

    if descartados:
        logger.warning("recomendador_slugs_invalidos", slugs=descartados, pais=pais)

    return elegidos
