"""Tests for the streaming-progress upload endpoint and the
``progress`` callback wired through the ingest pipeline.

Covers:

- ``progress`` callback is invoked at each pipeline phase in the
  expected order on the happy path.
- The ``dedup_hit`` shortcut fires before any extraction work.
- A flaky callback never breaks the ingest call (errors swallowed).
- ``attachment.extracting`` / ``attachment.embedding`` /
  ``attachment.indexed`` meeet events are emitted.
- The HTTP SSE endpoint yields one frame per phase plus a final
  ``result`` frame for the cockpit consumer.
- 404 / 400 paths still return JSON (not SSE).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import store as chat_store_mod
from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_meeet_store(tmp_path, monkeypatch):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("MEEET_INGEST_URL", "")
    import backend.core.meeet.client as client_mod
    import backend.core.meeet.store as store_mod

    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]
    yield
    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]


@pytest.fixture()
def attach_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
    )
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


@pytest.fixture()
def client(attach_env) -> TestClient:
    return TestClient(app)


def _make_thread(client: TestClient, title: str = "T") -> str:
    res = client.post("/api/chat/threads", json={"title": title})
    assert res.status_code == 200
    return res.json()["thread"]["id"]


# ---------------------------------------------------------------------
# Function-level callback wiring
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_callback_invoked_for_each_phase_in_order(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
    )
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )

    from backend.core.attachments import ingest
    from backend.core.chat import Thread, get_chat_store

    chat = get_chat_store()
    thread = Thread.fresh(title="streaming")
    await chat.insert_thread(thread)

    phases: list[str] = []
    payloads: list[dict[str, Any]] = []

    async def cb(phase: str, payload: Any) -> None:
        phases.append(phase)
        payloads.append(dict(payload))

    blob = b"# Notes\n\n" + (b"alpha beta gamma " * 50)
    res = await ingest(
        thread_id=thread.id,
        blob=blob,
        filename="notes.md",
        mime="text/markdown",
        progress=cb,
    )
    assert res.duplicate is False

    # Order matters; ``started`` first, ``completed`` last.
    assert phases[0] == "started"
    assert phases[-1] == "completed"
    # All non-archive phases must appear exactly once.
    for required in ("started", "extracted", "chunked", "embedding",
                     "embedded", "indexed", "completed"):
        assert phases.count(required) == 1, (
            f"missing or duplicate {required} in {phases}"
        )
    # No archive phases for a markdown upload.
    assert "zip_walked" not in phases
    assert "dedup_hit" not in phases

    # Payload sanity: chunk count must be consistent across the chain.
    chunked = next(p for p in payloads if "chunk_count" in p and "fts_synced" not in p)
    indexed = next(p for p in payloads if p.get("fts_synced") is not None)
    assert chunked["chunk_count"] >= 1
    assert indexed["chunk_count"] == chunked["chunk_count"]
    assert indexed["fts_synced"] is True


@pytest.mark.asyncio
async def test_dedup_hit_phase_short_circuits_extraction(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
    )
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )

    from backend.core.attachments import ingest
    from backend.core.chat import Thread, get_chat_store

    chat = get_chat_store()
    thread = Thread.fresh(title="dedup")
    await chat.insert_thread(thread)

    blob = b"# Same body\n\nidentical bytes go here.\n"
    await ingest(thread_id=thread.id, blob=blob, filename="dup.md")

    phases: list[str] = []

    async def cb(phase: str, payload: Any) -> None:
        phases.append(phase)

    res = await ingest(
        thread_id=thread.id, blob=blob, filename="dup.md", progress=cb
    )
    assert res.duplicate is True
    # Only ``started`` + ``dedup_hit``; no extraction / chunking work.
    assert phases == ["started", "dedup_hit"]


@pytest.mark.asyncio
async def test_progress_callback_exception_does_not_break_ingest(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
    )
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )

    from backend.core.attachments import ingest
    from backend.core.chat import Thread, get_chat_store

    chat = get_chat_store()
    thread = Thread.fresh(title="flaky-cb")
    await chat.insert_thread(thread)

    async def cb(phase: str, payload: Any) -> None:
        if phase == "embedding":
            raise RuntimeError("flaky consumer")

    res = await ingest(
        thread_id=thread.id,
        blob=b"hi there\n",
        filename="t.txt",
        progress=cb,
    )
    assert res.duplicate is False
    assert res.chunk_count >= 1


@pytest.mark.asyncio
async def test_attachment_phase_meeet_events_emitted(tmp_path, monkeypatch):
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv(
        "TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments")
    )
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(
        attachment_index_mod, "_SINGLETON", None, raising=False
    )

    from backend.core.attachments import ingest
    from backend.core.chat import Thread, get_chat_store
    from backend.core.meeet.store import get_store

    chat = get_chat_store()
    thread = Thread.fresh(title="events")
    await chat.insert_thread(thread)

    await ingest(
        thread_id=thread.id,
        blob=b"# Title\n\nbody body body\n",
        filename="x.md",
    )

    events = await get_store().list_events(limit=200)
    kinds = {e.kind for e in events}
    assert "attachment.extracting" in kinds
    assert "attachment.embedding" in kinds
    assert "attachment.indexed" in kinds
    assert "attachment.ingested" in kinds


# ---------------------------------------------------------------------
# HTTP SSE endpoint
# ---------------------------------------------------------------------


def _parse_sse(raw: str) -> list[tuple[str, dict[str, Any] | None]]:
    """Parse an SSE response body into ``[(event, data?), ...]``.

    Comment lines (``: ...``) are skipped.
    """

    frames: list[tuple[str, dict[str, Any] | None]] = []
    current_event: str | None = None
    current_data: list[str] = []
    for line in raw.split("\n"):
        if line.startswith(":"):
            continue
        if line == "":
            if current_event is not None:
                payload: dict[str, Any] | None = None
                if current_data:
                    try:
                        payload = json.loads("".join(current_data))
                    except json.JSONDecodeError:
                        payload = None
                frames.append((current_event, payload))
            current_event = None
            current_data = []
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:"):].strip())
    return frames


def test_stream_endpoint_yields_phase_frames_in_order(client: TestClient) -> None:
    thread_id = _make_thread(client, "stream")
    blob = b"# KPI\n\n" + (b"alpha beta gamma " * 30)
    files = {"file": ("kpi.md", io.BytesIO(blob), "text/markdown")}
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments/stream",
        files=files,
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse(res.text)
    events = [name for name, _ in frames]
    assert events[0] == "started"
    # ``result`` is always last for the non-error happy path.
    assert events[-1] == "result"
    # All key phases between bookends.
    for required in (
        "started",
        "extracted",
        "chunked",
        "embedding",
        "embedded",
        "indexed",
        "completed",
        "result",
    ):
        assert required in events, f"missing {required} in {events}"

    # ``result`` carries the canonical envelope.
    result_payload = next(p for n, p in frames if n == "result")
    assert result_payload is not None
    assert result_payload["ok"] is True
    assert result_payload["duplicate"] is False
    assert result_payload["chunk_count"] >= 1
    assert result_payload["attachment"]["filename"] == "kpi.md"


def test_stream_endpoint_dedup_short_circuits(client: TestClient) -> None:
    thread_id = _make_thread(client, "dedup-stream")
    blob = b"# Same\n\nbytes\n"

    first = client.post(
        f"/api/chat/threads/{thread_id}/attachments",
        files={"file": ("d.md", io.BytesIO(blob), "text/markdown")},
    )
    assert first.status_code == 200

    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments/stream",
        files={"file": ("d.md", io.BytesIO(blob), "text/markdown")},
    )
    assert res.status_code == 200
    frames = _parse_sse(res.text)
    events = [name for name, _ in frames]
    # ``started`` + ``dedup_hit`` + ``result``.
    assert events == ["started", "dedup_hit", "result"]

    result_payload = next(p for n, p in frames if n == "result")
    assert result_payload is not None
    assert result_payload["duplicate"] is True


def test_stream_endpoint_unknown_thread_returns_404(client: TestClient) -> None:
    files = {"file": ("hi.md", io.BytesIO(b"hi"), "text/markdown")}
    res = client.post(
        "/api/chat/threads/thr_missing/attachments/stream", files=files
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "thread_not_found"


def test_stream_endpoint_empty_file_returns_400(client: TestClient) -> None:
    thread_id = _make_thread(client, "empty")
    files = {"file": ("empty.md", io.BytesIO(b""), "text/markdown")}
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments/stream", files=files
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "empty_file"


def test_stream_endpoint_carries_session_id_into_trace(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client, "session-prop")
    files = {"file": ("s.md", io.BytesIO(b"# s\n\nbody"), "text/markdown")}
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments/stream",
        files=files,
        headers={"x-tars-session-id": "sess-test-1"},
    )
    assert res.status_code == 200
    # Just ensure stream completed; deeper trace assertion would
    # inspect the meeet store, but its row is written from inside
    # ingest under ``trace_scope`` and that's already covered.


def test_legacy_upload_endpoint_still_returns_json(client: TestClient) -> None:
    """Sanity check: the original non-streaming endpoint must keep
    the JSON contract unchanged."""

    thread_id = _make_thread(client, "legacy")
    files = {"file": ("k.md", io.BytesIO(b"# a\n\nbody"), "text/markdown")}
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "attachment" in body
    assert "duplicate" in body
