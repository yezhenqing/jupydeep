import inspect
import json
import logging
from typing import Any

from jupyter_server.base.handlers import APIHandler
from pydantic_ai.messages import ModelMessage
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from ..utils.user_scope import extract_user_scope, resolve_current_user
from ..engine import AgentEngine
from pydantic_ai.conversation_store import ConversationConflict

logger = logging.getLogger(__name__)


def _extract_model_messages(conv_or_entries: Any) -> list[ModelMessage]:
    if conv_or_entries is None:
        return []
    if isinstance(conv_or_entries, tuple) and len(conv_or_entries) == 2:
        _, entries = conv_or_entries
        return _extract_model_messages(entries)
    if hasattr(conv_or_entries, "messages") and isinstance(conv_or_entries.messages, (list, tuple)):
        return list(conv_or_entries.messages)
    if isinstance(conv_or_entries, (list, tuple)):
        msgs: list[ModelMessage] = []
        for item in conv_or_entries:
            msgs.append(item.message if hasattr(item, "message") else item)
        return msgs
    return []


def conversation_to_ui_messages(source: Any, entries: Any = None) -> list[dict[str, Any]]:
    raw_messages = _extract_messages_input(entries if entries is not None else source)
    ui_messages = VercelAIAdapter.dump_messages(raw_messages)

    dumped = [
        m.model_dump(mode="json", by_alias=True) if hasattr(m, "model_dump") else m
        for m in ui_messages
    ]
    return json.loads(json.dumps(dumped, default=str))


def _extract_messages_input(source: Any) -> list[ModelMessage]:
    return _extract_model_messages(source)


class BaseConversationHandler(APIHandler):

    def initialize(self):
        self._engine = AgentEngine.get_instance()

    @property
    def _store(self):
        store = self._engine.conversation_store
        return getattr(store, "store", store)

    async def get_current_user(self) -> Any:
        user = await resolve_current_user(self)
        self.current_user = user
        return user

    async def current_user_id(self) -> str:
        user = await self.get_current_user()
        return extract_user_scope(user)

    def write_json(self, payload: Any, status: int = 200) -> None:
        self.set_status(status)
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(payload, ensure_ascii=False))


def _serialize_record_summary(rec: Any) -> dict[str, Any]:
    conv_id = getattr(rec, "conversation_id", None)
    title = getattr(rec, "title", None)
    updated_at = getattr(rec, "updated_at", None)

    return {
        "id": conv_id,
        "conversation_id": conv_id,
        "title": title,
        "head_id": getattr(rec, "head_id", None),
        "revision": getattr(rec, "revision", None),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
    }


class ConversationsListHandler(BaseConversationHandler):
    """GET /jupydeep/conversations?limit=50"""

    async def get(self):
        scope = await self.current_user_id()

        try:
            raw_limit = self.get_argument("limit", None)
            limit = max(1, min(int(raw_limit), 200)) if raw_limit is not None else 50
        except ValueError:
            self.write_json({"error": "invalid limit"}, status=400)
            return

        try:
            records = await self._store.read_records(scope=scope, limit=limit)
        except Exception:
            logger.exception("read_records failed for scope=%s", scope)
            self.write_json({"error": "internal error"}, status=500)
            return

        self.write_json({
            "conversations": [_serialize_record_summary(r) for r in records],
        })


class ConversationMessagesHandler(BaseConversationHandler):
    """GET /jupydeep/conversations/<conversation_id>/messages"""

    async def get(self, conversation_id: str):
        scope = await self.current_user_id()

        try:
            if hasattr(self._store, "load"):
                conv = await self._store.load(conversation_id)
                rec = getattr(conv, "record", None) if conv is not None else None
                rec_scope = getattr(rec, "scope", getattr(conv, "scope", None))
                if conv is None or (rec_scope is not None and rec_scope != scope):
                    self.write_json({"error": "not found"}, status=404)
                    return
                messages_payload = conversation_to_ui_messages(conv)
                title = getattr(rec, "title", getattr(conv, "title", None))
            else:
                rec = await self._store.read_record(conversation_id)
                if rec is None or rec.scope != scope:
                    self.write_json({"error": "not found"}, status=404)
                    return
                entries = await self._store.read_history(rec.head_id)
                messages_payload = conversation_to_ui_messages(rec, entries)
                title = getattr(rec, "title", None)
        except Exception:
            logger.exception("load conversation failed: %s", conversation_id)
            self.write_json({"error": "internal error"}, status=500)
            return

        self.write_json({
            "conversation_id": conversation_id,
            "title": title,
            "messages": messages_payload,
        })


class ConversationDeleteHandler(BaseConversationHandler):
    """DELETE /jupydeep/conversations/<conversation_id>"""

    async def delete(self, conversation_id: str):
        scope = await self.current_user_id()
        conv_id = (conversation_id or "").strip()
        if not conv_id:
            self.write_json({"error": "missing conversation_id"}, status=400)
            return

        store = self._store
        if store is None:
            self.write_json({"error": "conversation store not available"}, status=500)
            return

        try:
            rec = await store.read_record(conv_id)
            if rec is None:
                self.write_json({"error": "not found"}, status=404)
                return

            rec_scope = getattr(rec, "scope", None)
            if rec_scope is not None and rec_scope != scope:
                self.write_json({"error": "forbidden"}, status=403)
                return

            revision = getattr(rec, "revision", None)
            if not revision:
                self.write_json({"error": "missing record revision"}, status=409)
                return

            await store.delete_record(conv_id, expected_revision=revision)
        except ConversationConflict:
            self.write_json(
                {"error": "conversation conflict, please retry"},
                status=409,
            )
            return
        except Exception:
            logger.exception("delete conversation failed: %s", conv_id)
            self.write_json({"error": "internal error"}, status=500)
            return

        self.write_json({
            "deleted": True,
            "conversation_id": conv_id,
        })