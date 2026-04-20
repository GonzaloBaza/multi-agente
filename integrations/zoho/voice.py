"""
Zoho Voice — cliente de Call Logs API.

Scope requerido: `ZohoVoice.call.READ`.

Endpoints usados (todos GET):
  {base}/logs                 → lista paginada con filtros
  {base}/logs/{logid}         → un log puntual

Donde {base} = `https://voice.zoho.com/rest/json/zv` (NO zohoapis.com — Voice
tiene dominio propio).

Respuesta real de Zoho (campos interesantes, capturados contra prod):
  - `logid`                       str   → UUID único del log
  - `call_type`                   str   → "outgoing" | "incoming" | "missed"
  - `start_time` / `end_time`     str   → epoch millis (sí, como string)
  - `duration`                    str   → "MM:SS" (string)
  - `caller_id_number`            str   → número que inició la llamada
  - `destination_number`          str   → número que recibió
  - `user_number`                 str   → número de la contraparte (cliente)
  - `did_number`                  str   → número corporativo que salió/entró
  - `agent_number`                str   → NOMBRE del agente humano (no número)
  - `department`                  str
  - `hangup_cause_displayname`    str   → "Atendida", "Usuario ocupado", ...
  - `hangup_cause_description`    str
  - `call_recording_transcription_status`  str   → "not_initiated" | "completed" | ...
  - `disconnected_by`             str   → "customer" | "agent"
  - `voicemail_read_by`           bool

El cliente normaliza los campos más útiles en un dict plano para el frontend
(`normalize_log`) y filtra por teléfono localmente — la API no soporta filtro
server-side por número (?phone=) confiable en todas las regiones.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from config.settings import get_settings
from integrations.zoho.voice_auth import ZohoVoiceAuth

logger = structlog.get_logger(__name__)


def _digits_only(phone: str) -> str:
    """Normalización para comparación tolerante: solo dígitos.

    Ej: '+54 9 11 1234-5678' y '5491112345678' matchean.
    No es perfecto (dos números distintos con los mismos últimos 10 dígitos
    matchearían), pero con los números con código de país es suficiente.
    """
    return "".join(c for c in phone if c.isdigit())


def _epoch_ms_to_iso(ms_str: str | None) -> str | None:
    if not ms_str:
        return None
    try:
        return datetime.utcfromtimestamp(int(ms_str) / 1000).isoformat() + "Z"
    except (ValueError, TypeError):
        return None


def normalize_log(raw: dict) -> dict[str, Any]:
    """Aplana el log crudo de Zoho a un shape consumible por el frontend.

    El raw de Zoho tiene ~50 campos; expongo solo los que voy a mostrar en la
    timeline. Si mañana hace falta más (transcripción, voicemail, costo), se
    agrega acá.
    """
    return {
        "logid": raw.get("logid") or raw.get("id"),
        "direction": raw.get("call_type"),  # outgoing / incoming / missed
        "start": _epoch_ms_to_iso(raw.get("start_time")),
        "end": _epoch_ms_to_iso(raw.get("end_time")),
        "duration": raw.get("duration"),  # "MM:SS"
        "from_number": raw.get("caller_id_number"),
        "to_number": raw.get("destination_number"),
        "customer_number": raw.get("user_number"),
        "did_number": raw.get("did_number"),
        "agent_name": raw.get("agent_number"),  # Zoho confunde, pero es el nombre
        "department": raw.get("department"),
        "hangup_cause": raw.get("hangup_cause_displayname"),
        "hangup_detail": raw.get("hangup_cause_description"),
        "disconnected_by": raw.get("disconnected_by"),
        "recording_status": raw.get("call_recording_transcription_status"),
        "has_voicemail": bool(raw.get("voicemail_read_by") is not None),
    }


class ZohoVoice:
    """Cliente de Zoho Voice Call Logs API.

    Uso:
        client = ZohoVoice()
        logs = await client.list_logs(phone="+5491112345678", limit=20)
    """

    def __init__(self) -> None:
        self._auth = ZohoVoiceAuth()

    @property
    def _base(self) -> str:
        return get_settings().zoho_voice_base_url

    async def list_logs(
        self,
        phone: str | None = None,
        limit: int = 50,
        offset: int = 0,
        from_date: str | None = None,
        to_date: str | None = None,
        call_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista call logs. Si se pasa `phone`, intenta filtrar server-side
        vía `userNumber` y además filtra client-side como red de seguridad.

        Zoho usa param names camelCase bien específicos — nombres "obvios"
        como limit/page/per_page tiran 400 `ZVT010 Extra parameter found`.
        Ver: https://help.zoho.com/portal/en/kb/zoho-voice/zoho-voice-apis/common-apis/articles/call-logs-api

        Params Zoho:
            from (int)       → offset
            size (int)       → cantidad
            fromDate (str)   → YYYY-MM-DD
            toDate (str)     → YYYY-MM-DD
            userNumber (str) → solo dígitos; matchea prefijo del cliente
            callType (str)   → incoming|outgoing|missed|bridged|forward
        """
        headers = await self._auth.auth_headers()
        # Overfetch si vamos a filtrar client-side (userNumber de Zoho matchea
        # prefijo, puede ser demasiado laxo o estricto según el formato).
        size = min(limit * 4 if phone else limit, 200)
        params: dict[str, Any] = {"from": offset, "size": size}
        if phone:
            params["userNumber"] = _digits_only(phone)
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if call_type:
            params["callType"] = call_type

        url = f"{self._base}/logs"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            logger.error(
                "zoho_voice_logs_error",
                status=resp.status_code,
                body=resp.text[:300],
                params=params,
            )
            return []

        data = resp.json()
        raw_logs = data.get("logs") or data.get("data") or []
        logs = [normalize_log(r) for r in raw_logs]

        # Filtro client-side extra por si userNumber matchea más laxo de lo
        # esperado. Comparamos últimos 10 dígitos (tolerante a +54 vs 54 vs
        # formatos con guiones).
        if phone:
            target_digits = _digits_only(phone)
            target = target_digits[-10:] if len(target_digits) >= 10 else target_digits
            logs = [
                log
                for log in logs
                if target
                and (
                    target in _digits_only(log.get("customer_number") or "")
                    or target in _digits_only(log.get("to_number") or "")
                    or target in _digits_only(log.get("from_number") or "")
                )
            ]
            logs = logs[:limit]

        return logs

    async def get_log(self, logid: str) -> dict[str, Any] | None:
        """Trae un log puntual por ID. Útil para grabación + transcripción."""
        headers = await self._auth.auth_headers()
        url = f"{self._base}/logs/{logid}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            logger.error(
                "zoho_voice_log_error",
                status=resp.status_code,
                logid=logid,
                body=resp.text[:300],
            )
            return None

        data = resp.json()
        raw = data.get("log") or data.get("data") or data
        return normalize_log(raw) if raw else None
