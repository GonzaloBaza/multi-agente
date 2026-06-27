"""Unit tests del mapeo de una conversación a fila CSV (pura, sin DB)."""

from __future__ import annotations

from api.inbox_api import CSV_HEADER, conversation_csv_row, conversation_transcript


def _sample(**kw):
    base = dict(
        id="abc-123",
        created="2026-06-01T10:00:00+00:00",
        last_activity="2026-06-02T11:30:00+00:00",
        channel="widget",
        name="Juan Pérez",
        email="juan@example.com",
        phone="+5491122334455",
        country="AR",
        queue="sales",
        lifecycle="hot",
        status="open",
        needs_human=True,
        bot_paused=False,
        message_count=7,
        last_message="hola\nquiero info",
    )
    base.update(kw)
    return base


def test_header_has_expected_columns():
    assert CSV_HEADER[0] == "id"
    assert "area" in CSV_HEADER
    assert "ultimo_mensaje" in CSV_HEADER
    assert "conversacion" in CSV_HEADER
    assert "checkout_enviado" in CSV_HEADER
    assert len(CSV_HEADER) == 18


def test_row_length_matches_header():
    row = conversation_csv_row(_sample())
    assert len(row) == len(CSV_HEADER)


def test_area_label_maps_queue():
    assert conversation_csv_row(_sample(queue="sales"))[CSV_HEADER.index("area")] == "Ventas"
    assert conversation_csv_row(_sample(queue="post-sales"))[CSV_HEADER.index("area")] == "Post-venta"
    assert conversation_csv_row(_sample(queue="billing"))[CSV_HEADER.index("area")] == "Cobranzas"


def test_booleans_are_si_no():
    row = conversation_csv_row(_sample(needs_human=True, bot_paused=False))
    assert row[CSV_HEADER.index("needs_human")] == "Sí"
    assert row[CSV_HEADER.index("bot_paused")] == "No"


def test_last_message_newlines_flattened():
    row = conversation_csv_row(_sample(last_message="hola\nquiero info"))
    assert "\n" not in row[CSV_HEADER.index("ultimo_mensaje")]
    assert row[CSV_HEADER.index("ultimo_mensaje")] == "hola quiero info"


def test_message_count_is_string():
    row = conversation_csv_row(_sample(message_count=7))
    assert row[CSV_HEADER.index("mensajes")] == "7"


def test_formula_injection_is_neutralized():
    # Campos atacables (nombre/último mensaje vienen de usuarios externos): si
    # empiezan con =, +, -, @, tab o CR se les antepone ' para que Excel no los
    # ejecute como fórmula.
    row = conversation_csv_row(
        _sample(name='=HYPERLINK("http://evil","click")', last_message="@SUM(1+1)")
    )
    assert row[CSV_HEADER.index("nombre")] == '\'=HYPERLINK("http://evil","click")'
    assert row[CSV_HEADER.index("ultimo_mensaje")] == "'@SUM(1+1)"


def test_plain_text_is_unchanged():
    row = conversation_csv_row(_sample(name="Juan Pérez", last_message="hola"))
    assert row[CSV_HEADER.index("nombre")] == "Juan Pérez"
    assert row[CSV_HEADER.index("ultimo_mensaje")] == "hola"


def test_row_includes_full_conversation():
    row = conversation_csv_row(_sample(conversacion="Cliente: hola\nBot: buenas"))
    assert row[CSV_HEADER.index("conversacion")] == "Cliente: hola\nBot: buenas"


def test_checkout_column_si_no():
    assert conversation_csv_row(_sample(checkout_sent=True))[CSV_HEADER.index("checkout_enviado")] == "Sí"
    assert conversation_csv_row(_sample())[CSV_HEADER.index("checkout_enviado")] == "No"


def test_transcript_formats_who_and_skips_system():
    msgs = [
        {"role": "user", "content": "hola", "metadata": None, "created_at": None},
        {"role": "assistant", "content": "buenas", "metadata": {"agent": "bot"}, "created_at": None},
        {"role": "assistant", "content": "te ayudo yo", "metadata": {"agent": "humano"}, "created_at": None},
        {"role": "system", "content": "ignorame", "metadata": None, "created_at": None},
    ]
    t = conversation_transcript(msgs)
    assert "Cliente: hola" in t
    assert "Bot: buenas" in t
    assert "Asesor: te ayudo yo" in t
    assert "ignorame" not in t          # system se omite
    assert t.count("\n") == 2           # 3 líneas (user, bot, asesor)


def test_transcript_bot_agents_are_bot_not_asesor():
    # metadata.agent del bot trae el nombre del agente IA (ventas/bienvenida/...),
    # NO "humano" → debe etiquetarse Bot, no Asesor. Solo 'humano' es Asesor.
    msgs = [{"role": "assistant", "content": "hola", "metadata": {"agent": "ventas"}, "created_at": None}]
    assert conversation_transcript(msgs) == "Bot: hola"
