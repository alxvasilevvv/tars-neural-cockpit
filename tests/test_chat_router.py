"""HTTP surface tests for the chat router (CRUD + SSE stream)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.chat import store as chat_store_module
from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from web_extras.app import app


@pytest.fixture()
def chat_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the chat singleton at a tmp DB so tests don't pollute ~/.tars."""

    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setattr(chat_store_module, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(chat_store_module, "_SINGLETON", None, raising=False)


@pytest.fixture()
def client(chat_db) -> TestClient:
    return TestClient(app)


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------


def test_create_and_list_threads(client: TestClient) -> None:
    res = client.post(
        "/api/chat/threads",
        json={"title": "Daily ops", "pack_slug": "ops_room"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    thr = body["thread"]
    assert thr["title"] == "Daily ops"
    assert thr["pack_slug"] == "ops_room"
    thread_id = thr["id"]

    listed = client.get("/api/chat/threads").json()
    assert listed["ok"] is True
    assert any(t["id"] == thread_id for t in listed["threads"])


def test_patch_archive_excludes_thread_from_active(client: TestClient) -> None:
    created = client.post("/api/chat/threads", json={"title": "T"}).json()
    thread_id = created["thread"]["id"]

    patched = client.patch(
        f"/api/chat/threads/{thread_id}", json={"archived": True}
    ).json()
    assert patched["thread"]["archived"] is True

    active = client.get("/api/chat/threads?archived=false").json()
    assert all(t["id"] != thread_id for t in active["threads"])
    archived = client.get("/api/chat/threads?archived=true").json()
    assert any(t["id"] == thread_id for t in archived["threads"])


def test_delete_thread_soft_deletes(client: TestClient) -> None:
    thr = client.post("/api/chat/threads", json={"title": "X"}).json()["thread"]
    res = client.delete(f"/api/chat/threads/{thr['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["thread"]["archived"] is True


def test_unknown_thread_404(client: TestClient) -> None:
    res = client.get("/api/chat/threads/thr_does_not_exist")
    assert res.status_code == 404


# ----------------------------------------------------------------------
# Streaming (SSE)
# ----------------------------------------------------------------------


def _parse_sse(stream: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    event = None
    for line in stream.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:") and event:
            try:
                payload = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                payload = {}
            out.append((event, payload))
            event = None
    return out


def test_post_message_streams_sse_with_local_voice(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force LocalChatVoice — guarantees deterministic stream regardless
    # of whether keys leak in from the host machine's vault.
    monkeypatch.delenv("TARS_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TARS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Also block keychain lookups during this test so the local fallback
    # is selected even on a developer laptop with creds saved.
    from backend.core.vault import keychain as kc_module

    monkeypatch.setattr(kc_module, "_security_bin", lambda: None, raising=False)

    thr = client.post("/api/chat/threads", json={"title": "stream"}).json()[
        "thread"
    ]
    res = client.post(
        f"/api/chat/threads/{thr['id']}/messages",
        json={"text": "hello world"},
        headers={"x-tars-session-id": "ses_test_1"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(res.text)
    kinds = [e[0] for e in events]
    assert "message.started" in kinds
    assert "token" in kinds
    assert "usage" in kinds
    assert "message.completed" in kinds
    assert kinds[-1] == "stream.closed"

    completed = next(p for k, p in events if k == "message.completed")
    assert completed["thread_id"] == thr["id"]
    assert completed["content"]


def test_get_thread_returns_persisted_messages(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TARS_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TARS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from backend.core.vault import keychain as kc_module

    monkeypatch.setattr(kc_module, "_security_bin", lambda: None, raising=False)

    thr = client.post("/api/chat/threads", json={"title": "persist"}).json()[
        "thread"
    ]
    res = client.post(
        f"/api/chat/threads/{thr['id']}/messages", json={"text": "ping"}
    )
    assert res.status_code == 200
    # Drain the stream so the assistant message gets persisted.
    _ = res.text

    described = client.get(f"/api/chat/threads/{thr['id']}").json()
    msgs = described["messages"]
    assert [m["role"] for m in msgs] == ["operator", "tars"]
    assert msgs[0]["content"] == "ping"
    assert msgs[1]["voice_model"] == "tars-local-chat-v1"


def test_post_message_rejects_empty_text(client: TestClient) -> None:
    thr = client.post("/api/chat/threads", json={}).json()["thread"]
    res = client.post(
        f"/api/chat/threads/{thr['id']}/messages", json={"text": "  "}
    )
    assert res.status_code == 400
