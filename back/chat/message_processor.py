from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from ..utils.text_utils import trim_excess_newlines


class MessageProcessor:
    @staticmethod
    def normalize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
        if not messages:
            return messages

        result: list[BaseMessage] = []
        for msg in messages:
            content = msg.content
            if isinstance(content, str) and not content.strip():
                continue
            result.append(msg)

        return MessageProcessor._ensure_alternating_roles(result)

    @staticmethod
    def _ensure_alternating_roles(messages: list[BaseMessage]) -> list[BaseMessage]:
        if len(messages) <= 1:
            return messages

        result = [messages[0]]
        for msg in messages[1:]:
            prev_role = MessageProcessor._role_of(result[-1])
            curr_role = MessageProcessor._role_of(msg)
            if prev_role == curr_role and prev_role == "human":
                result[-1] = HumanMessage(
                    content=result[-1].content + "\n" + msg.content
                )
            else:
                result.append(msg)
        return result

    @staticmethod
    def _role_of(msg: BaseMessage) -> str:
        if isinstance(msg, HumanMessage):
            return "human"
        if isinstance(msg, SystemMessage):
            return "system"
        if isinstance(msg, ToolMessage):
            return "tool"
        return "ai"

    @staticmethod
    def process_attachments(content: str, attachments: list[dict]) -> str:
        if not attachments:
            return content

        attachment_parts = []
        for att in attachments:
            name = att.get("name", "unknown")
            att_content = att.get("content", "")
            attachment_parts.append(f"### {name}\n{att_content}")

        attachment_text = "\n\n".join(attachment_parts)
        return f"{content}\n\n# 附件内容\n{attachment_text}"

    @staticmethod
    def handle_boundary(messages: list[BaseMessage]) -> list[BaseMessage]:
        if not messages:
            return messages

        result = list(messages)
        while result and isinstance(result[0], ToolMessage):
            result.pop(0)

        if result and isinstance(result[-1], ToolMessage):
            last_tool = result[-1]
            result.append(HumanMessage(content=f"[工具调用结果] {last_tool.content[:200]}"))

        return result

    @staticmethod
    def trim_excess_newlines(content: str | list) -> str | list:
        return trim_excess_newlines(content)
