"""
Tests del prompt del agente unificado de atención al alumno.

Post-venta se absorbió dentro de cobranzas: en la vida real es el mismo equipo,
y tenerlos separados hacía que el agente de post-venta contestara sobre estado
de pago sin acceso a los datos financieros.

Estos tests son el candado para que la absorción no pierda conocimiento ni deje
contradicciones entre lo que traía cada prompt.
"""

from __future__ import annotations

import pytest

from agents.collections.prompts import build_collections_prompt

FICHA = {
    "cobranzaId": "x",
    "alumno": "Ana",
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


@pytest.fixture
def prompt() -> str:
    return build_collections_prompt(FICHA)


# ── El conocimiento de post-venta sobrevivió a la absorción ────────────────


@pytest.mark.parametrize(
    "tema,marca",
    [
        ("recuperar contraseña", "¿Olvidaste tu contraseña?"),
        ("primer acceso", "Claves de acceso a tu cursada"),
        ("soporte de video", "10 Mbps"),
        ("vigencia del curso", "12 a 18 meses"),
        ("ampliación de vigencia", "ampliar-la-vigencia-de-mis-cursos"),
        ("examen final", "2 intentos"),
        ("certificado: requisitos", "72 horas hábiles"),
        ("certificado: blockchain", "blockchain"),
        ("avales", "CONAMEGE"),
        ("facturas", "Mis Facturas"),
        ("tutorías", "departamentodetutorias@msklatam.com"),
        ("oficina", "Av. Córdoba 1367"),
        ("teléfono", "0800-220-6334"),
        ("portal de tickets", "ayuda.msklatam.com/portal/es/newticket"),
    ],
)
def test_conocimiento_de_post_venta_presente(prompt, tema, marca):
    assert marca in prompt, f"se perdió: {tema}"


def test_el_certificado_se_baja_de_mis_certificados(prompt):
    """Bug ya corregido en prod: el bot mandaba a "Mis cursos"."""
    assert "Mis certificados" in prompt
    assert 'NO está en "Mis cursos"' in prompt


def test_no_inventa_foros_ni_comunidad(prompt):
    """MSK no tiene foros y el bot los inventaba."""
    assert "NO existen" in prompt
    assert "foros" in prompt


# ── No quedan contradicciones entre los dos prompts ───────────────────────


def test_no_deriva_a_si_mismo(prompt):
    """Ahora es un solo equipo: no puede decir que deriva a post-venta."""
    bajo = prompt.lower()
    for frase in ("derivo a post-venta", "te derivo a cobranzas", "área de post-venta"):
        assert frase not in bajo


def test_medios_de_pago_diferenciados_por_contexto(prompt):
    """Cobranzas los prohibía y post-venta los explicaba: se resuelve por
    contexto, no eliminando uno de los dos."""
    assert "CONSULTA INFORMATIVA" in prompt
    assert "GESTIONANDO UN COBRO" in prompt
    # Los nombres de sistemas internos siguen prohibidos siempre.
    assert "en ningún contexto" in prompt


def test_el_gate_de_ficha_no_bloquea_consultas_generales(prompt):
    """Preguntar la vigencia no puede disparar el flujo de deuda ni pedir email."""
    assert "NO NECESITAN ficha" in prompt
    assert "NO pidas el email" in prompt


def test_consulta_de_cursada_no_arranca_por_la_deuda(prompt):
    assert "MÓDULO ATENCIÓN AL ALUMNO" in prompt
    assert "NO arranques hablando de deuda" in prompt
    assert "resolvé PRIMERO lo que preguntó" in prompt


# ── Los bloques calculados siguen enganchados ─────────────────────────────


def test_trae_el_veredicto_de_estado_de_cuenta(prompt):
    assert "ESTADO DE CUENTA" in prompt
    assert "NO está saldado" in prompt  # esta ficha tiene saldo


def test_trae_el_bloque_de_horario(prompt):
    assert "HORARIO DE ATENCIÓN" in prompt


def test_usa_la_tool_unificada(prompt):
    assert "buscar_ficha_alumno" in prompt
    assert "buscar_alumno_mail_adc" not in prompt


def test_sin_ficha_no_rompe_y_no_afirma_estado():
    p = build_collections_prompt(None)
    assert "MÓDULO ATENCIÓN AL ALUMNO" in p
    assert "PROHIBIDO" in p  # dato insuficiente
