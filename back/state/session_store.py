import asyncio
from abc import ABC, abstractmethod

from langchain_core.messages import BaseMessage

from ..types import SessionInfo
from .session_state import SessionState


class SessionStore(ABC):
    @abstractmethod
    async def save_session(self, session: SessionState) -> None: ...

    @abstractmethod
    async def load_session(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> None: ...

    @abstractmethod
    async def list_sessions(self, user_id: str = "") -> list[SessionInfo]: ...

    @abstractmethod
    async def save_messages(self, session_id: str, messages: list[BaseMessage]) -> None: ...

    @abstractmethod
    async def load_messages(self, session_id: str) -> list[BaseMessage]: ...


class InMemorySessionStore(SessionStore):
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}
        self._user_index: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()

    async def save_session(self, session: SessionState) -> None:
        async with self._lock:
            self._sessions[session.session_id] = session
            if session.user_id:
                sids = self._user_index.setdefault(session.user_id, [])
                if session.session_id not in sids:
                    sids.append(session.session_id)

    async def load_session(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session and session.user_id:
                sids = self._user_index.get(session.user_id, [])
                if session_id in sids:
                    sids.remove(session_id)
                    if not sids:
                        del self._user_index[session.user_id]

    async def list_sessions(self, user_id: str = "") -> list[SessionInfo]:
        async with self._lock:
            if user_id:
                sids = self._user_index.get(user_id, [])
                sessions = [self._sessions[sid] for sid in sids if sid in self._sessions]
            else:
                sessions = list(self._sessions.values())
        return [_session_to_info(s) for s in sessions]

    async def save_messages(self, session_id: str, messages: list[BaseMessage]) -> None:
        pass

    async def load_messages(self, session_id: str) -> list[BaseMessage]:
        session = self._sessions.get(session_id)
        return await session.get_messages() if session else []


def _session_to_info(session: SessionState) -> SessionInfo:
    return SessionInfo(
        session_id=session.session_id,
        user_id=session.user_id,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
        message_count=session.message_count,
        tool_call_count=session.tool_call_count,
        task_status=session.task.state.status if session.task else None,
        paused=session.paused,
    )
