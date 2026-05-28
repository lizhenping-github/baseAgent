import inspect
from datetime import datetime

from ..memory.base_memory import BaseMemory


class PromptBuilder:
    @staticmethod
    def get_system_prompt(instruction: str) -> str:
        return inspect.cleandoc(instruction)

    @staticmethod
    def get_user_context(context: dict) -> str:
        sections = []
        if context.get("knowledge"):
            sections.append(f"""
# 业务知识
<USER_DOCUMENT>
{context["knowledge"]}
</USER_DOCUMENT>
""")
        if context.get("attachments"):
            sections.append(f"""
# 用户上传的附件内容
<ATTACHMENTS>
{context["attachments"]}
</ATTACHMENTS>
""")
        return "\n".join(sections)

    @staticmethod
    def get_system_context() -> str:
        return f"当前系统时间：{datetime.now()}"

    @staticmethod
    async def load_memory_prompt(memory: BaseMemory) -> str:
        content = await memory.load()
        if not content:
            return ""
        return f"""
# 长期记忆
<MEMORY>
{content}
</MEMORY>
"""

    @staticmethod
    async def build_final_prompt(
        instruction: str,
        context: dict | None = None,
        memory: BaseMemory | None = None,
    ) -> str:
        parts = [PromptBuilder.get_system_prompt(instruction)]
        parts.append(PromptBuilder.get_system_context())

        if context:
            user_ctx = PromptBuilder.get_user_context(context)
            if user_ctx:
                parts.append(user_ctx)

        if memory:
            memory_prompt = await PromptBuilder.load_memory_prompt(memory)
            if memory_prompt:
                parts.append(memory_prompt)

        return "\n\n".join(parts)
