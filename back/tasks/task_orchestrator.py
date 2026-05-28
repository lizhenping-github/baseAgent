import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..types import TaskPlanStatus, TaskStatus
from .base_task import BaseTask
from .task_plan import TaskPlan


@dataclass
class TaskResult:
    task_id: str
    task_name: str
    status: TaskStatus
    result: Any = None
    error: str | None = None


@dataclass
class OrchestratorResult:
    plan_id: str
    status: TaskPlanStatus
    task_results: list[TaskResult] = field(default_factory=list)
    final_result: Any = None
    execution_time: float = 0.0


class TaskOrchestrator:
    def __init__(
        self,
        max_parallel: int = 5,
        on_task_start: Callable[[str, str], None] | None = None,
        on_task_complete: Callable[[TaskResult], None] | None = None,
    ):
        self._max_parallel = max_parallel
        self._on_task_start = on_task_start
        self._on_task_complete = on_task_complete
        self._results: dict[str, Any] = {}
        self._task_instances: dict[str, BaseTask] = {}

    async def execute(
        self,
        plan: TaskPlan,
        task_factory: Callable[[str, dict[str, Any]], BaseTask],
    ) -> OrchestratorResult:
        start_time = time.time()
        task_results: list[TaskResult] = []
        self._results.clear()
        self._task_instances.clear()

        try:
            execution_order = plan.get_execution_order()
        except ValueError as e:
            return OrchestratorResult(
                plan_id=plan.plan_id,
                status=TaskPlanStatus.failed,
                task_results=[],
                execution_time=0.0,
            )

        all_tasks: list[BaseTask] = []
        for layer in execution_order:
            for task_def in layer:
                task = task_factory(task_def.task_type, task_def.parameters)
                task.task_id = f"{plan.plan_id}_{task_def.name}"
                self._task_instances[task_def.name] = task
                all_tasks.append(task)

        failed = False
        partial = False

        for layer in execution_order:
            layer_tasks = []
            for task_def in layer:
                task = self._task_instances[task_def.name]
                deps_results = {
                    dep: self._results.get(dep)
                    for dep in task_def.dependencies
                }
                layer_tasks.append((task_def, task, deps_results))

            if len(layer_tasks) == 1:
                result = await self._execute_single(layer_tasks[0])
                task_results.append(result)
                if result.status == TaskStatus.failed:
                    failed = True
                elif result.status == TaskStatus.killed:
                    partial = True
            else:
                layer_results = await self._execute_layer(layer_tasks)
                task_results.extend(layer_results)
                for r in layer_results:
                    if r.status == TaskStatus.failed:
                        failed = True
                    elif r.status == TaskStatus.killed:
                        partial = True

            if failed:
                break

        execution_time = time.time() - start_time
        status = TaskPlanStatus.completed
        if failed:
            status = TaskPlanStatus.failed
        elif partial:
            status = TaskPlanStatus.partial

        final_result = self._aggregate_results(task_results)

        return OrchestratorResult(
            plan_id=plan.plan_id,
            status=status,
            task_results=task_results,
            final_result=final_result,
            execution_time=execution_time,
        )

    async def _execute_single(
        self,
        task_info: tuple,
    ) -> TaskResult:
        task_def, task, deps_results = task_info

        if self._on_task_start:
            self._on_task_start(task.task_id, task_def.name)

        try:
            result = await task.start()
            self._results[task_def.name] = result

            task_result = TaskResult(
                task_id=task.task_id,
                task_name=task_def.name,
                status=task.state.status,
                result=result,
            )
        except Exception as e:
            task_result = TaskResult(
                task_id=task.task_id,
                task_name=task_def.name,
                status=TaskStatus.failed,
                error=str(e),
            )

        if self._on_task_complete:
            self._on_task_complete(task_result)

        return task_result

    async def _execute_layer(
        self,
        layer_tasks: list[tuple],
    ) -> list[TaskResult]:
        semaphore = asyncio.Semaphore(self._max_parallel)

        async def run_with_semaphore(task_info: tuple) -> TaskResult:
            async with semaphore:
                return await self._execute_single(task_info)

        tasks = [run_with_semaphore(t) for t in layer_tasks]
        return await asyncio.gather(*tasks)

    def _aggregate_results(self, task_results: list[TaskResult]) -> dict[str, Any]:
        return {
            r.task_name: {
                "status": r.status.value,
                "result": r.result,
                "error": r.error,
            }
            for r in task_results
        }

    async def cancel(self, plan_id: str) -> bool:
        cancelled = False
        for name, task in self._task_instances.items():
            if not task.state.is_terminal:
                await task.cancel()
                cancelled = True
        return cancelled

    def get_result(self, task_name: str) -> Any:
        return self._results.get(task_name)
