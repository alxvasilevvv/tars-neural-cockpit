"""HTTP-level tests for the attachment endpoints under /api/chat."""

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
def attach_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
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


def test_upload_attachment_runs_pipeline_and_dedupes(client: TestClient) -> None:
    thread_id = _make_thread(client, "rag")
    blob = (
        b"# KPI report\n\nPipeline grew but conversion stayed flat. "
        b"Top blocker GDPR redlines on three deals.\n"
    )
    files = {"file": ("kpi.md", io.BytesIO(blob), "text/markdown")}
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["duplicate"] is False
    assert body["chunk_count"] >= 1
    record = body["attachment"]
    assert record["filename"] == "kpi.md"
    assert record["thread_id"] == thread_id
    assert record["status"] == "ready"
    assert record["char_count"] > 0

    files = {"file": ("kpi.md", io.BytesIO(blob), "text/markdown")}
    dup = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    )
    assert dup.status_code == 200
    assert dup.json()["duplicate"] is True
    assert dup.json()["attachment"]["id"] == record["id"]


def test_upload_attachment_rejects_unknown_thread(client: TestClient) -> None:
    files = {"file": ("kpi.md", io.BytesIO(b"hi"), "text/markdown")}
    res = client.post("/api/chat/threads/thr_missing/attachments", files=files)
    assert res.status_code == 404


def test_list_attachments_returns_records_in_order(client: TestClient) -> None:
    thread_id = _make_thread(client, "list")
    for i, name in enumerate(("a.md", "b.md", "c.md")):
        files = {"file": (name, io.BytesIO(f"# {name}\n\n{i}".encode()), "text/markdown")}
        res = client.post(
            f"/api/chat/threads/{thread_id}/attachments", files=files
        )
        assert res.status_code == 200, res.text

    listing = client.get(f"/api/chat/threads/{thread_id}/attachments").json()
    assert listing["count"] == 3
    names = [a["filename"] for a in listing["attachments"]]
    assert names == ["a.md", "b.md", "c.md"]


def test_describe_attachment_includes_chunk_previews(client: TestClient) -> None:
    thread_id = _make_thread(client, "describe")
    blob = b"# KPI\n\n" + (b"alpha beta gamma " * 60)
    files = {"file": ("kpi.md", io.BytesIO(blob), "text/markdown")}
    upload = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    ).json()
    att_id = upload["attachment"]["id"]

    res = client.get(f"/api/chat/attachments/{att_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["attachment"]["id"] == att_id
    assert body["chunks"]
    assert "preview" in body["chunks"][0]


def test_extracted_returns_plain_text(client: TestClient) -> None:
    thread_id = _make_thread(client, "extract")
    files = {
        "file": ("plain.txt", io.BytesIO(b"hello world"), "text/plain"),
    }
    upload = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    ).json()
    att_id = upload["attachment"]["id"]

    res = client.get(f"/api/chat/attachments/{att_id}/extracted")
    assert res.status_code == 200
    assert res.text == "hello world"
    assert res.headers["x-tars-attachment-id"] == att_id


def test_retrieve_returns_top_chunks_for_query(client: TestClient) -> None:
    thread_id = _make_thread(client, "retrieve")
    blob = (
        b"# Quarterly KPI report\n\n"
        b"## EMEA\n\nPipeline grew but conversion stayed flat. "
        b"Top blocker GDPR redlines on three deals.\n\n"
        b"## APAC\n\nHealthy growth, no flagged risks.\n"
    )
    files = {"file": ("kpi.md", io.BytesIO(blob), "text/markdown")}
    client.post(f"/api/chat/threads/{thread_id}/attachments", files=files)

    res = client.post(
        f"/api/chat/threads/{thread_id}/retrieve",
        json={"query": "EMEA conversion blocker", "top_k": 3},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["count"] >= 1
    assert body["chunks"][0]["citation_id"] == "chunk_1"


def test_retrieve_requires_query(client: TestClient) -> None:
    thread_id = _make_thread(client, "noq")
    res = client.post(
        f"/api/chat/threads/{thread_id}/retrieve", json={"query": ""}
    )
    assert res.status_code == 400


def test_delete_attachment_drops_record(client: TestClient) -> None:
    thread_id = _make_thread(client, "del")
    files = {"file": ("byebye.txt", io.BytesIO(b"goodbye"), "text/plain")}
    upload = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    ).json()
    att_id = upload["attachment"]["id"]

    res = client.delete(f"/api/chat/attachments/{att_id}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True

    res = client.get(f"/api/chat/attachments/{att_id}")
    assert res.status_code == 404
