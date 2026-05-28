from typing import Any, Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from .base_task import BaseTask


ANALYSIS_SYSTEM_PROMPT = """你是一个数据分析专家。请分析给定的输入，并提供结构化的分析结果。

分析要点：
1. 识别关键信息和模式
2. 提取相关数据
3. 总结分析结论
4. 提供后续建议

请以清晰的格式输出分析结果。
"""


class AnalysisTask(BaseTask):
    def __init__(
        self,
        task_id: str | None = None,
        input_data: str | None = None,
        analysis_fn: Callable[[str], Awaitable[Any]] | None = None,
        model=None,
    ):
        super().__init__(task_id)
        self._input_data = input_data
        self._analysis_fn = analysis_fn
        self._model = model

    def set_input(self, input_data: str) -> None:
        self._input_data = input_data

    def set_model(self, model) -> None:
        self._model = model

    async def execute(self) -> Any:
        if self._analysis_fn:
            return await self._analysis_fn(self._input_data or "")

        if self._model and self._input_data:
            messages = [
                SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
                HumanMessage(content=self._input_data),
            ]
            response = await self._model.ainvoke(messages)
            return response.content

        return {"input": self._input_data, "analysis": "未配置分析模型"}
