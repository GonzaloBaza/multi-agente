"""
Integración con Twilio WhatsApp Sandbox / Business.
Envía mensajes de texto y soporta plantillas de Twilio.
"""
import httpx
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)

TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


class TwilioWhatsAppClient:
    def __init__(self):
        settings = get_settings()
        self._account_sid = settings.twilio_account_sid
        self._auth_token = settings.twilio_auth_token
        self._from_number = settings.twilio_whatsapp_from  # e.g. "whatsapp:+14155238886"

    async def send_text(self, to: str, text: str) -> dict:
        """
        Envía un mensaje de texto a un número de WhatsApp.
        to: número en formato internacional, e.g. "5491112345678"
        """
        # Normalizar número destino
        to_wa = f"whatsapp:+{to.lstrip('+')}" if not to.startswith("whatsapp:") else to

        url = TWILIO_API_URL.format(account_sid=self._account_sid)
        payload = {
            "From": self._from_number,
            "To": to_wa,
            "Body": text,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.post(
                    url,
                    data=payload,
                    auth=(self._account_sid, self._auth_token),
                )
                r.raise_for_status()
                result = r.json()
                logger.info("twilio_message_sent", to=to, sid=result.get("sid"))
                return result
            except httpx.HTTPStatusError as e:
                logger.error(
                    "twilio_send_error",
                    status=e.response.status_code,
                    body=e.response.text[:300],
                )
                raise
            except Exception as e:
                logger.error("twilio_send_exception", error=str(e))
                raise

    async def send_chunks(self, to: str, text: str, max_len: int = 1500) -> None:
        """Divide mensajes largos y los envía en partes."""
        chunks = _split_text(text, max_len)
        for chunk in chunks:
            await self.send_text(to, chunk)


def _split_text(text: str, max_len: int = 1500) -> list[str]:
    """Divide texto largo en partes respetando párrafos."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 <= max_len:
            current = (current + "\n\n" + paragraph).strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks or [text[:max_len]]


def parse_twilio_webhook(form_data: dict) -> dict | None:
    """
    Parsea el payload de Twilio (form-urlencoded).
    Retorna dict con los campos relevantes o None si no es un mensaje válido.

    Campos clave de Twilio:
        From: "whatsapp:+5491112345678"
        Body: texto del mensaje
        MessageSid: ID único
        ProfileName: nombre del usuario en WhatsApp
        NumMedia: cantidad de archivos adjuntos
    """
    from_raw = form_data.get("From", "")
    body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid", "")
    profile_name = form_data.get("ProfileName", "")
    num_media = int(form_data.get("NumMedia", "0"))

    if not from_raw:
        return None

    # Extraer número limpio: "whatsapp:+5491112345678" → "5491112345678"
    phone = from_raw.replace("whatsapp:+", "").replace("whatsapp:", "").lstrip("+")

    # Si hay adjunto y no hay texto
    if num_media > 0 and not body:
        body = "[El usuario envió un archivo adjunto]"

    return {
        "from": phone,
        "from_raw": from_raw,
        "text": body,
        "message_sid": message_sid,
        "name": profile_name,
    }
