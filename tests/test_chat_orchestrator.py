"""ChatOrchestrator integration tests.

Exercises the full streaming loop with deterministic voices, including
a mock voice that emits a tool-call sentinel so the policy gate +
domain action pipeline can be verified without an LLM in the loop.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, AsyncIterator, Sequence

import pytest

from backend.core.chat import ChatStore, Thread
from backend.core.chat.models import AttachmentRef, Message
from backend.core.chat.orchestrator import ChatOrchestrator
from backend.core.chat.voices import ChatChunk, ChatVoice, LocalChatVoice
from backend.core.policy import PolicyMode


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _store(tmp_path: Path) -> ChatStore:
    return ChatStore(str(tmp_path / "chat.sqlite"), enabled=True)


class _ScriptedVoice(ChatVoice):
    """Yield a fixed sequence of chunks — handy for tool-call routing tests."""

    def __init__(self, model: str, chunks: Sequence[ChatChunk]) -> None:
        self.model = model
        self._chunks = list(chunks)

    async def stream(  # type: ignore[override]
        self,
        thread,
        history,
        operator_text,
        attachments=(),
        *,
        system_prompt=None,
    ) -> AsyncIterator[ChatChunk]:
        for c in self._chunks:
            yield c


# ----------------------------------------------------------------------
# 1. End-to-end happy path with the local voice
# ----------------------------------------------------------------------


def test_orchestrator_streams_local_reply_and_persists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    orch = ChatOrchestrator(store=store, voice=LocalChatVoice())

    async def run() -> tuple[list[str], str]:
        thread = Thread.fresh(title="hello", pack_slug=None)
        await store.insert_thread(thread)
        kinds: list[str] = []
        final_text = ""
        async for ev in orch.post_message(
            thread.id, "hello, world!", session_id="ses_t1"
        ):
            kinds.append(ev.kind)
            if ev.kind == "message.completed":
                final_text = str(ev.data.get("content") or "")
        return kinds, final_text

    kinds, final_text = asyncio.run(run())
    # We expect at least: started → token(s) → usage → message.completed
    assert kinds[0] == "message.started"
    assert "token" in kinds
    assert "usage" in kinds
    assert kinds[-1] == "message.completed"
    assert final_text  # local voice composed something


def test_orchestrator_persists_operator_and_assistant(tmp_path: Path) -> None:
    store = _store(tmp_path)
    orch = ChatOrchestrator(store=store, voice=LocalChatVoice())

    async def run() -> list[Message]:
        thread = Thread.fresh()
        await store.insert_thread(thread)
        async for _ in orch.post_message(thread.id, "ping"):
            pass
        return await store.list_messages(thread.id, limit=10)

    msgs = asyncio.run(run())
    assert [m.role for m in msgs] == ["operator", "tars"]
    assert msgs[0].content == "ping"
    assert msgs[1].voice_model == "tars-local-chat-v1"
    assert msgs[1].cost_usd == 0.0  # local voice in the price table


def test_orchestrator_returns_error_for_unknown_thread(tmp_path: Path) -> None:
    store = _store(tmp_path)
    orch = ChatOrchestrator(store=store, voice=LocalChatVoice())

    async def run() -> list[str]:
        events = []
        async for ev in orch.post_message("thr_does_not_exist", "hi"):
            events.append(ev.kind)
        return events

    out = asyncio.run(run())
    assert out == ["error"]


# ----------------------------------------------------------------------
# 2. Tool-call routing
# ----------------------------------------------------------------------


_SCIENCE_TOOL_TEXT = (
    "Looking it up.\n"
    '<tool name="science.search_literature">'
    '{"query": "LLM agents", "limit": 1}'
    "</tool>\n"
    "Done."
)


def test_orchestrator_routes_non_destructive_tool_call(tmp_path: Path) -> None:
    """Non-destructive science.papers_today: should fire and complete."""

    store = _store(tmp_path)
    voice = _ScriptedVoice(
        "tars-mock-tool-v1",
        [
            ChatChunk(kind="text", text=_SCIENCE_TOOL_TEXT),
            ChatChunk(kind="usage", tokens_in=10, tokens_out=4),
            ChatChunk(kind="done"),
        ],
    )
    orch = ChatOrchestrator(store=store, voice=voice)

    async def run() -> tuple[list[str], list[dict[str, Any]]]:
        thread = Thread.fresh(pack_slug="science")
        await store.insert_thread(thread)
        kinds: list[str] = []
        completed: list[dict[str, Any]] = []
        async for ev in orch.post_message(
            thread.id, "find LLM agent papers", policy_mode=PolicyMode.AUTOPILOT
        ):
            kinds.append(ev.kind)
            if ev.kind == "tool_call.completed":
                completed.append(dict(ev.data))
        return kinds, completed

    kinds, completed = asyncio.run(run())
    assert "tool_call.proposed" in kinds
    assert "tool_call.allowed" in kinds
    assert "tool_call.completed" in kinds
    assert completed and completed[0]["slug"] == "science"
    assert completed[0]["action_id"] == "search_literature"


_DESTRUCTIVE_TOOL_TEXT = (
    "Drafting an email.\n"
    '<tool name="business.draft_email">'
    '{"to": "ops@meeet.world", "subject": "weekly", "send": false}'
    "</tool>\n"
    "Done."
)


def test_orchestrator_destructive_tool_blocks_in_confirm_mode(
    tmp_path: Path,
) -> None:
    """Confirm mode: destructive tool calls should land as queued events."""

    store = _store(tmp_path)
    voice = _ScriptedVoice(
        "tars-mock-tool-v1",
        [
            ChatChunk(kind="text", text=_DESTRUCTIVE_TOOL_TEXT),
            ChatChunk(kind="usage", tokens_in=12, tokens_out=4),
            ChatChunk(kind="done"),
        ],
    )
    orch = ChatOrchestrator(store=store, voice=voice)

    async def run() -> list[dict[str, Any]]:
        thread = Thread.fresh(pack_slug="business")
        await store.insert_thread(thread)
        events: list[dict[str, Any]] = []
        async for ev in orch.post_message(
            thread.id, "send the weekly email", policy_mode=PolicyMode.CONFIRM
        ):
            if ev.kind in {"tool_call.queued", "tool_call.allowed"}:
                events.append({"kind": ev.kind, **dict(ev.data)})
        return events

    events = asyncio.run(run())
    kinds = [e["kind"] for e in events]
    # Confirm mode should queue (or skip) — accept either as long as it
    # didn't auto-execute (no tool_call.allowed for destructive in
    # confirm mode unless a token is provided).
    assert "tool_call.queued" in kinds
    queued = [e for e in events if e["kind"] == "tool_call.queued"][0]
    assert queued["reason"] == "awaiting_confirmation"
    assert queued.get("policy_token")


def test_orchestrator_destructive_tool_runs_in_autopilot(tmp_path: Path) -> None:
    """Autopilot mode: destructive tool calls should execute through the gate."""

    store = _store(tmp_path)
    voice = _ScriptedVoice(
        "tars-mock-tool-v1",
        [
            ChatChunk(kind="text", text=_DESTRUCTIVE_TOOL_TEXT),
            ChatChunk(kind="usage", tokens_in=12, tokens_out=4),
            ChatChunk(kind="done"),
        ],
    )
    orch = ChatOrchestrator(store=store, voice=voice)

    async def run() -> list[dict[str, Any]]:
        thread = Thread.fresh(pack_slug="business")
        await store.insert_thread(thread)
        events: list[dict[str, Any]] = []
        async for ev in orch.post_message(
            thread.id, "send", policy_mode=PolicyMode.AUTOPILOT
        ):
            if ev.kind.startswith("tool_call."):
                events.append({"kind": ev.kind, **dict(ev.data)})
        return events

    events = asyncio.run(run())
    kinds = [e["kind"] for e in events]
    assert "tool_call.allowed" in kinds
    assert "tool_call.completed" in kinds


# ----------------------------------------------------------------------
# 3. Tool-block parser
# ----------------------------------------------------------------------


def test_split_tool_block_extracts_clean_request() -> None:
    text = (
        "Hello.\n"
        '<tool name="business.draft_email">{"to":"a@b.c","subject":"x"}</tool>'
        "\nBye."
    )
    emit, req, leftover = ChatOrchestrator._split_tool_block(text)
    assert emit == "Hello.\n"
    assert req is not None
    assert req["slug"] == "business"
    assert req["action_id"] == "draft_email"
    assert req["args"] == {"to": "a@b.c", "subject": "x"}
    assert leftover.strip() == "Bye."


def test_split_tool_block_holds_partial_sentinel() -> None:
    """Partial '<tool' should not leak to the operator stream."""

    text = "Streaming reply… <tool name=\"science.papers"
    emit, req, leftover = ChatOrchestrator._split_tool_block(text)
    assert emit == "Streaming reply… "
    assert req is None
    assert leftover.startswith("<tool")
