import asyncio
import time

from langchain_core.messages import BaseMessage

from ..tasks.base_task import BaseTask


class SessionState:
    def __init__(self, session_id: str, user_id: str = ""):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at: float = time.time()
        self.last_active_at: float = time.time()
        self._message_list: list[BaseMessage] = []
        self.tool_call_count: int = 0
        self.task: BaseTask | None = None
        self._lock = asyncio.Lock()
        self._paused = False

    async def add_message(self, message: BaseMessage) -> None:
        async with self._lock:
            self._message_list.append(message)
            self.last_active_at = time.time()

    async def get_messages(self) -> list[BaseMessage]:
        async with self._lock:
            return list(self._message_list)

    async def set_messages(self, messages: list[BaseMessage]) -> None:
        async with self._lock:
            self._message_list = list(messages)
            self.last_active_at = time.time()

    async def reset(self) -> None:
        async with self._lock:
            self._message_list.clear()
            self.tool_call_count = 0
            self.last_active_at = time.time()

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        self._paused = value

    @property
    def message_count(self) -> int:
        return len(self._message_list)

    @property
    def is_idle(self) -> bool:
        return self.task is None or self.task.state.is_terminal
