import asyncio
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict
from ._base import ConfigLoader

if TYPE_CHECKING:
    from ..engine import AgentEngine

from ..utils.logging import get_logger

logger = get_logger(__name__)


class GlobalSetting(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, validate_assignment=True, extra="ignore"
    )
    tool_timeout: float | None = Field(
        default=None, description="Default timeout for tool execution"
    )
    backend: str = Field(
        default="LocalBackend",
        description="Backends provide file storage for deep agents",
    )
    default_model: str = Field(default="", description="Default LLM model")
    default_agent: str = Field(default="", description="Default agent name")
    usage_limit_usd: float | None = Field(
        default=None, description="Total budget limit in USD"
    )
    # refer to https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/usage.py
    # be default it is set as 50, not enough for many long tasks
    request_limit: int | None = Field(
        default=50, description="The maximum number of requests allowed to the model"
    )
    total_tokens_limit: int | None = Field(
        default=None,
        description="The maximum number of tokens allowed in requests and responses combined",
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalSetting":
        return cls.model_validate(data)

    def get_diff(self, data: Dict[str, Any]) -> Dict[str, Any]:
        validated_data = self.model_validate(data).model_dump(exclude_unset=True)

        diff = {}
        for key in type(self).model_fields:
            if key in validated_data:
                new_val = validated_data[key]
                if getattr(self, key) != new_val:
                    diff[key] = new_val
        return diff

    def apply_diff(self, diff: Dict[str, Any]):
        for key, value in diff.items():
            setattr(self, key, value)


class UsageTracker:
    """
    Core utility for real-time resource usage and budget enforcement.

    This tracker monitors consumption metrics (e.g., tokens, API costs, or runtime credits)
    against a dynamic quota threshold.

    NOTE: This is a foundational stub pre-allocated for downstream integration.
    """

    def __init__(self, get_limit_func: Callable[[], float]):
        """
        Initialize the dynamic usage tracker.

        Args:
            get_limit_func (Callable[[], float]): A synchronous callback to evaluate
                the current active budget limit, isolating quota policy changes
                from the tracking engine.
        """
        self._get_limit = get_limit_func
        self.current_usage: float = 0.0

    def ask_consume(self, amount: float) -> bool:
        if amount <= 0:
            return True
        limit = self._get_limit()
        # Fine-grained control: A limit value of `None` denotes an unbounded upper limit.
        if limit is None:
            self.current_usage += amount
            return True
        if self.current_usage + amount > limit:
            return False
        self.current_usage += amount
        return True

    @property
    def usage_limit(self) -> float | str:
        limit = self._get_limit()
        if limit is None:
            return "Unlimited"
        return limit

    @property
    def remaining(self) -> float | str:
        """Evaluate and return the residual budget capacity."""
        limit = self._get_limit()
        if limit is None:
            return "Unlimited"
        return max(0.0, limit - self.current_usage)

    def __repr__(self):
        limit = self._get_limit()
        limit_str = f"${limit:.2f}" if limit is not None else "∞"
        return f"<Usage: ${self.current_usage:.4f} / {limit_str}>"


class GlobalSettingHub:
    _is_initialized: bool = False
    _is_configured: bool = False

    def __init__(
        self,
        global_setting_paths: Optional[List[Path]] = None,
        engine: Optional["AgentEngine"] = None,
    ):
        self._setting_paths = global_setting_paths
        # NOTE: The instances managed here represent fundamental infrastructure utilities
        # (e.g., `usageTracker`, `backend`) rather than episodic execution clients like LLMs or MCPs.
        self._active_instances: Dict[str, Any] = {}
        self._current_setting: Dict[str, Any] = {}
        self._parent = engine

    @property
    def default_model(self):
        if hasattr(self._current_setting, "default_model"):
            return self._current_setting.default_model
        elif isinstance(self._current_setting, dict):
            return self._current_setting.get("default_model", "")
        else:
            return ""

    @property
    def default_agent(self):
        if hasattr(self._current_setting, "default_agent"):
            return self._current_setting.default_agent
        elif isinstance(self._current_setting, dict):
            return self._current_setting.get("default_agent", "")
        else:
            return ""

    @property
    def global_setting(self) -> GlobalSetting:
        return self._current_setting

    @property
    def active_instances(self) -> Dict[str, Any]:
        return self._active_instances

    def configure(self):
        if self._is_configured:
            return

        if self._setting_paths:
            self._current_setting = GlobalSetting.from_dict(
                ConfigLoader.load_from_paths(self._setting_paths)["_root"]
            )
        else:  # use the default settings
            self._current_setting = GlobalSetting()

        self._is_configured = True

    async def materialize(self):
        # 1. set up usage tracker
        if getattr(self._current_setting, "usage_limit_usd", None) is not None:
            usageTracker = UsageTracker(lambda: self._current_setting.usage_limit_usd)
            self._active_instances["usageTracker"] = usageTracker

        # 2. set up backend
        if getattr(self._current_setting, "backend", None) is not None:
            pass
            # TODO: implement DockerBackend

        if self._active_instances:
            self._is_initialized = True

    async def update_from_dict(self, data: Dict[str, Any]):
        diff = self._current_setting.get_diff(data)
        if not diff:
            return
        try:
            # Step 1: Execute domain side effects (e.g., asynchronous external API invocations)
            await self._on_settings_changed(diff)

            # # Step 2: Commit state changes, executed and applied the diff.
            self._current_setting.apply_diff(diff)

            # remember to invalid the runtime_cache
            self._parent.reset_runtime()
        except Exception as e:
            raise e

    async def _on_settings_changed(self, diff: Dict[str, Any]):
        tasks = []
        for field, new_val in diff.items():
            handler_name = f"_handle_{field}_change"
            if hasattr(self, handler_name):
                handler = getattr(self, handler_name)
                tasks.append(handler(new_val))

        if tasks:
            await asyncio.gather(*tasks)

    async def _handle_usage_limit_usd_change(self, new_val: float):
        await asyncio.sleep(0.2)  # TODO: for real business
        logger.info(f"Handleing usage_limit_usd change for: {new_val}")

    async def _handle_backend_change(self, new_val: str):
        await asyncio.sleep(0.1)  # TODO: for real business
        logger.info(f"Handleing backend change for: {new_val}")

    async def cleanup(self):
        self._active_instances.clear()
        self._current_setting = None  # BaseModel
        self._setting_paths = None
        self._parent = None
