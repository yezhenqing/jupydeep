import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Any, TYPE_CHECKING
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from ._base import BaseComponent, ConfigLoader

if TYPE_CHECKING:
    from ..engine import AgentEngine

from ..utils.logging import get_logger

logger = get_logger(__name__)


class MCPServerConfig(BaseModel):
    """Single MCP Server configuration"""

    name: str = Field(..., description="MCP server name")
    command: str = Field(..., description="Command to start MCP server")
    args: List[str] = Field(default_factory=list, description="Command line arguments")
    url: str = Field(default="", description="MCP server base_url")
    transport: Literal["stdio", "sse", "streamable-http"] = Field(
        default="streamable-http", description="Transport protocol"
    )
    enabled: bool = Field(default=True, description="Whether to enable this server")
    env: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )

    @classmethod
    def from_dict(cls, data: dict) -> "MCPServerConfig":
        return cls(
            name=data.get("name", ""),
            command=data.get("command", ""),
            args=data.get("args", []),
            url=data.get("url", ""),
            transport=data.get("transport", "streamable-http"),
            enabled=data.get("enabled", True),
            env=data.get("env", {}),
        )

    def to_dict(self) -> dict:
        return self.model_dump()


class MCPComponent(BaseComponent):
    def __init__(
        self,
        mcp_setting_paths: Optional[List[Path]] = None,
        engine: Optional["AgentEngine"] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._setting_paths = mcp_setting_paths  # single json file
        self._current_settings: Dict[str, MCPServerConfig] = {}
        self._active_instances: Dict[str, MCPToolset] = {}
        self._parent = engine

    def get_mcp_names(self) -> list[str]:
        return [key for key in self._active_instances]

    def get_mcp_servers(self) -> list[str]:
        return [mcp for mcp in self._active_instances.values()]

    def getMCPServer(self, name):
        return self._active_instances.get(name, None)

    def configure(self):
        if self._is_configured:
            return

        if self._setting_paths:
            _raw_mcp_settings = ConfigLoader.load_from_paths(self._setting_paths)[
                "mcpServers"
            ]
            for key, val in _raw_mcp_settings.items():
                self._current_settings[key] = MCPServerConfig.from_dict(val)

        if self._current_settings:
            self._is_configured = True

    async def materialize(self):
        if self._is_initialized:
            return
        try:
            _result_dict = await self.reload_mcps(self._current_settings.keys())
            if any(mcp.get("status") == "success" for mcp in _result_dict.values()):
                self._is_initialized = True
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(
                f"CRITICAL error in MCP materialize: {error_msg}"
            )

    async def reload_mcps(self, mcp_keys: list[str]):
        """
        Refresh MCP instances

        Returns:
            dict: {
                'mcp-1': {
                    'status': 'success' or 'failed',
                    'message': 'description',
                    'details': {}
                },
                'mcp-2': {
                    'status': 'success' or 'failed',
                    'message': 'description',
                    'details': {}
                }
            }
        """
        _results = {}
        try:
            _tasks, _mcps, _names = [], [], []

            for _name in mcp_keys:
                if _name not in self._current_settings:
                    _results[_name] = {
                        "status": "failed",
                        "message": f"MCP-{_name} not found in settings",
                        "details": {},
                    }
                    continue

                try:
                    _config = self._current_settings[_name]
                    _inst = await self._create_mcp_client(_name, _config)
                    if _inst:
                        _tasks.append(self._validate_mcp_client(_name, _inst))
                        _mcps.append(_inst)
                        _names.append(_name)
                    else:
                        _results[_name] = {
                            "status": "failed",
                            "message": f"Failed to create MCP client instance - {_name}",
                            "details": {},
                        }
                except Exception as e:
                    _results[_name] = {
                        "status": "failed",
                        "message": f"Creation error for MCP: {str(e)}",
                        "details": {},
                    }

            if not _tasks:
                return _results

            _validations = await asyncio.gather(*_tasks, return_exceptions=True)

            for _name, _mcp, _res in zip(_names, _mcps, _validations):
                if isinstance(_res, Exception):
                    _results[_name] = {
                        "status": "failed",
                        "message": f"Validation error: {str(_res)}",
                        "details": {},
                    }
                elif isinstance(_res, dict) and _res.get("status") is True:
                    self._active_instances[_name] = _mcp
                    _results[_name] = {
                        "status": "success",
                        "message": f"MCP-{_name} is ready",
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
            msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            logger.error(f"CRITICAL error in reload_mcps: {msg}")
            return {
                name: {
                    "status": "failed",
                    "message": f"Critical error: {msg}",
                    "details": {},
                }
                for name in mcp_keys
            }

    async def _create_mcp_client(
        self, name: str, mcp_config: MCPServerConfig
    ) -> Optional[MCPToolset]:
        mcp_client = None
        transport_type = mcp_config.transport
        env_vars = getattr(mcp_config, "env", {})

        try:
            if transport_type == "stdio":
                transport = StdioTransport(
                    command=mcp_config.command,
                    args=mcp_config.args,
                    env=env_vars,
                )
                mcp_client = MCPToolset(transport)
            elif transport_type == "sse":
                mcp_client = MCPToolset(mcp_config.url)
            else:
                headers = {}
                token = self._parent.jupyter_context.token
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                mcp_client = MCPToolset(mcp_config.url, headers=headers)
        except Exception as e:
            raise e

        return mcp_client

    async def _validate_mcp_client(
        self, name: str, client: MCPToolset, timeout: float = 30
    ) -> Dict[str, Any]:
        """
        Validate if the MCP client is available

        Return: {'status': bool, 'message': str, 'tools_count': int}
        """
        try:
            async with asyncio.timeout(timeout):
                async with client as session:
                    # 执行一个轻量级操作来验证
                    response = await session.list_tools()
                    tools = getattr(
                        response,
                        "tools",
                        response if isinstance(response, list) else [],
                    )
                    if tools:
                        msg = f"Connected: {len(tools)} tools found"
                        logger.info(f"✅ {name} {msg}")
                        return {
                            "status": True,
                            "message": msg,
                            "tools_count": len(tools),
                        }
                    else:
                        msg = "Connected but no tools found"
                        logger.warning(f"⚠️ {name}: {msg}")
                        return {"status": False, "message": msg, "tools_count": 0}
        except asyncio.TimeoutError:
            msg = f"Validation timed out after {timeout}s"
            logger.error(f"❌ MCP '{name}' error: {msg}")
            return {"status": False, "message": msg, "tools_count": 0}
        except Exception as e:
            msg = str(e).splitlines()[0] if str(e) else "Unknown error"
            logger.error(f"MCP '{name}' validation failed: {msg}")
            return {"status": False, "message": msg, "tools_count": 0}

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
                self._current_settings[key] = MCPServerConfig.from_dict(
                    new_settings[key]
                )
                valid_keys_to_reload.append(key)
            except Exception as e:
                logger.error(f"Setting conversion failed for {key}: {e}")
                _details["failed"].append(key)

        if valid_keys_to_reload:
            _reload_report = await self.reload_mcps(valid_keys_to_reload)

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

        message = f"MCP Update completed: [Updated: {updated_str or 'None'}] [Removed: {removed_str or 'None'}]"
        if _details["failed"]:
            message += f" [Failed: {failed_str}]"

        return {"status": status, "message": message, "details": _details}

    async def _internal_delete(self, key):
        """Clean up MCP-related resources when the cache entry is being deleted"""
        instance = self._active_instances.get(key)
        if instance and isinstance(instance, MCPToolset):
            if hasattr(instance, "__aexit__") and instance.is_running:
                await instance.__aexit__(None, None, None)
        # Remove from active instances
        self._active_instances.pop(key, None)
        # Remove from current settings
        self._current_settings.pop(key, None)
        if self._parent:
            self._parent = None
