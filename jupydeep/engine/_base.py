import os
import re
import json
import asyncio
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, Any, List, TypeVar, Optional
from pydantic import BaseModel, ConfigDict, Field

from jupyter_server.services.contents.manager import ContentsManager
from jupyter_server.services.kernels.kernelmanager import MappingKernelManager
from jupyter_server.services.sessions.sessionmanager import SessionManager
from jupyter_client.kernelspec import KernelSpecManager

from ..utils.logging import get_logger


logger = get_logger(__name__)


class BaseComponent(ABC):
    def __init__(self):
        self._is_initialized: bool = False
        self._is_configured: bool = False

        self._active_instances: Dict[str, Any] = {}
        self._current_settings: Dict[str, BaseModel] = {}

    @abstractmethod
    def configure(self) -> None:
        """
        Synchronous hook to define the component's target configuration state.

        Subclasses must implement this logic to capture and validate intent 
        before downstream asynchronous materialization occurs.
        """
        pass

    @abstractmethod
    async def materialize(self) -> Any:
        """
        Asynchronous hook to instantiate and activate heavy component resources.

        Subclasses must implement this logic to transition the component from its 
        declared intent (configured target state) into a live, active instance.

        Returns:
            Any: The materialized active instance or runtime context.
        """
        pass

    @abstractmethod
    async def _internal_delete(self, key: str) -> None:
        """
        Asynchronously decommission and delete a specific active instance by its key.

        Must be overridden by subclasses to handle concrete resource cleanup, 
        such as terminating specific WebSocket sessions, freeing specific GPU memory,
        or killing downstream sub-processes.

        Args:
            key (str): The unique identifier of the active instance to be removed.
        """
        pass

    def compute_diff(
        self, new_settings: Dict[str, Dict], 
        ignore_keys: list[str] = []
    ) -> Dict:
        """
        Calculate the configuration delta between current and incoming settings.

        Args:
            new_settings (Dict[str, Dict]): The incoming target configuration state.
            ignore_keys (list[str], optional): Top-level keys to exclude from the evaluation 
                (e.g., runtime-only singletons). Defaults to [].

        Returns:
            Dict: A delta manifest containing partitioned structured changes:
                - `added`: New configuration blocks introduced.
                - `removed`: Deprecated configurations marked for decommissioning.
                - `changed`: Overlapping blocks that require parameter realignment.
        """
        # Serialize current active models to JSON primitives while bypassing ignored boundaries
        _old_settings = {
            key: val.model_dump(mode="json")
            for key, val in self._current_settings.items()
            if key not in ignore_keys
        }

        old_keys = set(_old_settings.keys())
        new_keys = set(new_settings.keys())

        # 1. Evaluate structural topology alterations (Additions & Removals)
        added = new_keys - old_keys
        removed = old_keys - new_keys
        common = old_keys & new_keys

        # 2. Isolate parameter drift within overlapping configuration boundaries
        changed_dict = {
            k: new_settings[k] for k in common if _old_settings[k] != new_settings[k]
        }

        return {
            "added": {k: new_settings[k] for k in added},
            "removed": {k: _old_settings[k] for k in removed},
            "changed": changed_dict,
        }

    async def shutdown(self):
        """
        Execute comprehensive teardown logic to decommission all active components.
        """
        logger.info(f"[{self.__class__.__name__}] Initiating shutdown sequence...")
        if self._active_instances:
            active_keys = list(self._active_instances.keys())
            tasks = [self._internal_delete(k) for k in active_keys]

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                # Audit and report any failures inside the pipeline
                for key, result in zip(active_keys, results):
                    if isinstance(result, Exception):
                        logger.warning(f"[{self.__class__.__name__}] ERROR: Failed to decommission instance '{key}': {result}")          
            except Exception as e:
               logger.warning(f"[{self.__class__.__name__}] CRITICAL: Unexpected pipeline breakdown during gather: {e}")

            # Flush in-memory runtime cache explicitly
            self._active_instances.clear()

        self._current_settings.clear()
        self._is_initialized = False
        self._is_configured = False

        logger.info(f"[{self.__class__.__name__}] Shutdown sequence completed successfully.")


class JupyterContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Basic connection info and workspace settings
    base_url: str = Field(..., description="The base URL of the Jupyter server")
    workspace: str = Field(..., description="The working directory or workspace path")
    token: str = Field(
        ..., repr=False, description="Authentication token for the server"
    )
    # Directory paths
    setting_json_dirs: List[Path] = Field(
        default_factory=list,
        description="List of directories containing settings JSON files",
    )
    agent_spec_dirs: List[Path] = Field(
        default_factory=list,
        description="List of directories containing agent specifications",
    )
    prj_agent_dir: Path = Field(description="The specific directory for project agents")

    contents_manager: "ContentsManager" = Field(
        description="Manager for handling file contents and operations"
    )
    kernel_manager: "MappingKernelManager" = Field(
        description="Manager for handling kernel lifecycles"
    )
    kernel_spec_manager: "KernelSpecManager" = Field(
        description="Manager for handling kernel specifications"
    )
    session_manager: "SessionManager" = Field(
        description="Manager for handling Jupyter sessions"
    )


T = TypeVar("T")

class ConfigLoader:
    """
    Configuration loading utility
    Supports multi-directory scanning, environment variable expansion, and deep dictionary merging
    """

    @staticmethod
    def expand_env_vars(data: Any) -> Any:
        """
        Expand environment variables in format ${VAR_NAME} or $VAR_NAME
        Returns the original data with environment variables expanded
        """
        pattern = re.compile(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

        def expand(value):
            if isinstance(value, str):

                def replace(match):
                    var_name = match.group(1) or match.group(2)
                    # Return empty string if environment variable doesn't exist
                    return os.environ.get(var_name, "")

                return pattern.sub(replace, value)
            elif isinstance(value, dict):
                return {k: expand(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand(v) for v in value]
            return value

        return expand(data)

    @staticmethod
    def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge two dictionaries.
        Values from update will override values in base for simple types,
        but dictionaries will be recursively merged.
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigLoader.deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    @staticmethod
    def _detect_format(file_path: str) -> str:
        """Detect file format based on file extension"""
        ext = Path(file_path).suffix.lower()
        if ext in [".yaml", ".yml"]:
            return "yaml"
        elif ext in [".json", ".jupyterlab-settings"]:
            return "json"
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _read_file(file_path: str) -> dict:
        """Read and parse file content based on its format"""
        fmt = ConfigLoader._detect_format(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            if fmt == "yaml":
                try:
                    import yaml

                    # safe_load may return None for empty files
                    data = yaml.safe_load(f)
                    return data if data is not None else {}
                except ImportError:
                    raise ImportError("PyYAML is required to load YAML files")
            else:
                try:
                    return json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse JSON in {file_path}: {e}")

    @classmethod
    def load_config_file(cls, file_path: str, expand_env: bool = True) -> dict:
        """Load a single configuration file"""
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")

        data = cls._read_file(str(p))
        if expand_env:
            data = cls.expand_env_vars(data)

        return data if isinstance(data, dict) else {}

    @classmethod
    def load_from_paths(
        cls, setting_paths: Optional[List[Path]], expand_env: bool = True
    ) -> Dict[str, Any]:
        """
        Core method: Read given list of Paths and merge all configurations
        
        :param setting_paths: List of Path objects found via glob (or None)
        :param expand_env: Whether to expand environment variables
        :return: Merged configuration dictionary
        """
        final_config = {}

        if not setting_paths:
            return final_config

        for file_path in setting_paths:
            if not file_path.is_file():
                continue
            try:
                file_config = cls.load_config_file(
                    str(file_path), expand_env=expand_env
                )
                if file_config:
                    final_config = cls.deep_merge(final_config, file_config)
            except Exception as e:
                logger.warning(f"Skipping file {file_path} due to error: {e}")

        return final_config
