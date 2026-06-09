import tornado
import json
import asyncio
from jupyter_server.base.handlers import APIHandler

from ..engine import AgentEngine
from ..engine._base import ConfigLoader
from ..utils.logging import get_logger

logger = get_logger(__name__)


# Simulate a global configuration change trigger
class EngineWatcher:
    def __init__(self):
        self.event = asyncio.Event()
        self.last_data = None

    def notify(self, data):
        """Notify all waiting handlers of configuration change"""
        self.last_data = data
        self.event.set()
        # Clear the event in the next event loop tick to ensure all wait() have completed
        asyncio.get_running_loop().call_soon(self.event.clear)


# Global singleton
watcher = EngineWatcher()
# 1. Get business engine instance
engine = AgentEngine.get_instance()


class EngineCatalogHandler(APIHandler):
    @tornado.web.authenticated
    async def get(self):
        # user = self.current_user
        summary = engine.runtime.get_summary()
        info_obj = summary.model_dump(
            include={
                "agents",
                "usage_limit",
                "mcps",
                "llms",
                "skills",
                "default_model",
                "default_agent",
            }
        )

        if not info_obj:
            return self.finish(
                {"status": "error", "message": "Engine info object not available"}
            )

        self.finish(
            {
                "status": "success",
                "message": "Engine info object send successfully",
                "payload": info_obj,
            }
        )


class EngineSSEHandler(APIHandler):
    async def get(self):
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")

        # Send the latest data once upon connection
        if watcher.last_data:
            self.write(f"data: {watcher.last_data}\n\n")
            await self.flush()

        # Then enter silent waiting loop
        try:
            while True:
                # 1. Block and wait for signal
                await watcher.event.wait()

                # 2. Woken up, send data
                if watcher.last_data:
                    message = f"data: {watcher.last_data}\n\n"
                    self.write(message)
                    await self.flush()

                # 3. After sending, reset event state so the loop blocks at wait again
                watcher.event.clear()
        except Exception:
            pass  # Client disconnected


class GlobalSettingHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))
        except Exception as e:
            return self.finish({"status": "error", "message": f"Invalid JSON: {e}"})

        if engine.global_setting_hub:
            await engine.global_setting_hub.update_from_dict(data)

        notify_obj = json.dumps(
            {
                "status": "success",
                "message": "Engine info object updated from globalsetting trigger",
                "payload": engine.runtime.to_dict(),
            }
        )
        watcher.notify(notify_obj)
        self.finish(notify_obj)


class LLMUpdateHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))

            _raw_settings = ConfigLoader.expand_env_vars(data)
            _new_settings = _raw_settings.get("llmModels")

            # get the LLM component
            llm_component = engine.getComponent("llm")

            _update_result = await llm_component.update_from_dict(_new_settings)

            notify_obj = json.dumps(
                {
                    "status": "success",
                    "message": "Engine info object updated from LLMUpdateHandler trigger",
                    "payload": engine.runtime.to_dict(),
                }
            )
            watcher.notify(notify_obj)

            return self.finish(
                {
                    "status": _update_result.get("status", "failed"),
                    "message": _update_result.get(
                        "message", "The LLM settings have been updated"
                    ),
                }
            )
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in LLMUpdateHandler-post: {error_msg}")
            return self.finish(
                {
                    "status": "error",
                    "message": f"CRITICAL error in LLM updating: {error_msg}",
                }
            )


class SkillsUpdateHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))
            _raw_settings = ConfigLoader.expand_env_vars(data)
            _new_settings = _raw_settings.get("skills")

            # get the Skill component
            skill_component = engine.getComponent("skill")

            _update_result = await skill_component.update_from_dict(_new_settings)

            notify_obj = json.dumps(
                {
                    "status": "success",
                    "message": "Engine info object updated from SkillUpdateHandler trigger",
                    "payload": engine.runtime.to_dict(),
                }
            )
            watcher.notify(notify_obj)

            return self.finish(
                {
                    "status": _update_result.get("status", "error"),
                    "message": _update_result.get(
                        "message", "The Skill settings have been updated"
                    ),
                }
            )
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in Skill UpdateHandler-post: {error_msg}")
            return self.finish(
                {
                    "status": "error",
                    "message": f"CRITICAL error in Skill updating: {error_msg}",
                }
            )


class MCPUpdateHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))

            _raw_settings = ConfigLoader.expand_env_vars(data)
            _new_settings = _raw_settings.get("mcpServers")
            print("new_settings:", _new_settings)
            # get the MCP component
            mcp_component = engine.getComponent("mcp")

            _update_result = await mcp_component.update_from_dict(_new_settings)

            notify_obj = json.dumps(
                {
                    "status": "success",
                    "message": "Engine info object updated from MCPUpdateHandler trigger",
                    "payload": engine.runtime.to_dict(),
                }
            )
            watcher.notify(notify_obj)

            return self.finish(
                {
                    "status": _update_result.get("status", "error"),
                    "message": _update_result.get(
                        "message", "The MCP settings have been updated"
                    ),
                }
            )
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in MCP UpdateHandler-post: {error_msg}")
            return self.finish(
                {
                    "status": "error",
                    "message": f"CRITICAL error in MCP updating: {error_msg}",
                }
            )


class AgentUpdateHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))
            _raw_settings = ConfigLoader.expand_env_vars(data)
            _new_settings = _raw_settings.get("agents")

            agent_manager = engine.agent_manager

            _update_result = await agent_manager.update_from_dict(_new_settings)

            notify_obj = json.dumps(
                {
                    "status": "success",
                    "message": "Engine info object updated from AgentUpdateHandler trigger",
                    "payload": engine.runtime.to_dict(),
                }
            )
            watcher.notify(notify_obj)

            return self.finish(
                {
                    "status": _update_result.get("status", "error"),
                    "message": _update_result.get(
                        "message", "The agent settings have been updated"
                    ),
                }
            )
        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in Agent UpdateHandler-post: {error_msg}")
            return self.finish(
                {
                    "status": "error",
                    "message": f"CRITICAL error in Agent updating: {error_msg}",
                }
            )
