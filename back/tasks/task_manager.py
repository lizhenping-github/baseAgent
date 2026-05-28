import asyncio

from ..types import TaskStatus
from .base_task import BaseTask


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, BaseTask] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, task: BaseTask) -> str:
        async with self._lock:
            self._tasks[task.task_id] = task
        await task.start()
        return task.task_id

    async def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        await task.cancel()
        return True

    def get_task_status(self, task_id: str) -> TaskStatus | None:
        task = self._tasks.get(task_id)
        return task.state.status if task else None

    def list_tasks(self, status: TaskStatus | None = None) -> list[BaseTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.state.status == status]
        return tasks

    async def cleanup_finished(self) -> int:
        async with self._lock:
            to_remove = [tid for tid, t in self._tasks.items() if t.state.is_terminal]
            for tid in to_remove:
                del self._tasks[tid]
        return len(to_remove)
