import asyncio
from collections.abc import Awaitable, Callable

from ..types import TaskStatus

_VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.pending: {TaskStatus.running, TaskStatus.killed},
    TaskStatus.running: {TaskStatus.completed, TaskStatus.failed, TaskStatus.killed},
    TaskStatus.completed: set(),
    TaskStatus.failed: set(),
    TaskStatus.killed: set(),
}


class TaskState:
    def __init__(self, task_id: str, initial: TaskStatus = TaskStatus.pending):
        self.task_id = task_id
        self._status = initial
        self._lock = asyncio.Lock()
        self._callbacks: list[Callable[[TaskStatus, TaskStatus], Awaitable[None]]] = []

    @property
    def status(self) -> TaskStatus:
        return self._status

    @property
    def is_terminal(self) -> bool:
        return self._status in {TaskStatus.completed, TaskStatus.failed, TaskStatus.killed}

    async def transition(self, new_status: TaskStatus) -> bool:
        async with self._lock:
            allowed = _VALID_TRANSITIONS.get(self._status, set())
            if new_status not in allowed:
                return False
            old_status = self._status
            self._status = new_status

        for callback in self._callbacks:
            await callback(old_status, new_status)
        return True

    def on_status_change(self, callback: Callable[[TaskStatus, TaskStatus], Awaitable[None]]) -> None:
        self._callbacks.append(callback)
