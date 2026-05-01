"""Tests for the chunk-neighbours endpoint and store helpers.

Backs the per-attachment hover preview surface from IDEAS:
``GET /api/chat/attachments/{id}/chunks/{chunk_id}/neighbours``
returns the chunk plus its ord-adjacent neighbours so the
cockpit can render a floating preview without paying for the
whole document.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments import index as attachment_index_mod
from backend.core.attachments import get_attachment_store
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


# ---------------------------------------------------------------------
# Helpers — upload a multi-chunk attachment under a fresh thread
# ---------------------------------------------------------------------


def _make_thread(client: TestClient, title: str = "neigh") -> str:
    res = client.post("/api/chat/threads", json={"title": title})
    assert res.status_code == 200
    return res.json()["thread"]["id"]


def _multi_chunk_blob(num_chunks: int = 5) -> bytes:
    """Default chunker splits at ~3200 chars; so feed ~4000 chars
    per intended chunk to guarantee N+ chunks."""

    sections = []
    for i in range(num_chunks):
        body = (
            f"# Section {i}\n\n"
            + ("alpha beta gamma delta epsilon zeta eta theta " * 80)
            + f"\n\n[end {i}]\n\n"
        )
        sections.append(body)
    return ("".join(sections)).encode("utf-8")


def _upload_multichunk(client: TestClient, thread_id: str) -> dict:
    blob = _multi_chunk_blob(num_chunks=6)
    files = {
        "file": ("doc.md", io.BytesIO(blob), "text/markdown"),
    }
    res = client.post(
        f"/api/chat/threads/{thread_id}/attachments", files=files
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["chunk_count"] >= 3, (
        "fixture must produce >=3 chunks; "
        f"got {body['chunk_count']}"
    )
    return body


def _list_chunks(client: TestClient, attachment_id: str) -> list[dict]:
    res = client.get(f"/api/chat/attachments/{attachment_id}")
    assert res.status_code == 200
    return res.json()["chunks"]


# ---------------------------------------------------------------------
# Store helpers — direct unit tests
# ---------------------------------------------------------------------


def test_get_chunk_returns_none_for_missing(attach_env) -> None:
    store = get_attachment_store()
    out = asyncio.run(store.get_chunk("chunk_does_not_exist"))
    assert out is None


def test_get_chunk_returns_chunk_when_present(client: TestClient) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    target_id = chunks[0]["id"]

    store = get_attachment_store()
    chunk = asyncio.run(store.get_chunk(target_id))
    assert chunk is not None
    assert chunk.id == target_id
    assert chunk.attachment_id == attachment_id
    assert chunk.text


def test_get_chunk_neighbours_returns_none_for_missing(
    attach_env,
) -> None:
    store = get_attachment_store()
    out = asyncio.run(store.get_chunk_neighbours("nope"))
    assert out is None


def test_get_chunk_neighbours_window_in_middle(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    # Pick a chunk that has at least 2 entries before AND after by
    # raw list position. The chunker doesn't guarantee contiguous
    # ord values (overlap windows leave gaps) so the test compares
    # against the ord-sorted neighbours instead.
    middle_idx = len(chunks) // 2
    middle = chunks[middle_idx]
    expected_before_ords = [c["ord"] for c in chunks[middle_idx - 2 : middle_idx]]
    expected_after_ords = [
        c["ord"] for c in chunks[middle_idx + 1 : middle_idx + 3]
    ]

    store = get_attachment_store()
    bundle = asyncio.run(
        store.get_chunk_neighbours(middle["id"], before=2, after=2)
    )
    assert bundle is not None
    target, before, after = bundle
    assert target.id == middle["id"]
    assert len(before) == 2
    assert len(after) == 2
    assert [c.ord for c in before] == expected_before_ords
    assert [c.ord for c in after] == expected_after_ords
    assert all(c.ord < target.ord for c in before)
    assert all(c.ord > target.ord for c in after)


def test_get_chunk_neighbours_window_clamps_at_start(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    first = chunks[0]

    store = get_attachment_store()
    bundle = asyncio.run(
        store.get_chunk_neighbours(first["id"], before=3, after=2)
    )
    assert bundle is not None
    target, before, after = bundle
    assert target.id == first["id"]
    assert before == []
    assert len(after) == 2


def test_get_chunk_neighbours_window_clamps_at_end(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    last = chunks[-1]

    store = get_attachment_store()
    bundle = asyncio.run(
        store.get_chunk_neighbours(last["id"], before=2, after=3)
    )
    assert bundle is not None
    target, before, after = bundle
    assert target.id == last["id"]
    assert len(before) == 2
    assert after == []


def test_get_chunk_neighbours_zero_window(client: TestClient) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    chunks = _list_chunks(client, body["attachment"]["id"])
    target_id = chunks[1]["id"]

    store = get_attachment_store()
    bundle = asyncio.run(
        store.get_chunk_neighbours(target_id, before=0, after=0)
    )
    assert bundle is not None
    target, before, after = bundle
    assert target.id == target_id
    assert before == []
    assert after == []


def test_get_chunk_neighbours_window_clamped_to_ten(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    chunks = _list_chunks(client, body["attachment"]["id"])
    middle = chunks[len(chunks) // 2]

    store = get_attachment_store()
    bundle = asyncio.run(
        store.get_chunk_neighbours(middle["id"], before=999, after=999)
    )
    assert bundle is not None
    _, before, after = bundle
    # We never return more than 10 either side regardless of the
    # operator-supplied window.
    assert len(before) <= 10
    assert len(after) <= 10


# ---------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------


def test_http_neighbours_returns_attachment_chunk_and_window(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours"
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["ok"] is True
    assert payload["attachment"]["id"] == attachment_id
    assert payload["attachment"]["filename"] == "doc.md"
    assert payload["attachment"]["thread_id"] == thread_id
    assert payload["chunk"]["id"] == middle["id"]
    assert payload["chunk"]["preview"]
    assert payload["window"] == {"before": 1, "after": 1}
    assert len(payload["before"]) <= 1
    assert len(payload["after"]) <= 1


def test_http_neighbours_full_text_default_includes_text(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours"
    )
    payload = res.json()
    assert "text" in payload["chunk"]
    assert payload["chunk"]["text"]


def test_http_neighbours_full_text_false_strips_text(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours",
        params={"full_text": "false"},
    )
    payload = res.json()
    assert "text" not in payload["chunk"]
    # The preview is always present for hover-card layout.
    assert payload["chunk"]["preview"]


def test_http_neighbours_supports_us_alias(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    uk = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours"
    ).json()
    us = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbors"
    ).json()
    assert uk == us


def test_http_neighbours_window_params_apply(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours",
        params={"before": 2, "after": 2},
    )
    payload = res.json()
    assert payload["window"] == {"before": 2, "after": 2}
    # Unless we are within 2 chunks of the edge, both sides fill.
    assert len(payload["before"]) + len(payload["after"]) <= 4


def test_http_neighbours_404_when_attachment_unknown(
    client: TestClient,
) -> None:
    res = client.get(
        "/api/chat/attachments/att_missing/chunks/c_missing/neighbours"
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "attachment_not_found"


def test_http_neighbours_404_when_chunk_unknown(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/c_does_not_exist/neighbours"
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "chunk_not_found"


def test_http_neighbours_404_when_chunk_belongs_to_other_attachment(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body_a = _upload_multichunk(client, thread_id)
    other_thread = _make_thread(client, title="other")
    body_b = _upload_multichunk(client, other_thread)
    chunk_b = _list_chunks(client, body_b["attachment"]["id"])[0]

    # Ask for `chunk_b` under attachment A → must 404, not leak.
    res = client.get(
        f"/api/chat/attachments/{body_a['attachment']['id']}"
        f"/chunks/{chunk_b['id']}/neighbours"
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "chunk_not_found"


def test_http_neighbours_rejects_negative_window(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours",
        params={"before": -1},
    )
    assert res.status_code == 422


def test_http_neighbours_rejects_oversized_window(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours",
        params={"after": 11},
    )
    assert res.status_code == 422


def test_http_neighbours_ord_ordering_is_ascending(
    client: TestClient,
) -> None:
    thread_id = _make_thread(client)
    body = _upload_multichunk(client, thread_id)
    attachment_id = body["attachment"]["id"]
    chunks = _list_chunks(client, attachment_id)
    middle = chunks[len(chunks) // 2]
    target_ord = middle["ord"]

    res = client.get(
        f"/api/chat/attachments/{attachment_id}"
        f"/chunks/{middle['id']}/neighbours",
        params={"before": 3, "after": 3},
    )
    payload = res.json()
    if payload["before"]:
        before_ords = [c["ord"] for c in payload["before"]]
        assert before_ords == sorted(before_ords)
        # The chunker doesn't emit dense ords (overlap windows
        # leave gaps); we only assert that every "before" chunk
        # is strictly before the target.
        assert all(o < target_ord for o in before_ords)
    if payload["after"]:
        after_ords = [c["ord"] for c in payload["after"]]
        assert after_ords == sorted(after_ords)
        assert all(o > target_ord for o in after_ords)
