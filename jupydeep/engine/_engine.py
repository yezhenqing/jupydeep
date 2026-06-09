import asyncio
from pydantic import BaseModel
from typing import Dict, Any, Optional, Union

from ._base import BaseComponent, JupyterContext
from ._global import GlobalSettingHub
from ..utils import get_setting_paths
from ..agent import DeepAgentManager
from ._mcp import MCPComponent
from ._llm import LLMComponent
from ._skill import SkillComponent

from ..utils.logging import get_logger

logger = get_logger(__name__)


class RuntimeSummary(BaseModel):
    """
    Collect backend information for frontend usage
    """

    default_model: str | None = None
    default_agent: str | None = None
    agents: Dict[str, Any] = {}
    mcps: list[str] = []
    llms: list[str] = []
    skills: list[str] = []
    usage_limit: Optional[Union[float, str]] = None


class _RuntimeView:
    __slots__ = ("_engine",)

    def __init__(self, engine: "AgentEngine"):
        self._engine = engine

    @property
    def agents(self) -> dict[str, dict]:
        agent_manager = self._engine.agent_manager
        agent_info = {}
        for _name in agent_manager._agent_instances.keys():
            _config = agent_manager._agent_configs[_name]
            agent_info[_name] = _config.opts.model_dump(mode="json")
        return agent_info

    @property
    def mcps(self) -> list[str]:
        mcp_comp = self._engine._components.get("mcp", None)
        return mcp_comp.get_mcp_names()

    @property
    def llms(self) -> list[str]:
        llm_comp = self._engine.getComponent("llm")
        _llms = []
        if llm_comp:
            _llms = llm_comp.getActiveLLMs()
        return _llms

    @property
    def skills(self) -> list[str]:
        skill_comp = self._engine.getComponent("skill")
        _skills = []
        if skill_comp:
            _skills = skill_comp.getActiveSkills()
        return _skills

    @property
    def default_model(self) -> Optional[str]:
        return self._engine.global_setting_hub.default_model

    @property
    def default_agent(self) -> Optional[str]:
        return self._engine.global_setting_hub.default_agent

    @property
    def usage_limit(self) -> float | str | None:
        hub_active_instances = self._engine.global_setting_hub.active_instances
        if hub_active_instances:
            usageTracker = hub_active_instances.get("usageTracker")
            if usageTracker:
                return usageTracker.usage_limit
            else:
                return None

    def to_dict(self) -> Dict[str, Any]:
        return self.get_summary().model_dump()

    def get_summary(self) -> RuntimeSummary:
        # Return a Pydantic object instead of a plain dict
        return RuntimeSummary(
            default_model=self.default_model,
            default_agent=self.default_agent,
            agents=self.agents,
            mcps=self.mcps,
            llms=self.llms,
            skills=self.skills,
            usage_limit=self.usage_limit,
        )


class AgentEngine:
    _instance = None
    _lock = asyncio.Lock()
    _global_setting_hub: Optional[GlobalSettingHub] = None
    _jupyter_context: Optional[JupyterContext] = None
    _components: Dict[str, BaseComponent] = {}
    _deep_agent_manager: Optional[DeepAgentManager] = None
    _is_initialized: bool = False
    _is_configured: bool = False

    _runtime_cache = None

    @classmethod
    def get_instance(cls) -> "AgentEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def runtime(self):
        # return _RuntimeView(self)
        if self._runtime_cache is None:
            self._runtime_cache = _RuntimeView(self)
        return self._runtime_cache

    def reset_runtime(self):
        self._runtime_cache = None

    @property
    def global_setting_hub(self) -> Optional[GlobalSettingHub]:
        return self._global_setting_hub

    @property
    def agent_manager(self) -> Optional[DeepAgentManager]:
        return self._deep_agent_manager

    @property
    def jupyter_context(self) -> Optional[JupyterContext]:
        return self._jupyter_context

    def load_context(self, jupyter_context):
        """
        Prepare the component's structural environment by mapping context and infrastructure paths.

        NOTE: This method strictly initializes the structural boundaries of the component objects;
        it does not trigger configuration binding (intent declaration) or runtime object materialization.
        """
        self._jupyter_context = jupyter_context

        # 1. Global setting hub
        global_setting_paths = get_setting_paths(
            jupyter_context.setting_json_dirs, prefix="global"
        )
        self._global_setting_hub = GlobalSettingHub(global_setting_paths, self)

        # 2. LLM model component
        llm_setting_paths = get_setting_paths(
            jupyter_context.setting_json_dirs, prefix="llm"
        )
        llm_component = LLMComponent(llm_setting_paths, self)
        self.register("llm", llm_component)

        # 3. MCP component
        mcp_setting_paths = get_setting_paths(
            jupyter_context.setting_json_dirs, prefix="mcp"
        )
        mcp_component = MCPComponent(mcp_setting_paths, self)
        self.register("mcp", mcp_component)

        # 4. Skill component
        skill_setting_paths = get_setting_paths(
            jupyter_context.setting_json_dirs, prefix="skill"
        )
        skill_component = SkillComponent(skill_setting_paths, self)
        self.register("skill", skill_component)

        # 5. DeepAgent Manager
        agent_spec_paths = jupyter_context.agent_spec_dirs
        deep_opts_paths = get_setting_paths(
            jupyter_context.setting_json_dirs, prefix="agent"
        )
        self._deep_agent_manager = DeepAgentManager(
            spec_dirs=agent_spec_paths,
            opts_paths=deep_opts_paths,
            jupyter_context=jupyter_context,
            engine=self,
        )

    def configure(self):
        if self._is_configured:
            return

        # 1. globalsetting hub
        if self._global_setting_hub:
            self._global_setting_hub.configure()

        # 2. multi components
        for _, comp in self._components.items():
            comp.configure()

        # 3. AgentManager
        if self._deep_agent_manager:
            self._deep_agent_manager.configure()

        self._is_configured = True

    async def materialize(self):
        async with self._lock:
            try:
                await self._global_setting_hub.materialize()
                tasks = [comp.materialize() for _, comp in self._components.items()]
                await asyncio.gather(*tasks, return_exceptions=True)
                await self._deep_agent_manager.materialize()
            except Exception as e:
                logger.error(
                    f"Failed to materialize AgentEngine: {str(e)}", exc_info=True
                )
                raise

    def register(self, name: str, component: BaseComponent):
        self._components[name] = component

    def getComponent(self, name: str) -> Optional[BaseComponent]:
        return self._components.get(name, None)

    """
    async def update_global_settings(self, setting: Dict[str, Any]):
        async with self._lock:
            for key, val in setting.items():
                self._globalSetting[key] = val
    """

    async def shutdown(self):
        async with self._lock:
            if self._global_setting_hub:
                await self._global_setting_hub.cleanup()

            tasks = [comp.shutdown() for comp in self._components.values()]
            await asyncio.gather(*tasks)

            # clean agent manager
            if self._deep_agent_manager:
                await self._deep_agent_manager.cleanup()
