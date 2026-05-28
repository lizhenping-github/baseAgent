import os
import re
from typing import Any

from .base_skill import ResourceReference, SkillMetadata


class SkillLoader:
    def __init__(self, skill_dir: str):
        self.skill_dir = skill_dir
        self.metadata: SkillMetadata | None = None
        self._resources: dict[str, ResourceReference] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        skill_md = os.path.join(self.skill_dir, "skill.md")
        if not os.path.exists(skill_md):
            return
        with open(skill_md, encoding="utf-8") as f:
            content = f.read()
        name_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        desc_match = re.search(r'^##\s+描述\s*\n(.+)', content, re.MULTILINE)
        self.metadata = SkillMetadata(
            name=name_match.group(1).strip() if name_match else os.path.basename(self.skill_dir),
            description=desc_match.group(1).strip() if desc_match else "",
        )

    def load_resource(self, resource_type: str, resource_name: str) -> ResourceReference | None:
        key = f"{resource_type}:{resource_name}"
        if key in self._resources:
            return self._resources[key]

        resource_dir = os.path.join(self.skill_dir, "references")
        if not os.path.exists(resource_dir):
            return None

        for fname in os.listdir(resource_dir):
            if fname.startswith(resource_name):
                fpath = os.path.join(resource_dir, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                ref = ResourceReference(type=resource_type, name=resource_name, path=fpath, content=content)
                self._resources[key] = ref
                return ref
        return None

    def resolve_resource_placeholder(self, instruction: str) -> str:
        pattern = r'\{\{resource:(\w+):(\w+)\}\}'

        def _replace(match: re.Match) -> str:
            rtype, rname = match.group(1), match.group(2)
            ref = self.load_resource(rtype, rname)
            return ref.content if ref else match.group(0)

        return re.sub(pattern, _replace, instruction)


class SkillExecutionConfig:
    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
        verbose: bool = False,
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.verbose = verbose


class SkillExecutor:
    def __init__(self, loader: SkillLoader, skill_name: str, config: SkillExecutionConfig | None = None):
        self.loader = loader
        self.skill_name = skill_name
        self.config = config or SkillExecutionConfig()

    def analyze_request(self, user_request: str) -> dict[str, Any]:
        return {
            "user_request": user_request,
            "request_type": "general",
            "needs_resource": False,
            "resource_needs": [],
        }

    def determine_execution_plan(self, analysis_result: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool_calls": [],
            "execution_steps": [],
            "resource_access": [],
        }

    def execute_skill(self, user_request: str) -> Any:
        from .base_skill import (
            SkillDetail,
            SkillDetailType,
            SkillInvokeResult,
            SkillResult,
            SkillStatus,
        )

        analysis = self.analyze_request(user_request)
        plan = self.determine_execution_plan(analysis)

        return SkillInvokeResult(
            to_skill={"analysis_result": analysis, "execution_plan": plan, "skill_name": self.skill_name},
            to_stream=SkillResult(
                content=f"技能 {self.skill_name} 执行成功",
                detail=SkillDetail(content={"analysis_result": analysis, "execution_plan": plan}, detail_type=SkillDetailType.json),
                status=SkillStatus.success,
            ),
            skill_name=self.skill_name,
        )
