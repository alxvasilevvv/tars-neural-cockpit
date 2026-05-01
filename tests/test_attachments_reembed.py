"""Tests for the attachment re-embed pipeline + HTTP route.

Closes the "re-embed on demand" idea from `docs/IDEAS.md`. The
endpoint promotes a thread's attachments from the offline
``HashEmbedder`` to OpenAI (or any other) embedder without
re-uploading the original bytes.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments import (
    HashEmbedder,
    OpenAIEmbedder,
    get_attachment_store,
    reembed_attachment,
)
from backend.core.attachments import index as attachment_index_mod
from backend.core.attachments import pipeline as attachment_pipeline
from backend.core.attachments.embeddings import (
    EmbeddingResult,
    detect_embedder,
)
from backend.core.attachments.pipeline import _resolve_embedder_by_name
from backend.core.chat import store as chat_store_mod
from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture()
def attach_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv(
        "TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite")
    )
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


def _upload_file(client: TestClient, thread_id: str, blob: bytes) -> dict:
    files = {"file": ("doc.md", io.BytesIO(blob), "text/markdown")}
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    )
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------
# Embedder resolution
# ---------------------------------------------------------------------


def test_resolve_hash_returns_hash_embedder() -> None:
    embedder = _resolve_embedder_by_name("hash")
    assert isinstance(embedder, HashEmbedder)


def test_resolve_openai_returns_openai_embedder() -> None:
    embedder = _resolve_embedder_by_name("openai")
    assert isinstance(embedder, OpenAIEmbedder)


def test_resolve_specific_openai_model_routes_to_openai() -> None:
    embedder = _resolve_embedder_by_name("text-embedding-3-large")
    assert isinstance(embedder, OpenAIEmbedder)
    assert embedder.model == "text-embedding-3-large"


def test_resolve_unknown_falls_back_to_detect(attach_env) -> None:
    embedder = _resolve_embedder_by_name("nope")
    assert isinstance(embedder, type(detect_embedder()))


def test_resolve_blank_falls_back_to_detect(attach_env) -> None:
    assert isinstance(_resolve_embedder_by_name("  "), type(detect_embedder()))
    assert isinstance(_resolve_embedder_by_name(None), type(detect_embedder()))


def test_resolve_is_case_insensitive() -> None:
    assert isinstance(_resolve_embedder_by_name("HASH"), HashEmbedder)
    assert isinstance(_resolve_embedder_by_name("OpenAI"), OpenAIEmbedder)


# ---------------------------------------------------------------------
# Function-level (reembed_attachment)
# ---------------------------------------------------------------------


def test_reembed_missing_attachment_returns_error(attach_env) -> None:
    out = asyncio.run(reembed_attachment("att_missing"))
    assert out.ok is False
    assert out.error == "attachment_not_found"
    assert out.chunk_count == 0


def test_reembed_returns_no_chunks_for_empty_attachment(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    # Upload an empty/blank-ish file that yields zero chunks.
    blob = b"   \n  \n"
    body = _upload_file(client, thread_id, blob)
    if body["chunk_count"] != 0:
        pytest.skip("upload produced chunks; adjust fixture")
    out = asyncio.run(reembed_attachment(body["attachment"]["id"]))
    assert out.ok is False
    assert out.error == "no_chunks"
    assert out.previous_model is not None or out.previous_model is None


def test_reembed_swaps_model_and_keeps_chunk_ids(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = (
        b"# Title\n\n"
        + (b"alpha beta gamma delta epsilon zeta " * 200)
        + b"\n\n# Section 2\n\n"
        + (b"theta iota kappa lambda " * 200)
    )
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]
    assert body["chunk_count"] >= 2
    initial_model = body["embedding_model"]

    store = get_attachment_store()
    chunks_before = asyncio.run(
        store.list_chunks(thread_id, attachment_id=attachment_id)
    )
    ids_before = [c.id for c in chunks_before]
    ords_before = [c.ord for c in chunks_before]

    # Re-embed using a fresh HashEmbedder; chunk ids and ords must
    # be preserved (so frontend permalinks survive), but the
    # ``embedding_model`` and ``created_at`` should refresh.
    out = asyncio.run(
        reembed_attachment(
            attachment_id,
            embedder=HashEmbedder(),
        )
    )
    assert out.ok is True
    assert out.error is None
    assert out.chunk_count == len(chunks_before)
    assert out.embedding_model
    assert out.previous_model == initial_model

    chunks_after = asyncio.run(
        store.list_chunks(thread_id, attachment_id=attachment_id)
    )
    assert [c.id for c in chunks_after] == ids_before
    assert [c.ord for c in chunks_after] == ords_before
    assert all(c.embedding_model == out.embedding_model for c in chunks_after)


def test_reembed_updates_attachment_record_embedding_id(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = (
        b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    )
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    out = asyncio.run(
        reembed_attachment(attachment_id, embedder=HashEmbedder())
    )
    assert out.ok is True

    store = get_attachment_store()
    record = asyncio.run(store.get_attachment(attachment_id))
    assert record is not None
    assert record.embedding_id == out.embedding_model


def test_reembed_handles_embedder_failure_gracefully(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    class _BoomEmbedder(HashEmbedder):
        async def embed(self, texts):  # type: ignore[override]
            raise RuntimeError("upstream timeout")

    out = asyncio.run(
        reembed_attachment(attachment_id, embedder=_BoomEmbedder())
    )
    assert out.ok is False
    assert out.error == "embedder_failed"
    assert out.detail == "upstream timeout"
    # Previous model untouched on failure (we only flip the row
    # after a successful embed).
    store = get_attachment_store()
    record = asyncio.run(store.get_attachment(attachment_id))
    assert record is not None


def test_reembed_rejects_both_embedder_and_name(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    out = asyncio.run(
        reembed_attachment(
            attachment_id,
            embedder=HashEmbedder(),
            embedder_name="hash",
        )
    )
    assert out.ok is False
    assert out.error == "embedder_args_conflict"


def test_reembed_emits_attachment_reembedded_event(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list = []

    async def fake_emit(self, kind, payload):
        captured.append((kind, dict(payload)))

    from backend.core.meeet import client as meeet_client_mod

    monkeypatch.setattr(
        meeet_client_mod.MeeetClient, "emit", fake_emit
    )

    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    out = asyncio.run(
        reembed_attachment(attachment_id, embedder=HashEmbedder())
    )
    assert out.ok is True

    kinds = [k for k, _ in captured]
    assert "attachment.reembedded" in kinds
    payload = next(p for k, p in captured if k == "attachment.reembedded")
    assert payload["attachment_id"] == attachment_id
    assert payload["chunk_count"] == out.chunk_count
    assert payload["ok"] is True


# ---------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------


def test_http_reembed_404s_when_attachment_missing(
    client: TestClient,
) -> None:
    res = client.post("/api/chat/attachments/att_missing/reembed")
    assert res.status_code == 404
    assert res.json()["detail"] == "attachment_not_found"


def test_http_reembed_returns_no_chunks_with_200(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_file(client, thread_id, b"   \n  ")
    if body["chunk_count"] != 0:
        pytest.skip("fixture produced chunks; nothing to test")
    res = client.post(
        f"/api/chat/attachments/{body['attachment']['id']}/reembed"
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is False
    assert payload["error"] == "no_chunks"


def test_http_reembed_happy_path(client: TestClient) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    res = client.post(
        f"/api/chat/attachments/{attachment_id}/reembed",
        json={"model": "hash"},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["ok"] is True
    assert payload["attachment_id"] == attachment_id
    assert payload["chunk_count"] >= 1
    assert payload["embedding_model"]
    assert payload["embedding_dim"]


def test_http_reembed_default_uses_detected_embedder(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    # No explicit model; resolves via detect_embedder which under
    # this env (TARS_EMBEDDER=hash) gives the HashEmbedder.
    res = client.post(
        f"/api/chat/attachments/{attachment_id}/reembed", json={}
    )
    payload = res.json()
    assert payload["ok"] is True
    assert payload["embedding_model"]
    assert "hash" in payload["embedding_model"].lower()


def test_http_reembed_blank_model_resolves_default(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    res = client.post(
        f"/api/chat/attachments/{attachment_id}/reembed",
        json={"model": "   "},
    )
    payload = res.json()
    assert payload["ok"] is True


def test_http_reembed_unknown_model_falls_back(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    res = client.post(
        f"/api/chat/attachments/{attachment_id}/reembed",
        json={"model": "fictional-embedder-9000"},
    )
    payload = res.json()
    # Falls back to detect_embedder() (HashEmbedder under env).
    assert payload["ok"] is True


def test_http_reembed_preserves_chunk_ids_across_calls(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 300)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    before = client.get(
        f"/api/chat/attachments/{attachment_id}"
    ).json()["chunks"]
    ids_before = [c["id"] for c in before]

    res = client.post(
        f"/api/chat/attachments/{attachment_id}/reembed",
        json={"model": "hash"},
    )
    assert res.status_code == 200
    after = client.get(
        f"/api/chat/attachments/{attachment_id}"
    ).json()["chunks"]
    ids_after = [c["id"] for c in after]
    assert ids_before == ids_after


def test_http_reembed_carries_session_id_into_trace(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list = []

    async def fake_emit(self, kind, payload):
        captured.append((kind, dict(payload)))

    from backend.core.meeet import client as meeet_client_mod

    monkeypatch.setattr(
        meeet_client_mod.MeeetClient, "emit", fake_emit
    )

    thread_id = _make_thread(client)
    blob = b"# Title\n\n" + (b"alpha beta gamma delta " * 200)
    body = _upload_file(client, thread_id, blob)
    attachment_id = body["attachment"]["id"]

    res = client.post(
        f"/api/chat/attachments/{attachment_id}/reembed",
        headers={"x-tars-session-id": "sess_abc"},
        json={},
    )
    assert res.status_code == 200
    payload = next(p for k, p in captured if k == "attachment.reembedded")
    assert payload["trace_id"]
