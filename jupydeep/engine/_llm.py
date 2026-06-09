import asyncio
from pathlib import Path
from typing import Dict, Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.models import Model as LLMModelEntity

from ._base import BaseComponent, ConfigLoader

if TYPE_CHECKING:
    from ..engine import AgentEngine

from ..utils.logging import get_logger

logger = get_logger(__name__)


class LLMModelConfig(BaseModel):
    """Single LLM Model configuration"""

    name: str = Field(..., description="Model name")
    provider: str = Field(..., description="Model provider")
    temperature: float = Field(
        default=0.2, ge=0, le=2, description="Controls randomness, range 0-1"
    )
    top_p: float = Field(
        default=0.9, ge=0, le=1.0, description="Nucleus sampling threshold, range 0-1"
    )

    llm_api_key: str = Field(default="", alias="api_key", description="API key")
    llm_api_base: str = Field(default="", alias="api_base", description="API base URL")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
    )

    @classmethod
    def from_dict(cls, data: dict) -> "LLMModelConfig":
        return cls(**data)


class LLMComponent(BaseComponent):
    def __init__(
        self,
        llm_setting_paths: Optional[List[Path]] = None,
        engine: Optional["AgentEngine"] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._setting_paths = llm_setting_paths  # single json file
        self._current_settings: Dict[str, LLMModelConfig] = {}
        self._active_instances: Dict[str, LLMModelEntity] = {}
        self._parent = engine

    @property
    def llms(self):
        return self.getActiveLLMs()

    def getActiveLLMs(self) -> list[str]:
        active_keys = [key for key in self._active_instances]
        return list(dict.fromkeys(active_keys))

    def getModel(self, name):
        return self._active_instances.get(name, None)

    def configure(self):
        if self._is_configured:
            return

        if self._setting_paths:
            _raw_llm_settings = ConfigLoader.load_from_paths(self._setting_paths)[
                "llmModels"
            ]
            for key, val in _raw_llm_settings.items():
                self._current_settings[key] = LLMModelConfig.from_dict(val)
        if self._current_settings:
            self._is_configured = True

    async def materialize(self):
        if self._is_initialized:
            return
        try:
            _loaded_models = await self.reload_models(self._current_settings.keys())

            if _loaded_models and self._active_instances:
                self._is_initialized = True
                # Run post-initialization tasks that depend on LLM
                await self.post_initialize()
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(
                f"CRITICAL error in LLM materialize: {error_msg}"
            )

    async def _create_llm_model(self, name, config):
        provider = OpenAIProvider(
            api_key=config.llm_api_key or "no-need",
            base_url=config.llm_api_base or None,
        )
        settings = ModelSettings(
            temperature=float(config.temperature),
            top_p=float(config.top_p),
            # max_tokens=int(config.max_tokens),
        )
        model = OpenAIChatModel(
            model_name=config.name, provider=provider, settings=settings
        )
        return model

    async def _validate_llm_client(
        self, name: str, model: LLMModelEntity | str
    ) -> bool:
        """
        Validate if the LLM client is available

        Returns: {'status': bool, 'message': str}
        """
        try:
            agent = Agent(
                model=model,
                output_type=bool,
                system_prompt="You are a connectivity test assistant, return with True or False.",
            )

            # Set timeout to avoid infinite blocking
            result = await asyncio.wait_for(
                agent.run(
                    "Connection test to LLM available, respond with True if you can connect successfully."
                ),
                timeout=30.0,
            )

            if result.output:
                logger.info(f"LLM '{name}' connection test succeeded")
                return {"status": True, "message": "Connection successful"}
            else:
                logger.warning(f"LLM '{name}' connection test returned False")
                return {
                    "status": False,
                    "message": "LLM Model returned False during validation",
                }

        except asyncio.TimeoutError:
            msg = "Validation timeout after 30 seconds"
            logger.error(f"LLM '{name}: ' {msg}")
            return {"status": False, "message": msg}
        except Exception as e:
            msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            logger.error(f"LLM '{name}' validation failed: {msg}")
            return {"status": False, "message": msg}

    async def update_from_dict(self, new_settings):
        """
        Returns:
            dict: {
                'status': 'success' or 'failed' or 'warning',
                'message': 'relevant information',
                'details': {
                    'updated': [],
                    'removed': [],
                    'failed': []
                }
            }
        """
        _diff_settings = self.compute_diff(new_settings)

        _updated_keys = {
            *_diff_settings.get("added", {}),
            *_diff_settings.get("changed", {}),
        }

        _removed_keys = _diff_settings.get("removed", {}).keys()

        _details = {"updated": [], "removed": [], "failed": []}

        valid_keys_to_reload = []
        for key in _updated_keys:
            try:
                self._current_settings[key] = LLMModelConfig.from_dict(
                    new_settings[key]
                )
                valid_keys_to_reload.append(key)
            except Exception as e:
                logger.error(f"Setting conversion failed for {key}: {e}")
                _details["failed"].append(key)

        if valid_keys_to_reload:
            _reload_report = await self.reload_models(valid_keys_to_reload)

            # The reload_report format here is { 'name': {'status': 'success', ...} }
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

        message = f"LLM Update completed: [Updated: {updated_str or 'None'}] [Removed: {removed_str or 'None'}]"
        if _details["failed"]:
            message += f" [Failed: {failed_str}]"

        # Ensure proper initialization state before return
        if not self._is_initialized:
            # it means the system has not been successfully initialized
            await self.post_initialize()
        elif not self._active_instances:
            # Handle de-initialization when no active LLM instances remain
            await self.de_initialize()
            self._is_initialized = False

        return {"status": status, "message": message, "details": _details}

    async def reload_models(self, model_keys: list[str]):
        """
        Refresh model instances

        Returns:
            dict: {
                'model-1': {
                    'status': 'success' or 'failed',
                    'message': 'description',
                    'details': {}
                },
                'model-2': {
                    'status': 'success' or 'failed',
                    'message': 'description',
                    'details': {}
                }
            }
        """
        _results = {}
        try:
            logger.info(f"Start to reload models: {model_keys}")
            _tasks, _llms, _names = [], [], []

            for _name in model_keys:
                if _name not in self._current_settings:
                    _results[_name] = {
                        "status": "failed",
                        "message": "Model not found in settings",
                        "details": {},
                    }
                    continue

                try:
                    _config = self._current_settings[_name]
                    _inst = await self._create_llm_model(_name, _config)
                    if _inst:
                        _tasks.append(self._validate_llm_client(_name, _inst))
                        _llms.append(_inst)
                        _names.append(_name)
                    else:
                        _results[_name] = {
                            "status": "failed",
                            "message": "Failed to create LLM client instance",
                            "details": {},
                        }
                except Exception as e:
                    _results[_name] = {
                        "status": "failed",
                        "message": f"Creation error: {str(e)}",
                        "details": {},
                    }

            if not _tasks:
                return _results

            _validations = await asyncio.gather(*_tasks, return_exceptions=True)

            for _name, _llm, _res in zip(_names, _llms, _validations):
                if isinstance(_res, Exception):
                    _results[_name] = {
                        "status": "failed",
                        "message": f"Validation error: {str(_res)}",
                        "details": {},
                    }
                elif isinstance(_res, dict) and _res.get("status") is True:
                    self._active_instances[_name] = _llm
                    _results[_name] = {
                        "status": "success",
                        "message": "Model is ready",
                        "details": {},
                    }
                else:
                    msg = (
                        _res.get("message")
                        if isinstance(_res, dict)
                        else "Validation failed"
                    )
                    _results[_name] = {
                        "status": "failed",
                        "message": msg,
                        "details": {},
                    }

            return _results

        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in reload_models: {error_msg}")
            return {
                name: {
                    "status": "failed",
                    "message": f"Critical error: {msg}",
                    "details": {},
                }
                for name in model_keys
            }

    async def post_initialize(self) -> None:
        """
        Set up system-level configurations that depend on LLM initialization.

        This includes setting globalSetting.default_model to an active LLM instance
        if no valid default model is currently configured.

        Returns:
            None
        """
        global_setting = self._parent.global_setting_hub.global_setting
        default_model = global_setting.default_model

        if not default_model:
            # Assign the first available LLM as default model
            global_setting.default_model = self.getActiveLLMs()[0]

        agentManager = self._parent.agent_manager
        if agentManager._is_configured and not agentManager._is_initialized:
            # configurated but not materialized
            await agentManager.materialize()

    async def de_initialize(self) -> None:
        """
        Clear system-level configurations during de-initialization.

        Removes the default_model reference to prevent stale LLM instance usage
        after active instances have been removed.

        Returns:
            None
        """
        global_setting = self._parent.global_setting_hub.global_setting
        default_model = global_setting.default_model

        if default_model:
            global_setting.default_model = ""

        # agentManager also need to be set as not initialized
        agentManager = self._parent.agent_manager
        agentManager._is_initialized = False

    async def _internal_delete(self, key):
        """Clean up LLM-related resources when the cache entry is being deleted"""
        # Remove from active instances
        self._active_instances.pop(key, None)
        # Remove from current settings
        self._current_settings.pop(key, None)
        if self._parent:
            self._parent = None
