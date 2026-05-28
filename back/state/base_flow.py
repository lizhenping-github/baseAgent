import asyncio
import threading

from ..constants import STREAM_INTERVAL
from ..types import ChunkType


class BaseFlow:
    def __init__(self):
        self._chunk = ""
        self._end = False
        self._pre_chunk_type: ChunkType | None = None
        self._total_output = ""
        self._lock = threading.Lock()
        self._event = asyncio.Event()

    async def get_chunk(self):
        while True:
            with self._lock:
                has_chunk = len(self._chunk) > 0
                is_end = self._end
                chunk = self._chunk
                self._chunk = ""
            if has_chunk:
                yield chunk
            if is_end:
                break
            try:
                await asyncio.wait_for(self._event.wait(), timeout=STREAM_INTERVAL)
                self._event.clear()
            except asyncio.TimeoutError:
                pass

    def add_chunk(self, content: str, chunk_type: ChunkType = ChunkType.text) -> None:
        content = str(content)
        with self._lock:
            temp = ""
            if self._pre_chunk_type is None:
                temp += f"\n<{chunk_type.value}>\n"
            elif chunk_type != self._pre_chunk_type:
                temp += f"\n</{self._pre_chunk_type.value}>\n"
                temp += f"\n<{chunk_type.value}>\n"
            temp += content

            if chunk_type not in (ChunkType.think, ChunkType.text):
                temp += f"\n</{chunk_type.value}>\n"
                self._pre_chunk_type = None
            else:
                self._pre_chunk_type = chunk_type

            self._total_output += temp
            self._chunk += temp
        self._event.set()

    def close(self) -> None:
        with self._lock:
            if self._pre_chunk_type is not None:
                temp = f"\n</{self._pre_chunk_type.value}>\n"
                self._total_output += temp
                self._chunk += temp
                self._pre_chunk_type = None
            self._end = True
        self._event.set()
