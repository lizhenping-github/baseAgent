from typing import Any, Awaitable, Callable

from .base_task import BaseTask


class ChatTask(BaseTask):
    def __init__(
        self,
        task_id: str | None = None,
        execute_fn: Callable[[], Awaitable[Any]] | None = None,
    ):
        super().__init__(task_id)
        self._execute_fn = execute_fn

    async def execute(self) -> Any:
        if self._execute_fn:
            return await self._execute_fn()
        return None

    def set_execute_fn(self, fn: Callable[[], Awaitable[Any]]) -> None:
        self._execute_fn = fn
