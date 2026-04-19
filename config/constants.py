from enum import StrEnum


class AgentType(StrEnum):
    SALES = "ventas"
    COLLECTIONS = "cobranzas"
    POST_SALES = "post_venta"
    CLOSER = "closer"
    HUMAN = "humano"


class Country(StrEnum):
    ARGENTINA = "AR"
    MEXICO = "MX"
    COLOMBIA = "CO"
    PERU = "PE"
    CHILE = "CL"
    URUGUAY = "UY"


COUNTRY_PHONE_PREFIXES: dict[str, Country] = {
    "54": Country.ARGENTINA,
    "52": Country.MEXICO,
    "57": Country.COLOMBIA,
    "51": Country.PERU,
    "56": Country.CHILE,
    "598": Country.URUGUAY,
}

COUNTRY_CURRENCY: dict[Country, str] = {
    Country.ARGENTINA: "ARS",
    Country.MEXICO: "MXN",
    Country.COLOMBIA: "COP",
    Country.PERU: "PEN",
    Country.CHILE: "CLP",
    Country.URUGUAY: "UYU",
}

# Conversation TTL in Redis (seconds)
CONVERSATION_TTL = 60 * 60 * 24 * 7  # 7 days

# Max conversation history to send to LLM
MAX_HISTORY_MESSAGES = 20

# Handoff triggers
HANDOFF_KEYWORDS = [
    "hablar con una persona",
    "agente humano",
    "persona real",
    "quiero hablar con alguien",
    "operador",
    "asesor",
]


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    WIDGET = "widget"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    HANDED_OFF = "handed_off"
    CLOSED = "closed"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_ARREARS = "in_arrears"
