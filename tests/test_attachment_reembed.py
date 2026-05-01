"""Tests for the on-demand attachment re-embed path.

Two layers:

1. Storage helpers added to :class:`AttachmentStore`
   (``update_chunk_embedding``, ``list_chunks_by_model``).
2. The ``reembed_*`` orchestrators in
   ``backend/core/attachments/reembed.py``.
3. The two HTTP endpoints
   (``POST /api/chat/attachments/{id}/reembed`` and
   ``POST /api/chat/attachments/reembed-by-model``).
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_chat_db(monkeypatch, tmp_path: Path):
    """Pin every store to a tmp dir so tests don't touch the home
    directory's sqlite files.
    """

    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_BLOB_DIR", str(tmp_path / "blobs")
    )
    monkeypatch.setenv("MEMORY_STORE", "disabled")
    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("TARS_EMBEDDER", "hash")

    from backend.core.chat import store as chat_mod
    from backend.core.attachments import index as att_mod

    monkeypatch.setattr(chat_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(att_mod, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(chat_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(att_mod, "_SINGLETON", None, raising=False)


# ---------------------------------------------------------------------
# Helpers — seed a thread + an attachment + N chunks at a given model
# ---------------------------------------------------------------------


async def _seed_thread() -> str:
    from backend.core.chat.store import get_chat_store
    from backend.core.chat.models import Thread

    chat = get_chat_store()
    thr = Thread.fresh(title="Test", pack_slug="business")
    await chat.insert_thread(thr)
    return thr.id


async def _seed_attachment(
    thread_id: str, attachment_id: str = "att_test"
) -> None:
    from backend.core.attachments.index import (
        AttachmentRecord,
        get_attachment_store,
    )

    store = get_attachment_store()
    rec = AttachmentRecord(
        id=attachment_id,
        thread_id=thread_id,
        message_id=None,
        mime="text/plain",
        filename="test.txt",
        bytes_total=11,
        storage_path=f"/tmp/{attachment_id}.bin",
        extracted_text="hello world",
        embedding_id=None,
        created_at=time.time(),
        content_hash=f"hash_{attachment_id}",
        status="ready",
        error=None,
        meta={},
        char_count=11,
    )
    await store.upsert_attachment(rec)


async def _seed_chunks(
    *,
    attachment_id: str,
    thread_id: str,
    n: int,
    embedding_model: str | None = "tars-hash-bigram-v1-d384",
    text_prefix: str = "chunk",
) -> None:
    from backend.core.attachments.index import (
        Chunk,
        get_attachment_store,
    )

    store = get_attachment_store()
    chunks = []
    for i in range(n):
        chunks.append(
            Chunk(
                id=f"ck_{attachment_id}_{i}",
                attachment_id=attachment_id,
                thread_id=thread_id,
                ord=i,
                text=f"{text_prefix} {i} body text",
                char_start=0,
                char_end=20,
                heading=None,
                page=None,
                embedding_model=embedding_model,
                embedding_dim=384 if embedding_model else None,
                embedding=[0.1] * 384 if embedding_model else None,
                tokens_in=4,
                created_at=time.time(),
            )
        )
    await store.replace_chunks(attachment_id, thread_id, chunks)


# ---------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_chunk_embedding_writes_in_place():
    from backend.core.attachments.index import get_attachment_store

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    await _seed_chunks(attachment_id="att_test", thread_id=thr_id, n=1)

    store = get_attachment_store()
    ok = await store.update_chunk_embedding(
        chunk_id="ck_att_test_0",
        model="text-embedding-3-small",
        dim=4,
        vector=[1.0, 2.0, 3.0, 4.0],
    )
    assert ok is True

    chunks = await store.list_chunks(thr_id)
    assert chunks[0].embedding_model == "text-embedding-3-small"
    assert chunks[0].embedding_dim == 4
    assert chunks[0].embedding == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.asyncio
async def test_update_chunk_embedding_returns_false_for_missing_id():
    from backend.core.attachments.index import get_attachment_store

    await _seed_thread()
    store = get_attachment_store()
    ok = await store.update_chunk_embedding(
        chunk_id="does_not_exist",
        model="m",
        dim=1,
        vector=[1.0],
    )
    assert ok is False


@pytest.mark.asyncio
async def test_list_chunks_by_model_filters_by_model():
    from backend.core.attachments.index import get_attachment_store

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id, "att_a")
    await _seed_attachment(thr_id, "att_b")
    await _seed_chunks(
        attachment_id="att_a", thread_id=thr_id, n=2,
        embedding_model="tars-hash-bigram-v1-d384",
    )
    await _seed_chunks(
        attachment_id="att_b", thread_id=thr_id, n=1,
        embedding_model="text-embedding-3-small",
    )

    store = get_attachment_store()
    hashed = await store.list_chunks_by_model(
        embedding_model="tars-hash-bigram-v1-d384"
    )
    openai = await store.list_chunks_by_model(
        embedding_model="text-embedding-3-small"
    )
    assert len(hashed) == 2
    assert len(openai) == 1
    assert all(c.embedding_model == "tars-hash-bigram-v1-d384" for c in hashed)


@pytest.mark.asyncio
async def test_list_chunks_by_model_can_scope_to_thread():
    from backend.core.chat.models import Thread
    from backend.core.chat.store import get_chat_store
    from backend.core.attachments.index import get_attachment_store

    chat = get_chat_store()
    thr_a = Thread.fresh(title="A")
    thr_b = Thread.fresh(title="B")
    await chat.insert_thread(thr_a)
    await chat.insert_thread(thr_b)
    await _seed_attachment(thr_a.id, "att_a")
    await _seed_attachment(thr_b.id, "att_b")
    await _seed_chunks(
        attachment_id="att_a", thread_id=thr_a.id, n=2,
    )
    await _seed_chunks(
        attachment_id="att_b", thread_id=thr_b.id, n=3,
    )

    store = get_attachment_store()
    only_a = await store.list_chunks_by_model(
        embedding_model="tars-hash-bigram-v1-d384",
        thread_id=thr_a.id,
    )
    assert len(only_a) == 2


# ---------------------------------------------------------------------
# reembed_chunks orchestrator
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reembed_chunks_skips_blank_text():
    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.index import (
        Chunk,
        get_attachment_store,
    )
    from backend.core.attachments.reembed import reembed_chunks

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    await _seed_chunks(attachment_id="att_test", thread_id=thr_id, n=1)
    store = get_attachment_store()
    chunks = await store.list_chunks(thr_id)
    # Replace one with blank text
    blank = Chunk(
        id="ck_blank", attachment_id="att_test", thread_id=thr_id,
        ord=99, text="   ", char_start=0, char_end=3,
        heading=None, page=None, embedding_model="prev",
        embedding_dim=4, embedding=[0.0] * 4,
        tokens_in=1, created_at=time.time(),
    )
    res = await reembed_chunks(
        list(chunks) + [blank],
        embedder=HashEmbedder(),
        force=True,
    )
    assert res["ok"] is True
    assert res["skipped_blank"] == 1


@pytest.mark.asyncio
async def test_reembed_chunks_skips_when_already_at_target_model():
    """Without ``force``, chunks whose ``embedding_model`` already
    matches and already have a vector are left alone.
    """

    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.reembed import reembed_chunks

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    embedder = HashEmbedder()
    await _seed_chunks(
        attachment_id="att_test",
        thread_id=thr_id,
        n=2,
        embedding_model=embedder.model,
    )
    chunks = await get_attachment_store().list_chunks(thr_id)

    res = await reembed_chunks(chunks, embedder=embedder, force=False)
    assert res["ok"] is True
    assert res["embedded"] == 0
    assert res["skipped_same"] == 2


@pytest.mark.asyncio
async def test_reembed_chunks_force_rewrites_even_when_model_matches():
    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.reembed import reembed_chunks

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    embedder = HashEmbedder()
    await _seed_chunks(
        attachment_id="att_test",
        thread_id=thr_id,
        n=2,
        embedding_model=embedder.model,
    )
    chunks = await get_attachment_store().list_chunks(thr_id)

    res = await reembed_chunks(chunks, embedder=embedder, force=True)
    assert res["embedded"] == 2
    assert res["skipped_same"] == 0


@pytest.mark.asyncio
async def test_reembed_chunks_returns_failure_when_embedder_unavailable():
    from backend.core.attachments.embeddings import Embedder, EmbeddingResult
    from backend.core.attachments.reembed import reembed_chunks

    class Unavailable(Embedder):
        model = "absent"
        dim = 4

        async def is_available(self) -> bool:
            return False

        async def embed(self, texts):  # pragma: no cover - never reached
            raise RuntimeError("should not call")

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    await _seed_chunks(attachment_id="att_test", thread_id=thr_id, n=1)
    from backend.core.attachments.index import get_attachment_store

    chunks = await get_attachment_store().list_chunks(thr_id)
    res = await reembed_chunks(chunks, embedder=Unavailable())
    assert res["ok"] is False
    assert res["reason"] == "embedder_unavailable"


@pytest.mark.asyncio
async def test_reembed_chunks_isolates_batch_failure():
    """A raising embedder bumps ``failed`` instead of crashing."""

    from backend.core.attachments.embeddings import Embedder, EmbeddingResult
    from backend.core.attachments.reembed import reembed_chunks

    class Flaky(Embedder):
        model = "flaky"
        dim = 4

        async def is_available(self) -> bool:
            return True

        async def embed(self, texts):
            raise RuntimeError("simulated upstream timeout")

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    await _seed_chunks(attachment_id="att_test", thread_id=thr_id, n=2)
    from backend.core.attachments.index import get_attachment_store

    chunks = await get_attachment_store().list_chunks(thr_id)
    res = await reembed_chunks(
        chunks, embedder=Flaky(), force=True, target_model="flaky"
    )
    assert res["ok"] is True
    assert res["failed"] == 2
    assert res["embedded"] == 0


# ---------------------------------------------------------------------
# reembed_attachment orchestrator
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reembed_attachment_writes_through_store():
    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.reembed import reembed_attachment

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id)
    await _seed_chunks(
        attachment_id="att_test", thread_id=thr_id, n=3,
        embedding_model="legacy-model",
    )

    res = await reembed_attachment("att_test", embedder=HashEmbedder())
    assert res["ok"] is True
    assert res["embedded"] == 3
    assert res["attachment_id"] == "att_test"
    assert res["thread_id"] == thr_id

    store = get_attachment_store()
    chunks = await store.list_chunks(thr_id)
    assert all(
        c.embedding_model == HashEmbedder().model for c in chunks
    )


@pytest.mark.asyncio
async def test_reembed_attachment_404_for_missing_id():
    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.reembed import reembed_attachment

    res = await reembed_attachment(
        "att_does_not_exist", embedder=HashEmbedder()
    )
    assert res["ok"] is False
    assert res["reason"] == "attachment_not_found"


# ---------------------------------------------------------------------
# reembed_by_model orchestrator
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reembed_by_model_promotes_old_chunks_only():
    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.reembed import reembed_by_model

    thr_id = await _seed_thread()
    await _seed_attachment(thr_id, "att_old")
    await _seed_attachment(thr_id, "att_new")
    await _seed_chunks(
        attachment_id="att_old", thread_id=thr_id, n=2,
        embedding_model="legacy-model",
    )
    await _seed_chunks(
        attachment_id="att_new", thread_id=thr_id, n=1,
        embedding_model="text-embedding-3-small",
    )

    res = await reembed_by_model(
        "legacy-model", embedder=HashEmbedder(), force=True,
    )
    assert res["ok"] is True
    assert res["embedded"] == 2
    assert res["old_model"] == "legacy-model"

    store = get_attachment_store()
    chunks = await store.list_chunks(thr_id)
    by_model = {c.embedding_model for c in chunks}
    # legacy-model is gone, openai survives, hash is the new one
    assert "legacy-model" not in by_model
    assert "text-embedding-3-small" in by_model
    assert HashEmbedder().model in by_model


@pytest.mark.asyncio
async def test_reembed_by_model_scopes_to_thread():
    from backend.core.chat.models import Thread
    from backend.core.chat.store import get_chat_store
    from backend.core.attachments.embeddings import HashEmbedder
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.reembed import reembed_by_model

    chat = get_chat_store()
    thr_a = Thread.fresh(title="A")
    thr_b = Thread.fresh(title="B")
    await chat.insert_thread(thr_a)
    await chat.insert_thread(thr_b)
    await _seed_attachment(thr_a.id, "att_a")
    await _seed_attachment(thr_b.id, "att_b")
    await _seed_chunks(
        attachment_id="att_a", thread_id=thr_a.id, n=2,
        embedding_model="legacy-model",
    )
    await _seed_chunks(
        attachment_id="att_b", thread_id=thr_b.id, n=2,
        embedding_model="legacy-model",
    )

    res = await reembed_by_model(
        "legacy-model",
        embedder=HashEmbedder(),
        force=True,
        thread_id=thr_a.id,
    )
    assert res["embedded"] == 2
    assert res["thread_id"] == thr_a.id

    # Thread B's chunks are still on legacy-model.
    store = get_attachment_store()
    b_chunks = await store.list_chunks(thr_b.id)
    assert all(c.embedding_model == "legacy-model" for c in b_chunks)


# ---------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------


@pytest.fixture
def http_client():
    from web_extras.app import app
    return TestClient(app)


def test_http_reembed_attachment_round_trip(http_client: TestClient):
    asyncio.run(_seed_thread())
    # _seed_thread returns the id but we ran it once — fetch from DB
    from backend.core.chat.store import get_chat_store
    chat = get_chat_store()
    threads = asyncio.run(chat.list_threads(limit=10))
    thr_id = threads[0].id

    asyncio.run(_seed_attachment(thr_id))
    asyncio.run(_seed_chunks(
        attachment_id="att_test", thread_id=thr_id, n=2,
        embedding_model="legacy-model",
    ))

    res = http_client.post(
        "/api/chat/attachments/att_test/reembed", json={"force": True}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["embedded"] == 2
    assert body["attachment_id"] == "att_test"


def test_http_reembed_attachment_404(http_client: TestClient):
    res = http_client.post(
        "/api/chat/attachments/att_missing/reembed", json={}
    )
    assert res.status_code == 404


def test_http_reembed_by_model_requires_old_model(
    http_client: TestClient,
):
    res = http_client.post(
        "/api/chat/attachments/reembed-by-model", json={}
    )
    assert res.status_code == 400


def test_http_reembed_by_model_promotes(http_client: TestClient):
    from backend.core.chat.store import get_chat_store

    asyncio.run(_seed_thread())
    chat = get_chat_store()
    threads = asyncio.run(chat.list_threads(limit=10))
    thr_id = threads[0].id

    asyncio.run(_seed_attachment(thr_id))
    asyncio.run(_seed_chunks(
        attachment_id="att_test", thread_id=thr_id, n=3,
        embedding_model="legacy-model",
    ))

    res = http_client.post(
        "/api/chat/attachments/reembed-by-model",
        json={"old_model": "legacy-model", "force": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["embedded"] == 3
    assert body["old_model"] == "legacy-model"


def test_http_reembed_by_model_clamps_limit(http_client: TestClient):
    """Limit clamping: garbage value falls back to 500, then clamped
    inside the helper to [1, 5000]. Just confirm the endpoint doesn't
    500 on a negative value.
    """

    from backend.core.chat.store import get_chat_store

    asyncio.run(_seed_thread())
    chat = get_chat_store()
    threads = asyncio.run(chat.list_threads(limit=10))
    thr_id = threads[0].id
    asyncio.run(_seed_attachment(thr_id))
    asyncio.run(_seed_chunks(
        attachment_id="att_test", thread_id=thr_id, n=1,
        embedding_model="legacy-model",
    ))

    res = http_client.post(
        "/api/chat/attachments/reembed-by-model",
        json={
            "old_model": "legacy-model",
            "limit": "not-a-number",
            "force": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["embedded"] == 1
