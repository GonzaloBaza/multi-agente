"""
Mapeo canónico de motivos de rechazo de pago a explicaciones humanas.

Las claves coinciden 1-a-1 con los `PaymentErrorStatus` del frontend
(`msk-front/src/app/[lang]/checkout/utils/paymentErrorMessages.ts`):
    insufficient_funds | card_declined | expired_card | invalid_card |
    processing_error   | fraud_high_risk | invalid_session | rejected

El frontend ya hace el mapping de los códigos crudos de cada gateway
(MP statusDetail, Rebill error code, Stripe error code) a estos status
canónicos vía `mapRebillErrorToStatus()` y similares. El widget recibe
el código YA mapeado en el evento `msk:paymentRejected`.

`explicacion` reusa los `userMessage` de Ariel del front (mismo texto que
el user ve en la pantalla de rechazo). `accion` agrega el próximo paso
concreto que el agente puede ofrecer.

Si llega un código que no está en el dict, se hace fallback al `message`
crudo del frontend (el agente lo parafrasea).
"""

# Mapeo: status canónico (matchea PaymentErrorStatus del front) → texto humano
# + acción concreta. El gateway específico (MP/Rebill/Stripe) se reporta
# aparte en el `gateway` del payload.
PAYMENT_REJECTIONS: dict[str, dict[str, str]] = {
    "insufficient_funds": {
        "titulo": "Fondos insuficientes",
        "explicacion": (
            "Tu tarjeta no tiene fondos suficientes. Prueba con otra tarjeta o "
            "método de pago."
        ),
        "accion": (
            "Probá con otra tarjeta de crédito o débito, o esperá a que se "
            "libere cupo en la cuenta. Si querés, te genero un nuevo link "
            "ahora."
        ),
    },
    "card_declined": {
        "titulo": "Tarjeta rechazada",
        "explicacion": (
            "Tu tarjeta fue rechazada por el banco. Verifica los datos o "
            "prueba con otra tarjeta."
        ),
        "accion": (
            "Revisá que el nombre del titular, número y datos coincidan, o "
            "probá con otra tarjeta. A veces el banco bloquea pagos online "
            "y conviene autorizarlos por la app del homebanking."
        ),
    },
    "expired_card": {
        "titulo": "Tarjeta vencida",
        "explicacion": "La tarjeta que usaste está vencida. Utiliza una tarjeta válida.",
        "accion": "Usá una tarjeta vigente — te genero un nuevo link cuando estés listo.",
    },
    "invalid_card": {
        "titulo": "Datos de tarjeta inválidos",
        "explicacion": (
            "Los datos de tu tarjeta son inválidos. Verifica el número, fecha "
            "y CVV."
        ),
        "accion": (
            "Revisá número, fecha de vencimiento y los 3 dígitos del dorso "
            "(CVV) — un dígito de más o de menos hace que el sistema "
            "rechace el pago."
        ),
    },
    "processing_error": {
        "titulo": "Error de procesamiento",
        "explicacion": (
            "Ocurrió un error al procesar tu pago. Intenta nuevamente o "
            "contacta a un asesor."
        ),
        "accion": (
            "Esperá un par de minutos y reintentá — suelen ser caídas "
            "momentáneas de la red bancaria. Si persiste, te derivo con "
            "un asesor humano."
        ),
    },
    "fraud_high_risk": {
        "titulo": "Validación bloqueada por seguridad",
        "explicacion": (
            "Hubo un inconveniente validando esta tarjeta. Te recomendamos "
            "intentar con otra."
        ),
        "accion": (
            "El sistema antifraude bloqueó la operación — no es un problema "
            "tuyo. Probá con otra tarjeta, o autorizá el consumo desde la app "
            "del banco antes de reintentar."
        ),
    },
    "invalid_session": {
        "titulo": "Sesión de pago expirada",
        "explicacion": (
            "Tu sesión de pago expiró. Por favor, actualiza la página y "
            "vuelve a intentarlo."
        ),
        "accion": (
            "Refrescá la página del checkout y reintentá. Si querés, te paso "
            "un nuevo link de pago directo por acá."
        ),
    },
    "rejected": {
        "titulo": "Pago rechazado",
        "explicacion": (
            "No pudimos procesar tu inscripción. Por favor, prueba con otro "
            "método de pago o contacta con un asesor."
        ),
        "accion": (
            "Probá con otra tarjeta, o si querés te derivo con un asesor "
            "humano para revisar qué pasó puntualmente."
        ),
    },
}


def explain_rejection(
    code: str = "",
    raw_message: str = "",
    reason: str = "",
) -> dict[str, str]:
    """
    Devuelve la explicación humana para un código de rechazo.

    Prioridad:
      1. Match exacto del `code` en el dict canónico → texto pulido.
      2. Si no matchea pero hay `raw_message`/`reason` → fallback con texto crudo.
      3. Genérico.

    Returns: {titulo, explicacion, accion, code}
    """
    code_norm = (code or "").strip().lower()
    if code_norm in PAYMENT_REJECTIONS:
        info = PAYMENT_REJECTIONS[code_norm]
        return {
            "titulo": info["titulo"],
            "explicacion": info["explicacion"],
            "accion": info["accion"],
            "code": code_norm,
        }

    fallback_text = (raw_message or reason or "").strip()
    if fallback_text:
        return {
            "titulo": "Pago rechazado",
            "explicacion": fallback_text[:400],
            "accion": (
                "Te puedo ayudar a entender qué pasó y a probar con otra "
                "tarjeta. También podés contactar al banco emisor."
            ),
            "code": code_norm or "unknown",
        }

    return {
        "titulo": "Pago rechazado",
        "explicacion": (
            "El pago fue rechazado por la procesadora — no recibimos un "
            "motivo específico."
        ),
        "accion": (
            "Probá con otra tarjeta de crédito o débito, o contactá al banco "
            "emisor para más detalles."
        ),
        "code": code_norm or "unknown",
    }


def build_context_block(rejection: dict) -> str:
    """
    Toma el payload `payment_rejection` (que viene del widget vía
    `msk:paymentRejected`) y devuelve un bloque markdown para inyectar al
    contexto del agente sales/closer. El agente lo lee como instrucción de
    cómo arrancar la conversación tras un rechazo.

    `rejection` debe tener la forma:
        {reason: str, code: str, message: str, gateway?: str}

    Si todos los campos están vacíos, devuelve "" (no se inyecta nada).
    """
    if not rejection or not isinstance(rejection, dict):
        return ""

    code = rejection.get("code") or ""
    raw_message = rejection.get("message") or ""
    reason = rejection.get("reason") or ""
    gateway = rejection.get("gateway") or ""

    if not (code or raw_message or reason):
        return ""

    info = explain_rejection(code=code, raw_message=raw_message, reason=reason)

    return (
        "## ⚠️ CONTEXTO CRÍTICO — RECHAZO DE PAGO RECIENTE\n\n"
        "El usuario acaba de tener un pago rechazado en el checkout. **Tu primer "
        "turno DEBE arrancar reconociendo el rechazo y explicando el motivo en "
        "lenguaje claro.** No saludos genéricos — empatía + información + acción.\n\n"
        f"**Motivo del rechazo: {info['titulo']}**\n"
        f"  - Código del gateway: `{info['code']}`{(' (' + gateway + ')') if gateway else ''}\n"
        f"  - Explicación humana: {info['explicacion']}\n"
        f"  - Próximo paso recomendado: {info['accion']}\n\n"
        "## INSTRUCCIONES PARA ESTE TURNO\n"
        "1. Empezá con empatía breve (1 línea, sin sobreactuar): «Vi que tuviste "
        "un problema con el pago — te explico qué pasó».\n"
        "2. Explicá el motivo del rechazo con tus propias palabras, basándote en "
        "la **explicación humana** de arriba (NO leas el código crudo al user).\n"
        "3. Ofrecé el **próximo paso recomendado** como acción concreta.\n"
        "4. Si el usuario quiere reintentar, generá un nuevo link de pago con "
        "`create_payment_link` (mismo curso, asumí que ya viene del checkout).\n"
        "5. Si pide hablar con un humano o el motivo es ambiguo, derivá con "
        "HANDOFF_REQUIRED.\n"
        "6. **NO inventes** otros motivos ni sugiras métodos que MSK no acepta "
        "(solo tarjeta crédito/débito — ver Regla #7)."
    )
