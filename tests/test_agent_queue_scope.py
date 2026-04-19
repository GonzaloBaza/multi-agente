"""
Tests unitarios del helper de scoping por cola.

`_agent_queue_scope_sql` toma la lista de colas de un profile (ej
`["ventas_AR", "cobranzas_MP"]`) y emite un fragmento SQL que limita las
conversaciones visibles a esas combinaciones de (queue, country).

Es el centro del filtro server-side por rol — si se rompe, los agentes ven
conversaciones ajenas. Vale la pena tener cobertura de los casos borde
(cola inválida, país raro, lista vacía).
"""

from __future__ import annotations

from api.inbox_api import _agent_queue_scope_sql


def test_empty_list_returns_none():
    assert _agent_queue_scope_sql([]) is None


def test_invalid_entries_ignored():
    # Ninguno de estos es una cola válida → resultado vacío.
    assert _agent_queue_scope_sql(["", "junk", "ventas_", "_AR", "ventas"]) is None


def test_single_primary_country():
    sql = _agent_queue_scope_sql(["ventas_AR"])
    assert sql is not None
    assert "cm.queue = 'sales'" in sql
    assert "= 'AR'" in sql
    # Ningún OR para un solo item (pero el wrapper sí está).
    assert sql.startswith("(") and sql.endswith(")")


def test_multi_country_multi_queue():
    sql = _agent_queue_scope_sql(["ventas_AR", "cobranzas_MX", "post_venta_CL"])
    assert sql is not None
    assert "cm.queue = 'sales'" in sql
    assert "cm.queue = 'billing'" in sql
    assert "cm.queue = 'post-sales'" in sql
    assert "'AR'" in sql
    assert "'MX'" in sql
    assert "'CL'" in sql
    # Los fragmentos OR-eados dan 3 pares de paréntesis internos.
    assert sql.count(" OR ") == 2


def test_mp_uses_not_in_primary():
    sql = _agent_queue_scope_sql(["ventas_MP"])
    assert sql is not None
    assert "NOT IN" in sql
    # Los 5 países primarios tienen que estar en la lista.
    for c in ("AR", "CL", "EC", "MX", "CO"):
        assert f"'{c}'" in sql


def test_mixed_valid_and_invalid():
    # La cola rara se descarta, la válida se mantiene.
    sql = _agent_queue_scope_sql(["cualquier_cosa", "ventas_AR"])
    assert sql is not None
    assert "cm.queue = 'sales'" in sql
    assert "'AR'" in sql


def test_country_must_be_two_alpha_chars():
    # Defensa: si alguien guarda una cola con "país" raro, no explotamos y
    # tampoco inyectamos SQL — simplemente se descarta.
    sql = _agent_queue_scope_sql(["ventas_AR123"])
    assert sql is None
    sql = _agent_queue_scope_sql(["ventas_X"])
    assert sql is None
    sql = _agent_queue_scope_sql(["ventas_ar"])
    # "ar" (lowercase) → se normaliza a upper → "AR", debería pasar.
    assert sql is not None and "'AR'" in sql
