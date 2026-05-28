from typing import Any

from pydantic import BaseModel, Field

from ..types import ChunkType, ToolDetailType, ToolStatus


class ToolDetail(BaseModel):
    type: ToolDetailType
    content: str

    def __init__(self, content: str, detail_type: ToolDetailType = ToolDetailType.text):
        super().__init__(type=detail_type, content=content)


class ToStreamResult(BaseModel):
    type: ChunkType
    content: Any


class TextResult(ToStreamResult):
    type: ChunkType = ChunkType.text
    content: str

    def __init__(self, content: str):
        super().__init__(content=content)


class Tool(BaseModel):
    content: str
    detail: ToolDetail | None = None
    state: ToolStatus = ToolStatus.success
    id: str | None


class ToolResult(ToStreamResult):
    type: ChunkType = ChunkType.tool
    content: Tool

    def __init__(
        self,
        content: str,
        detail: ToolDetail | None = None,
        state: ToolStatus = ToolStatus.success,
        tool_id: str | None = None,
    ):
        super().__init__(content=Tool(content=content, detail=detail, state=state, id=tool_id))


class SuggestionResult(ToStreamResult):
    type: ChunkType = ChunkType.suggestion
    content: list[str]


class InteractResult(ToStreamResult):
    type: ChunkType = ChunkType.interact
    content: Any


class ToolInvokeResult(BaseModel):
    to_tool: Any
    to_stream: ToStreamResult | None = Field(default=None, description="前端展示用，可以不传")

    def __init__(self, to_tool: Any, to_stream: ToStreamResult | None = None):
        super().__init__(to_tool=to_tool, to_stream=to_stream)
