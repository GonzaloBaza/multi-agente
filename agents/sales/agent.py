"""
Agente de Ventas — LangGraph ReAct agent con RAG sobre cursos médicos.
Capacidades: buscar cursos, responder dudas, generar links de pago, registrar en Zoho.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from config.settings import get_settings
from agents.sales.tools import (
    search_courses,
    get_course_details,
    create_payment_link,
    create_or_update_lead,
    create_sales_order,
)
from agents.sales.prompts import build_sales_prompt

SALES_TOOLS = [
    search_courses,
    get_course_details,
    create_payment_link,
    create_or_update_lead,
    create_sales_order,
]


def build_sales_agent(country: str = "AR", channel: str = "whatsapp"):
    """
    Construye el agente de ventas con el sistema prompt y herramientas.
    Retorna un agente compilado (LangGraph CompiledGraph).
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )

    system_prompt = build_sales_prompt(country=country, channel=channel)

    agent = create_react_agent(
        model=llm,
        tools=SALES_TOOLS,
        prompt=SystemMessage(content=system_prompt),
    )
    return agent
