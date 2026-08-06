"""
Guard de identidad para las tools que exponen datos de cuenta.

Motivo: la tool `buscar_alumno_mail_adc` de cobranzas no tenía ningún control.
Cualquiera podía abrir el widget en incógnito, elegir "Soporte Cobros", tipear
el mail de otra persona y recibir su ficha financiera completa (nombre, país,
importe de contrato, cuotas, deuda, último pago).

El widget ya bloqueaba esto al armar el contexto (`channels/widget.py`), así que
la política del sistema era clara — lo que faltaba era aplicarla también a las
tools, que el LLM puede invocar en cualquier momento con el texto que el usuario
haya escrito.

Regla (definida con Gonzalo, ago-2026): solo se muestran datos de cuenta a
identidades **verificadas por el canal** — sesión activa en msklatam.com o
número de WhatsApp. Un email tipeado en el chat no alcanza.
"""

from __future__ import annotations

from utils.agent_context import current_identity_source, identidad_verificada, log_to_conv

# Lo lee el LLM, no el usuario: son instrucciones de qué hacer en este turno.
# Sin esto el modelo tiende a decir "no encontré tu cuenta", que suena a que
# buscó y no había — y encima confirma o niega la existencia de un email ajeno.
MENSAJE_REQUIERE_LOGIN = (
    "⛔ ACCESO DENEGADO — la identidad del usuario NO está verificada. "
    "NO podemos darle información de cuenta (cursos, vencimientos, accesos, pagos, "
    "deuda, cuotas) de NADIE, ni siquiera si dice ser el dueño del email.\n\n"
    "Acciones a hacer EN ESTE TURNO:\n"
    "1. NO inventes datos de cuenta. NO digas «no encontré» (suena a que buscaste, "
    "y además revela si ese email existe o no).\n"
    "2. Pedile que inicie sesión en https://msklatam.com para que podamos acceder "
    "a su información personal.\n"
    "3. Si dice que NO PUEDE INICIAR SESIÓN, ayudalo con tips de recuperación "
    "(olvidé mi contraseña, modo incógnito, limpiar caché) — SIN dar datos "
    "específicos de la cuenta.\n"
    "4. Si nada funciona, derivá al portal de tickets: "
    "https://ayuda.msklatam.com/portal/es/newticket y emití `[CARGAR_TICKET]`."
)


async def bloquear_si_no_verificado(accion: str, email: str = "") -> str | None:
    """
    Devuelve el mensaje de rechazo si la identidad NO está verificada, o None si
    se puede continuar. Las tools deben hacer:

        if (rechazo := await bloquear_si_no_verificado("mi_tool", email)):
            return rechazo
    """
    if identidad_verificada():
        return None

    await log_to_conv(
        "error",
        {
            "action": f"{accion}_sin_verificar",
            "detail": (
                f"Bloqueado: identidad '{current_identity_source.get()}' no verificada · "
                f"email consultado={email or '(s/d)'}"
            ),
        },
    )
    return MENSAJE_REQUIERE_LOGIN
