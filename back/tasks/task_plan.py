import uuid
from typing import Literal

from .task_definition import TaskDefinition


class TaskPlan:
    def __init__(
        self,
        execution_mode: Literal["sequential", "parallel", "dag"] = "sequential",
        plan_id: str | None = None,
    ):
        self.plan_id = plan_id or str(uuid.uuid4())
        self.definitions: list[TaskDefinition] = []
        self.execution_mode = execution_mode
        self._name_index: dict[str, TaskDefinition] = {}

    def add_task(self, definition: TaskDefinition) -> None:
        if definition.name in self._name_index:
            raise ValueError(f"任务名称重复: {definition.name}")
        self.definitions.append(definition)
        self._name_index[definition.name] = definition

    def get_task(self, name: str) -> TaskDefinition | None:
        return self._name_index.get(name)

    def get_execution_order(self) -> list[list[TaskDefinition]]:
        if self.execution_mode == "sequential":
            return [[t] for t in self.definitions]
        if self.execution_mode == "parallel":
            return [self.definitions]
        return self._topological_sort()

    def _topological_sort(self) -> list[list[TaskDefinition]]:
        in_degree: dict[str, int] = {t.name: 0 for t in self.definitions}
        graph: dict[str, list[str]] = {t.name: [] for t in self.definitions}

        for task in self.definitions:
            for dep in task.dependencies:
                if dep in graph:
                    graph[dep].append(task.name)
                    in_degree[task.name] += 1

        result: list[list[TaskDefinition]] = []
        remaining = set(in_degree.keys())

        while remaining:
            layer = [name for name in remaining if in_degree[name] == 0]
            if not layer:
                raise ValueError("检测到循环依赖")

            layer_tasks = [self._name_index[name] for name in layer]
            layer_tasks.sort(key=lambda t: -t.priority)
            result.append(layer_tasks)

            for name in layer:
                remaining.remove(name)
                for child in graph[name]:
                    in_degree[child] -= 1

        return result

    def validate(self) -> bool:
        try:
            self._topological_sort()
            return True
        except ValueError:
            return False

    def get_dependencies_result_keys(self, task_name: str) -> list[str]:
        task = self._name_index.get(task_name)
        if not task:
            return []
        return [f"result_{dep}" for dep in task.dependencies]
