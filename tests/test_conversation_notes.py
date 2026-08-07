"""
Tests de la nota interna del equipo sobre una conversación.

Es UNA nota por conversación (se pisa, no se acumula) y la edita cualquiera
del equipo. Lo importante que cuidan estos tests:
  - guardar un texto vacío BORRA la nota (no hay endpoint DELETE aparte),
  - el texto de la nota NO viaja al audit log (puede tener datos del alumno),
  - queda registrado quién la editó.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/inbox/conversations/11111111-1111-1111-1111-111111111111/notes"

USUARIO = {"id": "u-gbaza", "email": "gonzalobaza@msklatam.com", "name": "Gonza Baza", "role": "admin"}


@pytest.fixture
def client():
    from api.admin import verify_admin_or_session
    from main import app

    app.dependency_overrides[verify_admin_or_session] = lambda: {"auth": "session", "user": USUARIO}
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(verify_admin_or_session, None)


def _put(client, notes: str):
    """Ejecuta el PUT con la capa de datos mockeada. Devuelve (response, mocks)."""
    set_notes = AsyncMock(
        return_value={
            "notes": notes.strip() or None,
            "notes_updated_at": None,
            "notes_updated_by": USUARIO["id"],
            "notes_updated_by_name": USUARIO["name"],
        }
    )
    log_action = AsyncMock()
    with (
        patch("memory.conversation_meta.set_notes", set_notes),
        patch("utils.inbox_jobs.log_action", log_action),
    ):
        res = client.put(PATH, json={"notes": notes})
    return res, set_notes, log_action


def test_guardar_nota(client):
    res, set_notes, _ = _put(client, "Llamar después de las 18h")
    assert res.status_code == 200, res.text
    assert res.json()["notes"] == "Llamar después de las 18h"
    assert set_notes.await_args.args[1] == "Llamar después de las 18h"


def test_queda_registrado_el_autor(client):
    """Sin esto no se sabe quién dejó el contexto del caso."""
    _res, set_notes, _ = _put(client, "algo")
    kw = set_notes.await_args.kwargs
    assert kw["author_id"] == "u-gbaza"
    assert kw["author_name"] == "Gonza Baza"


def test_texto_vacio_borra_la_nota(client):
    """No hay DELETE aparte: mandar vacío es la forma de borrar."""
    res, set_notes, _ = _put(client, "   ")
    assert res.status_code == 200
    assert res.json()["notes"] == ""
    assert set_notes.await_args.args[1] == "   "  # el trim lo hace la capa de datos


def test_el_texto_de_la_nota_no_va_al_audit_log(client):
    """Puede tener datos del alumno y el audit log se lee desde otra pantalla."""
    secreto = "El alumno dijo que su tarjeta termina en 4242"
    _res, _sn, log_action = _put(client, secreto)

    assert log_action.await_count == 1
    registrado = str(log_action.await_args.args)
    assert secreto not in registrado
    assert "4242" not in registrado
    # Pero sí queda constancia de la acción y de quién fue.
    assert log_action.await_args.args[0] == "u-gbaza"
    assert log_action.await_args.args[1] == "notes"


def test_el_audit_log_distingue_guardar_de_borrar(client):
    _res, _sn, log = _put(client, "hola")
    assert log.await_args.args[3]["accion"] == "guardada"

    _res, _sn, log = _put(client, "")
    assert log.await_args.args[3]["accion"] == "borrada"


def test_leer_nota_inexistente_devuelve_vacio(client):
    with patch("memory.conversation_meta.get_meta", AsyncMock(return_value=None)):
        res = client.get(PATH)
    assert res.status_code == 200
    assert res.json() == {"notes": "", "notes_updated_at": None, "notes_updated_by_name": ""}
