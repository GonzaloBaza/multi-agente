"""
Tests del nodo que atiende el intent `post_venta`.

El agente de post-venta se eliminó: sus capacidades viven en el agente de
Atención al Alumno (cobranzas). Lo que NO se puede borrar es el identificador
`post_venta`, porque es el valor con el que están guardadas ~900 conversaciones
reales — ver el test del final.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.router import run_student_support_node

STATE = {"messages": [], "channel": "widget", "country": "AR", "email": "", "phone": ""}


@pytest.mark.asyncio
async def test_el_intent_post_venta_lo_atiende_el_agente_unificado():
    agente = AsyncMock()
    agente.ainvoke.return_value = {"messages": []}
    with (
        patch("agents.router.build_collections_agent", return_value=agente) as build,
        patch("agents.router._cargar_ficha", AsyncMock(return_value=None)),
    ):
        await run_student_support_node(dict(STATE))
    build.assert_called_once()
    assert build.call_args.kwargs["country"] == "AR"


@pytest.mark.asyncio
async def test_el_pais_del_canal_llega_al_agente():
    """Sin esto el horario de atención se evalúa siempre en huso de Buenos Aires."""
    agente = AsyncMock()
    agente.ainvoke.return_value = {"messages": []}
    with (
        patch("agents.router.build_collections_agent", return_value=agente) as build,
        patch("agents.router._cargar_ficha", AsyncMock(return_value=None)),
    ):
        await run_student_support_node(dict(STATE, country="MX"))
    assert build.call_args.kwargs["country"] == "MX"


@pytest.mark.asyncio
async def test_funciona_igual_por_whatsapp():
    agente = AsyncMock()
    agente.ainvoke.return_value = {"messages": []}
    with (
        patch("agents.router.build_collections_agent", return_value=agente) as build,
        patch("agents.router._cargar_ficha", AsyncMock(return_value=None)),
    ):
        await run_student_support_node(dict(STATE, channel="whatsapp"))
    build.assert_called_once()


def test_el_nodo_sigue_llamandose_post_venta():
    """Renombrarlo rompería el clasificador, los edges y las colas guardadas."""
    import inspect

    from agents import router

    src = inspect.getsource(router.build_supervisor)
    assert 'add_node("post_venta", run_student_support_node)' in src


def test_el_enum_post_sales_NO_se_puede_borrar():
    """~900 conversaciones en producción tienen current_agent='post_venta'.

    `postgres_store` hace `AgentType(conv_row["current_agent"])` al leerlas: sin
    este miembro tiran ValueError, el error se traga como warning y se crea una
    conversación NUEVA. El alumno pierde todo su historial, sin error visible.
    """
    from config.constants import AgentType

    assert AgentType.POST_SALES.value == "post_venta"


def test_el_agente_viejo_ya_no_existe():
    """No queremos código muerto: post_sales se eliminó por completo."""
    import importlib

    for mod in ("agents.post_sales", "agents.post_sales.agent", "agents.post_sales.prompts"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


# ── Bugs latentes de mapeo (claves en inglés vs valores en español) ────────


def test_el_hint_de_continuidad_se_activa():
    """Los valores del enum están en español. Un dict con claves en inglés
    nunca matcheaba, así que el clasificador perdía el contexto de qué agente
    venía atendiendo y saltaba de agente a mitad de conversación."""
    import inspect

    from agents import router

    src = inspect.getsource(router.classify_intent)
    assert '{"sales": "ventas"' not in src
    assert "agent_label = current if current in" in src


def test_la_cola_de_handoff_usa_los_valores_del_enum():
    """Con claves en inglés el fallback no matcheaba nunca y las
    conversaciones de cobranzas y post-venta se auto-asignaban a ventas_XX."""
    import inspect

    from channels import widget

    src = inspect.getsource(widget)
    assert '"post_sales": "post_venta",\n                    "closer"' not in src
    assert "_AT.COLLECTIONS.value: \"cobranzas\"" in src
