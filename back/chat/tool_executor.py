import inspect
import json

from langchain_core.messages import ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from ..constants import MAX_TOOL_ITERATIONS
from ..tools.base_tool import BaseTool
from ..tools.tool_registry import create_tool_instance
from ..tools.tool_result import ToolDetail, ToolResult, ToStreamResult
from ..types import ToolChoice, ToolDetailType, ToolStatus
from ..utils.text_utils import trim_excess_newlines
from .stream_handler import StreamHandler


class ToolExecutor:
    @staticmethod
    async def execute_tool(
        tool: BaseTool,
        push_chunk_fn=None,
        on_invoke_hook=None,
        on_instance_hook=None,
        telemetry=None,
    ) -> ToolMessage:
        tool_message_content = ""
        tool_message_artifact = ""
        ok = True
        error = None

        tool_span = None
        if telemetry:
            tool_span = telemetry.tool_span(tool)

        try:
            if on_instance_hook:
                on_instance_hook(tool)

            before_result = tool.before_invoke()
            if before_result and push_chunk_fn:
                ToolExecutor._push_tool_stream(before_result, push_chunk_fn)

            invoke_result = tool.invoke()
            if inspect.isawaitable(invoke_result):
                invoke_result = await invoke_result

            if on_invoke_hook:
                on_invoke_hook(tool, invoke_result)

            if isinstance(invoke_result.to_tool, object) and hasattr(invoke_result.to_tool, "model_dump_json"):
                tool_message_content = invoke_result.to_tool.model_dump_json()
            else:
                tool_message_content = str(invoke_result.to_tool)

            if invoke_result.to_stream:
                tool_message_artifact = invoke_result.to_stream.model_dump_json()
                if push_chunk_fn:
                    ToolExecutor._push_tool_stream(invoke_result.to_stream, push_chunk_fn)
            else:
                tool_message_artifact = ""

        except Exception as e:
            ok = False
            error = str(e)
            tool_message_content = f"调用工具失败：{e}"
            tool_result = ToolResult(
                content="调用工具失败",
                detail=ToolDetail(content=f"{e}", detail_type=ToolDetailType.text),
                state=ToolStatus.error,
                tool_id=tool.tool_call_id,
            )
            tool_message_artifact = tool_result.model_dump_json()
            if push_chunk_fn:
                ToolExecutor._push_tool_stream(tool_result, push_chunk_fn)

        tool_message = ToolMessage(
            tool_call_id=tool.tool_call_id,
            content=tool_message_content,
            artifact=tool_message_artifact,
        )

        if tool_span:
            tool_span.finish(tool_message, ok=ok, error=error)

        return tool_message

    @staticmethod
    def _push_tool_stream(value: ToStreamResult, push_chunk_fn) -> None:
        temp = value.content
        if hasattr(temp, "model_dump_json"):
            temp = temp.model_dump_json()
        elif not isinstance(temp, str):
            temp = json.dumps(temp, ensure_ascii=False)
        push_chunk_fn(chunk=temp, chunk_type=value.type)

    @staticmethod
    async def execute_tool_loop(
        model,
        message_list: list,
        tool_list: list[type[BaseTool]],
        push_chunk_fn=None,
        is_stop_fn=None,
        save_message_fn=None,
        tool_choice: ToolChoice = ToolChoice.auto,
        max_iterations: int = MAX_TOOL_ITERATIONS,
        telemetry=None,
        on_invoke_hook=None,
        on_instance_hook=None,
        on_tool_call_fn=None,
    ) -> None:
        bound_model = model.bind_tools(
            [convert_to_openai_tool(t) for t in tool_list],
            tool_choice=tool_choice,
        )

        iteration = 0
        while iteration < max_iterations:
            if is_stop_fn and await is_stop_fn():
                break
            iteration += 1

            stream = bound_model.astream(message_list)
            handler = StreamHandler(push_chunk_fn, is_stop_fn)
            ai_message = await handler.process_stream(stream)

            ai_message.content = trim_excess_newlines(ai_message.content)
            message_list.append(ai_message)
            if save_message_fn:
                await save_message_fn(ai_message)

            if not ai_message.tool_calls:
                break

            if is_stop_fn and await is_stop_fn():
                break

            for tool_call in ai_message.tool_calls:
                try:
                    tool = create_tool_instance(tool_call.get("name"), tool_call.get("args"))
                    if tool is None:
                        raise Exception(f"工具参数验证失败：{tool_call.get('name')}")
                    tool.tool_call_id = tool_call.get("id")
                    tool_message = await ToolExecutor.execute_tool(
                        tool, push_chunk_fn, on_invoke_hook, on_instance_hook, telemetry
                    )
                    if on_tool_call_fn:
                        await on_tool_call_fn()
                    message_list.append(tool_message)
                    if save_message_fn:
                        await save_message_fn(tool_message)
                except Exception as e:
                    tool_result = ToolResult(
                        content="工具调用异常",
                        detail=ToolDetail(f"{e}"),
                        state=ToolStatus.error,
                        tool_id=tool_call.get("id"),
                    )
                    if push_chunk_fn:
                        ToolExecutor._push_tool_stream(tool_result, push_chunk_fn)
                    tool_msg = ToolMessage(
                        tool_call_id=tool_call.get("id"),
                        content=f"工具调用异常：{e}",
                        artifact=tool_result.model_dump_json(),
                    )
                    message_list.append(tool_msg)
                    if save_message_fn:
                        await save_message_fn(tool_msg)
