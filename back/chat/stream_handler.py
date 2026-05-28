import json
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, AIMessageChunk

from ..types import ChunkType
from ..utils.text_utils import extract_and_format_function_calls


class StreamHandler:
    def __init__(self, push_chunk_fn, is_stop_fn=None):
        self._push_chunk = push_chunk_fn
        self._is_stop = is_stop_fn

    async def _is_stopped(self) -> bool:
        if self._is_stop:
            return await self._is_stop()
        return False

    async def handle_text_chunk(self, chunk: str) -> None:
        self._push_chunk(chunk, ChunkType.text)

    async def handle_think_chunk(self, chunk: str) -> None:
        self._push_chunk(chunk, ChunkType.think)

    async def process_stream(self, stream: AsyncIterator[AIMessageChunk]) -> AIMessage:
        content = ""
        tool_name = ""
        tool_args = ""
        tool_id = ""
        stop_stream = False

        async for chunk in stream:
            if await self._is_stopped():
                stop_stream = True
                break

            content += chunk.content
            if chunk.content:
                await self.handle_text_chunk(chunk.content)

            if chunk.tool_call_chunks and chunk.tool_call_chunks[0]:
                tc = chunk.tool_call_chunks[0]
                if tc.get("name"):
                    tool_id = tc.get("id", "")
                    tool_name = tc["name"]
                    tool_args = ""
                if tc.get("args"):
                    tool_args += tc["args"]

        ai_message = AIMessage(content=content)

        extra_tool_calls = extract_and_format_function_calls(content)
        if extra_tool_calls:
            if not ai_message.tool_calls:
                ai_message.tool_calls = []
            ai_message.tool_calls.extend(extra_tool_calls)
            ai_message.content = content.split("<function_calls>")[0]

        if tool_name and not stop_stream:
            if not ai_message.tool_calls:
                ai_message.tool_calls = []
            ai_message.tool_calls.insert(0, {
                "name": tool_name,
                "args": json.loads(tool_args) if tool_args else {},
                "id": tool_id,
                "type": "tool_call",
            })

        return ai_message
