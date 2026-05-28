import importlib.util
import os
import sys

from .base_skill import BaseSkill, SkillMetadata

_REGISTRY: dict[str, type[BaseSkill]] = {}


def _register_skill_class(cls: type[BaseSkill]) -> None:
    if cls.__name__ not in _REGISTRY:
        _REGISTRY[cls.__name__] = cls


def register_skill(name: str, metadata: SkillMetadata | None = None):
    def decorator(cls: type[BaseSkill]) -> type[BaseSkill]:
        if not issubclass(cls, BaseSkill):
            raise TypeError("Registered class must inherit from BaseSkill")
        if metadata:
            cls.metadata = metadata
        else:
            cls.metadata = SkillMetadata(name=name, description=f"{name} skill")
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_skill(name: str) -> type[BaseSkill] | None:
    return _REGISTRY.get(name)


def list_skills() -> dict[str, type[BaseSkill]]:
    return _REGISTRY.copy()


def create_skill_instance(skill_name: str, **kwargs) -> BaseSkill:
    if 'loader' not in kwargs:
        try:
            from .skill_loader import SkillLoader
            skill_dir = f'agent/skills/{skill_name}'
            if os.path.exists(skill_dir):
                kwargs['loader'] = SkillLoader(skill_dir)
        except Exception:
            pass

    skill_class = get_skill(skill_name)
    if not skill_class:
        return BaseSkill(skill_name, **kwargs)
    return skill_class(skill_name, **kwargs)


def load_skills_from_dir(directory: str) -> list[str]:
    loaded = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py") and not file.startswith("_"):
                module_path = os.path.join(root, file)
                module_name = os.path.splitext(os.path.basename(file))[0]
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    try:
                        spec.loader.exec_module(module)
                        for _name, obj in module.__dict__.items():
                            if (
                                isinstance(obj, type)
                                and issubclass(obj, BaseSkill)
                                and obj != BaseSkill
                                and hasattr(obj, "metadata")
                            ):
                                skill_name = obj.metadata.name
                                if skill_name not in _REGISTRY:
                                    _REGISTRY[skill_name] = obj
                                    loaded.append(skill_name)
                    except Exception as e:
                        print(f"加载技能模块失败 {module_name}: {e}")
    return loaded
