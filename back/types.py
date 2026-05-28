from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    killed = "killed"


class TaskPlanStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class ChunkType(str, Enum):
    think = "think"
    text = "text"
    visualized = "visualized"
    interact = "interact"
    tool = "tool"
    suggestion = "suggestion"
    plan = "plan"
    command = "command"


class ToolChoice(str, Enum):
    auto = "auto"
    required = "required"
    none = "none"


class ToolStatus(str, Enum):
    success = "success"
    error = "error"
    loading = "loading"


class SkillStatus(str, Enum):
    success = "success"
    error = "error"
    info = "info"


class SkillDetailType(str, Enum):
    text = "text"
    json = "json"
    data = "data"


class ToolDetailType(str, Enum):
    text = "text"
    table = "table"


class TelemetryRecorder(Protocol):
    def llm_span(self) -> Any: ...
    def tool_span(self, tool: Any) -> Any: ...


@dataclass
class SessionInfo:
    session_id: str
    user_id: str
    created_at: float
    last_active_at: float
    message_count: int
    tool_call_count: int
    task_status: TaskStatus | None
    paused: bool
