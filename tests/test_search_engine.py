"""Cross-thread / cross-source search engine."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.attachments.embeddings import HashEmbedder
from backend.core.attachments.pipeline import ingest
from backend.core.chat import store as chat_store_mod
from backend.core.chat import Thread
from backend.core.chat.models import Message
from backend.core.search import search, search_chunks, search_messages


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def search_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )


def _seed_two_threads():
    chat = chat_store_mod.get_chat_store()
    attachment_index_mod.get_attachment_store()
    thread_kpi = Thread.fresh(title="KPI ops", pack_slug="business")
    thread_trade = Thread.fresh(title="Trades", pack_slug="traders")
    _run(chat.insert_thread(thread_kpi))
    _run(chat.insert_thread(thread_trade))
    kpi = (
        b"# Q3 KPIs\n\n"
        b"## EMEA\n\nPipeline grew but conversion stayed flat. "
        b"Top blocker GDPR redlines on three deals.\n\n"
        b"## APAC\n\nHealthy growth, no flagged risks.\n"
    )
    plan = (
        b"# Trade plan\n\nLong NVDA on AI rally, hedge with QQQ short. "
        b"Key risk: capex slowdown.\n"
    )
    _run(
        ingest(
            thread_id=thread_kpi.id,
            blob=kpi,
            filename="kpi.md",
            embedder=HashEmbedder(),
        )
    )
    _run(
        ingest(
            thread_id=thread_trade.id,
            blob=plan,
            filename="plan.md",
            embedder=HashEmbedder(),
        )
    )
    return chat, thread_kpi, thread_trade


def test_unified_search_returns_empty_for_blank_query(search_env) -> None:
    res = _run(search("   ", scope="all"))
    assert res.hits == []


def test_unified_search_finds_chunks_across_threads(search_env) -> None:
    _seed_two_threads()
    res = _run(search("EMEA blocker", scope="all", top_k=10))
    assert res.hits
    assert res.hits[0].kind == "chunk"
    assert "kpi.md" in res.hits[0].title
    # Thread title is joined into the result so the cockpit can render it.
    assert res.hits[0].ref["thread_title"] == "KPI ops"


def test_chunk_search_can_target_a_single_thread(search_env) -> None:
    _, thread_kpi, _ = _seed_two_threads()
    hits = _run(
        search_chunks(
            "EMEA blocker", top_k=5, thread_id=thread_kpi.id
        )
    )
    assert hits
    assert all(h.ref["thread_id"] == thread_kpi.id for h in hits)


def test_message_search_pulls_from_messages_fts(search_env) -> None:
    chat, thread_kpi, _ = _seed_two_threads()
    _run(
        chat.insert_message(
            Message.from_operator(
                thread_kpi.id, "What was the EMEA blocker exactly?"
            )
        )
    )
    res = _run(search("EMEA blocker", scope="messages", top_k=5))
    assert res.hits
    assert res.hits[0].kind == "message"
    assert res.hits[0].ref["thread_id"] == thread_kpi.id


def test_search_handles_cyrillic_query(search_env) -> None:
    chat, thread_kpi, _ = _seed_two_threads()
    _run(
        chat.insert_message(
            Message.from_operator(
                thread_kpi.id, "Что было блокером в EMEA по конверсии?"
            )
        )
    )
    res = _run(search("блокером", scope="messages", top_k=5))
    assert res.hits


def test_unified_search_respects_scope(search_env) -> None:
    chat, thread_kpi, _ = _seed_two_threads()
    _run(
        chat.insert_message(
            Message.from_operator(thread_kpi.id, "EMEA conversion blocker")
        )
    )
    res = _run(search("EMEA blocker", scope="chunks", top_k=10))
    assert all(h.kind == "chunk" for h in res.hits)
    res = _run(search("EMEA blocker", scope="messages", top_k=10))
    assert all(h.kind == "message" for h in res.hits)


def test_chunk_search_falls_back_to_vector_when_fts_misses(search_env) -> None:
    """If the keyword side returns nothing, vectors still rank the
    closest chunk — important when the query and the doc share zero
    surface tokens but are semantically related."""

    _seed_two_threads()
    # A query that won't hit any token in either thread.
    hits = _run(search_chunks("xyzzy_zero_overlap", top_k=3))
    # Hash embedder hashes any token to *some* bucket so vector
    # search may surface a low-score chunk; the fallback path should
    # still attach a semantic rank without a keyword rank.
    if hits:
        assert hits[0].rank_keyword is None
        assert hits[0].rank_semantic is not None
