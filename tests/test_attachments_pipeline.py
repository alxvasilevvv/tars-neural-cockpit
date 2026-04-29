"""Ingest pipeline + retrieval tests.

We use a temp directory for file storage and the per-test ``ChatStore``
so we don't touch ``~/.tars`` during CI.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from backend.core.attachments import ingest, retrieve
from backend.core.attachments.embeddings import HashEmbedder
from backend.core.attachments.index import AttachmentStore
from backend.core.attachments.pipeline import (
    IngestError,
    delete_attachment,
)
from backend.core.chat import ChatStore, Thread


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def chat_attachment_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")

    from backend.core.chat import store as chat_store_mod
    from backend.core.attachments import index as attachment_index_mod

    chat_store_mod._SINGLETON = None
    attachment_index_mod._SINGLETON = None
    chat_store = chat_store_mod.get_chat_store()
    attachment_store = attachment_index_mod.get_attachment_store()

    yield chat_store, attachment_store, tmp_path

    chat_store_mod._SINGLETON = None
    attachment_index_mod._SINGLETON = None


def _make_thread(chat_store: ChatStore) -> Thread:
    thread = Thread.fresh(title="t")
    _run(chat_store.insert_thread(thread))
    return thread


def test_ingest_persists_record_and_chunks(chat_attachment_env) -> None:
    chat_store, attachment_store, tmp_path = chat_attachment_env
    thread = _make_thread(chat_store)
    blob = (
        b"# KPI report\n\n"
        b"EMEA pipeline grew but conversion stayed flat.\n\n"
        b"## Top blocker\n\nGDPR redlines on three deals.\n"
    )

    result = _run(
        ingest(
            thread_id=thread.id,
            blob=blob,
            filename="kpi.md",
            embedder=HashEmbedder(),
        )
    )

    assert result.duplicate is False
    assert result.chunk_count >= 1
    assert result.embedding_model.startswith("tars-hash-bigram")

    saved = _run(attachment_store.get_attachment(result.record.id))
    assert saved is not None
    assert saved.thread_id == thread.id
    assert saved.filename == "kpi.md"
    assert saved.char_count > 0
    assert os.path.isfile(saved.storage_path)


def test_ingest_dedupes_identical_bytes_in_same_thread(chat_attachment_env) -> None:
    chat_store, _, _ = chat_attachment_env
    thread = _make_thread(chat_store)
    blob = b"alpha beta gamma delta " * 5

    a = _run(
        ingest(
            thread_id=thread.id,
            blob=blob,
            filename="a.txt",
            embedder=HashEmbedder(),
        )
    )
    b = _run(
        ingest(
            thread_id=thread.id,
            blob=blob,
            filename="a.txt",
            embedder=HashEmbedder(),
        )
    )
    assert b.duplicate is True
    assert a.record.id == b.record.id


def test_ingest_rejects_oversized_blob(chat_attachment_env, monkeypatch) -> None:
    chat_store, _, _ = chat_attachment_env
    thread = _make_thread(chat_store)
    monkeypatch.setenv("TARS_ATTACHMENT_MAX_BYTES", str(8 * 1024))

    with pytest.raises(IngestError):
        _run(
            ingest(
                thread_id=thread.id,
                blob=b"x" * (16 * 1024),
                filename="big.bin",
                embedder=HashEmbedder(),
            )
        )


def test_ingest_rejects_empty_blob(chat_attachment_env) -> None:
    chat_store, _, _ = chat_attachment_env
    thread = _make_thread(chat_store)
    with pytest.raises(IngestError):
        _run(
            ingest(
                thread_id=thread.id,
                blob=b"",
                filename="zero.txt",
                embedder=HashEmbedder(),
            )
        )


def test_retrieve_returns_relevant_chunks(chat_attachment_env) -> None:
    chat_store, _, _ = chat_attachment_env
    thread = _make_thread(chat_store)
    blob = (
        b"# Quarterly KPI report\n\n"
        b"## North America\n\n"
        b"Closed 24 deals, average deal size 18k USD.\n\n"
        b"## EMEA\n\n"
        b"Pipeline grew but conversion stayed flat. "
        b"Top blocker GDPR redlines on three deals.\n\n"
        b"## APAC\n\n"
        b"Healthy growth, no flagged risks.\n"
    )
    _run(
        ingest(
            thread_id=thread.id,
            blob=blob,
            filename="kpi.md",
            embedder=HashEmbedder(),
        )
    )

    hits = _run(
        retrieve(
            thread.id,
            "EMEA conversion blocker GDPR",
            top_k=4,
            embedder=HashEmbedder(),
        )
    )
    assert hits, "retrieval should have at least one hit"
    assert hits[0].citation_id == "chunk_1"
    # The top chunk should mention either EMEA, GDPR, or blocker terms.
    top_text = hits[0].chunk.text.lower()
    assert any(t in top_text for t in ("emea", "gdpr", "blocker"))


def test_retrieve_returns_empty_for_blank_thread(chat_attachment_env) -> None:
    chat_store, _, _ = chat_attachment_env
    thread = _make_thread(chat_store)
    hits = _run(
        retrieve(
            thread.id,
            "anything",
            top_k=4,
            embedder=HashEmbedder(),
        )
    )
    assert hits == []


def test_delete_attachment_removes_row_chunks_and_bytes(chat_attachment_env) -> None:
    chat_store, attachment_store, _ = chat_attachment_env
    thread = _make_thread(chat_store)
    blob = b"something to delete\n\nstill here.\n"

    res = _run(
        ingest(
            thread_id=thread.id,
            blob=blob,
            filename="delme.txt",
            embedder=HashEmbedder(),
        )
    )
    saved = _run(attachment_store.get_attachment(res.record.id))
    assert saved is not None
    storage_path = saved.storage_path

    ok = _run(delete_attachment(res.record.id))
    assert ok is True
    assert _run(attachment_store.get_attachment(res.record.id)) is None
    assert not os.path.exists(storage_path)
