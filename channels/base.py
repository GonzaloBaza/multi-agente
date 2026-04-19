"""
Base class para todos los canales de comunicación.
Define la interfaz común que cada canal debe implementar.
"""

from abc import ABC, abstractmethod


class ChannelProcessor(ABC):
    """Interfaz base para procesadores de canal."""

    @abstractmethod
    async def process_incoming(self, payload: dict) -> dict:
        """Parsea el payload del webhook y retorna mensaje normalizado."""
        ...

    @abstractmethod
    async def send_text(self, to: str, text: str) -> dict:
        """Envía un mensaje de texto."""
        ...

    @abstractmethod
    async def send_media(self, to: str, media_url: str, media_type: str, caption: str = "") -> dict:
        """Envía un archivo multimedia."""
        ...

    @abstractmethod
    async def send_template(self, to: str, template: str, params: list) -> dict:
        """Envía un template/plantilla."""
        ...

    @abstractmethod
    async def mark_as_read(self, message_id: str) -> None:
        """Marca un mensaje como leído."""
        ...

    def supports_buttons(self) -> bool:
        return False

    def supports_media(self) -> bool:
        return False

    def supports_templates(self) -> bool:
        return False

    def supports_typing(self) -> bool:
        return False

    @property
    @abstractmethod
    def channel_name(self) -> str: ...
