"""
Tests del sandbox /api/v1/admin/test-agent.

Motivo: el endpoint declaraba `forced_agent` en el request model pero NUNCA se
lo pasaba a `route_message`, así que el selector "Forzar agente" de la UI no
hacía nada — todos los mensajes pasaban por el clasificador. Lo mismo con el
email del alumno, sin el cual es imposible reproducir en el sandbox los bugs
que dependen de la ficha (estado de cuenta, cuotas, saldo).

Estos tests son el candado para que no se vuelva a desconectar.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/admin/test-agent"


@pytest.fixture
def client_as_admin():
    """TestClient con `get_current_user` overrideado a un admin."""
    from api.auth import get_current_user
    from main import app

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-admin",
        "email": "admin@test.local",
        "name": "Admin Test",
        "role": "admin",
    }
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _routed_kwargs(client, payload: dict) -> dict:
    """Ejecuta el endpoint con `route_message` mockeado y devuelve sus kwargs."""
    fake = AsyncMock(
        return_value={
            "response": "ok",
            "agent_used": "cobranzas",
            "handoff_requested": False,
            "handoff_reason": "",
        }
    )
    with patch("agents.router.route_message", fake):
        res = client.post(PATH, json=payload)
    assert res.status_code == 200, res.text
    assert fake.await_count == 1
    return fake.await_args.kwargs


def test_forced_agent_llega_al_router(client_as_admin):
    """El selector "Forzar agente" tiene que llegar a route_message."""
    kwargs = _routed_kwargs(
        client_as_admin,
        {"message": "hola", "forced_agent": "collections"},
    )
    assert kwargs["forced_agent"] == "collections"


def test_forced_agent_none_no_fuerza(client_as_admin):
    """Sin forzar agente, route_message recibe None (clasifica el router)."""
    kwargs = _routed_kwargs(client_as_admin, {"message": "hola"})
    assert kwargs["forced_agent"] is None


def test_email_del_alumno_llega_al_router(client_as_admin):
    """Sin el email no se puede resolver la ficha → no se reproducen los bugs."""
    kwargs = _routed_kwargs(
        client_as_admin,
        {"message": "¿mi curso está pagado?", "email": "alumno@test.local"},
    )
    assert kwargs["email"] == "alumno@test.local"


def test_contexto_del_alumno_completo(client_as_admin):
    """phone / user_name / has_debt / is_student / page_slug se propagan."""
    kwargs = _routed_kwargs(
        client_as_admin,
        {
            "message": "hola",
            "phone": "+5491122334455",
            "user_name": "Raúl",
            "page_slug": "cardiologia-amir",
            "has_debt": True,
            "is_student": True,
        },
    )
    assert kwargs["phone"] == "+5491122334455"
    assert kwargs["user_name"] == "Raúl"
    assert kwargs["page_slug"] == "cardiologia-amir"
    assert kwargs["has_debt"] is True
    assert kwargs["is_student"] is True


def test_phone_default_no_rompe(client_as_admin):
    """Sin phone explícito se manda el placeholder 'test', no vacío."""
    kwargs = _routed_kwargs(client_as_admin, {"message": "hola"})
    assert kwargs["phone"] == "test"


def test_mensaje_vacio_da_400(client_as_admin):
    res = client_as_admin.post(PATH, json={"message": "   "})
    assert res.status_code == 400
