"""
Candado del advisory lock que serializa el armado del esquema.

El contenedor levanta con `--workers 2` y ambos corren `ensure_schema()` al
arrancar. Casi todos los statements son `if not exists`, pero
`create or replace function` y el `drop trigger` + `create trigger` escriben en
el catálogo de Postgres siempre, y dos workers a la vez chocaban con "tuple
concurrently updated".

El que perdía abortaba a mitad y el error se traga en main.py, así que en el
peor caso el trigger `messages_touch_conv` quedaba dropeado sin recrear — y ese
trigger mantiene `conversations.updated_at`, o sea el orden del inbox. Fallaba
en silencio.
"""

from __future__ import annotations

import inspect

from memory import postgres_store


def test_ensure_schema_toma_advisory_lock():
    src = inspect.getsource(postgres_store.ensure_schema)
    assert "pg_advisory_xact_lock" in src
    assert "_SCHEMA_LOCK_ID" in src


def test_el_lock_es_transaccional_no_de_sesion():
    """Supabase nos conecta por pgbouncer en transaction mode: la conexión del
    servidor se recicla entre statements. Un `pg_advisory_lock` de sesión se
    tomaría en una conexión y el unlock podría caer en otra, dejándolo colgado
    para siempre. El transaccional se libera al cerrar la transacción."""
    src = inspect.getsource(postgres_store.ensure_schema)
    assert "pg_advisory_lock(" not in src, "lock de sesión: se cuelga con pgbouncer"
    assert "conn.transaction()" in src, "el lock transaccional necesita una transacción explícita"


def test_el_lock_id_es_estable():
    """Si cambia, dos versiones del proceso dejan de excluirse entre sí."""
    assert postgres_store._SCHEMA_LOCK_ID == 4577120936


def test_el_ddl_riesgoso_sigue_estando_cubierto():
    """Si alguien agrega otro statement no-idempotente al schema, que sepa que
    depende de este lock."""
    sql = postgres_store.SCHEMA_SQL.lower()
    assert "create or replace function" in sql
    assert "drop trigger if exists" in sql
