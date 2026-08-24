"""Tests del detector determinista de opt-out (utils/optout.py).

La regla de diseño: solo frases INEQUÍVOCAS de "no me contacten" cortan en
seco. Objeciones de venta ("es caro", "no me interesa" suelto) y frases
operativas ("no me manden el link todavía") NO deben matchear — esos grises
los decide el LLM con la tool `marcar_no_contactar`.
"""

import pytest

from utils.optout import es_optout_explicito

OPTOUTS = [
    "no me escriban más",
    "No me escriban mas por favor",
    "no me manden más mensajes",
    "no me contacten nunca",
    "no me llames más",
    "NO ME MOLESTEN",
    "no molesten",
    "dejen de escribirme",
    "deja de mandarme cosas",
    "dejen de insistir",
    "no quiero recibir más información",
    "no quiero saber nada",
    "no quiero saber más nada de esto",
    "no quiero más info",
    "no quiero mas mensajes",
    "no quiero que me escriban",
    "no quiero que me llamen",
    "borrame",
    "bórrenme de ahí",
    "eliminame",
    "sacame de la lista",
    "sáquenme de su base",
    "quitame de la lista",
    "basta de mensajes",
    "basta de spam",
    "no insistan",
    "stop",
    "STOP",
    "baja",
    "Baja.",
    # combinado con otra frase alrededor
    "che la verdad no me interesa, no me escriban más",
    "gracias pero dejen de mandar promociones",
]

NO_OPTOUTS = [
    # objeciones de venta — las maneja el agente
    "no me interesa",
    "no me interesa por ahora",
    "es muy caro",
    "lo voy a pensar",
    "ahora no puedo",
    # frases operativas que contienen verbos parecidos
    "no me manden el link todavía",
    "no me llames hoy, mejor mañana",
    "no me escriban al mail, prefiero acá",
    "todavía no quiero pagar",
    "no quiero el curso de urgencias, prefiero el de hemodinamia",
    "quiero saber más del curso",
    "mandame más info",
    # 'stop'/'baja' embebidos en frase normal
    "quiero dar de baja mi tarjeta del pago",
    "en la parada del stop está el hospital",
    # saludo/normal
    "hola, qué tal?",
    "cuánto sale el curso?",
    "",
]


@pytest.mark.parametrize("texto", OPTOUTS)
def test_detecta_optout(texto):
    assert es_optout_explicito(texto), f"debería cortar: {texto!r}"


@pytest.mark.parametrize("texto", NO_OPTOUTS)
def test_no_falso_positivo(texto):
    assert not es_optout_explicito(texto), f"NO debería cortar: {texto!r}"
