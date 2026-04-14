"""
Notificaciones al equipo humano vía Slack y email.
Se disparan en handoffs o escalaciones.
"""
import httpx
from config.settings import get_settings
import structlog

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
