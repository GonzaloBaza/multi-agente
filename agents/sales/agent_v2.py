"""
Agente de Ventas v2 — mismo flujo que `agent.py` pero con:
  - prompt PODADO + reforzado (`build_sales_prompt_v2`)
  - modelo configurable por env `SALES_V2_MODEL` (default gpt-4.1)

Reúsa TODA la infra de armado de `agent.py` (priority header, bloques CTWA/HSM,
catálogo, brief del curso, master warning, tools) importándola → no duplica lógica
y las reglas de categoría V (CTWA/HSM) se preservan automáticamente.

Aislado de producción: el endpoint v1 y `build_sales_agent` no se tocan.
"""

import os

import structlog
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Reúso de helpers de v1 (sin modificarlos).
from agents.sales.agent import (
    SALES_TOOLS,
    _build_ctwa_context_block,
    _build_hsm_reply_context_block,
    _build_master_page_warning,
    _build_priority_profile_header,
    _format_course_context,
    _format_user_profile,
)
from agents.sales.prompts_v2 import build_sales_prompt_v2
from config.constants import is_master_slug as _is_master_slug
from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Modelo del agente v2. Configurable por env para A/B sin redeploy de código.
SALES_V2_MODEL_DEFAULT = "gpt-4.1"


def _v2_model() -> str:
    return os.environ.get("SALES_V2_MODEL", SALES_V2_MODEL_DEFAULT).strip() or SALES_V2_MODEL_DEFAULT


async def build_sales_agent_v2(
    country: str = "AR",
    channel: str = "whatsapp",
    page_slug: str = "",
    user_profile: dict | None = None,
    campaign_config: dict | None = None,
):
    """Igual que `build_sales_agent` pero con prompt v2 + modelo configurable.

    Mantiene la MISMA firma para que el endpoint v2 lo invoque idéntico al v1.
    """
    settings = get_settings()
    model_name = _v2_model()
    llm = ChatOpenAI(
        model=model_name,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )

    # --- STEP 1: resolver curso (idéntico a v1) ---
    course = None
    _master_page = bool(page_slug and _is_master_slug(page_slug))
    if page_slug and not _master_page:
        try:
            from integrations import courses_cache

            course = await courses_cache.get_course(country.lower(), page_slug)
            if not (course and course.get("brief_md")):
                logger.info("sales_v2_no_brief_for_slug", country=country, slug=page_slug)
                course = None
        except Exception as e:
            logger.warning("sales_v2_brief_load_failed", error=str(e), slug=page_slug)
            course = None

    # --- STEP 2: priority header con perfil (reusado de v1) ---
    priority_header = _build_priority_profile_header(user_profile=user_profile, course=course)

    # --- STEP 3: prompt base PODADO v2 ---
    base_prompt = build_sales_prompt_v2(
        country=country,
        channel=channel,
        campaign_config=campaign_config,
        is_ctwa=bool((user_profile or {}).get("ctwa")),
    )
    system_prompt = (priority_header + base_prompt) if priority_header else base_prompt

    # --- STEP 3b: contexto de campaña CTWA/HSM (reusado de v1 — categoría V) ---
    up = user_profile or {}
    if up.get("ctwa"):
        system_prompt = _build_ctwa_context_block(up) + "\n\n---\n\n" + system_prompt
    elif up.get("curso_nombre") and not up.get("profession") and not up.get("specialty"):
        hsm_ctx = _build_hsm_reply_context_block(up)
        if hsm_ctx:
            system_prompt = hsm_ctx + "\n\n---\n\n" + system_prompt

    if _master_page:
        system_prompt = _build_master_page_warning(page_slug) + system_prompt

    # --- STEP 4: catálogo compacto del país (idéntico a v1) ---
    try:
        from memory import postgres_store

        catalog = await postgres_store.get_catalog_compact(country)
        if catalog:
            system_prompt += f"\n\n---\n\n{catalog}\n\n"
            system_prompt += (
                "👆 El catálogo completo del país está envuelto en "
                f"`<catalogo_{country.upper()}>...</catalogo_{country.upper()}>`. "
                "Ya lo tenés — NO busques. Para vender otro curso usá `get_course_brief(slug)`. "
                "No mezcles datos entre filas: cada fila es un curso independiente.\n"
            )
    except Exception as e:
        logger.warning("sales_v2_catalog_inject_failed", error=str(e))

    # --- STEP 5: brief del curso activo (reusado de v1) ---
    if course:
        system_prompt += _format_course_context(
            course, user_profile, has_priority_header=bool(priority_header)
        )

    # --- STEP 6: fallback perfil suelto (reusado de v1) ---
    if user_profile and not page_slug and not priority_header:
        prof_ctx = _format_user_profile(user_profile)
        if prof_ctx:
            system_prompt += prof_ctx

    logger.info("sales_v2_agent_built", model=model_name, country=country, channel=channel)

    agent = create_react_agent(
        model=llm,
        tools=SALES_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )
    return agent
