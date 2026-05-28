import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..state.task_state import TaskState
from ..types import TaskStatus


class BaseTask(ABC):
    def __init__(self, task_id: str | None = None):
        self.task_id = task_id or str(uuid.uuid4())
        self.state = TaskState(self.task_id)
        self.created_at = datetime.now()
        self.result: Any = None

    @abstractmethod
    async def execute(self) -> Any:
        pass

    async def cancel(self) -> None:
        await self.state.transition(TaskStatus.killed)

    async def start(self) -> Any:
        ok = await self.state.transition(TaskStatus.running)
        if not ok:
            return None
        try:
            self.result = await self.execute()
            await self.state.transition(TaskStatus.completed)
            return self.result
        except Exception as e:
            await self.state.transition(TaskStatus.failed)
            raise e
