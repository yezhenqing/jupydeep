# jupydeep/components/_store.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import aiosqlite
from pydantic import TypeAdapter

from pydantic_ai.conversation_store import (
    ConversationEntry,
    ConversationRecord,
    ConversationStore,
    ConversationConflict,
)
from pydantic_ai.messages import ModelMessage

from ._base import BaseComponent
from ..utils.logging import get_logger

logger = get_logger(__name__)

_MSG_ADAPTER = TypeAdapter(ModelMessage)

from pydantic_ai.usage import RunUsage
from pydantic_ai.messages import DeferredToolRequests
_USAGE_ADAPTER = TypeAdapter("RunUsage")
_REQ_ADAPTER = TypeAdapter("DeferredToolRequests")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_records (
    conversation_id TEXT PRIMARY KEY,
    head_id         TEXT,
    scope           TEXT,
    title           TEXT,
    usage_json      TEXT NOT NULL,
    deferred_json   TEXT,
    forked_from     TEXT,
    forked_at       TEXT,
    branches_json   TEXT NOT NULL DEFAULT '[]',
    revision        TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    format_version  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS conversation_entries (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    parent_id       TEXT,
    kind            TEXT NOT NULL DEFAULT 'message',
    message_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entry_conv ON conversation_entries(conversation_id);
CREATE INDEX IF NOT EXISTS idx_record_scope
    ON conversation_records(scope, updated_at DESC);
"""


class SQLiteConversationStore(ConversationStore):

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    async def init(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.executescript(_SCHEMA)
            await db.commit()

    async def close(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    async def read_record(self, conversation_id: str) -> ConversationRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT conversation_id, head_id, scope, title, usage_json, deferred_json, "
                "       forked_from, forked_at, branches_json, revision, updated_at, "
                "       format_version "
                "FROM conversation_records WHERE conversation_id = ?",
                (conversation_id,),
            ) as cur:
                row = await cur.fetchone()
        return self._row_to_record(row) if row else None

    async def read_records(
        self, *, scope: str | None = None, limit: int | None = None
    ) -> Sequence[ConversationRecord]:
        sql = (
            "SELECT conversation_id, head_id, scope, title, usage_json, deferred_json, "
            "       forked_from, forked_at, branches_json, revision, updated_at, "
            "       format_version FROM conversation_records "
        )
        params: list = []
        if scope is not None:
            sql += "WHERE scope = ? "
            params.append(scope)
        sql += "ORDER BY updated_at DESC "
        if limit is not None:
            sql += "LIMIT ?"
            params.append(limit)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        return [self._row_to_record(r) for r in rows]

    async def write_record(
        self,
        record: ConversationRecord,
        *,
        new_entries: Sequence[ConversationEntry] = (),
        expected_revision: str | None,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            if expected_revision is None:
                try:
                    await db.execute(
                        "INSERT INTO conversation_records "
                        "(conversation_id, head_id, scope, usage_json, deferred_json, "
                        " forked_from, forked_at, branches_json, revision, updated_at, "
                        " format_version) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        self._record_to_params(record),
                    )
                except aiosqlite.IntegrityError:
                    await db.rollback()
                    raise ConversationConflict(record.conversation_id)
            else:
                cur = await db.execute(
                    "UPDATE conversation_records SET "
                    "  head_id=?, usage_json=?, deferred_json=?, "
                    "  forked_from=?, forked_at=?, branches_json=?, "
                    "  revision=?, updated_at=? "
                    "WHERE conversation_id=? AND scope IS ? AND revision=?",
                    (
                        record.head_id,
                        _USAGE_ADAPTER.dump_json(record.usage).decode(),
                        (_REQ_ADAPTER.dump_json(record.deferred_tool_requests).decode()
                         if record.deferred_tool_requests else None),
                        record.forked_from,
                        record.forked_at,
                        json.dumps(record.branches),
                        record.revision,
                        record.updated_at.isoformat(),
                        record.conversation_id,
                        record.scope,
                        expected_revision,
                    ),
                )
                if cur.rowcount == 0:
                    await db.rollback()
                    raise ConversationConflict(record.conversation_id)

            for e in new_entries:
                await db.execute(
                    "INSERT INTO conversation_entries "
                    "(id, conversation_id, parent_id, kind, message_json, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        e.id, record.conversation_id, e.parent_id, e.kind,
                        _MSG_ADAPTER.dump_json(e.message).decode(),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            await db.commit()

    async def delete_record(
        self, conversation_id: str, *, expected_revision: str
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "DELETE FROM conversation_records "
                "WHERE conversation_id = ? AND revision = ?",
                (conversation_id, expected_revision),
            )
            if cur.rowcount == 0:
                await db.rollback()
                raise ConversationConflict(conversation_id)
            await db.execute(
                "DELETE FROM conversation_entries WHERE conversation_id = ?",
                (conversation_id,),
            )
            await db.commit()

    async def read_entry(self, entry_id: str) -> ConversationEntry:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, parent_id, kind, message_json "
                "FROM conversation_entries WHERE id = ?",
                (entry_id,),
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            raise KeyError(entry_id)
        return ConversationEntry(
            id=row[0], parent_id=row[1], kind=row[2],
            message=_MSG_ADAPTER.validate_json(row[3]),
        )

    async def read_history(
        self, head_id: str | None, *, limit: int | None = None
    ) -> list[ConversationEntry]:
        if head_id is None:
            return []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT conversation_id FROM conversation_entries WHERE id = ?",
                (head_id,),
            ) as cur:
                r = await cur.fetchone()
            if r is None:
                return []
            conv_id = r[0]
            if limit is None:
                sql = (
                    "SELECT id, parent_id, kind, message_json "
                    "FROM conversation_entries WHERE conversation_id = ? "
                    "ORDER BY rowid ASC"
                )
                params: list = [conv_id]
            else:
                sql = (
                    "SELECT id, parent_id, kind, message_json "
                    "FROM conversation_entries WHERE conversation_id = ? "
                    "ORDER BY rowid DESC LIMIT ?"
                )
                params = [conv_id, limit]
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        if limit is not None:
            rows = list(reversed(rows))
        return [
            ConversationEntry(
                id=r[0], parent_id=r[1], kind=r[2],
                message=_MSG_ADAPTER.validate_json(r[3]),
            )
            for r in rows
        ]

    async def set_title(
        self,
        conversation_id: str,
        title: str | None,
        *,
        scope: str | None = None,
        only_if_empty: bool = False,
    ) -> bool:
        sql = "UPDATE conversation_records SET title = ? WHERE conversation_id = ?"
        params: list[Any] = [title, conversation_id]

        if only_if_empty:
            sql += " AND (title IS NULL OR title = '')"
        if scope is not None:
            sql += " AND scope = ?"
            params.append(scope)

        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(sql, params)
            await db.commit()
            return cur.rowcount > 0

    def _row_to_record(self, r) -> ConversationRecord:
        rec = ConversationRecord(
            conversation_id=r[0], 
            head_id=r[1], 
            scope=r[2],
            #title=r[3],  # no such column in the default ConversationRecord
            usage=_USAGE_ADAPTER.validate_json(r[4]),
            deferred_tool_requests=(
                _REQ_ADAPTER.validate_json(r[5]) if r[5] else None
            ),
            forked_from=r[6], 
            forked_at=r[7],
            branches=json.loads(r[8]), 
            revision=r[9],
            updated_at=datetime.fromisoformat(r[10]).astimezone(timezone.utc),
            format_version=r[11],
        )
        try:
            object.__setattr__(rec, "title", r[3])
        except Exception:
            pass
        return rec

    def _record_to_params(self, rec: ConversationRecord) -> tuple:
        return (
            rec.conversation_id, rec.head_id, rec.scope,
            _USAGE_ADAPTER.dump_json(rec.usage).decode(),
            (_REQ_ADAPTER.dump_json(rec.deferred_tool_requests).decode()
             if rec.deferred_tool_requests else None),
            rec.forked_from, rec.forked_at, json.dumps(rec.branches),
            rec.revision, rec.updated_at.isoformat(), rec.format_version,
        )


class StoreComponent(BaseComponent):

    def __init__(self, db_path: str | Path):
        super().__init__()
        self._store = SQLiteConversationStore(db_path)

    @property
    def store(self) -> SQLiteConversationStore:
        return self._store

    async def set_title(
        self,
        conversation_id: str,
        title: str | None,
        *,
        scope: str | None = None,
        only_if_empty: bool = False,
    ) -> bool:
        return await self._store.set_title(
            conversation_id,
            title,
            scope=scope,
            only_if_empty=only_if_empty,
        )

    def configure(self) -> None:
        self._is_configured = True

    async def materialize(self) -> Any:
        if self._is_initialized:
            return self._store
        await self._store.init()
        self._is_initialized = True
        logger.info("[StoreComponent] materialized at %s", self._store.db_path)
        return self._store

    async def _internal_delete(self, key: str) -> None:
        return None

    async def shutdown(self):
        if self._is_initialized:
            await self._store.close()
            self._is_initialized = False
        self._is_configured = False
        logger.info("[StoreComponent] shutdown complete")