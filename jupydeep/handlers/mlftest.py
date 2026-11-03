import tornado
import json
from jupyter_server.base.handlers import APIHandler
from jupyter_core.utils import run_sync
from tornado.httpclient import AsyncHTTPClient, HTTPError
from ..utils.logging import get_logger
from . import get_watcher

# Global singleton
_watcher = None


def get_global_watcher():
    global _watcher
    if _watcher is None:
        _watcher = run_sync(get_watcher)()
    return _watcher


logger = get_logger(__name__)


async def check_mlflow_health(
    tracking_uri: str, timeout: float = 3.0
) -> tuple[bool, str]:
    """Helper function to test connection and health of an MLflow tracking server.

    Args:
        tracking_uri: The base URI of the MLflow tracking server.
        timeout: Request timeout in seconds.

    Returns:
        A tuple of (is_healthy, message_or_error_detail)
    """
    http_client = AsyncHTTPClient()
    health_url = f"{tracking_uri.rstrip('/')}/health"

    try:
        response = await http_client.fetch(health_url, request_timeout=timeout)
        if response.code == 200:
            return True, "Connection successful! MLflow server is ready."
        else:
            return False, f"MLflow server responded with status code: {response.code}"
    except HTTPError as http_err:
        err_detail = (
            str(http_err).splitlines()[0] if str(http_err) else "Unknown HTTP error"
        )
        return False, f"MLflow HTTP error: {err_detail}"
    except Exception as conn_err:
        err_detail = (
            str(conn_err).splitlines()[0] if str(conn_err) else "Connection refused"
        )
        return False, f"Failed to connect: {err_detail}"


class MLflowTestHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            # Defer imports to prevent circular dependencies
            from ..engine import AgentEngine

            engine = AgentEngine.get_instance()
            watcher = get_global_watcher()

            # 1. Parse incoming JSON body
            data = json.loads(self.request.body.decode("utf-8"))
            tracking_uri = data.get("tracking_uri", "http://127.0.0.1:5000")

            # 2. Use the reusable health check function
            is_healthy, message = await check_mlflow_health(tracking_uri)

            global_setting = engine.global_setting_hub.global_setting

            if is_healthy:
                if global_setting.enable_system_mlflow:
                    global_setting.set_mlflow_connected(True)
            else:
                global_setting.set_mlflow_connected(False)

            notify_obj = json.dumps(
                {
                    "status": "success",
                    "event": "global_updated",
                    "message": "Engine info object updated from MLflow status trigger",
                    "payload": engine.runtime.to_dict(),
                }
            )
            watcher.notify(notify_obj)

            self.finish(
                {
                    "status": "success",
                    "message": message,
                }
            )

        except Exception as e:
            error_msg = str(e).splitlines()[0] if str(e) else "No detailed message"
            logger.error(f"CRITICAL error in MLflowTestHandler-post: {error_msg}")
            return self.finish(
                {
                    "status": "error",
                    "message": f"CRITICAL error testing MLflow connection: {error_msg}",
                }
            )
