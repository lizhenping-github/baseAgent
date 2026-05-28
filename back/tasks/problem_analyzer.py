import json
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from .task_definition import TaskDefinition
from .task_plan import TaskPlan


ANALYSIS_PROMPT = """你是一个任务分析专家。你的职责是将用户的复杂问题分解为可执行的子任务。

请分析用户的问题，并输出一个任务分解计划。

输出格式（JSON）：
```json
{
    "execution_mode": "sequential|parallel|dag",
    "tasks": [
        {
            "name": "任务名称（英文，唯一标识）",
            "description": "任务描述",
            "task_type": "chat|analysis|tool",
            "parameters": {"参数key": "参数value"},
            "dependencies": ["依赖的任务名称"],
            "priority": 0
        }
    ]
}
```

任务类型说明：
- chat: 对话任务，用于生成回答
- analysis: 分析任务，用于数据处理和分析
- tool: 工具任务，用于执行特定操作

执行模式说明：
- sequential: 串行执行，任务按顺序依次执行
- parallel: 并行执行，所有任务同时执行
- dag: 按依赖关系执行，支持复杂的依赖图

注意：
1. 任务名称必须唯一且为英文
2. dependencies 中的任务名称必须存在
3. 不要创建循环依赖
4. 合理设置优先级（数值越大越优先）

用户问题：
{user_input}

上下文：
{context}
"""


class ProblemAnalyzer:
    def __init__(self, model, max_retries: int = 3):
        self._model = model
        self._max_retries = max_retries

    async def analyze(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
        execution_mode: Literal["sequential", "parallel", "dag"] = "dag",
    ) -> TaskPlan:
        context_str = json.dumps(context, ensure_ascii=False) if context else "无"
        prompt = ANALYSIS_PROMPT.format(
            user_input=user_input,
            context=context_str,
        )

        messages = [
            SystemMessage(content="你是一个任务分析专家，请严格按照JSON格式输出。"),
            HumanMessage(content=prompt),
        ]

        for _ in range(self._max_retries):
            try:
                response = await self._model.ainvoke(messages)
                plan = self._parse_response(response.content, execution_mode)
                if plan and plan.validate():
                    return plan
            except Exception:
                continue

        return self._create_default_plan(user_input, execution_mode)

    def _parse_response(
        self,
        content: str,
        default_mode: str,
    ) -> TaskPlan | None:
        try:
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                return None

            json_str = content[json_start:json_end]
            data = json.loads(json_str)

            mode = data.get("execution_mode", default_mode)
            plan = TaskPlan(execution_mode=mode)

            for task_data in data.get("tasks", []):
                task_def = TaskDefinition(
                    name=task_data.get("name", ""),
                    description=task_data.get("description", ""),
                    task_type=task_data.get("task_type", "chat"),
                    parameters=task_data.get("parameters", {}),
                    dependencies=task_data.get("dependencies", []),
                    priority=task_data.get("priority", 0),
                )
                plan.add_task(task_def)

            return plan
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _create_default_plan(
        self,
        user_input: str,
        execution_mode: str,
    ) -> TaskPlan:
        plan = TaskPlan(execution_mode=execution_mode)
        plan.add_task(TaskDefinition(
            name="analyze",
            description="分析用户问题",
            task_type="analysis",
            parameters={"input": user_input},
            dependencies=[],
            priority=10,
        ))
        plan.add_task(TaskDefinition(
            name="respond",
            description="生成回答",
            task_type="chat",
            parameters={"input": user_input},
            dependencies=["analyze"],
            priority=0,
        ))
        return plan

    async def decompose(
        self,
        problem: str,
        max_subtasks: int = 5,
    ) -> list[TaskDefinition]:
        plan = await self.analyze(problem)
        return plan.definitions[:max_subtasks]
