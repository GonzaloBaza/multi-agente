"""
Unit tests del armado de WHERE para el listado de conversaciones.

`_build_conversations_where` toma los filtros del inbox + el user logueado y
emite (where_clause, params). Es pura (no toca DB) — misma filosofía que
test_agent_queue_scope.py.
"""

from __future__ import annotations

from api.inbox_api import _build_conversations_where


def _call(**kw):
    base = dict(
        user=None, view=None, lifecycle=None, channel=None, queue=None,
        country=None, assigned_to=None, search=None, date_from=None, date_to=None,
    )
    base.update(kw)
    return _build_conversations_where(**base)


def test_admin_no_filters_hides_resolved():
    where, params = _call()
    assert "cm.status is null OR cm.status != 'resolved'" in where
    assert params == []


def test_agente_sin_id_ni_colas_no_ve_nada():
    where, params = _call(user={"role": "agente", "id": None, "queues": []})
    assert where == "WHERE FALSE"
    assert params == []


def test_channel_filter_param():
    where, params = _call(channel="widget")
    assert "c.channel = $1" in where
    assert params == ["widget"]


def test_date_range_params():
    from datetime import datetime, timezone

    where, params = _call(date_from="2026-06-01", date_to="2026-06-30")
    assert "c.updated_at >= $1::timestamptz" in where
    assert "c.updated_at <= $2::timestamptz" in where
    # asyncpg necesita datetime aware (no string) para ::timestamptz
    assert params[0] == datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert params[1] == datetime(2026, 6, 30, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_malformed_date_is_ignored():
    where, params = _call(date_from="no-es-fecha")
    assert "updated_at" not in where
    assert params == []


def test_queue_and_lifecycle_share_param_numbering():
    where, params = _call(queue="sales", lifecycle="hot")
    assert "cm.queue = $1" in where
    assert "lifecycle_override, cm.lifecycle_auto, 'new') = $2" in where
    assert params == ["sales", "hot"]


def test_search_uses_single_param_three_times():
    where, params = _call(search="juan")
    assert where.count("$1") == 3  # name, email, last_message comparten $1
    assert params == ["%juan%"]    # se envuelve en %...%


def test_mine_view_without_user_is_false():
    where, params = _call(view="mine", user=None)
    assert "FALSE" in where
    assert params == []


def test_checkout_sent_filter():
    # True → EXISTS (mensaje con link de checkout); False → NOT EXISTS; None → sin filtro.
    where_yes, p_yes = _call(checkout_sent=True)
    assert "msklatam.com/checkout" in where_yes
    assert "NOT EXISTS" not in where_yes
    assert p_yes == []  # el literal no agrega params

    where_no, _ = _call(checkout_sent=False)
    assert "NOT EXISTS" in where_no

    where_none, _ = _call(checkout_sent=None)
    assert "checkout" not in where_none
