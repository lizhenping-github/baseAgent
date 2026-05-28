from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from ..types import SkillDetailType, SkillStatus


class SkillMetadata(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)


class SkillDetail(BaseModel):
    content: Any
    detail_type: SkillDetailType = SkillDetailType.text


class SkillResult(BaseModel):
    content: str
    detail: SkillDetail
    status: SkillStatus
    skill_id: str | None = None


class SkillInvokeResult(BaseModel):
    to_skill: dict[str, Any]
    to_stream: SkillResult | None = None
    skill_name: str
    skill_id: str | None = None

    class Config:
        arbitrary_types_allowed = True


class ResourceReference(BaseModel):
    type: str
    name: str
    path: str
    content: str | None = None


class BaseSkill(BaseModel, ABC):
    skill_call_id: str | None = Field(default=None, exclude=True)
    skill_name: str = Field(default="", exclude=True)
    skill_id: str | None = Field(default=None, exclude=True)
    kwargs: dict[str, Any] = Field(default_factory=dict, exclude=True)
    loader: Any = Field(default=None, exclude=True)
    executor: Any = Field(default=None, exclude=True)

    def __init__(self, skill_name: str, **kwargs):
        super().__init__(**kwargs)
        self.skill_name = skill_name
        self.skill_id = kwargs.get("skill_id")
        self.kwargs = kwargs
        self.loader = kwargs.get("loader")
        self.executor = None

    def before_invoke(self) -> SkillResult | None:
        return None

    @abstractmethod
    def analyze_request(self, user_request: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def determine_execution_plan(self, analysis_result: dict[str, Any]) -> dict[str, Any]:
        pass

    async def invoke(self, user_request: str) -> SkillInvokeResult:
        try:
            if self.executor:
                result = self.executor.execute_skill(user_request)
                result.skill_id = self.skill_id
                return result

            analysis_result = self.analyze_request(user_request)
            execution_plan = self.determine_execution_plan(analysis_result)
            processed_plan = self._process_resource_references(execution_plan)

            return SkillInvokeResult(
                to_skill={
                    "analysis_result": analysis_result,
                    "execution_plan": processed_plan,
                    "skill_name": self.skill_name,
                },
                to_stream=SkillResult(
                    content=f"技能 {self.skill_name} 执行成功",
                    detail=SkillDetail(
                        content={"analysis_result": analysis_result, "execution_plan": processed_plan},
                        detail_type=SkillDetailType.json,
                    ),
                    status=SkillStatus.success,
                ),
                skill_name=self.skill_name,
                skill_id=self.skill_id,
            )
        except Exception as e:
            return SkillInvokeResult(
                to_skill={"error": str(e), "skill_name": self.skill_name},
                to_stream=SkillResult(
                    content=f"技能 {self.skill_name} 执行失败",
                    detail=SkillDetail(content=str(e), detail_type=SkillDetailType.text),
                    status=SkillStatus.error,
                ),
                skill_name=self.skill_name,
                skill_id=self.skill_id,
            )

    def _process_resource_references(self, execution_plan: dict[str, Any]) -> dict[str, Any]:
        if "instruction" in execution_plan and self.loader:
            execution_plan["instruction"] = self.loader.resolve_resource_placeholder(
                execution_plan["instruction"]
            )

        for resource in execution_plan.get("resource_access", []):
            if self.loader:
                try:
                    resource_ref = self.loader.load_resource(
                        resource.get("type"), resource.get("name")
                    )
                    if resource_ref:
                        resource["content"] = resource_ref.content
                except Exception as e:
                    resource["error"] = str(e)

        return execution_plan

    def get_resource(self, resource_type: str, resource_name: str) -> ResourceReference | None:
        if self.loader:
            try:
                return self.loader.load_resource(resource_type, resource_name)
            except Exception:
                pass
        return None

    def after_invoke(self, result: SkillInvokeResult) -> None:
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .skill_registry import _register_skill_class
        _register_skill_class(cls)
