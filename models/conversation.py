import uuid
from datetime import datetime
from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from config.constants import AgentType, Channel, ConversationStatus, Country
from models.message import Message


class UserProfile(BaseModel):
    """Datos del contacto identificado."""

    zoho_contact_id: str | None = None
    zoho_lead_id: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    country: Country = Country.ARGENTINA
    lms_user_id: str | None = None
    active_courses: list[str] = Field(default_factory=list)
    payment_status: str | None = None


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: Channel
    external_id: str  # Botmaker chat_id or widget session_id
    user_profile: UserProfile = Field(default_factory=UserProfile)
    current_agent: AgentType = AgentType.SALES
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[Message] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def get_history_for_llm(self, max_messages: int = 20) -> list[dict]:
        recent = self.messages[-max_messages:]
        return [m.to_langchain_dict() for m in recent if m.role.value in ("user", "assistant")]


class ConversationState(BaseModel):
    """LangGraph state schema — typed dict compatible."""

    conversation_id: str
    channel: str
    country: str = "AR"
    user_profile: dict = Field(default_factory=dict)
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    current_agent: str = AgentType.SALES.value
    intent: str | None = None
    pending_action: str | None = None
    last_tool_result: dict = Field(default_factory=dict)
    handoff_requested: bool = False
    handoff_reason: str | None = None

    class Config:
        arbitrary_types_allowed = True
