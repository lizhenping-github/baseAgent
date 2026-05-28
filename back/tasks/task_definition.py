from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskDefinition:
    name: str
    description: str
    task_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    priority: int = 0
    timeout: int | None = None
