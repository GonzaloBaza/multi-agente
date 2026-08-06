"""
Tests del dispatch del intent `post_venta` detrás del flag de unificación.

La garantía que importa: con el flag vacío (default) el comportamiento es
IDÉNTICO al de antes de la fusión. Eso es lo que permite deployar el código sin
cambiar nada en producción y prender la unificación después, canal por canal.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.router import _agente_unificado_habilitado, run_student_support_node


def _flag(valor: str):
    """Patchea el CSV de canales habilitados en settings."""
    s = AsyncMock()
    s.unified_student_agent_channels = valor
    return patch("config.settings.get_settings", return_value=s)


STATE = {"messages": [], "channel": "widget", "country": "AR", "email": "", "phone": ""}


# ── El flag ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "flag,canal,esperado",
    [
        ("", "widget", False),  # default: apagado en todos lados
        ("", "whatsapp", False),
        ("widget", "widget", True),
        ("widget", "whatsapp", False),  # canal por canal
        ("widget,whatsapp", "whatsapp", True),
        ("  widget , whatsapp  ", "whatsapp", True),  # tolera espacios
        ("widget", "WIDGET", True),  # case-insensitive
        ("widget", "", False),
    ],
)
def test_flag_por_canal(flag, canal, esperado):
    with _flag(flag):
        assert _agente_unificado_habilitado(canal) is esperado


def test_flag_ilegible_no_rompe_y_queda_apagado():
    """Si settings explota, se cae al comportamiento viejo, no al nuevo."""
    with patch("config.settings.get_settings", side_effect=RuntimeError("boom")):
        assert _agente_unificado_habilitado("widget") is False


# ── El dispatch ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_con_flag_apagado_responde_el_agente_viejo():
    viejo = AsyncMock(return_value={"messages": [], "handoff_requested": False})
    with _flag(""), patch("agents.router.run_post_sales_node", viejo):
        await run_student_support_node(dict(STATE))
    viejo.assert_awaited_once()


@pytest.mark.asyncio
async def test_con_flag_prendido_responde_el_agente_unificado():
    viejo = AsyncMock()
    agente = AsyncMock()
    agente.ainvoke.return_value = {"messages": []}
    with (
        _flag("widget"),
        patch("agents.router.run_post_sales_node", viejo),
        patch("agents.router.build_collections_agent", return_value=agente) as build,
        patch("agents.router._cargar_ficha", AsyncMock(return_value=None)),
    ):
        await run_student_support_node(dict(STATE))

    viejo.assert_not_called()
    build.assert_called_once()
    # El país tiene que viajar: sin esto el horario se evalúa siempre en AR.
    assert build.call_args.kwargs["country"] == "AR"


@pytest.mark.asyncio
async def test_el_pais_del_canal_llega_al_agente():
    agente = AsyncMock()
    agente.ainvoke.return_value = {"messages": []}
    with (
        _flag("widget"),
        patch("agents.router.build_collections_agent", return_value=agente) as build,
        patch("agents.router._cargar_ficha", AsyncMock(return_value=None)),
    ):
        await run_student_support_node(dict(STATE, country="MX"))
    assert build.call_args.kwargs["country"] == "MX"


@pytest.mark.asyncio
async def test_otro_canal_sigue_con_el_viejo():
    viejo = AsyncMock(return_value={"messages": [], "handoff_requested": False})
    with _flag("widget"), patch("agents.router.run_post_sales_node", viejo):
        await run_student_support_node(dict(STATE, channel="whatsapp"))
    viejo.assert_awaited_once()


# ── El grafo no cambia ─────────────────────────────────────────────────────


def test_el_nodo_sigue_llamandose_post_venta():
    """Renombrarlo rompería el clasificador, los edges y las colas guardadas."""
    import inspect

    from agents import router

    src = inspect.getsource(router.build_supervisor)
    assert 'add_node("post_venta", run_student_support_node)' in src


def test_el_enum_post_sales_sigue_existiendo():
    """Borrarlo haría perder el historial de conversaciones en silencio:
    ValidationError tragada → fallback a Postgres → ValueError tragada →
    get_or_create crea una conversación NUEVA."""
    from config.constants import AgentType

    assert AgentType.POST_SALES.value == "post_venta"
