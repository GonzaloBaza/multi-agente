from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from config.settings import get_settings
from agents.collections.tools import (
    buscar_alumno_mail_adc,
    buscar_suscripcion_rebill,
    generar_insta_link_rebill,
)
from agents.collections.prompts import build_collections_prompt

COLLECTIONS_TOOLS = [
    buscar_alumno_mail_adc,
    buscar_suscripcion_rebill,
    generar_insta_link_rebill,
]


def build_collections_agent(ficha: dict | None = None):
    """
    Construye el agente de cobranzas.
    ficha: datos del alumno de Area_de_cobranzas (si ya se conocen).
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
    )
    system_prompt = build_collections_prompt(ficha)
    agent = create_react_agent(
        model=llm,
        tools=COLLECTIONS_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )
    return agent
