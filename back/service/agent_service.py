import asyncio
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sse_starlette import EventSourceResponse

from ..chat.context_compactor import ContextCompactor
from ..chat.prompt_builder import PromptBuilder
from ..chat.tool_executor import ToolExecutor
from ..constants import DEFAULT_MAX_TOKENS, MAX_CALL_TIMES
from ..exceptions import SessionBusyError, SessionNotFoundError
from ..memory.base_memory import BaseMemory
from ..state.base_flow import BaseFlow
from ..state.session_manager import SessionManager
from ..state.session_state import SessionState
from ..state.session_store import _session_to_info
from ..tasks.analysis_task import AnalysisTask
from ..tasks.chat_task import ChatTask
from ..tasks.problem_analyzer import ProblemAnalyzer
from ..tasks.task_orchestrator import OrchestratorResult, TaskOrchestrator
from ..tasks.task_plan import TaskPlan
from ..tools.base_tool import BaseTool
from ..types import ChunkType, SessionInfo, TaskStatus, ToolChoice


class AgentService:
    def __init__(
        self,
        model,
        tool_list: list[type[BaseTool]] | None = None,
        session_manager: SessionManager | None = None,
        enable_orchestration: bool = True,
    ):
        self._model = model
        self._tool_list = tool_list or []
        self._session_manager = session_manager or SessionManager()
        self._enable_orchestration = enable_orchestration
        self._orchestrator: TaskOrchestrator | None = None
        self._analyzer: ProblemAnalyzer | None = None

        if enable_orchestration:
            self._orchestrator = TaskOrchestrator()
            self._analyzer = ProblemAnalyzer(model)

    async def create_session(self, user_id: str = "") -> str:
        session = await self._session_manager.create_session(user_id)
        return session.session_id

    async def chat(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str = "",
        context: dict | None = None,
        memory: BaseMemory | None = None,
        tool_choice: ToolChoice = ToolChoice.auto,
        attachments: list[dict] | None = None,
    ) -> EventSourceResponse:
        session = await self._session_manager.get_session(session_id)
        if not session:
            raise SessionNotFoundError(session_id)

        if not session.is_idle:
            raise SessionBusyError(session_id)

        task = ChatTask()
        await self._session_manager.register_task(task)
        session.task = task
        await task.state.transition(TaskStatus.running)

        final_prompt = await PromptBuilder.build_final_prompt(system_prompt, context, memory)
        await session.add_message(SystemMessage(content=final_prompt))
        await session.add_message(HumanMessage(content=user_input))

        flow = BaseFlow()

        async def _is_stop():
            return session.task is not None and session.task.state.is_terminal

        async def run():
            try:
                iteration = 0
                while iteration < MAX_CALL_TIMES:
                    if await _is_stop():
                        break

                    messages = await session.get_messages()
                    messages = await ContextCompactor.auto_compact(messages, DEFAULT_MAX_TOKENS)
                    await session.set_messages(messages)

                    await ToolExecutor.execute_tool_loop(
                        model=self._model,
                        message_list=messages,
                        tool_list=self._tool_list,
                        push_chunk_fn=flow.add_chunk,
                        is_stop_fn=_is_stop,
                        save_message_fn=lambda msg: session.add_message(msg),
                        on_tool_call_fn=lambda: _increment_tool_count(session),
                        tool_choice=tool_choice,
                        telemetry=None,
                    )
                    iteration += 1

                    messages = await session.get_messages()
                    if not messages or not isinstance(messages[-1], AIMessage):
                        break

            except Exception as e:
                flow.add_chunk(f"对话失败: {str(e)}", ChunkType.text)
            finally:
                if not task.state.is_terminal:
                    await task.state.transition(TaskStatus.completed)
                await self._session_manager.remove_task(task.task_id)
                flow.close()

        asyncio.create_task(run())
        return EventSourceResponse(flow.get_chunk())

    async def stop_session(self, session_id: str) -> bool:
        session = await self._session_manager.get_session(session_id)
        if not session or not session.task:
            return False
        await session.task.cancel()
        return True

    async def delete_session(self, session_id: str) -> bool:
        return await self._session_manager.delete_session(session_id)

    async def get_session_info(self, session_id: str) -> SessionInfo | None:
        session = await self._session_manager.get_session(session_id)
        if not session:
            return None
        return _session_to_info(session)

    async def list_sessions(self, user_id: str = "") -> list[SessionInfo]:
        return await self._session_manager.list_sessions(user_id)

    async def get_chat_history(self, session_id: str) -> list[dict]:
        session = await self._session_manager.get_session(session_id)
        if not session:
            return []
        messages = await session.get_messages()
        return [_message_to_dict(m) for m in messages]

    async def get_task_status(self, task_id: str) -> TaskStatus | None:
        task = await self._session_manager.get_task(task_id)
        return task.state.status if task else None

    async def chat_with_orchestration(
        self,
        session_id: str,
        user_input: str,
        execution_mode: Literal["sequential", "parallel", "dag"] = "dag",
        context: dict | None = None,
        plan: TaskPlan | None = None,
    ) -> OrchestratorResult:
        if not self._orchestrator or not self._analyzer:
            raise RuntimeError("任务编排未启用，请在初始化时设置 enable_orchestration=True")

        session = await self._session_manager.get_session(session_id)
        if not session:
            raise SessionNotFoundError(session_id)

        if not session.is_idle:
            raise SessionBusyError(session_id)

        if plan is None:
            plan = await self._analyzer.analyze(user_input, context, execution_mode)

        def task_factory(task_type: str, params: dict) -> ChatTask | AnalysisTask:
            if task_type == "analysis":
                task = AnalysisTask(
                    input_data=params.get("input", user_input),
                    model=self._model,
                )
            else:
                task = ChatTask()
            return task

        result = await self._orchestrator.execute(plan, task_factory)
        return result

    async def analyze_problem(
        self,
        user_input: str,
        context: dict | None = None,
        execution_mode: Literal["sequential", "parallel", "dag"] = "dag",
    ) -> TaskPlan:
        if not self._analyzer:
            raise RuntimeError("任务编排未启用")

        return await self._analyzer.analyze(user_input, context, execution_mode)


def _increment_tool_count(session: SessionState) -> None:
    session.tool_call_count += 1


def _message_to_dict(message) -> dict:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    role = "unknown"
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, HumanMessage):
        role = "human"
    elif isinstance(message, AIMessage):
        role = "ai"
    elif isinstance(message, ToolMessage):
        role = "tool"

    return {
        "role": role,
        "content": message.content,
    }
