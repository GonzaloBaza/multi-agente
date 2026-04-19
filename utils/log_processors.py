"""
Processors de structlog para scrubbing de PII + normalización.

Los logs estructurados del backend van a Sentry (errores), a stdout (Docker
logs), y potencialmente a Loki en el futuro. En cualquier destino NO queremos
que aparezcan passwords, tokens, emails de clientes o números de teléfono en
claro — es un leak a auditoría/compliance ademas de riesgo legal.

Aplicamos un processor que:
  - Redacta valores de claves sensibles por nombre (`password`, `token`,
    `x-session-token`, `secret`, `api_key`, etc).
  - Ofusca emails (`juan@foo.com` → `j***@foo.com`) en cualquier campo.
  - Trunca teléfonos largos (`5491152170771` → `549***0771`).

NO filtramos contenido de mensajes del usuario (field `content` suele ser
largo y puede contener info médica que el equipo necesita debuggear). Si
compliance lo exige, se puede endurecer con redacción total.
"""

from __future__ import annotations

import re
from typing import Any

# Claves cuyo VALOR se reemplaza por "[redacted]" sin inspección.
_SENSITIVE_KEYS = {
    "password",
    "new_password",
    "old_password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "session_token",
    "x-session-token",
    "x_session_token",
    "msk_session",
    "api_key",
    "admin_key",
    "x-admin-key",
    "x_admin_key",
    "secret",
    "client_secret",
    "webhook_secret",
    "app_secret_key",
    "supabase_secret_key",
    "authorization",
}

_EMAIL_RE = re.compile(r"([A-Za-z0-9_.+-])[A-Za-z0-9_.+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
# Teléfono: 10+ dígitos seguidos, con o sin +.
_PHONE_RE = re.compile(r"(\+?\d{3})\d{4,}(\d{4})")


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        s = _EMAIL_RE.sub(r"\1***\2", value)
        s = _PHONE_RE.sub(r"\1***\2", s)
        return s
    if isinstance(value, dict):
        return {k: _scrub_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    return value


def pii_scrubber(_logger, _name, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor — redacta claves sensibles y ofusca emails/teléfonos."""
    for k in list(event_dict.keys()):
        lower = k.lower()
        if lower in _SENSITIVE_KEYS:
            event_dict[k] = "[redacted]"
        else:
            event_dict[k] = _scrub_value(event_dict[k])
    return event_dict
