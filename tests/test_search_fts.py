"""FTS5 backbone — chunk + message indexing, sanitisation, backfill."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.attachments.embeddings import HashEmbedder
from backend.core.attachments.pipeline import ingest
from backend.core.chat import store as chat_store_mod
from backend.core.chat import Thread
from backend.core.chat.models import Message
from backend.core.search import (
    backfill_chunk_fts,
    backfill_message_fts,
    drop_fts_tables,
    ensure_fts_indexes,
    fts_match_chunks,
    fts_match_messages,
)
from backend.core.search.fts import sanitise_query


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def fts_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


# ----------------------------------------------------------------------
# Sanitiser
# ----------------------------------------------------------------------


def test_sanitise_query_trims_punctuation_and_quotes_tokens() -> None:
    assert sanitise_query("EMEA: blocker?") == '"EMEA" OR "blocker"'
    # FTS5 keyword tokens are dropped; surviving identifiers are quoted.
    assert sanitise_query('quote with stuff') == '"quote" OR "with" OR "stuff"'
    assert sanitise_query("AND OR NOT NEAR") == ""
    assert sanitise_query("") == ""
    assert sanitise_query("  *** ") == ""


def test_sanitise_query_handles_cyrillic() -> None:
    out = sanitise_query("Что было блокером?")
    assert "Что" in out
    assert "блокером" in out


# ----------------------------------------------------------------------
# Indexes
# ----------------------------------------------------------------------


def test_ensure_fts_indexes_creates_tables_idempotently(fts_env) -> None:
    chat = chat_store_mod.get_chat_store()
    ensure_fts_indexes(chat=chat)
    # Second call should not raise.
    ensure_fts_indexes(chat=chat)
    # Empty state — both queries return empty.
    assert fts_match_chunks("anything", chat=chat) == []
    assert fts_match_messages("anything", chat=chat) == []


def test_chunk_index_populated_on_ingest(fts_env) -> None:
    chat = chat_store_mod.get_chat_store()
    attachment_index_mod.get_attachment_store()
    thread = Thread.fresh(title="t")
    _run(chat.insert_thread(thread))
    blob = (
        b"# KPI report\n\n## EMEA\n\n"
        b"Pipeline grew but conversion stayed flat. "
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
    rows = fts_match_chunks("EMEA blocker GDPR", chat=chat)
    assert rows
    assert "EMEA" in rows[0]["snippet"] or "GDPR" in rows[0]["snippet"]
    assert "<mark>" in rows[0]["snippet"]


def test_message_index_populated_on_insert(fts_env) -> None:
    chat = chat_store_mod.get_chat_store()
    thread = Thread.fresh(title="t")
    _run(chat.insert_thread(thread))
    msg = Message.from_operator(thread.id, "What was the EMEA blocker?")
    _run(chat.insert_message(msg))
    rows = fts_match_messages("EMEA blocker", chat=chat)
    assert rows
    assert rows[0]["msg_id"] == msg.id
    assert rows[0]["thread_id"] == thread.id


def test_backfill_rebuilds_index(fts_env) -> None:
    chat = chat_store_mod.get_chat_store()
    attachment_index_mod.get_attachment_store()
    thread = Thread.fresh(title="t")
    _run(chat.insert_thread(thread))
    _run(
        ingest(
            thread_id=thread.id,
            blob=b"hello world keyword test",
            filename="x.txt",
            embedder=HashEmbedder(),
        )
    )
    _run(chat.insert_message(Message.from_operator(thread.id, "hello hello")))
    drop_fts_tables(chat=chat)
    ensure_fts_indexes(chat=chat)
    # After ensure with empty FTS the lazy backfill should refill from
    # the source tables, but ensure runs only on first creation. Force
    # an explicit backfill — that's what the public helpers are for.
    chunk_count = backfill_chunk_fts(chat=chat)
    msg_count = backfill_message_fts(chat=chat)
    assert chunk_count == 1
    assert msg_count == 1


def test_chunk_index_cleared_on_attachment_delete(fts_env) -> None:
    chat = chat_store_mod.get_chat_store()
    attachment_index_mod.get_attachment_store()
    thread = Thread.fresh(title="t")
    _run(chat.insert_thread(thread))
    res = _run(
        ingest(
            thread_id=thread.id,
            blob=b"unique-token-zorbax-42",
            filename="z.txt",
            embedder=HashEmbedder(),
        )
    )
    rows = fts_match_chunks("zorbax", chat=chat)
    assert rows

    from backend.core.attachments.pipeline import delete_attachment
    _run(delete_attachment(res.record.id))
    rows = fts_match_chunks("zorbax", chat=chat)
    assert rows == []
