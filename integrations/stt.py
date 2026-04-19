"""
Speech-to-Text vía OpenAI Whisper.

Transcribe archivos de audio entrantes (WhatsApp voice notes, widget, etc)
para que los agentes IA puedan entender el contenido y responder al mismo.

Usage:
    text = await transcribe_file("/tmp/voice.ogg")
    text = await transcribe_bytes(audio_bytes, filename="audio.ogg")
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Extensiones soportadas por Whisper
SUPPORTED_EXTS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".oga", ".flac", ".amr"}

# Límite: Whisper acepta hasta 25 MB por archivo
MAX_FILE_SIZE = 25 * 1024 * 1024


def is_enabled() -> bool:
    """True si OpenAI está configurado (siempre tendríamos key si LLM funciona)."""
    from config.settings import get_settings

    return bool(get_settings().openai_api_key)


async def transcribe_file(filepath: str | Path, language: str | None = "es") -> str:
    """Transcribe un archivo de audio. Retorna string vacío si falla."""
    p = Path(filepath)
    if not p.exists() or not p.is_file():
        logger.warning("stt_file_not_found", path=str(p))
        return ""
    if p.stat().st_size > MAX_FILE_SIZE:
        logger.warning("stt_file_too_large", path=str(p), size=p.stat().st_size)
        return ""
    if p.suffix.lower() not in SUPPORTED_EXTS:
        logger.warning("stt_unsupported_ext", path=str(p), ext=p.suffix)
        return ""

    from openai import AsyncOpenAI

    from config.settings import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        with open(p, "rb") as f:
            resp = await asyncio.wait_for(
                client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language=language,
                    response_format="text",
                ),
                timeout=30,
            )
        text = (resp if isinstance(resp, str) else getattr(resp, "text", "")).strip()
        logger.info("stt_ok", path=str(p), chars=len(text))
        return text
    except TimeoutError:
        logger.warning("stt_timeout", path=str(p))
        return ""
    except Exception as e:
        logger.error("stt_failed", path=str(p), error=str(e))
        return ""


async def transcribe_bytes(
    audio_bytes: bytes, filename: str = "audio.ogg", language: str | None = "es"
) -> str:
    """Transcribe bytes de audio (sin pasar por filesystem). Retorna '' si falla."""
    import os
    import tempfile

    suffix = Path(filename).suffix or ".ogg"
    if suffix.lower() not in SUPPORTED_EXTS:
        suffix = ".ogg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        return await transcribe_file(tmp_path, language=language)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
