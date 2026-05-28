from langchain_core.messages import BaseMessage

from ..constants import AUTO_COMPACT_THRESHOLD, COMPACT_KEEP_RECENT
from ..memory.conversation_memory import ConversationMemory


class ContextCompactor:
    _memory = ConversationMemory()

    @staticmethod
    async def auto_compact(
        messages: list[BaseMessage],
        token_limit: int,
        threshold: float = AUTO_COMPACT_THRESHOLD,
    ) -> list[BaseMessage]:
        estimated = ContextCompactor._memory.estimate_tokens(messages)
        if estimated < token_limit * threshold:
            return messages
        return await ContextCompactor._memory.compact(messages)

    @staticmethod
    async def reactive_compact(
        messages: list[BaseMessage],
        keep_recent: int = COMPACT_KEEP_RECENT,
    ) -> list[BaseMessage]:
        return await ContextCompactor._memory.compact(messages)

    @staticmethod
    def estimate_tokens(messages: list[BaseMessage]) -> int:
        return ConversationMemory.estimate_tokens(messages)
