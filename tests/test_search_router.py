"""HTTP surface for the search + timeline endpoints."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import store as chat_store_mod
from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


@pytest.fixture()
def search_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
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


@pytest.fixture()
def client(search_env) -> TestClient:
    return TestClient(app)


def _seed(client: TestClient) -> tuple[str, str]:
    a = client.post(
        "/api/chat/threads", json={"title": "KPI ops", "pack_slug": "business"}
    ).json()["thread"]["id"]
    b = client.post(
        "/api/chat/threads", json={"title": "Trades", "pack_slug": "traders"}
    ).json()["thread"]["id"]
    client.post(
        f"/api/chat/threads/{a}/attachments",
        files={
            "file": (
                "kpi.md",
                io.BytesIO(
                    b"# KPIs\n\n## EMEA\n\nPipeline grew but conversion "
                    b"stayed flat. Top blocker GDPR redlines.\n"
                ),
                "text/markdown",
            )
        },
    )
    client.post(
        f"/api/chat/threads/{b}/attachments",
        files={
            "file": (
                "plan.md",
                io.BytesIO(b"# Trade\n\nLong NVDA hedge with QQQ short.\n"),
                "text/markdown",
            )
        },
    )
    return a, b


def test_unified_search_endpoint_returns_hits(client: TestClient) -> None:
    _seed(client)
    res = client.post("/api/search", json={"query": "EMEA blocker"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] >= 1
    assert body["scope"] == "all"
    assert body["hits"][0]["kind"] == "chunk"
    assert body["hits"][0]["ref"]["thread_title"] == "KPI ops"


def test_search_validates_query(client: TestClient) -> None:
    res = client.post("/api/search", json={"query": "  "})
    assert res.status_code == 400


def test_search_validates_scope(client: TestClient) -> None:
    res = client.post(
        "/api/search", json={"query": "EMEA", "scope": "garbage"}
    )
    assert res.status_code == 400


def test_chunks_search_with_thread_filter(client: TestClient) -> None:
    a, b = _seed(client)
    res = client.post(
        "/api/search/chunks",
        json={"query": "EMEA blocker", "thread_id": a},
    ).json()
    assert all(h["ref"]["thread_id"] == a for h in res["hits"])


def test_messages_search_finds_inserted_message(client: TestClient) -> None:
    a, _ = _seed(client)
    # Drive an SSE turn so the operator message gets persisted + indexed.
    with client.stream(
        "POST",
        f"/api/chat/threads/{a}/messages",
        json={"text": "What was the EMEA blocker exactly?"},
        headers={"accept": "text/event-stream"},
    ) as r:
        for _ in r.iter_lines():
            pass

    res = client.post(
        "/api/search/messages", json={"query": "EMEA blocker"}
    ).json()
    assert res["count"] >= 1


def test_traces_search_returns_empty_when_meeet_disabled(client: TestClient) -> None:
    res = client.post(
        "/api/search/traces", json={"query": "anything"}
    ).json()
    assert res["count"] == 0


def test_thread_timeline_endpoint_returns_chronological_entries(
    client: TestClient,
) -> None:
    a, _ = _seed(client)
    # Run an assistant turn so the timeline has a message + retrieval event.
    with client.stream(
        "POST",
        f"/api/chat/threads/{a}/messages",
        json={"text": "Summarise the EMEA blocker."},
        headers={"accept": "text/event-stream"},
    ) as r:
        for _ in r.iter_lines():
            pass

    res = client.get(f"/api/chat/threads/{a}/timeline").json()
    assert res["ok"] is True
    assert res["count"] >= 2
    # Sorted by timestamp, ascending.
    timestamps = [e["ts"] for e in res["entries"]]
    assert timestamps == sorted(timestamps)
    # Sources represented include attachment + message at minimum.
    sources = {e["source"] for e in res["entries"]}
    assert "attachment" in sources
    assert "message" in sources
