from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.collections.prompts import build_collections_prompt
from agents.collections.tools import (
    buscar_ficha_alumno,
    buscar_suscripcion_rebill,
    generar_insta_link_rebill,
    send_nps_survey,
)
from config.settings import get_settings

COLLECTIONS_TOOLS = [
    buscar_ficha_alumno,
    buscar_suscripcion_rebill,
    generar_insta_link_rebill,
    send_nps_survey,
]


def build_collections_agent(ficha: dict | None = None, country: str | None = None):
    """
    Construye el agente de Atención al Alumno (cobranzas + cursada + soporte).

    Args:
        ficha: datos del alumno de Area_de_cobranzas (si ya se conocen).
        country: ISO-2 del país. Solo se usa para resolver el horario de
            atención en la hora local. Si no viene, se cae al país de la ficha,
            y si tampoco hay, a Buenos Aires. Importa pasarlo cuando NO hay
            ficha (consultas de campus o certificados de alumnos sin registro
            de cobranzas): sin esto, un alumno de México a las 17:00 recibiría
            "estamos fuera del horario de atención".
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
    )
    system_prompt = build_collections_prompt(ficha, country=country)
    agent = create_react_agent(
        model=llm,
        tools=COLLECTIONS_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )
    return agent
