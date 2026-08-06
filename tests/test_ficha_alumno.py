"""
Tests de `buscar_ficha_alumno`, la tool unificada de atención al alumno.

Reemplaza a `buscar_alumno_mail_adc` (solo financiero) y a `get_student_info`
(solo cursos). Tener las dos por separado era la causa del incidente original:
post-venta contestaba sobre el estado de pago viendo únicamente el `Status` de
la orden de venta, sin acceso a cuotas ni saldo.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from utils.agent_context import current_identity_source

FICHA_ADC = {
    "cobranzaId": "adc-1",
    "alumno": "Ana Gómez",
    "email": "ana@ejemplo.com",
    "pais": "Argentina",
    "moneda": "ARS",
    "importeContrato": 120000.0,
    "importePagado": 40000.0,
    "saldoTotal": 80000.0,
    "saldoPendiente": 0.0,
    "valorCuota": 10000.0,
    "cuotasTotales": 12,
    "cuotasPagas": 4,
    "cuotasPendientes": 8,
    "cuotasVencidas": 0,
    "diasAtraso": 0,
}

CONTACTO = {"id": "c-1", "First_Name": "Ana", "Last_Name": "Gómez", "LMS_User_ID": "ana.gomez"}
ORDENES = [{"Curso_Nombre": "Cardiología AMIR", "Status": "Contrato Efectivo", "LMS_Platform": "Tropos"}]


@pytest.fixture(autouse=True)
def _identidad_verificada():
    token = current_identity_source.set("session")
    yield
    current_identity_source.reset(token)


def _correr(adc=None, contacto=None, ordenes=None, adc_error=None, contacto_error=None):
    from agents.collections.tools import buscar_ficha_alumno

    z = AsyncMock()
    if adc_error:
        z.search_by_email.side_effect = adc_error
    else:
        z.search_by_email.return_value = adc or {}

    c = AsyncMock()
    if contacto_error:
        c.search_by_email_with_cursadas.side_effect = contacto_error
    else:
        c.search_by_email_with_cursadas.return_value = contacto or {}

    so = AsyncMock()
    so.list_by_contact.return_value = ordenes or []

    async def _go():
        with (
            patch("agents.collections.tools.ZohoAreaCobranzas", return_value=z),
            patch("integrations.zoho.contacts.ZohoContacts", return_value=c),
            patch("integrations.zoho.sales_orders.ZohoSalesOrders", return_value=so),
        ):
            return await buscar_ficha_alumno.ainvoke({"email": "ana@ejemplo.com"})

    return _go()


@pytest.mark.asyncio
async def test_trae_la_foto_completa_en_una_sola_llamada():
    """Financiero + académico + cursos juntos: nadie responde con media foto."""
    out = await _correr(adc=FICHA_ADC, contacto=CONTACTO, ordenes=ORDENES)
    assert "FICHA_ALUMNO_ENCONTRADA" in out  # financiero
    assert "ESTADO DE CUENTA" in out  # veredicto
    assert "Ana Gómez" in out  # académico
    assert "Cardiología AMIR" in out  # cursos
    assert "ana.gomez" in out  # acceso al campus


@pytest.mark.asyncio
async def test_el_status_de_la_orden_va_desambiguado():
    """`Status` decía 'Contrato Efectivo' y el bot lo leía como 'ya pagó'."""
    out = await _correr(adc=FICHA_ADC, contacto=CONTACTO, ordenes=ORDENES)
    assert "NO indica que el contrato esté saldado" in out


@pytest.mark.asyncio
async def test_el_veredicto_encabeza_y_dice_que_no_esta_saldado():
    out = await _correr(adc=FICHA_ADC, contacto=CONTACTO, ordenes=ORDENES)
    assert "NO está saldado" in out
    assert "CONTRATO SALDADO" not in out


@pytest.mark.asyncio
async def test_sin_registro_de_cobranzas_no_asume_que_no_debe():
    """Alumno en Contacts pero sin ficha financiera: el silencio no es 'está al día'."""
    out = await _correr(adc={}, contacto=CONTACTO, ordenes=ORDENES)
    assert "PROHIBIDO" in out  # bloque DATO_INSUFICIENTE
    assert "Ana Gómez" in out  # los cursos igual se informan


@pytest.mark.asyncio
async def test_alumno_inexistente():
    out = await _correr(adc={}, contacto={})
    assert "No encontré" in out


@pytest.mark.asyncio
async def test_si_falla_una_fuente_las_otras_igual_responden():
    """Zoho ADC caído no puede dejar al alumno sin información de cursada."""
    out = await _correr(adc_error=TimeoutError("ADC caído"), contacto=CONTACTO, ordenes=ORDENES)
    assert "Ana Gómez" in out
    assert "Cardiología AMIR" in out
    assert "PROHIBIDO" in out  # sin financiero no se afirma estado de pago


@pytest.mark.asyncio
async def test_si_falla_contacts_igual_da_el_estado_de_cuenta():
    out = await _correr(adc=FICHA_ADC, contacto_error=TimeoutError("Contacts caído"))
    assert "FICHA_ALUMNO_ENCONTRADA" in out
    assert "ESTADO DE CUENTA" in out


@pytest.mark.asyncio
async def test_alumno_sin_cursos_lo_dice_explicito():
    out = await _correr(adc=FICHA_ADC, contacto=CONTACTO, ordenes=[])
    assert "Sin cursos registrados" in out
