"""Chunks attachment-DB JOIN filters (Phase L8 follow-up to PR #46).

Pins ``pack:`` / ``mime:`` / ``since:`` / ``until:`` filters for chunk
search. The attachments + chunks tables live in the same SQLite WAL
file as ``threads``/``messages`` (``~/.tars/chat.sqlite``), so this is
a single-DB JOIN — no cross-store coordination.

Three layers under test:

1. ``fts_match_chunks`` low-level kwargs.
2. ``search_chunks`` engine-level inline DSL parsing
   (``pack:business`` etc.).
3. Unified ``search`` propagating filters into the chunks scope.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
import uuid
from pathlib import Path

import pytest

from backend.core.attachments import index as attachment_index_mod
from backend.core.attachments.index import Chunk, get_attachment_store
from backend.core.chat import Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Attachment, new_attachment_id
from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.search.engine import search, search_chunks
from backend.core.search.fts import (
    ensure_fts_indexes,
    fts_match_chunks,
    index_chunk,
)


def _run(coro):
    return asyncio.run(coro)


def _mk_attachment(
    thread_id: str, mime: str, filename: str, *, created_at: float | None = None
) -> Attachment:
    return Attachment(
        id=new_attachment_id(),
        thread_id=thread_id,
        message_id=None,
        mime=mime,
        filename=filename,
        bytes_total=10,
        storage_path=f"/tmp/{filename}",
        extracted_text=None,
        embedding_id=None,
        created_at=created_at or time.time(),
    )


def _override_created_at(
    chat: ChatStore, attachment_id: str, created_at: float
) -> None:
    conn = sqlite3.connect(chat.db_path)
    try:
        conn.execute(
            "UPDATE attachments SET created_at = ? WHERE id = ?",
            (created_at, attachment_id),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def isolated_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
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


@pytest.fixture()
def seeded(isolated_chat) -> dict[str, str]:
    """Seed two threads (business, science) with three attachments
    + one matching chunk each. ``a3`` (image) is back-dated ~1M
    seconds so time-window filters can exclude it."""

    chat = get_chat_store()

    t1 = Thread.fresh(title="deal", pack_slug="business")
    t2 = Thread.fresh(title="paper", pack_slug="science")
    _run(chat.insert_thread(t1))
    _run(chat.insert_thread(t2))

    now = time.time()
    a1 = _mk_attachment(t1.id, "application/pdf", "deal.pdf", created_at=now)
    a2 = _mk_attachment(t2.id, "text/plain", "abs.txt", created_at=now)
    a3 = _mk_attachment(t2.id, "image/png", "fig.png", created_at=now)
    for a in (a1, a2, a3):
        _run(chat.insert_attachment(a))
    _override_created_at(chat, a3.id, now - 1_000_000)

    ensure_fts_indexes(chat=chat)
    attachments = get_attachment_store()

    rows = [
        (t1.id, a1.id, "EMEA blocker quarterly numbers"),
        (t2.id, a2.id, "EMEA neuroscience review piece"),
        (t2.id, a3.id, "EMEA architecture diagram thumbnail"),
    ]
    for thread_id, att_id, text in rows:
        chunk_id = "c_" + uuid.uuid4().hex[:10]
        chunk = Chunk(
            id=chunk_id,
            attachment_id=att_id,
            thread_id=thread_id,
            ord=0,
            text=text,
            char_start=0,
            char_end=len(text),
            heading=None,
            page=None,
            embedding_model=None,
            embedding_dim=None,
            embedding=None,
            tokens_in=0,
            created_at=now,
        )
        _run(attachments.replace_chunks(att_id, thread_id, [chunk]))
        index_chunk(
            chunk_id=chunk_id,
            attachment_id=att_id,
            thread_id=thread_id,
            text=text,
        )

    return {
        "t_biz": t1.id,
        "t_sci": t2.id,
        "a1": a1.id,
        "a2": a2.id,
        "a3": a3.id,
    }


# ---------------------------------------------------------------------
# Low-level fts_match_chunks
# ---------------------------------------------------------------------


def test_fts_no_filters_returns_every_match(seeded) -> None:
    rows = fts_match_chunks("EMEA")
    assert {r["attachment_id"] for r in rows} == {
        seeded["a1"],
        seeded["a2"],
        seeded["a3"],
    }


def test_fts_pack_filter_narrows_to_business(seeded) -> None:
    rows = fts_match_chunks("EMEA", pack="business")
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a1"]}


def test_fts_pack_filter_narrows_to_science(seeded) -> None:
    rows = fts_match_chunks("EMEA", pack="science")
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a2"], seeded["a3"]}


def test_fts_mime_filter_literal(seeded) -> None:
    rows = fts_match_chunks("EMEA", mime="text/plain")
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a2"]}


def test_fts_mime_filter_wildcard_matches_image_subtypes(seeded) -> None:
    rows = fts_match_chunks("EMEA", mime="image/*")
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a3"]}


def test_fts_since_filter_excludes_old_attachments(seeded) -> None:
    rows = fts_match_chunks("EMEA", since=time.time() - 60)
    ids = {r["attachment_id"] for r in rows}
    # a3 was back-dated ~1M seconds, so it should drop out.
    assert ids == {seeded["a1"], seeded["a2"]}


def test_fts_until_filter_keeps_old_drops_new(seeded) -> None:
    rows = fts_match_chunks("EMEA", until=time.time() - 60)
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a3"]}


def test_fts_pack_and_mime_compose_with_AND(seeded) -> None:
    rows = fts_match_chunks(
        "EMEA", pack="science", mime="text/plain"
    )
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a2"]}


def test_fts_thread_id_still_works_alongside_new_filters(seeded) -> None:
    rows = fts_match_chunks(
        "EMEA", thread_id=seeded["t_sci"], mime="image/*"
    )
    ids = {r["attachment_id"] for r in rows}
    assert ids == {seeded["a3"]}


def test_fts_no_match_returns_empty(seeded) -> None:
    rows = fts_match_chunks("EMEA", pack="traders")
    assert rows == []


# ---------------------------------------------------------------------
# search_chunks parses inline DSL
# ---------------------------------------------------------------------


def test_search_chunks_parses_inline_pack_token(seeded) -> None:
    hits = _run(search_chunks("EMEA pack:business"))
    assert hits, "expected at least one hit"
    assert all(h.ref.get("thread_id") == seeded["t_biz"] for h in hits)
    assert any(h.ref.get("attachment_id") == seeded["a1"] for h in hits)


def test_search_chunks_parses_inline_mime_token(seeded) -> None:
    hits = _run(search_chunks("EMEA mime:text/plain"))
    assert {h.ref.get("attachment_id") for h in hits} == {seeded["a2"]}


def test_search_chunks_explicit_kwarg_wins_over_inline(seeded) -> None:
    # Inline says business, kwarg says science → science wins.
    hits = _run(
        search_chunks("EMEA pack:business", pack="science")
    )
    ids = {h.ref.get("attachment_id") for h in hits}
    assert ids and ids.issubset({seeded["a2"], seeded["a3"]})


def test_search_chunks_inline_since_excludes_old_attachment(seeded) -> None:
    hits = _run(search_chunks("EMEA since:1d"))
    ids = {h.ref.get("attachment_id") for h in hits}
    assert seeded["a3"] not in ids
    assert seeded["a1"] in ids or seeded["a2"] in ids


# ---------------------------------------------------------------------
# Unified search() propagates filters
# ---------------------------------------------------------------------


def test_unified_search_chunks_scope_honours_pack(seeded) -> None:
    res = _run(search("EMEA pack:business", scope="chunks"))
    assert res.filters.get("pack") == "business"
    chunk_hits = [h for h in res.hits if h.kind == "chunk"]
    assert chunk_hits
    for h in chunk_hits:
        assert h.ref.get("thread_id") == seeded["t_biz"]


def test_unified_search_chunks_scope_honours_mime_wildcard(seeded) -> None:
    res = _run(search("EMEA mime:image/*", scope="chunks"))
    assert res.filters.get("mime") == "image/*"
    chunk_hits = [h for h in res.hits if h.kind == "chunk"]
    assert {h.ref.get("attachment_id") for h in chunk_hits} == {
        seeded["a3"]
    }


def test_unified_search_cleaned_query_strips_filter_tokens(seeded) -> None:
    res = _run(search("EMEA pack:business mime:application/pdf", scope="chunks"))
    # The cleaned text only retains the keyword.
    assert "pack:" not in (res.cleaned_query or "")
    assert "mime:" not in (res.cleaned_query or "")
    assert "EMEA" in (res.cleaned_query or "")


# ---------------------------------------------------------------------
# HTTP wiring (chunks endpoint inherits the DSL through search_chunks)
# ---------------------------------------------------------------------


def test_http_chunks_endpoint_honours_inline_pack(seeded) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/search/chunks",
            json={"query": "EMEA pack:business"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["hits"], "expected hits"
    for hit in body["hits"]:
        assert hit["ref"].get("thread_id") == seeded["t_biz"]


def test_http_chunks_endpoint_honours_inline_mime(seeded) -> None:
    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/search/chunks",
            json={"query": "EMEA mime:text/plain"},
        )
    body = resp.json()
    ids = {h["ref"].get("attachment_id") for h in body["hits"]}
    assert ids == {seeded["a2"]}
