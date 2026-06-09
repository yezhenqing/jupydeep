from pathlib import Path
from importlib.metadata import version
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, TYPE_CHECKING
import pydantic_deep.bundled_skills as bundled
from pydantic_deep.toolsets.skills import Skill as SkillEntity, SkillsDirectory

from ._base import BaseComponent, ConfigLoader

if TYPE_CHECKING:
    from ..engine import AgentEngine

from ..utils.logging import get_logger

logger = get_logger(__name__)


class SkillConfig(BaseModel):
    """Single Skill configuration"""

    name: str = Field(..., description="Skill name")
    category: str = Field(..., min_length=1, description="The category of this skill")
    version: str = Field(default="v1.0.0", description="The version of this skill")
    description: str = Field(default="")
    base_dir: Path = Field(..., description="The root directory of this skill")
    enabled: bool = Field(default=True, description="flag to enable this skill")
    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillConfig":
        return cls(**data)


class SkillComponent(BaseComponent):
    def __init__(
        self,
        skill_setting_paths: Optional[List[Path]] = None,
        engine: Optional["AgentEngine"] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._setting_paths = skill_setting_paths
        self._current_settings: Dict[str, SkillConfig] = {}
        self._active_instances: Dict[str, SkillEntity] = {}
        self._parent = engine

    @property
    def skills(self):
        return self.getActiveSkills()

    def getActiveSkills(self) -> list[str]:
        return [key for key in self._active_instances]

    def getSkill(self, name):
        return self._active_instances.get(name, None)

    def configure(self):
        if self._is_configured:
            return

        bundled_skill_dir = Path(list(bundled.__path__)[0])
        for item_dir in bundled_skill_dir.iterdir():
            _name = item_dir.stem
            _version = f"v{version('pydantic-deep')}"
            _category = "pydantic-agent"
            _skill_key = "/".join([_category, _version, _name])
            self._current_settings[_skill_key] = SkillConfig.from_dict(
                {
                    "name": _name,
                    "category": _category,
                    "enabled": True,
                    "base_dir": str(bundled_skill_dir),
                }
            )

        if self._setting_paths:
            _raw_skill_settings = ConfigLoader.load_from_paths(self._setting_paths)[
                "skills"
            ]
            for key, val in _raw_skill_settings.items():
                _config = SkillConfig.from_dict(val)
                _skill_key = "/".join([_config.category, _config.version, key])
                self._current_settings[_skill_key] = _config

        if self._current_settings:
            self._is_configured = True
        logger.info(
            f"Skill Component - configure: {list(self._current_settings.keys())}"
        )

    async def materialize(self):
        if self._is_initialized:
            return
        try:
            _result_dict = await self.reload_skills(self._current_settings.keys())
            if any(skill.get("status") == "success" for skill in _result_dict.values()):
                self._is_initialized = True
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            logger.error(
                f"CRITICAL error in Skill materialize: {error_type} - {error_msg}"
            )

    async def update_from_dict(self, new_settings):
        """
        Returns:
            dict: {
                'status': 'success' or 'failed' or 'warning',
                'message': 'description',
                'details': {
                    'updated': [],
                    'removed': [],
                    'failed': []
                }
            }
        """
        _new_settings = {
            f"{val.get('category', 'default')}/{val.get('version', 'v1')}/{key}": val
            for key, val in new_settings.items()
        }

        _ignore_keys = [
            key
            for key in self._current_settings.keys()
            if key.startswith("pydantic-agent")
        ]
        _diff_settings = self.compute_diff(_new_settings, _ignore_keys)
        _updated_keys = {
            *_diff_settings.get("added", {}),
            *_diff_settings.get("changed", {}),
        }
        _removed_keys = _diff_settings.get("removed", {}).keys()

        _details = {"updated": [], "removed": [], "failed": []}

        valid_keys_to_reload = []
        for key in _updated_keys:
            try:
                self._current_settings[key] = SkillConfig.from_dict(_new_settings[key])
                valid_keys_to_reload.append(key)
            except Exception as e:
                logger.error(f"Setting conversion failed for {key}: {e}")
                _details["failed"].append(key)

        if valid_keys_to_reload:
            _reload_report = await self.reload_skills(valid_keys_to_reload)

            for name, info in _reload_report.items():
                if info.get("status") == "success":
                    _details["updated"].append(name)
                else:
                    _details["failed"].append(name)

        for key in _removed_keys:
            try:
                self._active_instances.pop(key, None)
                self._current_settings.pop(key, None)
                _details["removed"].append(key)
            except Exception as e:
                logger.error(f"Remove failed for {key}: {e}")
                _details["failed"].append(key)

        status = "success"
        if _details["failed"]:
            status = (
                "warning" if (_details["updated"] or _details["removed"]) else "failed"
            )

        updated_str = ", ".join(_details["updated"])
        removed_str = ", ".join(_details["removed"])
        failed_str = ", ".join(_details["failed"])

        message = f"Skill Update completed: [Updated: {updated_str or 'None'}] [Removed: {removed_str or 'None'}]"
        if _details["failed"]:
            message += f" [Failed: {failed_str}]"

        return {"status": status, "message": message, "details": _details}

    async def reload_skills(self, skill_keys: list[str]):
        """
        Refresh Skill instances

        Returns:
            dict: {
                'skill-1': {
                    'status': 'success' or 'failed',
                    'message': 'description',
                    'details': {}
                },
                'skill-2': {
                    'status': 'success' or 'failed',
                    'message': 'description',
                    'details': {}
                }
            }
        """
        _results = {}
        try:
            for _key in skill_keys:
                if _key not in self._current_settings:
                    _results[_key] = {
                        "status": "failed",
                        "message": f"Skill key {_key} not found in current settings",
                        "details": {},
                    }
                    continue

                _config = self._current_settings[_key]
                _source = SkillsDirectory(path=_config.base_dir)
                key_last_part = Path(_key).name
                for _name, _skill in _source.get_skills().items():
                    if Path(_name).stem == key_last_part:
                        if isinstance(_skill, SkillEntity):
                            self._active_instances[_key] = _skill
                            _results[_key] = {
                                "status": "success",
                                "message": "Skill is ready",
                                "details": {},
                            }
                        else:
                            _results[_key] = {
                                "status": "failed",
                                "message": "Skill failed to load",
                                "details": {},
                            }
            return _results
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in reload_skills: {error_msg}")
            return {
                name: {
                    "status": "failed",
                    "message": f"Critical error: {error_msg}",
                    "details": {},
                }
                for name in skill_keys
            }

    async def _internal_delete(self, key):
        """Clean up MCP-related resources when the cache entry is being deleted"""
        # Remove from active instances
        self._active_instances.pop(key, None)
        # Remove from current settings
        self._current_settings.pop(key, None)
        if self._parent:
            self._parent = None
