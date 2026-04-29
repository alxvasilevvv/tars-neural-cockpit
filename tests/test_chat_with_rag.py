"""End-to-end test: ingest a file, ask a question, verify the orchestrator
emits ``context.retrieved`` events and persists sources on the assistant
message."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.attachments import ingest
from backend.core.attachments.embeddings import HashEmbedder
from backend.core.chat import store as chat_store_mod
from backend.core.chat import Thread
from backend.core.chat.orchestrator import ChatOrchestrator
from backend.core.chat.voices import LocalChatVoice


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )


def test_orchestrator_emits_context_retrieved_when_thread_has_chunks(env) -> None:
    chat_store = chat_store_mod.get_chat_store()
    thread = Thread.fresh(title="rag", pack_slug="business")
    _run(chat_store.insert_thread(thread))

    blob = (
        b"# KPI report\n\n## EMEA\n\nPipeline grew but conversion stayed flat. "
        b"Top blocker GDPR redlines on three deals.\n"
    )
    _run(
        ingest(
            thread_id=thread.id,
            blob=blob,
            filename="kpi.md",
            embedder=HashEmbedder(),
        )
    )

    orch = ChatOrchestrator(store=chat_store, voice=LocalChatVoice())

    async def collect():
        events = []
        async for ev in orch.post_message(
            thread.id, "Расскажи про блокер в EMEA"
        ):
            events.append(ev)
        return events

    events = _run(collect())
    kinds = [ev.kind for ev in events]
    assert "context.retrieved" in kinds

    ctx = next(ev for ev in events if ev.kind == "context.retrieved")
    assert len(ctx.data["chunks"]) >= 1
    assert ctx.data["chunks"][0]["citation_id"] == "chunk_1"

    completed = next(ev for ev in events if ev.kind == "message.completed")
    sources = completed.data.get("sources") or []
    assert sources
    assert sources[0]["citation_id"] == "chunk_1"
    assert sources[0]["filename"] == "kpi.md"


def test_orchestrator_skips_retrieval_for_empty_thread(env) -> None:
    chat_store = chat_store_mod.get_chat_store()
    thread = Thread.fresh(title="empty")
    _run(chat_store.insert_thread(thread))

    orch = ChatOrchestrator(store=chat_store, voice=LocalChatVoice())

    async def collect():
        events = []
        async for ev in orch.post_message(thread.id, "say hi please"):
            events.append(ev)
        return events

    events = _run(collect())
    kinds = [ev.kind for ev in events]
    assert "context.retrieved" not in kinds
    assert "message.completed" in kinds


def test_orchestrator_skips_retrieval_for_short_query(env) -> None:
    chat_store = chat_store_mod.get_chat_store()
    thread = Thread.fresh(title="short")
    _run(chat_store.insert_thread(thread))
    _run(
        ingest(
            thread_id=thread.id,
            blob=b"# heavy ML doc with lots of text " * 30,
            filename="ml.md",
            embedder=HashEmbedder(),
        )
    )

    orch = ChatOrchestrator(store=chat_store, voice=LocalChatVoice())

    async def collect():
        events = []
        async for ev in orch.post_message(thread.id, "yes"):
            events.append(ev)
        return events

    events = _run(collect())
    kinds = [ev.kind for ev in events]
    assert "context.retrieved" not in kinds
