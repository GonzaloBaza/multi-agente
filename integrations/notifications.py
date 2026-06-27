"""
Notificaciones al equipo humano vía Slack y email.
Se disparan en handoffs o escalaciones.
"""

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


async def notify_slack(message: str) -> bool:
    """Envía mensaje al webhook de Slack configurado."""
    settings = get_settings()
    if not settings.slack_webhook_url:
        logger.debug("slack_not_configured")
        return False

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                settings.slack_webhook_url,
                json={"text": message},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("slack_notification_failed", error=str(e))
            return False


async def notify_send_failure(
    *,
    channel: str,
    destino: str,
    error: str,
    conversation_id: str | None = None,
    throttle_key: str | None = None,
) -> None:
    """Alerta a Slack cuando FALLA el envío de un mensaje al usuario (WhatsApp/
    widget). No reintenta — solo avisa. Throttle por conversación/destino (1
    alerta cada 10 min por clave) para no inundar Slack ante un fallo masivo.

    Bulletproof: nunca lanza — se llama desde paths de envío críticos y no debe
    romperlos. Si Slack/Redis fallan, se loguea y sigue."""
    try:
        settings = get_settings()
        if not settings.slack_webhook_url:
            return

        # Throttle: 1 alerta por clave cada 10 min.
        key = throttle_key or conversation_id or destino or "unknown"
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url)
            try:
                first = await client.set(f"send_fail_alert:{key}", "1", nx=True, ex=600)
            finally:
                await client.aclose()
            if not first:
                return  # ya avisamos por esta clave en los últimos 10 min
        except Exception:
            pass  # si Redis falla, alertamos igual (mejor ruido que silencio)

        link = (
            f"\n• Conv: https://agentes.msklatam.com/inbox?conv={conversation_id}"
            if conversation_id else ""
        )
        msg = (
            f"🚨 *El bot no pudo enviar un mensaje*\n"
            f"• Canal: {channel}\n"
            f"• Destino: `{destino}`\n"
            f"• Error: {str(error)[:300]}"
            f"{link}"
        )
        await notify_slack(msg)
        logger.warning("send_failure_alerted", channel=channel, destino=destino)
    except Exception as e:
        logger.warning("notify_send_failure_failed", error=str(e))


async def notify_handoff(
    channel: str,
    external_id: str,
    user_name: str,
    reason: str,
    agent: str,
) -> None:
    msg = (
        f"🤝 *Handoff solicitado*\n"
        f"• Canal: {channel}\n"
        f"• ID conversación: `{external_id}`\n"
        f"• Usuario: {user_name or 'Desconocido'}\n"
        f"• Agente: {agent}\n"
        f"• Motivo: {reason}"
    )
    await notify_slack(msg)
    logger.info("handoff_notified", channel=channel, external_id=external_id)


async def notify_payment_confirmed(
    user_name: str,
    course_name: str,
    amount: float,
    currency: str,
    order_id: str,
) -> None:
    msg = (
        f"✅ *Pago confirmado*\n"
        f"• Alumno: {user_name}\n"
        f"• Curso: {course_name}\n"
        f"• Monto: {currency} {amount:,.0f}\n"
        f"• Orden Zoho: `{order_id}`"
    )
    await notify_slack(msg)
