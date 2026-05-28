import asyncio
import time
import uuid

from ..tasks.base_task import BaseTask
from ..tasks.task_manager import TaskManager
from ..types import SessionInfo, TaskStatus
from .session_state import SessionState
from .session_store import InMemorySessionStore, SessionStore, _session_to_info


class SessionManager:
    def __init__(
        self,
        store: SessionStore | None = None,
        ttl: int = 7200,
        cleanup_interval: int = 300,
    ):
        self._store = store or InMemorySessionStore()
        self._ttl = ttl
        self._cleanup_interval = cleanup_interval
        self._active_sessions: dict[str, SessionState] = {}
        self._task_manager = TaskManager()
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def create_session(self, user_id: str = "", session_id: str | None = None) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        session = SessionState(sid, user_id)
        async with self._lock:
            self._active_sessions[sid] = session
        await self._store.save_session(session)
        return session

    async def get_session(self, session_id: str) -> SessionState | None:
        async with self._lock:
            session = self._active_sessions.get(session_id)
        if session:
            return session
        session = await self._store.load_session(session_id)
        if session:
            async with self._lock:
                self._active_sessions[session_id] = session
        return session

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            session = self._active_sessions.pop(session_id, None)
        if not session:
            return False
        if session.task and not session.task.state.is_terminal:
            await session.task.cancel()
        await self._store.delete_session(session_id)
        return True

    async def list_sessions(self, user_id: str = "") -> list[SessionInfo]:
        return await self._store.list_sessions(user_id)

    async def register_task(self, task: BaseTask) -> BaseTask:
        async with self._lock:
            self._task_manager._tasks[task.task_id] = task
        return task

    async def remove_task(self, task_id: str) -> None:
        async with self._lock:
            self._task_manager._tasks.pop(task_id, None)

    async def get_task(self, task_id: str) -> BaseTask | None:
        return self._task_manager._tasks.get(task_id)

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self._cleanup_expired()
            await self._cleanup_terminal_tasks()

    async def _cleanup_expired(self) -> None:
        now = time.time()
        expired = []
        async with self._lock:
            for sid, session in self._active_sessions.items():
                if now - session.last_active_at > self._ttl and session.is_idle:
                    expired.append(sid)
        for sid in expired:
            await self.delete_session(sid)

    async def _cleanup_terminal_tasks(self) -> None:
        await self._task_manager.cleanup_finished()
