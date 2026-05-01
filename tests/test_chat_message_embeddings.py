"""Vector + BM25 blend for chat messages.

Exercises three layers in one place:

1. ``ChatStore`` schema migrations + set/get/list/count helpers.
2. ``embed_pending_messages`` orchestrator.
3. ``search_messages`` RRF fusion across keyword + vector.

Plus the HTTP endpoint ``POST /api/search/embed-messages``.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments.embeddings import HashEmbedder
from backend.core.chat import store as chat_store_mod
from backend.core.chat import Thread
from backend.core.chat.embeddings import embed_pending_messages
from backend.core.chat.models import Message
from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.search import search_messages


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def isolated_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)


def _seed_thread() -> tuple[ChatStore, Thread]:
    chat = get_chat_store()
    thread = Thread.fresh(title="Brief", pack_slug="business")
    _run(chat.insert_thread(thread))
    return chat, thread


def test_messages_table_carries_embedding_columns(isolated_chat) -> None:
    chat = get_chat_store()
    conn = sqlite3.connect(chat.db_path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
    finally:
        conn.close()
    assert {"embedding_model", "embedding_dim", "embedding_blob"} <= cols


def test_set_and_get_message_embedding(isolated_chat) -> None:
    chat, thread = _seed_thread()
    msg = Message.from_operator(thread.id, "What's the EMEA blocker?")
    _run(chat.insert_message(msg))

    _run(
        chat.set_message_embedding(
            msg.id,
            model="test-fake",
            dim=4,
            vector=[0.1, 0.2, 0.3, 0.4],
        )
    )
    out = _run(chat.get_message_embeddings([msg.id]))
    assert msg.id in out
    info = out[msg.id]
    assert info["model"] == "test-fake"
    assert info["dim"] == 4
    assert info["vector"] == pytest.approx([0.1, 0.2, 0.3, 0.4], abs=1e-6)


def test_pending_count_and_list_walk_only_unembedded(isolated_chat) -> None:
    chat, thread = _seed_thread()
    a = Message.from_operator(thread.id, "First operator question.")
    b = Message.from_operator(thread.id, "Second operator question.")
    _run(chat.insert_message(a))
    _run(chat.insert_message(b))

    assert _run(chat.count_messages_pending_embedding()) == 2
    pending = _run(chat.list_messages_pending_embedding())
    assert {m.id for m in pending} == {a.id, b.id}

    _run(
        chat.set_message_embedding(
            a.id, model="m", dim=2, vector=[1.0, 0.0]
        )
    )
    assert _run(chat.count_messages_pending_embedding()) == 1
    pending = _run(chat.list_messages_pending_embedding())
    assert {m.id for m in pending} == {b.id}


def test_pending_skips_messages_with_empty_content(isolated_chat) -> None:
    chat, thread = _seed_thread()
    blank = Message.from_operator(thread.id, "")
    real = Message.from_operator(thread.id, "the real one")
    _run(chat.insert_message(blank))
    _run(chat.insert_message(real))
    pending = _run(chat.list_messages_pending_embedding())
    assert {m.id for m in pending} == {real.id}


def test_embed_pending_messages_uses_hash_embedder(isolated_chat) -> None:
    chat, thread = _seed_thread()
    for text in [
        "Pipeline grew but conversion stayed flat in EMEA.",
        "APAC is healthy, no flagged risks.",
        "Long NVDA on AI rally; hedge with QQQ short.",
    ]:
        _run(chat.insert_message(Message.from_operator(thread.id, text)))

    out = _run(embed_pending_messages(chat=chat, embedder=HashEmbedder()))
    assert out["ok"] is True
    assert out["embedded"] == 3
    assert out["failed"] == 0
    assert out["remaining"] == 0
    assert "tars-hash-bigram-v1" in out["model"]


def test_embed_pending_returns_unavailable_for_offline_embedder(
    isolated_chat,
) -> None:
    chat, thread = _seed_thread()
    _run(chat.insert_message(Message.from_operator(thread.id, "hi")))

    class _Unavailable(HashEmbedder):
        async def is_available(self) -> bool:  # type: ignore[override]
            return False

    out = _run(embed_pending_messages(chat=chat, embedder=_Unavailable()))
    assert out["ok"] is False
    assert out["reason"] == "embedder_unavailable"
    assert out["remaining"] == 1


def test_embed_pending_short_circuits_when_nothing_pending(
    isolated_chat,
) -> None:
    chat, _ = _seed_thread()
    out = _run(embed_pending_messages(chat=chat, embedder=HashEmbedder()))
    assert out["ok"] is True
    assert out["embedded"] == 0
    assert out["total_pending"] == 0


def test_embed_pending_skips_failing_batch_without_raising(
    isolated_chat,
) -> None:
    chat, thread = _seed_thread()
    msg = Message.from_operator(thread.id, "anything")
    _run(chat.insert_message(msg))

    class _Boom(HashEmbedder):
        async def embed(self, texts):  # type: ignore[override]
            raise RuntimeError("transport down")

    out = _run(embed_pending_messages(chat=chat, embedder=_Boom()))
    assert out["ok"] is True
    assert out["embedded"] == 0
    assert out["failed"] == 1
    assert out["remaining"] == 1


def test_search_messages_keyword_only_when_no_embeddings(
    isolated_chat,
) -> None:
    chat, thread = _seed_thread()
    _run(
        chat.insert_message(
            Message.from_operator(thread.id, "EMEA blocker GDPR redlines")
        )
    )
    hits = _run(search_messages("EMEA blocker", top_k=5))
    assert hits, "BM25 should still hit even without embeddings"
    assert hits[0].rank_keyword == 1
    assert hits[0].rank_semantic is None


def test_search_messages_blends_vector_with_bm25(isolated_chat) -> None:
    chat, thread = _seed_thread()
    bm25_only = Message.from_operator(
        thread.id,
        "EMEA blocker GDPR redlines on three deals",
    )
    paraphrase = Message.from_operator(
        thread.id,
        "European pipeline conversion stayed flat — same blocker pattern",
    )
    unrelated = Message.from_operator(
        thread.id,
        "Trade plan: long NVDA on AI rally with QQQ hedge",
    )
    for m in (bm25_only, paraphrase, unrelated):
        _run(chat.insert_message(m))

    out = _run(embed_pending_messages(chat=chat, embedder=HashEmbedder()))
    assert out["embedded"] == 3

    hits = _run(
        search_messages(
            "EMEA blocker", top_k=5, embedder=HashEmbedder()
        )
    )
    msg_ids = [h.ref["msg_id"] for h in hits]
    assert bm25_only.id in msg_ids
    top_hit = hits[0]
    assert top_hit.rank_keyword is not None
    semantic_ranked = [h for h in hits if h.rank_semantic is not None]
    assert semantic_ranked, "at least one hit should carry a semantic rank"
    assert top_hit.score > 0.0


def test_search_messages_embedder_failure_falls_back_silently(
    isolated_chat,
) -> None:
    chat, thread = _seed_thread()
    _run(
        chat.insert_message(
            Message.from_operator(thread.id, "EMEA blocker text")
        )
    )
    _run(embed_pending_messages(chat=chat, embedder=HashEmbedder()))

    class _BoomEmbedder(HashEmbedder):
        async def embed(self, texts):  # type: ignore[override]
            raise RuntimeError("embedder down")

    hits = _run(
        search_messages("EMEA blocker", top_k=5, embedder=_BoomEmbedder())
    )
    assert hits
    assert hits[0].rank_keyword is not None
    assert hits[0].rank_semantic is None


# --------------------------------------------------------------- HTTP


@pytest.fixture()
def http_app(isolated_chat):
    from web_extras.app import app

    with TestClient(app) as client:
        yield client


def test_embed_messages_endpoint_runs(http_app: TestClient) -> None:
    chat = get_chat_store()
    thread = Thread.fresh(title="HTTP", pack_slug="business")
    _run(chat.insert_thread(thread))
    _run(
        chat.insert_message(
            Message.from_operator(thread.id, "what is the EMEA blocker?")
        )
    )

    resp = http_app.post(
        "/api/search/embed-messages", json={"limit": 50, "batch_size": 8}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["embedded"] >= 1
    assert body["pending_at_start"] >= 1
    assert body["remaining"] == 0


def test_embed_messages_endpoint_caps_input(http_app: TestClient) -> None:
    resp = http_app.post(
        "/api/search/embed-messages",
        json={"limit": 99999, "batch_size": 99999},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
