"""Round-trip tests for the chat layer dataclasses + SQLite store."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.chat import (
    ChatStore,
    Message,
    Thread,
    ToolCall,
)
from backend.core.chat.models import Attachment, new_attachment_id


def _store(tmp_path: Path) -> ChatStore:
    return ChatStore(str(tmp_path / "chat.sqlite"), enabled=True)


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


def test_thread_fresh_assigns_id_and_timestamps() -> None:
    t = Thread.fresh(title="Daily ops", pack_slug="ops_room")
    assert t.id.startswith("thr_")
    assert t.title == "Daily ops"
    assert t.pack_slug == "ops_room"
    assert t.created_at == t.updated_at
    assert t.archived is False


def test_message_helpers_set_roles_and_extras() -> None:
    op = Message.from_operator("thr_x", "hi")
    assert op.role == "operator"
    assert op.content == "hi"
    tars = Message.from_tars(
        "thr_x",
        "hello",
        trace_id="trc_1",
        parent_msg_id=op.id,
        cost_usd=0.0123,
        route="cloud",
        tokens_in=4,
        tokens_out=2,
        voice_model="anthropic/claude",
        extra={"voice_error": None},
    )
    assert tars.role == "tars"
    assert tars.parent_msg_id == op.id
    assert tars.cost_usd == 0.0123
    assert tars.route == "cloud"
    assert tars.tokens_in == 4
    assert dict(tars.extra) == {"voice_error": None}
    assert tars.id != op.id


def test_tool_call_lifecycle_dict_roundtrip() -> None:
    tc = ToolCall.fresh(
        message_id="msg_1",
        slug="business",
        action_id="draft_email",
        args={"to": "ops@meeet.world", "subject": "ping"},
        trace_id="trc_t",
    )
    assert tc.status == "pending"
    assert tc.id.startswith("tcl_")
    payload = tc.to_dict()
    assert payload["slug"] == "business"
    assert payload["args"]["to"] == "ops@meeet.world"
    assert payload["status"] == "pending"


# ----------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------


def test_store_creates_thread_and_lists_messages(tmp_path: Path) -> None:
    store = _store(tmp_path)

    async def run() -> None:
        thr = Thread.fresh(title="t", pack_slug="science")
        await store.insert_thread(thr)
        loaded = await store.get_thread(thr.id)
        assert loaded is not None
        assert loaded.title == "t"

        op = Message.from_operator(thr.id, "research papers about LLMs")
        await store.insert_message(op)
        ai = Message.from_tars(
            thr.id,
            "Here are 3 picks…",
            parent_msg_id=op.id,
            cost_usd=0.0,
            route="edge",
            tokens_in=5,
            tokens_out=20,
            voice_model="tars-local-chat-v1",
        )
        await store.insert_message(ai)

        msgs = await store.list_messages(thr.id, limit=10)
        assert [m.role for m in msgs] == ["operator", "tars"]
        assert msgs[0].content == "research papers about LLMs"
        assert msgs[1].voice_model == "tars-local-chat-v1"
        # updated_at moved forward
        refreshed = await store.get_thread(thr.id)
        assert refreshed is not None
        assert refreshed.updated_at >= thr.created_at

    asyncio.run(run())


def test_store_patches_thread_archived_and_pack(tmp_path: Path) -> None:
    store = _store(tmp_path)

    async def run() -> None:
        thr = Thread.fresh(title="t")
        await store.insert_thread(thr)
        patched = await store.patch_thread(
            thr.id, {"pack_slug": "research_lab", "archived": True}
        )
        assert patched is not None
        assert patched.pack_slug == "research_lab"
        assert patched.archived is True

        # Active list excludes archived by default
        active = await store.list_threads(archived=False)
        assert all(t.id != thr.id for t in active)
        archived = await store.list_threads(archived=True)
        assert any(t.id == thr.id for t in archived)

    asyncio.run(run())


def test_store_persists_tool_calls(tmp_path: Path) -> None:
    store = _store(tmp_path)

    async def run() -> None:
        thr = Thread.fresh()
        await store.insert_thread(thr)
        ai = Message.from_tars(thr.id, "running…")
        await store.insert_message(ai)

        tc = ToolCall.fresh(
            message_id=ai.id,
            slug="science",
            action_id="papers_today",
            args={"q": "LLM agents"},
        )
        await store.upsert_tool_call(tc)
        loaded = await store.list_tool_calls(ai.id)
        assert len(loaded) == 1
        assert loaded[0].args == {"q": "LLM agents"}
        assert loaded[0].status == "pending"

    asyncio.run(run())


def test_store_disabled_is_a_silent_noop(tmp_path: Path) -> None:
    store = ChatStore(str(tmp_path / "chat.sqlite"), enabled=False)

    async def run() -> None:
        thr = Thread.fresh()
        await store.insert_thread(thr)
        assert await store.get_thread(thr.id) is None
        assert await store.list_threads() == []

    asyncio.run(run())


def test_attachment_table_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)

    async def run() -> None:
        thr = Thread.fresh()
        await store.insert_thread(thr)
        att = Attachment(
            id=new_attachment_id(),
            thread_id=thr.id,
            message_id=None,
            mime="text/plain",
            filename="notes.txt",
            bytes_total=11,
            storage_path="/tmp/notes.txt",
            extracted_text="hello world",
            embedding_id=None,
            created_at=1714000000.0,
        )
        await store.insert_attachment(att)
        listed = await store.list_attachments(thr.id)
        assert len(listed) == 1
        assert listed[0].filename == "notes.txt"
        assert listed[0].extracted_text == "hello world"

    asyncio.run(run())
