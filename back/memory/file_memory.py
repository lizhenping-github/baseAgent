import inspect
from pathlib import Path

from ..constants import MAX_MEMORY_LENGTH
from .base_memory import BaseMemory


class FileMemory(BaseMemory):
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    async def load(self) -> str:
        if not self.file_path.exists():
            return ""
        return self.file_path.read_text(encoding="utf-8")

    async def save(self, content: str) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(content, encoding="utf-8")

    async def update(self, new_content: str) -> str:
        current = await self.load()
        if new_content.strip() == "无":
            return current

        merged = f"{current}\n\n{new_content}" if current else new_content
        if len(merged) > MAX_MEMORY_LENGTH:
            merged = merged[:MAX_MEMORY_LENGTH]
        await self.save(merged)
        return merged

    async def exists(self) -> bool:
        return self.file_path.exists()

    async def update_with_llm(self, new_content: str, llm_callable) -> str:
        current = await self.load()
        prompt = inspect.cleandoc(f"""
            根据新内容调整文档，返回完整文档。如果无需调整，只输出"无"。

            要求：
            - markdown格式，层级清晰
            - 不超过{MAX_MEMORY_LENGTH}字
            - 精简且有价值

            当前文档：
            {current}

            新内容：
            {new_content}
        """)
        result = await llm_callable(prompt)
        return await self.update(result)
