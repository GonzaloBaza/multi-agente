"""Tests del post-procesador de atribución idlead en links del sitio."""

from utils.idlead_links import con_idlead

LID = "5344455000511626541"


def test_sin_url_no_toca():
    assert con_idlead("Hola, ¿cómo estás?", LID) == "Hola, ¿cómo estás?"


def test_sin_lead_no_toca():
    t = "Mirá https://msklatam.com/curso/diabetes"
    assert con_idlead(t, "") == t
    assert con_idlead(t, None) == t


def test_url_simple():
    out = con_idlead("Inscribite: https://msklatam.com/checkout/diabetes", LID)
    assert out == f"Inscribite: https://msklatam.com/checkout/diabetes?idlead={LID}"


def test_url_con_query_existente():
    out = con_idlead("https://msklatam.com/checkout/diabetes/?utm_source=bot", LID)
    assert out == f"https://msklatam.com/checkout/diabetes/?utm_source=bot&idlead={LID}"


def test_ya_tiene_idlead_no_duplica():
    t = f"https://msklatam.com/curso/diabetes?idlead={LID}"
    assert con_idlead(t, LID) == t


def test_subdominios_intactos():
    t = "Portal: https://ayuda.msklatam.com/portal/es/newticket"
    assert con_idlead(t, LID) == t


def test_puntuacion_final_fuera_de_url():
    out = con_idlead("Entrá a https://msklatam.com/curso/diabetes.", LID)
    assert out == f"Entrá a https://msklatam.com/curso/diabetes?idlead={LID}."


def test_fragmento_queda_al_final():
    out = con_idlead("https://msklatam.com/curso/diabetes/#avales", LID)
    assert out == f"https://msklatam.com/curso/diabetes/?idlead={LID}#avales"


def test_markdown_link():
    out = con_idlead("[Inscribite acá](https://msklatam.com/checkout/diabetes)", LID)
    assert out == f"[Inscribite acá](https://msklatam.com/checkout/diabetes?idlead={LID})"


def test_varias_urls():
    t = "Curso: https://msklatam.com/curso/a — pago: https://msklatam.com/checkout/a"
    out = con_idlead(t, LID)
    assert out.count(f"idlead={LID}") == 2


def test_dominio_pelado():
    out = con_idlead("Visitá https://msklatam.com y vemos", LID)
    assert out == f"Visitá https://msklatam.com?idlead={LID} y vemos"
