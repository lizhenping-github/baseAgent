from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from .tool_result import ToolInvokeResult, ToStreamResult


class BaseTool(BaseModel, ABC):
    tool_call_id: str | None = Field(default=None, exclude=True)

    def before_invoke(self) -> ToStreamResult | None:
        return None

    @abstractmethod
    async def invoke(self) -> ToolInvokeResult:
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .tool_registry import _register_tool_class
        _register_tool_class(cls)
