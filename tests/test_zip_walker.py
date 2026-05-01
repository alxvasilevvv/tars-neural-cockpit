"""Tests for the zip archive walker.

Two layers:

1. Unit tests for the walker primitives (env helpers, name safety,
   summary shape).
2. End-to-end pipeline tests: upload a zip → expanded children
   land as siblings linked via ``parent_attachment_id`` in meta.
"""

from __future__ import annotations

import asyncio
import io
import os
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_chat_db(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
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


def _make_zip(entries: dict[str, bytes]) -> bytes:
    """Build an in-memory zip from a dict of name → bytes."""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


async def _seed_thread() -> str:
    from backend.core.chat.store import get_chat_store
    from backend.core.chat.models import Thread

    chat = get_chat_store()
    thr = Thread.fresh(title="ZipTest")
    await chat.insert_thread(thr)
    return thr.id


# ---------------------------------------------------------------------
# Detection / safety primitives
# ---------------------------------------------------------------------


def test_is_zip_mime_recognises_canonical_types():
    from backend.core.attachments.zip_walker import is_zip_mime

    assert is_zip_mime("application/zip") is True
    assert is_zip_mime("application/x-zip-compressed") is True
    assert is_zip_mime("application/zip; charset=utf-8") is True
    assert is_zip_mime("text/plain") is False
    assert is_zip_mime(None) is False
    assert is_zip_mime("") is False


def test_looks_like_zip_uses_magic_bytes():
    from backend.core.attachments.zip_walker import looks_like_zip

    assert looks_like_zip(b"PK\x03\x04rest") is True
    assert looks_like_zip(b"PK\x05\x06rest") is True
    assert looks_like_zip(b"hello") is False


def test_looks_like_zip_falls_back_to_filename_suffix():
    from backend.core.attachments.zip_walker import looks_like_zip

    assert looks_like_zip(b"random", filename="archive.zip") is True
    assert looks_like_zip(b"random", filename="archive.ZIP") is True
    assert looks_like_zip(b"random", filename="not-a-zip.txt") is False


def test_unsafe_name_rejects_traversal_and_absolute_paths():
    from backend.core.attachments.zip_walker import _is_unsafe_name

    assert _is_unsafe_name("../etc/passwd") is True
    assert _is_unsafe_name("/etc/passwd") is True
    assert _is_unsafe_name("\\windows\\boot.ini") is True
    assert _is_unsafe_name("__MACOSX/._hidden") is True
    assert _is_unsafe_name("docs/readme.md") is False
    assert _is_unsafe_name("file.txt") is False
    assert _is_unsafe_name("") is True


def test_env_helpers_clamp_garbage(monkeypatch):
    from backend.core.attachments.zip_walker import (
        zip_max_depth,
        zip_max_entries,
        zip_max_entry_bytes,
    )

    monkeypatch.setenv("TARS_ZIP_MAX_ENTRIES", "not-a-number")
    monkeypatch.setenv("TARS_ZIP_MAX_ENTRY_BYTES", "0")  # falls back below floor
    monkeypatch.setenv("TARS_ZIP_MAX_DEPTH", "999")

    assert zip_max_entries() == 200  # default
    # max_entry_bytes floor is 1024
    assert zip_max_entry_bytes() == 1024
    # depth clamped to 5
    assert zip_max_depth() == 5


# ---------------------------------------------------------------------
# Pipeline: upload a zip → expanded children
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zip_upload_expands_into_child_attachments():
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.pipeline import ingest

    thr_id = await _seed_thread()
    blob = _make_zip(
        {
            "hello.txt": b"hello world\nthis is a test",
            "readme.md": b"# Title\nbody",
            "logs/app.log": b"log line 1",
        }
    )
    res = await ingest(
        thread_id=thr_id, blob=blob, filename="archive.zip",
    )
    parent = res.record
    assert parent.meta.get("zip_walk") is not None
    summary = parent.meta["zip_walk"]
    assert summary["expanded"] == 3
    assert summary["skipped"] == 0
    assert summary["failed"] == 0
    assert summary["truncated"] is False

    store = get_attachment_store()
    records = await store.list_attachments(thr_id)
    names = {r.filename for r in records}
    # Children retain their basename (path components stripped).
    assert "archive.zip" in names
    assert "hello.txt" in names
    assert "readme.md" in names
    assert "app.log" in names


@pytest.mark.asyncio
async def test_zip_children_link_to_parent_via_meta():
    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.pipeline import ingest

    thr_id = await _seed_thread()
    res = await ingest(
        thread_id=thr_id,
        blob=_make_zip({"a.txt": b"alpha"}),
        filename="archive.zip",
    )
    parent_id = res.record.id

    store = get_attachment_store()
    records = await store.list_attachments(thr_id)
    children = [r for r in records if r.id != parent_id]
    assert len(children) == 1
    assert children[0].meta.get("parent_attachment_id") == parent_id


@pytest.mark.asyncio
async def test_zip_walk_skips_directories_and_unsafe_paths():
    from backend.core.attachments.pipeline import ingest

    thr_id = await _seed_thread()
    # Build a zip with a directory entry, a traversal, and a normal file.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dir/", b"")  # directory marker
        zf.writestr("../escape.txt", b"nope")
        zf.writestr("safe.txt", b"hello")
    blob = buf.getvalue()

    res = await ingest(
        thread_id=thr_id, blob=blob, filename="bad.zip",
    )
    summary = res.record.meta["zip_walk"]
    assert summary["expanded"] == 1
    # 1 directory + 1 traversal entry skipped
    assert summary["skipped"] == 2
    # The successful one shows up under entries.
    ok_entries = [e for e in summary["entries"] if e["ok"]]
    assert len(ok_entries) == 1
    assert ok_entries[0]["name"] == "safe.txt"


@pytest.mark.asyncio
async def test_zip_walk_respects_max_entries_cap(monkeypatch):
    from backend.core.attachments.pipeline import ingest

    monkeypatch.setenv("TARS_ZIP_MAX_ENTRIES", "2")

    thr_id = await _seed_thread()
    blob = _make_zip(
        {f"f{i}.txt": f"content {i}".encode() for i in range(5)}
    )
    res = await ingest(
        thread_id=thr_id, blob=blob, filename="big.zip",
    )
    summary = res.record.meta["zip_walk"]
    assert summary["truncated"] is True
    assert summary["expanded"] + summary["skipped"] + summary["failed"] == 2


@pytest.mark.asyncio
async def test_zip_walk_drops_oversize_member(monkeypatch):
    from backend.core.attachments.pipeline import ingest

    monkeypatch.setenv("TARS_ZIP_MAX_ENTRY_BYTES", "1024")

    thr_id = await _seed_thread()
    blob = _make_zip(
        {
            "tiny.txt": b"hello",
            "huge.txt": b"X" * 5000,
        }
    )
    res = await ingest(
        thread_id=thr_id, blob=blob, filename="mixed.zip",
    )
    summary = res.record.meta["zip_walk"]
    assert summary["expanded"] == 1
    assert summary["skipped"] == 1
    huge_entry = [e for e in summary["entries"] if e["name"] == "huge.txt"]
    assert huge_entry
    assert huge_entry[0]["ok"] is False
    assert "skip_oversize" in huge_entry[0]["error"]


@pytest.mark.asyncio
async def test_zip_walk_handles_corrupt_archive():
    from backend.core.attachments.pipeline import ingest

    thr_id = await _seed_thread()
    # PK header but garbage body — zipfile can detect this.
    blob = b"PK\x03\x04" + b"garbage" * 100
    res = await ingest(
        thread_id=thr_id, blob=blob, filename="broken.zip", mime="application/zip",
    )
    summary = res.record.meta["zip_walk"]
    assert summary["expanded"] == 0
    assert summary["failed"] >= 1


@pytest.mark.asyncio
async def test_walk_archives_false_disables_expansion():
    """When the caller explicitly opts out of walking, the zip lands
    as a single binary attachment (no children, no zip_walk meta).
    """

    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.pipeline import ingest

    thr_id = await _seed_thread()
    res = await ingest(
        thread_id=thr_id,
        blob=_make_zip({"a.txt": b"alpha"}),
        filename="archive.zip",
        walk_archives=False,
    )
    assert res.record.meta.get("zip_walk") is None

    store = get_attachment_store()
    records = await store.list_attachments(thr_id)
    assert len(records) == 1


@pytest.mark.asyncio
async def test_nested_zip_walked_up_to_max_depth(monkeypatch):
    """A zip-of-zip is walked at depth 0 → inner zip is also walked at
    depth 1. With ``TARS_ZIP_MAX_DEPTH=1`` the inner one lands as a
    blob (no further walk).
    """

    from backend.core.attachments.pipeline import ingest

    monkeypatch.setenv("TARS_ZIP_MAX_DEPTH", "1")

    thr_id = await _seed_thread()
    inner = _make_zip({"deep.txt": b"deep contents"})
    outer = _make_zip({"inner.zip": inner, "top.txt": b"top contents"})
    res = await ingest(
        thread_id=thr_id, blob=outer, filename="outer.zip",
    )
    summary = res.record.meta["zip_walk"]
    # outer expanded 2 children: inner.zip (as blob, no further walk)
    # and top.txt.
    assert summary["expanded"] == 2

    # Inner zip child does NOT have a zip_walk in its meta — the
    # max_depth=1 stopped recursion.
    from backend.core.attachments.index import get_attachment_store

    store = get_attachment_store()
    records = await store.list_attachments(thr_id)
    inner_record = [r for r in records if r.filename == "inner.zip"][0]
    assert inner_record.meta.get("zip_walk") is None


@pytest.mark.asyncio
async def test_zip_walk_dedup_within_thread():
    """Two zip members with identical bytes share the same content
    hash; the second one dedups against the first.
    """

    from backend.core.attachments.index import get_attachment_store
    from backend.core.attachments.pipeline import ingest

    thr_id = await _seed_thread()
    blob = _make_zip({"a.txt": b"same content", "b.txt": b"same content"})
    res = await ingest(
        thread_id=thr_id, blob=blob, filename="dupes.zip",
    )
    summary = res.record.meta["zip_walk"]
    # Both succeed; the second one carries duplicate=True.
    ok_entries = [e for e in summary["entries"] if e["ok"]]
    assert len(ok_entries) == 2
    duplicates = [e for e in ok_entries if e["duplicate"]]
    assert len(duplicates) == 1

    # Only one row in storage for the deduped pair, plus the parent.
    store = get_attachment_store()
    records = await store.list_attachments(thr_id)
    # parent + one dedup'd child = 2 records total
    assert len(records) == 2
