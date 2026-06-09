# handlers/chat.py
import json
import time
import uuid

# from datetime import datetime
import tornado
from enum import Enum
from typing import Any, Dict
from dataclasses import dataclass, field
from pydantic import ValidationError
from starlette.requests import Request
from tornado.httputil import HTTPServerRequest
from pydantic_ai.usage import UsageLimits
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from jupyter_server.base.handlers import APIHandler

from ..engine import AgentEngine
from ..agent import JupyterDeps

from ..utils.logging import get_logger

logger = get_logger(__name__)


class DataEventType(Enum):
    """Data event types - output to frontend"""

    STATUS = "status"
    STATUS_WARNING = "warning"
    STATUS_ERROR = "error"
    PROGRESS = "progress"
    THINKING = "thinking"
    TEXT_CHUNK = "text_chunk"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DONE = "done"


@dataclass
class DataEvent:
    """Data stream event - with sequence number to ensure ordering"""

    type: DataEventType
    message: str
    sequence: int = 0  # Global sequence number to ensure ordering
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        payload = json.dumps(
            {
                'type': self.type.value,
                'message': self.message,
                'sequence': self.sequence,
                'metadata': self.metadata,
            }
        )
        return f"data: {payload}\n\n"

    def to_vercel_format(self) -> Dict[str, Any]:
        """Convert to Vercel AI SDK format (for useChat)"""
        if self.type == DataEventType.TEXT_CHUNK:
            return {"choices": [{"delta": {"content": self.message}, "index": 0}]}
        elif self.type == DataEventType.THINKING:
            return {
                "choices": [{"delta": {"reasoning_content": self.message}, "index": 0}]
            }
        else:
            # Other events as metadata
            return {
                "type": self.type.value,
                "message": self.message,
                "metadata": self.metadata,
            }


class ChatStreamHandler(APIHandler):
    """
    Vercel AI SDK streaming chat handler

    Features:
    - Supports direct connection with useChat hook
    - Guarantees message ordering
    """

    def initialize(self):
        self._engine = AgentEngine.get_instance()
        global_setting = self._engine.global_setting_hub.global_setting
        self.usage_limits = UsageLimits(
            request_limit=global_setting.request_limit,
            total_tokens_limit=global_setting.total_tokens_limit,
        )

    def set_default_headers(self):
        """Set SSE response headers"""
        self.set_header("Content-Type", SSE_CONTENT_TYPE)
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

    async def prepare(self):
        self.session_id = self.get_argument("session_id", None)
        self.agent_id = self.get_argument("agent_id", None)

    async def post(self):
        """Handle POST request - streaming response"""
        try:
            body = self.request.body
            if not body:
                self._send_error("Empty request body", 400)
                return

            data = json.loads(self.request.body)
            agent_id = data.get("agent_id")
            _agent, _deps = self._engine._deep_agent_manager.getAgentAndDeps(agent_id)

            tornado_request = TornadoVercelBridge(self.request)

            try:
                adapter = await VercelAIAdapter.from_request(
                    tornado_request, agent=_agent, sdk_version=6
                )
            except ValidationError as v_err:
                logger.warning(f"Protocol Validation Failed: {v_err}")
                self._send_error("Invalid Vercel AI protocol format", 422)
                return

            await self._run_adapter_stream(adapter, _deps)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            if not self.handler_finished:
                self._send_error(str(e), 500)

    async def _run_adapter_stream(self, adapter: VercelAIAdapter, deps: JupyterDeps):
        """
        # for debug: to capture all_messages
        captured_messages = None

        async def on_complete(run_result):
            nonlocal captured_messages
            captured_messages = run_result.all_messages_json()
            messages_data = json.loads(captured_messages)
            # Use append mode, write one complete JSON object at a time
            current_date = datetime.now().strftime("%Y%m%d")
            with open(
                f"debug_messages_{current_date}.jsonl", "a", encoding="utf-8"
            ) as f:
                record = {
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": adapter.conversation_id,
                    "total_messages": len(run_result.all_messages()),
                    "messages": messages_data,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # on_complete can return additional protocol events
            return []

        """
        try:
            kwargs = {"deps": deps}
            if self.usage_limits:
                kwargs["usage_limits"] = self.usage_limits
            # if on_complete:
            #    kwargs["on_complete"] = on_complete
            event_stream = adapter.run_stream(**kwargs)
            sse_stream = adapter.encode_stream(event_stream)

            chunk_count = 0
            async for sse_chunk in sse_stream:
                if sse_chunk:
                    self.write(sse_chunk)
                    await self.flush()
                    chunk_count += 1

            if chunk_count == 0:
                logger.warning("No chunks were generated from the adapter stream.")

            # Send termination signal according to Vercel specification
            self.write("data: [DONE]\n\n")
            await self.flush()
        except tornado.iostream.StreamClosedError:
            logger.warning("Client disconnected during streaming")
        except Exception as e:
            logger.exception(f"Streaming error in _run_adapter_stream: {e}")
            # If not finished yet, try to send error message
            if not self._finished:
                self.write(f'data: {{"error": "{str(e)}"}}\n\n')
                await self.flush()

    def _send_sse_event(self, event: DataEvent):
        self.write(event.to_sse())

    def _send_error(self, message: str, status_code: int):
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"error": message}))
        self.finish()


class TornadoVercelBridge(Request):
    """
    Converts Tornado's native request context (and ASGI signals)
    to the standard specification expected by Vercel AI SDK.
    """

    def __init__(self, request: HTTPServerRequest) -> None:
        # 1. Clean and upgrade data before initialization
        self.processed_body = self._prepare_vercel_payload(request.body)

        # 2. Build minimal ASGI Scope
        scope = {
            "type": "http",
            "method": request.method,
            "path": request.path,
            "query_string": request.query.encode("utf-8"),
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in request.headers.items()
            ],
            "server": (
                request.host.split(":")[0],
                int(request.host.split(":")[1]) if ":" in request.host else 80,
            ),
        }

        # 3. Core change: define receive closure that matches processed data
        async def receive() -> dict[str, Any]:
            return {
                "type": "http.request",
                "body": self.processed_body,
                "more_body": False,
            }

        # 4. Call Starlette Request base constructor
        super().__init__(scope, receive)

    def _prepare_vercel_payload(self, raw_body: bytes) -> bytes:
        """
        Convert raw payload to the strict format required by VercelAIAdapter.
        """
        if not raw_body:
            return b'{"trigger": "submit-message", "messages": []}'

        try:
            data = json.loads(raw_body)

            # A. Inject discriminator
            # pydantic-ai expects 'submit-message' or 'regenerate-message'
            current_trigger = data.get("trigger")
            if current_trigger not in ["submit-message", "regenerate-message"]:
                data["trigger"] = "submit-message"

            # B. Fill root ID
            if "id" not in data:
                data["id"] = str(uuid.uuid4())

            # C. Deep convert message structure
            if "messages" in data and isinstance(data["messages"], list):
                for msg in data["messages"]:
                    # Ensure each message has an ID
                    if "id" not in msg:
                        msg["id"] = str(uuid.uuid4())

                    # Convert OpenAI-style content to Vercel-style parts
                    # Avoid 'Extra inputs are not permitted' error
                    if "parts" not in msg and "content" in msg:
                        content_val = msg.pop("content")
                        msg["parts"] = [{"type": "text", "text": str(content_val)}]

            return json.dumps(data).encode("utf-8")

        except Exception as e:
            # If parsing fails, return as-is and let subsequent validation logic throw standard erro
            logger.warning(f"Payload preprocessing failed: {e}")
            return raw_body

    async def body(self) -> bytes:
        """
        Override body method to ensure it always returns processed data.
        """
        return self.processed_body
