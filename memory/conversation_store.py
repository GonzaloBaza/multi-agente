import json
import redis.asyncio as aioredis
from functools import lru_cache
from models.conversation import Conversation, UserProfile
from models.message import Message, MessageRole
from config.settings import get_settings
from config.constants import CONVERSATION_TTL, Channel
import structlog

logger = structlog.get_logger(__name__)


class ConversationStore:
    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    def _key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}"

    def _index_key(self, channel: str, external_id: str) -> str:
        return f"idx:{channel}:{external_id}"

    async def get(self, conversation_id: str) -> Conversation | None:
        raw = await self._redis.get(self._key(conversation_id))
        if not raw:
            return None
        try:
            return Conversation.model_validate_json(raw)
        except Exception:
            logger.warning("corrupt_conversation", conversation_id=conversation_id)
            return None

    async def get_by_external(self, channel: Channel, external_id: str) -> Conversation | None:
        conv_id = await self._redis.get(self._index_key(channel.value, external_id))
        if not conv_id:
            return None
        return await self.get(conv_id.decode())

    async def save(self, conversation: Conversation) -> None:
        pipe = self._redis.pipeline()
        pipe.setex(
            self._key(conversation.id),
            CONVERSATION_TTL,
            conversation.model_dump_json(),
        )
        pipe.setex(
            self._index_key(conversation.channel.value, conversation.external_id),
            CONVERSATION_TTL,
            conversation.id,
        )
        await pipe.execute()

    async def get_or_create(
        self,
        channel: Channel,
        external_id: str,
        country: str = "AR",
    ) -> tuple[Conversation, bool]:
        """Returns (conversation, is_new)."""
        existing = await self.get_by_external(channel, external_id)
        if existing:
            return existing, False

        conversation = Conversation(
            channel=channel,
            external_id=external_id,
            user_profile=UserProfile(country=country),
        )
        await self.save(conversation)
        logger.info("conversation_created", id=conversation.id, channel=channel, external_id=external_id)
        return conversation, True

    async def append_message(self, conversation: Conversation, message: Message) -> Conversation:
        conversation.add_message(message)
        await self.save(conversation)
        return conversation

    async def delete(self, conversation_id: str, channel: str, external_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.delete(self._key(conversation_id))
        pipe.delete(self._index_key(channel, external_id))
        await pipe.execute()


_store: ConversationStore | None = None


async def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        settings = get_settings()
        client = aioredis.from_url(settings.redis_url, decode_responses=False)
        _store = ConversationStore(client)
    return _store
