from typing import Any

from pydantic import ValidationError

from .base_tool import BaseTool

_REGISTRY: dict[str, type[BaseTool]] = {}


def _register_tool_class(cls: type[BaseTool]) -> None:
    if cls.__name__ not in _REGISTRY:
        _REGISTRY[cls.__name__] = cls


def register_tool(cls: type[BaseTool]) -> type[BaseTool]:
    _REGISTRY[cls.__name__] = cls
    return cls


def get_tool(name: str) -> type[BaseTool] | None:
    return _REGISTRY.get(name)


def create_tool_instance(name: str, args: dict[str, Any]) -> BaseTool | None:
    model_class = _REGISTRY.get(name)
    if not model_class:
        raise ValueError(f"未找到工具: '{name}'")
    try:
        return model_class(**args)
    except ValidationError:
        return None


def list_tools() -> dict[str, type[BaseTool]]:
    return _REGISTRY.copy()
