"""
Clasificador automático de conversaciones.
Corre después de cada respuesta del agente IA y asigna una etiqueta al lead.
"""

import structlog
from openai import AsyncOpenAI

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# TTL de las etiquetas en Redis. Sin esto quedaban fósiles para siempre:
# una conv de hace meses revivía en el kanban con su etiqueta vieja.
LABEL_TTL_SECONDS = 60 * 60 * 24 * 60  # 60 días

# OJO: "convertido" NO está acá a propósito. A esa columna solo se llega
# por señal real de compra (utils/conversion_check.py: Contacts.IDLEAD en
# Zoho) o por drag manual del supervisor. El LLM demostró confundir el
# "ya tenés acceso / pago registrado" de post-venta y cobranzas con una
# venta nueva — de 23 convertidos históricos, 18 eran soporte.
LABELS = {
    "caliente": "Muy interesado, pregunta por precio, fechas, formas de pago o quiere inscribirse",
    "tibio": "Interesado pero con dudas, pide más información o no se decide",
    "frio": "Respuestas breves, pasivo, sin preguntas, solo mira",
    "esperando_pago": "Recibió el link de pago; el pago aún no está verificado",
    "seguimiento": "Pidió que lo contacten después, o es gestión de soporte/post-venta",
    "no_interesa": "Dijo explícitamente que no le interesa o pidió que no lo contacten",
}

SYSTEM_PROMPT = """Sos un clasificador de leads para una empresa de cursos médicos.
Analizá la conversación y devolvé UNA SOLA palabra que representa el estado del lead.

Opciones:
- caliente: muy interesado, pregunta por precio/fechas/pago o quiere inscribirse
- tibio: interesado pero con dudas, pide más info, no se decide
- frio: pasivo, respuestas breves, sin preguntas, solo mira
- esperando_pago: recibió el link de pago, o dice que pagó/va a pagar (la verificación del pago la hace el sistema, no vos)
- seguimiento: pidió que lo contacten después, o es una gestión de soporte/post-venta/cobranzas
- no_interesa: dijo que no le interesa

REGLAS CRÍTICAS:
- NO existe la opción "convertido": aunque el agente confirme un pago, usá "esperando_pago" — la conversión real la verifica el sistema contra el CRM.
- Si la persona es ALUMNO con un problema (acceso al campus, reembolso, error, cuota, certificado), es "seguimiento" — no es un lead de venta.
- Gestiones de cobranzas (deuda, cuota vencida, medio de pago) también son "seguimiento".

Respondé SOLO con una de esas palabras, nada más."""


async def classify_conversation(messages: list, session_id: str) -> str | None:
    """
    Clasifica la conversación y guarda el label en Redis.
    Retorna el label asignado o None si falla.

    messages: lista de dicts {role, content}
    """
    if not messages or len(messages) < 2:
        return None

    # Solo los últimos 10 mensajes para no gastar tokens
    recent = messages[-10:]
    convo_text = "\n".join(
        f"{'Usuario' if m.get('role') == 'user' else 'Agente'}: {m.get('content', '')[:200]}"
        for m in recent
        if m.get("content")
    )

    try:
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # modelo barato para clasificación
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": convo_text},
            ],
            max_tokens=10,
            temperature=0,
        )

        label = response.choices[0].message.content.strip().lower()

        # Compat: si el modelo insiste con "convertido" (ya no es opción),
        # lo tratamos como pago sin verificar — el job de conversión decide.
        if label == "convertido":
            label = "esperando_pago"

        if label not in LABELS:
            logger.warning("classifier_unknown_label", label=label, session_id=session_id)
            return None

        # Guardar en Redis (con TTL — sin esto quedaban etiquetas fósiles)
        from memory.conversation_store import get_conversation_store

        store = await get_conversation_store()
        await store._redis.set(f"conv_label:{session_id}", label, ex=LABEL_TTL_SECONDS)

        # Broadcast SSE para que el inbox se actualice en tiempo real
        try:
            from utils.realtime import broadcast_event

            broadcast_event({"type": "label_updated", "session_id": session_id, "label": label})
        except Exception:
            pass

        logger.info("conversation_classified", session_id=session_id, label=label)
        return label

    except Exception as e:
        logger.warning("classifier_error", session_id=session_id, error=str(e))
        return None
