from langchain_core.messages import BaseMessage, SystemMessage

from ..constants import COMPACT_KEEP_RECENT


class ConversationMemory:
    def __init__(self, max_messages: int = 100, keep_recent: int = COMPACT_KEEP_RECENT):
        self.max_messages = max_messages
        self.keep_recent = keep_recent

    def should_compact(self, messages: list[BaseMessage], token_limit: int) -> bool:
        estimated = self.estimate_tokens(messages)
        return estimated > token_limit

    async def compact(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        if len(messages) <= self.keep_recent:
            return messages

        old_messages = messages[:-self.keep_recent]
        recent_messages = messages[-self.keep_recent:]

        summary = await self.summarize(old_messages)
        summary_msg = SystemMessage(content=f"[对话摘要]\n{summary}")

        return [summary_msg] + recent_messages

    async def summarize(self, messages: list[BaseMessage]) -> str:
        parts = []
        for msg in messages:
            role = type(msg).__name__.replace("Message", "")
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if content:
                parts.append(f"{role}: {content[:500]}")
        return "\n".join(parts)

    @staticmethod
    def estimate_tokens(messages: list[BaseMessage]) -> int:
        total = 0
        for msg in messages:
            content = msg.content
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total += len(item.get("text", ""))
        return total
