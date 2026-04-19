"""
Integración con Meta WhatsApp Cloud API.
Envía mensajes de texto, interactivos (botones/listas), templates y multimedia.
"""

import os
import uuid
from pathlib import Path

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"


class WhatsAppMetaClient:
    def __init__(self):
        settings = get_settings()
        self._token = settings.whatsapp_token
        self._phone_id = settings.whatsapp_phone_number_id
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, text: str) -> dict:
        """Envía un mensaje de texto simple."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return await self._post(payload)

    async def send_buttons(
        self, to: str, body: str, buttons: list[str], header: str = "", footer: str = ""
    ) -> dict:
        """
        Envía mensaje con botones de respuesta rápida (máx 3).
        buttons: lista de strings con el texto de cada botón.
        """
        buttons = buttons[:3]  # Meta permite máx 3
        interactive = {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"btn_{i}", "title": btn[:20]}}
                    for i, btn in enumerate(buttons)
                ]
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._post(payload)

    async def send_list(
        self, to: str, body: str, button_label: str, sections: list[dict], header: str = "", footer: str = ""
    ) -> dict:
        """
        Envía mensaje con lista de opciones (máx 10 items).

        sections: [
            {
                "title": "Sección 1",
                "rows": [
                    {"id": "row_1", "title": "Opción 1", "description": "Descripción opcional"},
                ]
            }
        ]
        """
        interactive = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_label[:20],
                "sections": sections,
            },
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._post(payload)

    async def send_template(
        self, to: str, template_name: str, language: str = "es_AR", components: list = None
    ) -> dict:
        """
        Envía un template aprobado por Meta (para mensajes proactivos).
        Solo se pueden enviar templates a usuarios que no iniciaron conversación en últimas 24hs.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }
        if components:
            payload["template"]["components"] = components

        return await self._post(payload)

    async def get_templates(self, limit: int = 100) -> list[dict]:
        """
        Lista las plantillas de mensajes del WABA.
        GET /{WABA_ID}/message_templates?limit=100
        Retorna solo las aprobadas (status=APPROVED).
        """
        settings = get_settings()
        waba_id = settings.whatsapp_waba_id
        if not waba_id:
            logger.warning("whatsapp_waba_id_not_configured")
            return []

        url = f"{GRAPH_URL}/{waba_id}/message_templates"
        params = {"limit": limit, "status": "APPROVED"}
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.get(url, params=params, headers=self._headers)
                r.raise_for_status()
                data = r.json()
                templates = data.get("data", [])
                # Parsear a formato simplificado
                result = []
                for t in templates:
                    components = t.get("components", [])
                    body_text = ""
                    header_info = None
                    buttons = []
                    for comp in components:
                        if comp["type"] == "BODY":
                            body_text = comp.get("text", "")
                        elif comp["type"] == "HEADER":
                            header_info = {
                                "format": comp.get("format", "TEXT"),
                                "text": comp.get("text", ""),
                            }
                        elif comp["type"] == "BUTTONS":
                            buttons = comp.get("buttons", [])

                    # Contar variables {{1}}, {{2}}...
                    import re

                    body_vars = re.findall(r"\{\{(\d+)\}\}", body_text)
                    header_vars = re.findall(
                        r"\{\{(\d+)\}\}", header_info.get("text", "") if header_info else ""
                    )

                    result.append(
                        {
                            "name": t["name"],
                            "language": t.get("language", "es_AR"),
                            "category": t.get("category", ""),
                            "status": t.get("status", ""),
                            "body": body_text,
                            "header": header_info,
                            "buttons": buttons,
                            "body_var_count": len(body_vars),
                            "header_var_count": len(header_vars),
                        }
                    )
                return result
            except httpx.HTTPStatusError as e:
                logger.error(
                    "whatsapp_get_templates_error", status=e.response.status_code, body=e.response.text[:300]
                )
                return []
            except Exception as e:
                logger.error("whatsapp_get_templates_exception", error=str(e))
                return []

    async def upload_media_for_template(self, filepath: str, mime_type: str) -> str:
        """
        Sube un archivo a Meta via Resumable Upload API para usar en templates.
        Retorna el header_handle necesario para crear templates con media.
        """
        settings = get_settings()
        app_id = settings.whatsapp_app_id
        if not app_id:
            raise ValueError("WHATSAPP_APP_ID no configurado en .env")

        file_size = os.path.getsize(filepath)
        file_name = os.path.basename(filepath)

        # Step 1: Create upload session
        session_url = f"{GRAPH_URL}/{app_id}/uploads"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                session_url,
                headers={"Authorization": f"Bearer {self._token}"},
                data={
                    "file_length": str(file_size),
                    "file_type": mime_type,
                    "file_name": file_name,
                },
            )
            r.raise_for_status()
            upload_session_id = r.json().get("id")

            if not upload_session_id:
                raise ValueError("No se pudo crear sesión de upload en Meta")

            # Step 2: Upload file data
            upload_url = f"{GRAPH_URL}/{upload_session_id}"
            with open(filepath, "rb") as f:
                file_data = f.read()

            r2 = await client.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {self._token}",
                    "file_offset": "0",
                    "Content-Type": mime_type,
                },
                content=file_data,
            )
            r2.raise_for_status()
            handle = r2.json().get("h")

            if not handle:
                raise ValueError("Meta no retornó header_handle")

            logger.info("template_media_uploaded", handle=handle[:30], file=file_name)
            return handle

    async def create_template(
        self,
        name: str,
        category: str,
        language: str,
        body_text: str,
        header_text: str = "",
        header_type: str = "",
        header_handle: str = "",
        footer_text: str = "",
        buttons: list[dict] = None,
    ) -> dict:
        """
        Crea una plantilla de mensaje en Meta Business Manager.
        POST /{WABA_ID}/message_templates
        category: MARKETING, UTILITY, AUTHENTICATION
        Soporta headers de texto y media (IMAGE, VIDEO, DOCUMENT).
        """
        settings = get_settings()
        waba_id = settings.whatsapp_waba_id
        if not waba_id:
            raise ValueError("WHATSAPP_WABA_ID no configurado")

        components = []

        # Header: texto o media
        if header_type and header_type.upper() in ("IMAGE", "VIDEO", "DOCUMENT") and header_handle:
            components.append(
                {
                    "type": "HEADER",
                    "format": header_type.upper(),
                    "example": {"header_handle": [header_handle]},
                }
            )
        elif header_text:
            components.append({"type": "HEADER", "format": "TEXT", "text": header_text})

        components.append({"type": "BODY", "text": body_text})

        if footer_text:
            components.append({"type": "FOOTER", "text": footer_text})

        if buttons:
            components.append({"type": "BUTTONS", "buttons": buttons})

        payload = {
            "name": name,
            "category": category.upper(),
            "language": language,
            "components": components,
        }

        url = f"{GRAPH_URL}/{waba_id}/message_templates"
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.post(url, json=payload, headers=self._headers)
                r.raise_for_status()
                result = r.json()
                logger.info("template_created", name=name, id=result.get("id", ""))
                return result
            except httpx.HTTPStatusError as e:
                logger.error(
                    "template_create_error", status=e.response.status_code, body=e.response.text[:500]
                )
                raise
            except Exception as e:
                logger.error("template_create_exception", error=str(e))
                raise

    async def delete_template(self, template_name: str) -> dict:
        """
        Elimina una plantilla de Meta Business Manager.
        DELETE /{WABA_ID}/message_templates?name={name}
        """
        settings = get_settings()
        waba_id = settings.whatsapp_waba_id
        if not waba_id:
            raise ValueError("WHATSAPP_WABA_ID no configurado")

        url = f"{GRAPH_URL}/{waba_id}/message_templates"
        params = {"name": template_name}
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.delete(url, params=params, headers=self._headers)
                r.raise_for_status()
                result = r.json()
                logger.info("template_deleted", name=template_name)
                return result
            except httpx.HTTPStatusError as e:
                logger.error(
                    "template_delete_error", status=e.response.status_code, body=e.response.text[:300]
                )
                raise

    async def send_typing(self, to: str) -> None:
        """Envía indicador de 'escribiendo...' al usuario en WhatsApp."""
        url = f"{GRAPH_URL}/{self._phone_id}/messages"
        # Meta no tiene un endpoint oficial de typing, pero podemos usar mark_as_read
        # que genera actividad visible. La forma real es enviar "typing" via on-premises API.
        # Para Cloud API usamos una acción que muestra actividad:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    url,
                    json={
                        "messaging_product": "whatsapp",
                        "status": "typing",
                        "recipient_type": "individual",
                        "to": to,
                    },
                    headers=self._headers,
                )
        except Exception:
            pass  # Non-critical, don't fail if typing indicator fails

    async def mark_as_read(self, message_id: str) -> dict:
        """Marca un mensaje como leído (muestra los dos ticks azules)."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return await self._post(payload)

    # ── Media ────────────────────────────────────────────────────────────────

    async def get_media_url(self, media_id: str) -> str:
        """Obtiene la URL de descarga de un media de Meta (efímera)."""
        url = f"{GRAPH_URL}/{media_id}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=self._headers)
            r.raise_for_status()
            return r.json().get("url", "")

    async def download_media(self, media_id: str, extension: str = "") -> str | None:
        """
        Descarga un media de Meta y lo guarda en /media/.
        Retorna la ruta relativa del archivo guardado (ej: 'media/abc123.jpg').
        """
        try:
            media_url = await self.get_media_url(media_id)
            if not media_url:
                return None

            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(media_url, headers=self._headers)
                r.raise_for_status()
                data = r.content

                # Generar nombre único
                filename = f"{uuid.uuid4().hex[:12]}{extension}"
                media_dir = Path(__file__).parent.parent / "media"
                media_dir.mkdir(exist_ok=True)
                filepath = media_dir / filename
                filepath.write_bytes(data)

                logger.info("media_downloaded", media_id=media_id, file=filename, size=len(data))
                return f"media/{filename}"
        except Exception as e:
            logger.error("media_download_error", media_id=media_id, error=str(e))
            return None

    async def send_image(self, to: str, image_url: str, caption: str = "") -> dict:
        """Envía una imagen por URL."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url},
        }
        if caption:
            payload["image"]["caption"] = caption
        return await self._post(payload)

    async def send_document(self, to: str, document_url: str, filename: str = "", caption: str = "") -> dict:
        """Envía un documento por URL."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {"link": document_url},
        }
        if filename:
            payload["document"]["filename"] = filename
        if caption:
            payload["document"]["caption"] = caption
        return await self._post(payload)

    async def send_video(self, to: str, video_url: str, caption: str = "") -> dict:
        """Envía un video por URL."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "video",
            "video": {"link": video_url},
        }
        if caption:
            payload["video"]["caption"] = caption
        return await self._post(payload)

    async def send_audio(self, to: str, audio_url: str) -> dict:
        """Envía un audio por URL."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"link": audio_url},
        }
        return await self._post(payload)

    async def upload_media(self, filepath: str, mime_type: str) -> str | None:
        """
        Sube un archivo a Meta y retorna el media_id.
        Esto permite enviar media sin URL pública.
        """
        url = f"{GRAPH_URL}/{self._phone_id}/media"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                with open(filepath, "rb") as f:
                    r = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {self._token}"},
                        data={"messaging_product": "whatsapp", "type": mime_type},
                        files={"file": (os.path.basename(filepath), f, mime_type)},
                    )
                    r.raise_for_status()
                    return r.json().get("id")
        except Exception as e:
            logger.error("media_upload_error", error=str(e))
            return None

    async def send_media_by_id(self, to: str, media_id: str, media_type: str, caption: str = "") -> dict:
        """Envía media usando un media_id previamente subido."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
            media_type: {"id": media_id},
        }
        if caption and media_type in ("image", "document"):
            payload[media_type]["caption"] = caption
        return await self._post(payload)

    async def _post(self, payload: dict) -> dict:
        from utils.circuit_breaker import meta_breaker

        if not meta_breaker.can_execute():
            logger.warning("whatsapp_circuit_open", state=meta_breaker.state.value)
            return {"error": "circuit_open", "message": "WhatsApp API temporarily unavailable"}

        url = f"{GRAPH_URL}/{self._phone_id}/messages"
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.post(url, json=payload, headers=self._headers)
                r.raise_for_status()
                meta_breaker.record_success()
                return r.json()
            except httpx.HTTPStatusError as e:
                meta_breaker.record_failure()
                logger.error("whatsapp_send_error", status=e.response.status_code, body=e.response.text[:300])
                raise
            except Exception as e:
                meta_breaker.record_failure()
                logger.error("whatsapp_send_exception", error=str(e))
                raise


def parse_buttons_tag(text: str) -> tuple[str, list[str]]:
    """
    Extrae botones del tag [BUTTONS: opción1 | opción2 | opción3] del texto del agente.
    Retorna (texto_limpio, lista_de_botones).
    """
    import re

    match = re.search(r"\[BUTTONS:\s*(.+?)\]", text, re.IGNORECASE)
    if not match:
        return text, []

    raw = match.group(1)
    buttons = [b.strip() for b in raw.split("|") if b.strip()]
    clean_text = text[: match.start()].strip() + text[match.end() :].strip()
    clean_text = clean_text.strip()
    return clean_text, buttons


def parse_list_tag(text: str) -> tuple[str, list[dict]]:
    """
    Extrae lista del tag [LIST: título1 | título2 | ...] del texto del agente.
    Retorna (texto_limpio, sections para send_list).
    """
    import re

    match = re.search(r"\[LIST:\s*(.+?)\]", text, re.IGNORECASE)
    if not match:
        return text, []

    raw = match.group(1)
    items = [i.strip() for i in raw.split("|") if i.strip()]
    sections = [
        {
            "title": "Opciones",
            "rows": [{"id": f"item_{i}", "title": item[:24]} for i, item in enumerate(items[:10])],
        }
    ]
    clean_text = text[: match.start()].strip() + text[match.end() :].strip()
    return clean_text.strip(), sections
