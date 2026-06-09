from pathlib import Path
from itertools import chain
from deepdiff import DeepDiff

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic_deep import create_deep_agent, DeepAgentDeps, LocalBackend
from pydantic_deep.toolsets.skills import SkillsToolset
from pydantic_deep import create_summarization_processor
from pydantic import BaseModel, Field, ConfigDict, model_validator, model_serializer
from pydantic_ai import AgentSpec, Agent

from ..engine._base import ConfigLoader
from ..utils.logging import get_logger

if TYPE_CHECKING:
    from ..engine import AgentEngine


import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

logger = get_logger(__name__)


class JupyterDeps(DeepAgentDeps):
    def __init__(self, jupyter_context, **kwargs):
        super().__init__(**kwargs)
        self.jupyter_context = jupyter_context


class CapabilityOpts(BaseModel):
    """
    Agent capablity options - refer to the Pydantic deep agents
    """

    model_config = ConfigDict(
        populate_by_name=True, validate_assignment=True, extra="ignore"
    )

    include_todo: bool = True
    include_filesystem: bool = True
    include_subagents: bool = True
    include_plan: bool = True
    include_liteparse: bool = True
    context_manager: bool = True
    web_search: bool = True
    web_fetch: bool = True

    # we don't handle these capabilities right now, for next TODO
    cost_tracking: bool = False
    include_checkpoints: bool = False
    include_teams: bool = False
    include_memory: bool = False


class DeepAgentOptions(BaseModel):
    """Config keys align with create_deep_agent parameters for easy unpacking"""

    model_config = ConfigDict(
        populate_by_name=True, validate_assignment=True, extra="ignore"
    )

    capabilities: CapabilityOpts = Field(default_factory=CapabilityOpts)

    # thinking: Literal["high", "medium", "low"] = Field(default="high")

    model: str = Field(default="")
    description: str = Field(default="")

    deep_skills: List[str] = Field(default=[])
    deep_mcps: List[str] = Field(default=[])
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def pre_validate_capabilities(cls, data: Any) -> Any:
        """
        Input adaptation: When data comes from frontend JSON form,
        convert capabilities: ["web_search", "include_todo"...]
        to internal CapabilityOpts object structure.
        """
        if isinstance(data, dict) and "capabilities" in data:
            caps_raw = data["capabilities"]
            if isinstance(caps_raw, list):
                caps_dict = {
                    field: False for field in CapabilityOpts.model_fields.keys()
                }
                for cap_name in caps_raw:
                    if cap_name in caps_dict:
                        caps_dict[cap_name] = True
                data["capabilities"] = caps_dict
        return data

    @model_serializer(mode="wrap")
    def serialize_to_schema_format(self, handler) -> Dict[str, Any]:
        """
        Output adaptation: When exporting or serializing data to the frontend,
        repack the internal Capabilities boolean object into a string array to
        fully comply with JSON Schema.
        """
        result = handler(self)
        if "capabilities" not in result:
            return result
        active_caps = []
        if isinstance(self.capabilities, CapabilityOpts):
            for field_name in CapabilityOpts.model_fields.keys():
                if getattr(self.capabilities, field_name) is True:
                    active_caps.append(field_name)
        result["capabilities"] = active_caps
        return result

    def merge(self, **overrides) -> "DeepAgentOptions":
        data = self.model_dump()
        # data.update({k: v for k, v in overrides.items() if v is not None})
        data.update(
            {
                k: v
                for k, v in overrides.items()
                if v is not None and not (isinstance(v, str) and not v.strip())
            }
        )
        return DeepAgentOptions(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeepAgentOptions":
        return cls.model_validate(data)


class AgentConfig:
    def __init__(self, spec: AgentSpec, opts: DeepAgentOptions = None):
        self._spec = spec
        if opts:
            self._deep_opts = opts
        else:
            self._deep_opts = DeepAgentOptions()

        if self._spec.description and not self._deep_opts.description.strip():
            self._deep_opts.description = self._spec.description

    def update_opts(self, setting: Dict):
        self._deep_opts = self._deep_opts.merge(**setting)

    @property
    def spec(self):
        return self._spec

    @property
    def opts(self):
        return self._deep_opts

    def as_dict(self):
        _config = {
            "instructions": self._spec.instructions,
            "description": self._deep_opts.description or self._spec.description or "",
            "model": self._spec.model,
            **(self._spec.model_settings or {}),
            **self._deep_opts.capabilities.model_dump(),
            **self._deep_opts.model_dump(
                exclude={"deep_mcps", "deep_skills", "capabilities", "enabled"}
            ),
        }
        return _config


class DeepAgentManager:
    def __init__(
        self,
        spec_dirs: Optional[List[Path]] = None,
        opts_paths: Optional[List[Path]] = None,
        jupyter_context: Optional[Any] = None,
        engine: Optional["AgentEngine"] = None,
    ):

        self._spec_dirs = spec_dirs  # is_dir
        self._opts_paths = opts_paths  # is_file
        self._jupyter_context = jupyter_context
        self._parent = engine

        self._agent_configs: Dict[str, AgentConfig] = {}
        self._agent_instances: Dict[str, Agent] = {}
        self._agent_deps: Dict[JupyterDeps] = {}

        self._is_initialized: bool = False
        self._is_configured: bool = False

    @property
    def agents(self):
        return list(self._agent_instances.keys())

    def getAgentAndDeps(self, name):
        _agent = self._agent_instances.get(name, None)
        _deps = self._agent_deps.get(name, None)
        return _agent, _deps

    def configure(self):
        for d in self._spec_dirs:
            if not d.exists():
                continue
            for f in chain(d.rglob("*.yaml"), d.rglob("*.yml"), d.rglob("*.json")):
                agentSpec = AgentSpec.from_file(f)
                agentName = agentSpec.name.strip()
                self._agent_configs[agentName] = AgentConfig(spec=agentSpec)

        _raw_agent_settings = ConfigLoader.load_from_paths(self._opts_paths).get(
            "agents", {}
        )
        for _name, _setting in _raw_agent_settings.items():
            if _name in self._agent_configs:
                self._agent_configs[_name].update_opts(_setting)

        self._is_configured = True

    async def materialize(self):
        for key in self._agent_configs.keys():
            _config = self._agent_configs[key]
            _agent, _deps = self.deep_enhanced(_config)
            if _agent and _deps:
                self._agent_instances[key] = _agent
                self._agent_deps[key] = _deps

        if self._agent_instances:
            self._is_initialized = True

    def deep_enhanced(self, config: AgentConfig):
        _config_dict = config.as_dict()

        # 1. LLM model part
        llm_model = None
        model_name = _config_dict.get("model", None)
        llm_comp = self._parent.getComponent("llm")
        if model_name and model_name in llm_comp.llms:
            llm_model = llm_comp.getModel(model_name)
        else:  # use the default model
            global_hub = self._parent.global_setting_hub
            if global_hub.default_model:
                llm_model = llm_comp.getModel(global_hub.default_model)
        if not llm_model:
            logger.warning(
                "Not able to create agents due to the lack of available LLM models"
            )
            return (None, None)  # corresponds to _agent, _deps
        _config_dict.pop("model")  # we use llm_model in the later agent creation

        # 2. Global setting (tool timeout)
        if self._parent.global_setting_hub:
            global_setting = self._parent.global_setting_hub.global_setting
            if global_setting.tool_timeout:
                _config_dict["tool_timeout"] = global_setting.tool_timeout

        toolsets = []

        # 3. MCP servers
        if config.opts.deep_mcps:
            mcp_component = self._parent.getComponent("mcp")
            mcp_servers = [
                mcp_component.getMCPServer(mcp_name)
                for mcp_name in config.opts.deep_mcps
            ]
            toolsets.extend(mcp_servers)

        # 4. Skills part
        if config.opts.deep_skills:
            skill_component = self._parent.getComponent("skill")
            skills = [
                skill_component.getSkill(skill_name)
                for skill_name in config.opts.deep_skills
                if skill_name in skill_component.skills
            ]
            if skills:
                toolsets.append(SkillsToolset(skills=skills))

        processor = create_summarization_processor(
            trigger=("tokens", 100000),  # Summarize when reaching 100k tokens
            keep=("messages", 20),  # Keep last 20 messages after summarization
        )
        _agent = create_deep_agent(
            **_config_dict,
            model=llm_model,
            toolsets=toolsets,
            # include_skills=True,
            include_skills=False,  # we will set skills through SkillsToolset
            history_processors=[processor],
        )

        _deps = self.build_deps(config.opts)

        # @_agent.tool
        # def test_error_tool(ctx: RunContext) -> str:
        #    """Test usage: Force tool error injection"""
        #    print("==================Agent RunContext==============")
        #    print(ctx.deps.jupyter_context)
        #    raise Exception("Forced tool error for testing UI error handling")

        return _agent, _deps

    def build_deps(self, opts: DeepAgentOptions = None):
        local_backend = LocalBackend(root_dir=self._jupyter_context.workspace)
        # deps = DeepAgentDeps(backend=local_backend)
        deps = JupyterDeps(jupyter_context=self._jupyter_context, backend=local_backend)
        return deps

    async def update_from_dict(self, new_settings):
        """
        Returns:
            dict: {
                'status': 'success' or 'failed' or 'warning',
                'message': '描述信息',
                'details': {
                    'updated': [],
                    'removed': [],
                    'failed': []
                }
            }
        """
        _diff_settings = self.compute_diff(new_settings)

        # in agent part, only changed/updated happened, no add/remove
        _updated_keys = {
            *_diff_settings.get("added", {}),
            *_diff_settings.get("changed", {}),
        }
        _details = {"updated": [], "removed": [], "failed": []}

        for key in _updated_keys:
            try:
                self._agent_configs[key].update_opts(new_settings[key])
                _config = self._agent_configs[key]
                _agent, _deps = self.deep_enhanced(_config)
                if _agent and _deps:
                    self._agent_instances[key] = _agent
                    self._agent_deps[key] = _deps
                    _details["updated"].append(key)
            except Exception as e:
                logger.error(f"Updating agent failed for {key}: {e}")
                _details["failed"].append(key)

        if self._agent_instances:
            self._is_initialized = True

        status = "success"
        if _details["failed"]:
            status = "warning" if _details["updated"] else "failed"

        updated_str = ", ".join(_details["updated"])
        failed_str = ", ".join(_details["failed"])

        message = f"Agent Update completed: [Updated: {updated_str or 'None'}]"
        if _details["failed"]:
            message += f" [Failed: {failed_str}]"

        return {"status": status, "message": message, "details": _details}

    def compute_diff(
        self, new_settings: Dict[str, Dict], ignore_keys: list[str] = []
    ) -> Dict:
        _old_settings = {
            # key: val.as_dict()
            key: val.opts.model_dump(mode="json")
            for key, val in self._agent_configs.items()
            if key not in ignore_keys
        }

        old_keys = set(_old_settings.keys())
        new_keys = set(new_settings.keys())

        added = new_keys - old_keys
        removed = old_keys - new_keys
        common = old_keys & new_keys

        changed_dict = {
            k: new_settings[k]
            for k in common
            if DeepDiff(_old_settings[k], new_settings[k], ignore_order=True)
        }

        return {
            "added": {k: new_settings[k] for k in added},
            "removed": {k: _old_settings[k] for k in removed},
            "changed": changed_dict,
        }

    async def cleanup(self):
        """Clear all runtime data including configurations"""
        self._agent_configs.clear()
        self._agent_instances.clear()
        self._agent_deps.clear()
        self._is_initialized = False
        self._is_configured = False
