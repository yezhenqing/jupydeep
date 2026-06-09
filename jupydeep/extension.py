import json
import os
from pathlib import Path

from jupyter_server.extension.application import ExtensionApp
from jupyter_core.paths import jupyter_config_path, jupyter_path
from jupyter_server.utils import url_path_join

from .engine import JupyterContext, AgentEngine
from .utils import find_dirs_with_nested_subfolder
from .handlers.engine import (
    GlobalSettingHandler,
    EngineCatalogHandler,
    EngineSSEHandler,
    MCPUpdateHandler,
    LLMUpdateHandler,
    SkillsUpdateHandler,
    AgentUpdateHandler,
)
from .handlers.chat import ChatStreamHandler
from .utils.logging import setup_logging, get_logger


logger = get_logger(__name__)


class AgentEngineExtension(ExtensionApp):
    """Jupyter Server Extension for JupyDeep Agent Engine."""

    name = "jupydeep"
    load_other_extensions = True
    description = "JupyDeep: Your AI partner in Jupyter, powered by Pydantic agents — and beyond."
    extension_url = "/jupydeep"

    @property
    def base_url(self):
        return self.serverapp.base_url

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._agentEngine = AgentEngine.get_instance()

    def initialize(self):
        """
        Initialize the JupyDeep Agent Engine extension.

        This follows the architecture of decoupling 'Intent' (synchronous settings)
        from 'Implementation' (asynchronous materialization), as the transition from
        "intent" to "active instance" depends on resource availability and system constraints.
        """
        super().initialize()  # self.serverapp will be available after this
  
        logger.info("Initializing JupyDeep Agent Engine.")

        # Environment injection (for agent dependency injection lately)
        jupyter_context = self._extract_jupyter_context()

        JUPYDEEP_AGENT_ROOT = os.environ.get("JUPYDEEP_AGENT_ROOT")
        if not JUPYDEEP_AGENT_ROOT:
            # Fallback to the project's current agent directory if it is unset
            JUPYDEEP_AGENT_ROOT = jupyter_context.prj_agent_dir
            os.environ["JUPYDEEP_AGENT_ROOT"] = str(JUPYDEEP_AGENT_ROOT)

        self._agentEngine.load_context(jupyter_context)

        # Intent Definition (Synchronous): Configure the agent's target state ('WHAT' it should be).
        # This applies user settings and prepares for downstream materialization.
        self._agentEngine.configure()

        # Materialization (Asynchronous): Realize the 'HOW' of the agent.
        # Handles resource-intensive tasks (loading models, managing mcps...).
        # Note: The actual event loop scheduling is deferred to `start_extension`.

        # self.serverapp.io_loop.add_callback(self._agentEngine.materialize) # Please refer to start_extension
        logger.info("Agent Engine configuration complete; materialization scheduled.")

    def initialize_settings(self):
        """
        Initialize and configure the extension runtime environment.
        
        Configures system-wide logging and registers immutable singletons 
        or settings required by the extension lifecycle.
        """
        setup_logging(debug=False, log_to_file=False)
        logger.info("Initializing extension settings...")
        
        # NOTE: `_agentEngine` acts as a global/thread-safe singleton within the process.
        # Direct registration to `self.settings` is skipped to prevent redundant references 
        # and enforce single-source-of-truth access.
        # self.settings['agent_engine'] = self._agentEngine

    def initialize_handlers(self):
        """Initialize handlers."""
        api_base_url = url_path_join(self.base_url, self.extension_url)

        self.handlers.extend(
            [
                (url_path_join(api_base_url, "global"), GlobalSettingHandler),
                (url_path_join(api_base_url, "mcp"), MCPUpdateHandler),
                (url_path_join(api_base_url, "llm"), LLMUpdateHandler),
                (url_path_join(api_base_url, "skills"), SkillsUpdateHandler),
                (url_path_join(api_base_url, "agents"), AgentUpdateHandler),
                (url_path_join(api_base_url, "catalog"), EngineCatalogHandler),
                (url_path_join(api_base_url, "engine-sse"), EngineSSEHandler),
                (url_path_join(api_base_url, "chat"), ChatStreamHandler),
            ]
        )


    async def start_extension(self):
        """
        Start the JupyDeep extension and trigger post-server-start lifecycles.
        
        This hook is invoked asynchronously once the Jupyter Server has fully 
        initialized, making it the ideal entry point to materialize heavy resources.
        """
        try:
            # Asynchronously materialize the agent engine (load models, allocate runtimes)
            # now that the server's event loop is active and stable.
            await self._agentEngine.materialize()
        except Exception as e:
            # Fail-fast approach: Log and propagate the exception to prevent 
            # the server from running in a corrupted or half-baked state.
            logger.error(f"Fatal error during agent engine materialization: {e}")
            raise

        logger.info("JupyDeep Agent Engine materialized successfully!")

    async def stop_extension(self):
        """
        Gracefully tear down the extension and release managed resources.
        
        Invoked during the Jupyter Server shutdown sequence to ensure clean 
        termination of active agent sessions and background processes.
        """
        logger.info("Stopping JupyDeep Extension...")

        if self._agentEngine:
            # Asynchronously dematerialize the agent engine, terminating 
            # active MCP connections, flushing skills, and freeing hardware resources.
            await self._agentEngine.shutdown()

        logger.info("JupyDeep Extension stopped safely.")

    def _extract_jupyter_context(self):
        """
        Encapsulate Jupyter Server internal managers into a strongly-typed Context.

        This context serves as the 'Deps' injection for Pydantic AI Agents/ToolHooks,
        providing them with managed access to the Jupyter environment.
        """

        _setting_json_dirs = find_dirs_with_nested_subfolder(
            jupyter_config_path(), "jupydeep"
        )

        # https://vstorm-co.github.io/pydantic-deepagents/advanced/context-files/
        _prj_agent_dir = Path(self.serverapp.root_dir) / ".agents"

        # Scan and compile multi-source paths for Agent-spec YAML declarations
        _raw_sources = [str(p) for p in jupyter_path()]
        if _prj_agent_dir.is_dir():
            _raw_sources.append(str(_prj_agent_dir))
        _agent_spec_dirs = find_dirs_with_nested_subfolder(_raw_sources, "agent_specs")

        try:
            _context = JupyterContext(
                base_url=self.serverapp.base_url,
                workspace=self.serverapp.root_dir,
                token=self.serverapp.token,
                setting_json_dirs=_setting_json_dirs,
                agent_spec_dirs=_agent_spec_dirs,
                prj_agent_dir=_prj_agent_dir,
                contents_manager=self.serverapp.contents_manager,
                kernel_manager=self.serverapp.kernel_manager,
                kernel_spec_manager=self.serverapp.kernel_spec_manager,
                session_manager=self.serverapp.session_manager,
            )
            # Serialize metadata for transparent auditing and lifecycle logging
            _context_info = {
                "base_url": self.serverapp.base_url,
                "workspace": str(self.serverapp.root_dir),  # convert to str
                "setting_json_dirs": [str(d) for d in _setting_json_dirs],
                "agent_spec_dirs": [str(d) for d in _agent_spec_dirs],
                "prj_agent_dir": str(_prj_agent_dir) if _prj_agent_dir else None,
            }

            logger.info(
                "JupyterContext successfully constructed:\n%s",
                json.dumps(_context_info, indent=2, ensure_ascii=False)
            )

            return _context

        except Exception as e:
            logger.error(
                f"Failed to initialize JupyterContext boundary: {str(e)}", exc_info=True
            )
            return None

    async def _start_jupyter_server_extension(self, serverapp):
        """
        Start the extension - called after Jupyter Server starts.
        """
        await self.start_extension()


# -----------------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------------

main = launch_new_instance = AgentEngineExtension.launch_instance
