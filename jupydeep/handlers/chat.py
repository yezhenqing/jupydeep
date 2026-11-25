# handlers/chat.py
import json
import time
import uuid
import asyncio

# from datetime import datetime
import tornado
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from pydantic import ValidationError
from starlette.requests import Request
from tornado.httputil import HTTPServerRequest
from pydantic_ai.usage import UsageLimits
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from jupyter_server.base.handlers import APIHandler
from pydantic_ai.conversation import Conversation
from pydantic_ai.conversation_store import ConversationConflict
from pydantic_ai import Agent

from ..engine import AgentEngine
from ..agent import JupyterDeps
from ..utils.user_scope import extract_user_scope, resolve_current_user
from ..utils.stream_errors import sanitize_stream_error
from ..utils.logging import get_logger

from . import get_watcher

logger = get_logger(__name__)


SSE_DONE = "data: [DONE]\n\n"

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
        self.agent_id: str | None = None
        self.session_id: str | None = None

        self._background_tasks: set[asyncio.Task[Any]] = set()

    @property
    def _store(self):
        return self._engine.conversation_store

    def set_default_headers(self):
        """Set SSE response headers"""
        self.set_header("Content-Type", SSE_CONTENT_TYPE)
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

    async def prepare(self):
        self.session_id = self.get_argument("session_id", None)
        self.agent_id = self.get_argument("agent_id", None)
        self.current_user = await resolve_current_user(self)

    async def current_user_id(self) -> str:
        if getattr(self, "current_user", None) is None:
            self.current_user = await resolve_current_user(self)
        return extract_user_scope(self.current_user)

    async def post(self):
        """Handle POST request - streaming response"""
        
        try:
            body = self.request.body
            if not body:
                self._send_error("Empty request body", 400)
                return

            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON body: %s", e)
            self._send_error("Invalid JSON body", 400)
            return

        agent_id = data.get("agent_id") or self.agent_id
        self.agent_id = agent_id
        self.session_id = data.get("session_id") or self.session_id
        _messages = data.get("messages")

        if not agent_id:
            self._send_error("Missing agent_id", 400)
            return

        if not _messages:
            self._send_error("Missing message", 400)
            return

        try:
            _agent, _deps = self._engine._deep_agent_manager.getAgentAndDeps(agent_id)
        except Exception as e:
            logger.exception("Unknown agent_id=%s: %s", agent_id, e)
            self._send_error("Unknown agent_id", 404)
            return

        scope = await self.current_user_id()
        tornado_request = TornadoVercelBridge(self.request)

        try:
            adapter = await VercelAIAdapter.from_request(
                tornado_request, 
                agent=_agent, 
                sdk_version=6,
                conversation_store=self._store,
                conversation_scope=scope
            )
        except ValidationError as v_err:
            logger.warning(f"Protocol Validation Failed: {v_err}")
            self._send_error("Invalid Vercel AI protocol format", 422)
            return
        except Exception as e:
            logger.exception("Failed to build adapter: %s", e)
            self._send_error("Failed to build adapter", 400)
            return

        conversation_id = getattr(adapter, "conversation_id", None)

        emit_conversation_id = bool(
            conversation_id and tornado_request.id_generated
        )

        user_text = self._extract_user_text(_messages)

        await self._run_adapter_stream(
            adapter = adapter, 
            deps = _deps,
            agent=_agent,
            user_text=user_text,
            conversation_id=conversation_id,
            emit_conversation_id=emit_conversation_id,
            scope=scope,
        )

    async def _run_adapter_stream(
        self, 
        adapter: VercelAIAdapter, 
        deps: JupyterDeps,
        agent: Agent,
        user_text: str,
        conversation_id: str | None = None,
        emit_conversation_id: bool = False,
        scope: str = "",
    ):
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
        completed_normally = False
        try:
            if emit_conversation_id:
                init_sse = self._format_custom_data_event(
                    "conversation",
                    {"conversation_id": str(conversation_id)},
                )
                self.write(init_sse)
                await self.flush()

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
            self.write(SSE_DONE)
            await self.flush()
            completed_normally = True
        except tornado.iostream.StreamClosedError:
            logger.info(
                "Client disconnected during streaming: agent_id=%s", self.agent_id
            )
        except Exception as e:
            error_code, safe_msg = sanitize_stream_error(e)
            logger.exception(
                "Streaming error in _run_adapter_stream [error_code=%s, conversation_id=%s]: %s",
                error_code,
                conversation_id,
                e,
            )
            # If not finished yet, try to send error message
            if not self._finished:
                payload = json.dumps(
                    {
                        "type": "error",
                        "errorText": f"[{error_code}] {safe_msg}",
                    },
                    ensure_ascii=False,
                )
                self.write(f"data: {payload}\n\n")
                await self.flush()
        # after stream
        if (
            completed_normally
            and emit_conversation_id
            and conversation_id
            and user_text
        ):
            self._schedule_title_update(
                conversation_id=conversation_id,
                scope=scope,
                agent=agent,
                user_text=user_text,
            )

    def _extract_user_text(self, messages) -> str:
        texts = []
        for msg in messages:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            for part in msg.get("parts") or []:
                if isinstance(part, dict) and part.get("type") == "text":
                    t = part.get("text")
                    if isinstance(t, str) and t.strip():
                        texts.append(t.strip())
        return "\n".join(texts)

    async def _generate_conversation_title_by_agent(
        self, agent: Agent, user_text: str
    ) -> str:
        title_agent = Agent(
            agent.model, 
            output_type=str,
            system_prompt=(
                "Generate a short conversation title based on the user's first message. "
                "Keep it under 10 words, no trailing punctuation, no quotation marks. "
                "Return only the title text, with no prefix."
            ),
            retries={"output": 1},
        )
        result = await title_agent.run(user_text)
        return (result.output or "Unknown title").strip()

    async def _update_title(
        self, conversation_id: str, scope: str, agent: Agent, user_text: str
    ) -> None:
        if self._store is None or not conversation_id:
            return
        try:
            title = await self._generate_conversation_title_by_agent(agent, user_text)
            if not title:
                logger.warning("Title agent returned empty for %s", conversation_id)
                return
            updated = await self._store.set_title(
                conversation_id,
                title,
                scope=scope,
                only_if_empty=True,
            )
            logger.info(
                f"[title-debug] set_title updated={updated} title={title!r} for {conversation_id}"
            )
            if updated:
                watcher = await get_watcher()
                notify_obj = json.dumps({
                    "event": "conversation_title",
                    "payload": {
                        "conversation_id": conversation_id,
                        "title": title,
                        "scope": scope,
                    },
                })
                watcher.notify(notify_obj)
                logger.info(f"[title-debug] notified watcher for {conversation_id}")
        except Exception as e:
            logger.warning("Failed to update title for %s: %s", conversation_id, e)

    def _schedule_title_update(
        self, conversation_id: str, scope: str, agent: Agent, user_text: str
    ) -> None:
        #print(f"[title-debug] schedule conversation_id={conversation_id} scope={scope}")
        task = asyncio.create_task(
            self._update_title(conversation_id, scope, agent, user_text)
        )
        self._background_tasks.add(task)

        def _on_done(t: asyncio.Task[Any]) -> None:
            self._background_tasks.discard(t)
            if not t.cancelled() and (exc := t.exception()) is not None:
                logger.warning("[title-debug] task crashed: %r", exc)

        task.add_done_callback(_on_done)
        

    def _send_error(self, message: str, status_code: int):
        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"error": message}))
        self.finish()

    @staticmethod
    def _format_custom_data_event(event_name: str, data: Dict[str, Any]) -> str:
        payload = {
            "type": f"data-{event_name}",
            "data": data,
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class TornadoVercelBridge(Request):
    """
    Converts Tornado's native request context (and ASGI signals)
    to the standard specification expected by Vercel AI SDK.
    """

    def __init__(self, request: HTTPServerRequest) -> None:
        self.id_generated: bool = False
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
            self.id_generated = True
            return b'{"trigger": "submit-message", "messages": []}'

        try:
            data = json.loads(raw_body)

            # A. Inject discriminator
            # pydantic-ai expects 'submit-message' or 'regenerate-message'
            current_trigger = data.get("trigger")
            if current_trigger not in ["submit-message", "regenerate-message"]:
                data["trigger"] = "submit-message"

            # B. Fill root ID
            if "id" not in data or not data.get("id"):
                data["id"] = str(uuid.uuid4())
                self.id_generated = True
            else:
                self.id_generated = False

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
