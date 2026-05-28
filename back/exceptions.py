class SessionError(Exception):
    pass


class SessionNotFoundError(SessionError):
    def __init__(self, session_id: str):
        super().__init__(f"会话不存在: {session_id}")
        self.session_id = session_id


class SessionBusyError(SessionError):
    def __init__(self, session_id: str):
        super().__init__(f"会话正在对话中: {session_id}")
        self.session_id = session_id
