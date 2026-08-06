"""
Tests del guard de identidad.

Contexto: la tool `buscar_ficha_alumno` de cobranzas devolvía la ficha
financiera completa a cualquiera que escribiera un email en el chat. Bastaba
abrir el widget en incógnito, elegir "Soporte Cobros" y tipear el mail de otra
persona para ver su nombre, importe de contrato, cuotas, deuda y último pago.

Regla: solo identidades verificadas POR EL CANAL (sesión en msklatam.com o
número de WhatsApp) acceden a datos de cuenta.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from utils.agent_context import current_identity_source, identidad_verificada
from utils.identity_guard import MENSAJE_REQUIERE_LOGIN, bloquear_si_no_verificado

FICHA = {
    "cobranzaId": "abc",
    "alumno": "Alumno Ajeno",
    "email": "victima@ejemplo.com",
    "pais": "Argentina",
    "moneda": "ARS",
    "importeContrato": 212881.0,
    "importePagado": 100000.0,
    "saldoTotal": 112881.0,
    "saldoPendiente": 17740.0,
    "valorCuota": 17740.0,
    "cuotasTotales": 12,
    "cuotasPagas": 5,
    "cuotasPendientes": 7,
    "cuotasVencidas": 1,
    "diasAtraso": 10,
}


def _contacts_mock(contacto: dict | None = None) -> AsyncMock:
    m = AsyncMock()
    m.search_by_email_with_cursadas.return_value = contacto or {}
    m.search_by_email.return_value = contacto or None
    return m


def _so_mock(ordenes: list | None = None) -> AsyncMock:
    m = AsyncMock()
    m.list_by_contact.return_value = ordenes or []
    return m


@pytest.fixture(autouse=True)
def _reset_identidad():
    token = current_identity_source.set("none")
    yield
    current_identity_source.reset(token)


# ── El guard en sí ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("fuente", ["session", "phone"])
async def test_identidades_verificadas_pasan(fuente):
    current_identity_source.set(fuente)
    assert identidad_verificada() is True
    assert await bloquear_si_no_verificado("x") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fuente", ["typed", "none", "", "cualquier_cosa"])
async def test_identidades_no_verificadas_se_bloquean(fuente):
    current_identity_source.set(fuente)
    assert identidad_verificada() is False
    assert await bloquear_si_no_verificado("x") == MENSAJE_REQUIERE_LOGIN


@pytest.mark.asyncio
async def test_default_es_bloquear():
    """Sin canal que setee nada, no se dan datos de cuenta."""
    assert await bloquear_si_no_verificado("x") == MENSAJE_REQUIERE_LOGIN


def test_el_mensaje_no_revela_si_el_email_existe():
    """Confirmar o negar la existencia de una cuenta ya es filtrar información."""
    assert "no encontré" in MENSAJE_REQUIERE_LOGIN.lower()  # aparece como PROHIBICIÓN
    assert "NO digas «no encontré»" in MENSAJE_REQUIERE_LOGIN
    assert "msklatam.com" in MENSAJE_REQUIERE_LOGIN


# ── La tool de cobranzas: el agujero que se cierra ─────────────────────────


@pytest.mark.asyncio
async def test_cobranzas_no_entrega_ficha_a_email_tipeado():
    """El ataque real: anónimo tipea el mail de un tercero en el widget."""
    from agents.collections.tools import buscar_ficha_alumno

    current_identity_source.set("typed")
    zoho = AsyncMock()
    with (
        patch("agents.collections.tools.ZohoAreaCobranzas", return_value=zoho),
        patch("integrations.zoho.contacts.ZohoContacts", return_value=_contacts_mock()),
        patch("integrations.zoho.sales_orders.ZohoSalesOrders", return_value=_so_mock()),
    ):
        out = await buscar_ficha_alumno.ainvoke({"email": "victima@ejemplo.com"})

    assert out == MENSAJE_REQUIERE_LOGIN
    # Ni siquiera se consulta Zoho: no filtramos por timing ni por logs.
    zoho.search_by_email.assert_not_called()
    for dato in ("Alumno Ajeno", "212.881", "112.881", "17.740"):
        assert dato not in out


@pytest.mark.asyncio
async def test_cobranzas_entrega_ficha_con_sesion_verificada():
    from agents.collections.tools import buscar_ficha_alumno

    current_identity_source.set("session")
    zoho = AsyncMock()
    zoho.search_by_email.return_value = FICHA
    with (
        patch("agents.collections.tools.ZohoAreaCobranzas", return_value=zoho),
        patch("integrations.zoho.contacts.ZohoContacts", return_value=_contacts_mock()),
        patch("integrations.zoho.sales_orders.ZohoSalesOrders", return_value=_so_mock()),
    ):
        out = await buscar_ficha_alumno.ainvoke({"email": "victima@ejemplo.com"})

    assert "FICHA_ALUMNO_ENCONTRADA" in out
    zoho.search_by_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_whatsapp_puede_consultar_su_cuenta():
    """Regresión: por WhatsApp el ContextVar quedaba en su default y la tool
    rechazaba SIEMPRE, aunque el número lo verifique el canal."""
    from agents.collections.tools import buscar_ficha_alumno

    current_identity_source.set("phone")
    zoho = AsyncMock()
    zoho.search_by_email.return_value = FICHA
    with (
        patch("agents.collections.tools.ZohoAreaCobranzas", return_value=zoho),
        patch("integrations.zoho.contacts.ZohoContacts", return_value=_contacts_mock()),
        patch("integrations.zoho.sales_orders.ZohoSalesOrders", return_value=_so_mock()),
    ):
        out = await buscar_ficha_alumno.ainvoke({"email": "alumno@ejemplo.com"})

    assert out != MENSAJE_REQUIERE_LOGIN
    assert "FICHA_ALUMNO_ENCONTRADA" in out


# ── La tool de post-venta ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_venta_no_entrega_cursos_a_email_tipeado():
    from agents.post_sales.tools import get_student_info

    current_identity_source.set("typed")
    contacts = AsyncMock()
    with patch("agents.post_sales.tools.ZohoContacts", return_value=contacts):
        out = await get_student_info.ainvoke({"email": "victima@ejemplo.com"})

    assert out == MENSAJE_REQUIERE_LOGIN
    contacts.search_by_email.assert_not_called()


@pytest.mark.asyncio
async def test_las_dos_tools_usan_el_mismo_guard():
    """No puede haber una puerta con llave y otra abierta."""
    from agents.collections.tools import buscar_ficha_alumno
    from agents.post_sales.tools import get_student_info

    current_identity_source.set("none")
    with (
        patch("agents.collections.tools.ZohoAreaCobranzas", return_value=AsyncMock()),
        patch("integrations.zoho.contacts.ZohoContacts", return_value=_contacts_mock()),
        patch("agents.post_sales.tools.ZohoContacts", return_value=AsyncMock()),
    ):
        a = await buscar_ficha_alumno.ainvoke({"email": "x@y.com"})
        b = await get_student_info.ainvoke({"email": "x@y.com"})
    assert a == b == MENSAJE_REQUIERE_LOGIN
