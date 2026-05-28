from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel as PydanticModel

from ..exceptions import SessionBusyError, SessionNotFoundError
from ..service.agent_service import AgentService
from ..types import ToolChoice

router = APIRouter(prefix="/agent", tags=["agent"])

_agent_service: AgentService | None = None


def init_agent_service(service: AgentService) -> None:
    global _agent_service
    _agent_service = service


def _get_service() -> AgentService:
    if _agent_service is None:
        raise RuntimeError("AgentService 未初始化，请先调用 init_agent_service()")
    return _agent_service


class SessionCreateRequest(PydanticModel):
    user_id: str = ""


class SessionDeleteRequest(PydanticModel):
    session_id: str


class ChatRequest(PydanticModel):
    session_id: str
    user_input: str
    system_prompt: str = ""
    context: dict | None = None
    tool_choice: str = "auto"
    attachments: list[dict] | None = None


class ChatStopRequest(PydanticModel):
    session_id: str


class CommandResultRequest(PydanticModel):
    session_id: str
    tool_call_id: str
    result: dict


@router.post("/session/create", summary="创建会话")
async def create_session(request: SessionCreateRequest):
    service = _get_service()
    session_id = await service.create_session(user_id=request.user_id)
    return {"success": True, "data": {"session_id": session_id}}


@router.get("/session/list", summary="会话列表")
async def list_sessions(user_id: str = ""):
    service = _get_service()
    sessions = await service.list_sessions(user_id)
    return {"success": True, "data": [asdict(s) for s in sessions]}


@router.get("/session/{session_id}", summary="会话详情")
async def get_session_info(session_id: str):
    service = _get_service()
    info = await service.get_session_info(session_id)
    if not info:
        return {"success": False, "message": "会话不存在"}
    return {"success": True, "data": asdict(info)}


@router.post("/session/delete", summary="删除会话")
async def delete_session(request: SessionDeleteRequest):
    service = _get_service()
    ok = await service.delete_session(request.session_id)
    return {"success": ok}


@router.get("/session/{session_id}/history", summary="对话历史")
async def get_chat_history(session_id: str):
    service = _get_service()
    history = await service.get_chat_history(session_id)
    return {"success": True, "data": history}


@router.post("/chat", summary="对话（SSE 流式）")
async def chat(request: ChatRequest):
    service = _get_service()
    tool_choice = ToolChoice(request.tool_choice)
    try:
        return await service.chat(
            session_id=request.session_id,
            user_input=request.user_input,
            system_prompt=request.system_prompt,
            context=request.context,
            tool_choice=tool_choice,
            attachments=request.attachments,
        )
    except SessionNotFoundError:
        return {"success": False, "message": "会话不存在"}
    except SessionBusyError:
        return {"success": False, "message": "会话正在对话中"}


@router.post("/chat/stop", summary="停止对话")
async def stop_chat(request: ChatStopRequest):
    service = _get_service()
    ok = await service.stop_session(request.session_id)
    return {"success": ok}


@router.get("/task/status", summary="任务状态")
async def get_task_status(task_id: str):
    service = _get_service()
    status = await service.get_task_status(task_id)
    if not status:
        return {"success": False, "message": "任务不存在"}
    return {"success": True, "data": {"task_id": task_id, "status": status.value}}


@router.post("/command/result", summary="接收命令执行结果")
async def receive_command_result(_request: CommandResultRequest):
    return {"success": True, "message": "命令执行结果已接收"}
