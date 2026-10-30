import tornado
import json
from jupyter_server.base.handlers import APIHandler
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MLflowTestHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            # 1. Parse incoming JSON body
            data = json.loads(self.request.body.decode("utf-8"))
            tracking_uri = data.get("tracking_uri", "http://127.0.0.1:5000")

            # 2. Test connection to MLflow tracking server health endpoint using Tornado's AsyncHTTPClient
            from tornado.httpclient import AsyncHTTPClient, HTTPError

            http_client = AsyncHTTPClient()

            health_url = f"{tracking_uri.rstrip('/')}/health"

            try:
                response = await http_client.fetch(health_url, request_timeout=3.0)
                if response.code == 200:
                    self.finish(
                        {
                            "status": "success",
                            "message": "Connection successful! MLflow server is ready.",
                        }
                    )
                else:
                    self.finish(
                        {
                            "status": "error",
                            "message": f"MLflow server responded with status code: {response.code}",
                        }
                    )
            except HTTPError as http_err:
                # Truncate and clean HTTP error message
                err_detail = (
                    str(http_err).splitlines()[0]
                    if str(http_err)
                    else "Unknown HTTP error"
                )
                self.finish(
                    {
                        "status": "error",
                        "message": f"MLflow server HTTP error: {err_detail}",
                    }
                )
            except Exception as conn_err:
                err_detail = (
                    str(conn_err).splitlines()[0]
                    if str(conn_err)
                    else "Connection refused"
                )
                self.finish(
                    {
                        "status": "error",
                        "message": f"Failed to connect to MLflow server: {err_detail}",
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
