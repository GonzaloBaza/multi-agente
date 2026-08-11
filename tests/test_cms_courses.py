"""
Tests del adaptador CMS → formato del catálogo.

El WP headless (cms1.msklatam.com) dejó de existir y el catálogo pasó a un CMS
propio sobre Supabase. En vez de reescribir `build_brief_md` (~600 líneas
afinadas a mano para vender), se traduce la entrada: el contenido es el mismo,
cambió de lugar.
"""

from __future__ import annotations

from integrations.msk_courses import _cms_a_item, build_brief_md, to_row

FILA_CMS = {
    "slug": "cuidados-paliativos",
    "title": "Máster en cuidados paliativos",
    "base_title": "Cuidados paliativos",
    "code": "8000000",
    "published_at": "2025-12-02T23:12:34+00:00",
    "duration": "1500",
    "modules": 12,
    "currency": "ARS",
    "total_price": 4960000,
    "max_installments": 12,
    "cedente": {"name": "AMIR", "title": "AMIR"},
    "categories": [{"name": "Otra"}, {"name": "Medicina intensiva", "is_primary": True}],
    "professions": [{"name": "Médicos"}],
    "avales": [{"name": "UDIMA", "link": "https://udima.es"}],
    "certificaciones": [{"title": "Cert UDIMA", "total_price": 1884800, "currency": "ARS"}],
    "authors": [{"name": "Dra. Ana Acevedo", "description": "Coordinadora"}],
    "habilidades": [{"name": "Atención paliativa"}],
    "kb_ai": {
        "perfiles_dirigidos": [{"perfil": "MÉDICO GENERAL", "que_obtiene": "Formación para generalistas"}],
        "datos_tecnicos": "<table><tr><td>Modalidad</td><td>100% online</td></tr></table>",
        "objetivos_de_aprendizaje": "<ul><li>Identificar pacientes</li></ul>",
        "descripcion_y_problematica": "<p>Descripción del máster</p>",
    },
    "content_data": {
        "a_quien": ["Médicos generalistas"],
        "que_aprenderas": ["Identificar pacientes"],
        "contenido": "<p>Los cuidados paliativos...</p>",
        "plan_de_estudio": {
            "pdf": "https://cms/temario.pdf",
            "modulos": [{"titulo": "Introducción"}, {"titulo": "Dolor"}],
        },
    },
}


def test_kb_ai_pasa_intacto():
    """Es lo que arma los perfiles con dolor/beneficio y los pitches. Si se
    rompe acá, el bot deja de vender bien."""
    it = _cms_a_item(FILA_CMS)
    assert it["kb_ai"] == FILA_CMS["kb_ai"]


def test_las_secciones_reubicadas_llegan_donde_las_busca_el_brief():
    it = _cms_a_item(FILA_CMS)
    s = it["sections"]
    assert s["habilities"][0]["name"] == "Atención paliativa"
    assert s["teaching_team"][0]["name"] == "Dra. Ana Acevedo"
    assert s["formacion_dirigida"] == ["Médicos generalistas"]
    assert s["learning"] == ["Identificar pacientes"]
    assert "cuidados paliativos" in s["content"]["content"]


def test_los_modulos_se_renombran_de_titulo_a_title():
    """El CMS los nombra en español; el armado del brief espera `title`."""
    it = _cms_a_item(FILA_CMS)
    mods = it["sections"]["study_plan"]["modules"]
    assert [m["title"] for m in mods] == ["Introducción", "Dolor"]
    assert it["study_plan_file"] == "https://cms/temario.pdf"


def test_los_avales_se_mapean_a_title():
    """Los avales traen `name`; el bloque de certificaciones espera `title`."""
    it = _cms_a_item(FILA_CMS)
    assert it["sections"]["institutions"][0]["title"] == "UDIMA"


def test_respeta_la_categoria_marcada_como_principal():
    """El CMS SÍ marca `is_primary` — no se puede asumir que es la primera."""
    it = _cms_a_item(FILA_CMS)
    assert to_row(it, "ar")["categoria"] == "Medicina intensiva"


def test_sin_is_primary_cae_a_la_primera():
    fila = {**FILA_CMS, "categories": [{"name": "Primera"}, {"name": "Segunda"}]}
    assert to_row(_cms_a_item(fila), "ar")["categoria"] == "Primera"


def test_el_valor_de_cuota_se_deriva():
    """El CMS guarda el total y la cantidad de cuotas, no el valor de cada una."""
    it = _cms_a_item(FILA_CMS)
    assert it["prices"]["price_installments"] == round(4960000 / 12, 2)


def test_sin_cuotas_no_divide_por_cero():
    it = _cms_a_item({**FILA_CMS, "max_installments": 0, "total_price": 1000})
    assert it["prices"]["price_installments"] is None


def test_fila_vacia_no_rompe():
    """El CMS puede tener cursos a medio cargar."""
    it = _cms_a_item({"slug": "x", "title": "X"})
    assert it["sections"]["study_plan"]["modules"] == []
    assert it["kb_ai"] == {}


def test_el_brief_sale_completo():
    brief = build_brief_md(_cms_a_item(FILA_CMS), "ar")
    for seccion in ["Máster en cuidados paliativos", "AMIR", "Perfiles objetivo", "Plan de estudios"]:
        assert seccion in brief


def test_to_row_llena_las_columnas_del_catalogo():
    row = to_row(_cms_a_item(FILA_CMS), "ar")
    assert row["slug"] == "cuidados-paliativos"
    assert row["cedente"] == "AMIR"
    assert row["total_price"] == 4960000.0
    assert row["duration_hours"] == 1500
    assert row["product_id"] == 8000000
    assert row["brief_md"]
