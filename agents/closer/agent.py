"""
Agente Sales Closer — LangGraph ReAct agent especializado en retomar leads y cerrar ventas.

Se activa cuando:
1. Un lead responde a un follow-up HSM (retargeting)
2. Un lead inactivo vuelve a escribir después de X días
3. El sistema detecta un lead caliente/tibio sin cierre

Reutiliza las herramientas de ventas + check_lead_history.
"""

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.closer.prompts import build_closer_prompt
from agents.closer.tools import CLOSER_TOOLS
from config.settings import get_settings


def build_closer_agent(
    country: str = "AR",
    channel: str = "whatsapp",
    lead_context: str = "",
):
    """
    Construye el agente closer con prompt personalizado según el contexto del lead.

    Args:
        country: Código de país
        channel: whatsapp | widget
        lead_context: Texto con datos del lead (cursos previos, label, historial)
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.4,  # Un poco más creativo que ventas para adaptarse
    )

    system_prompt = build_closer_prompt(
        country=country,
        channel=channel,
        lead_context=lead_context,
    )

    agent = create_react_agent(
        model=llm,
        tools=CLOSER_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )
    return agent
