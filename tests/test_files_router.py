"""HTTP-level tests for the Wave 102 ``/api/files`` router.

Reuses the same temp-DB pattern as ``test_attachments_router.py`` so
the singletons reset between cases and the chat schema is rebuilt
under ``tmp_path``.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import store as chat_store_mod
from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture()
def files_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("TARS_ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("TARS_EMBEDDER", "hash")
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "0")
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
def client(files_env) -> TestClient:
    return TestClient(app)


def _upload(
    client: TestClient,
    name: str,
    body: bytes,
    *,
    mime: str = "text/markdown",
    category: str | None = None,
) -> dict:
    files = [("files", (name, io.BytesIO(body), mime))]
    params = {}
    if category:
        params["category"] = category
    res = client.post("/api/files/upload", files=files, params=params)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["uploaded"] >= 1
    return body["results"][0]["file"]


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------


def test_categories_lists_standard_set(client: TestClient) -> None:
    res = client.get("/api/files/categories")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    slugs = {c["slug"] for c in body["categories"]}
    # Each pre-built category from Wave 102 spec.
    for expected in (
        "contracts",
        "decks",
        "reports",
        "research",
        "legal",
        "correspondence",
        "code",
        "uncategorized",
    ):
        assert expected in slugs


def test_upload_multipart_returns_expected_shape(client: TestClient) -> None:
    files = [
        ("files", ("a.md", io.BytesIO(b"# alpha\nbody"), "text/markdown")),
        ("files", ("b.md", io.BytesIO(b"# beta\nbody"), "text/markdown")),
    ]
    res = client.post("/api/files/upload", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["uploaded"] == 2
    assert body["failed"] == 0
    assert len(body["results"]) == 2
    for entry in body["results"]:
        f = entry["file"]
        # Wave 102 surface keys.
        for key in ("id", "category", "tags", "pinned", "thumbnail_url"):
            assert key in f


def test_upload_rejects_empty(client: TestClient) -> None:
    files = [("files", ("empty.md", io.BytesIO(b""), "text/markdown"))]
    res = client.post("/api/files/upload", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["uploaded"] == 0
    assert body["failed"] == 1


def test_list_filters_by_category(client: TestClient) -> None:
    a = _upload(client, "deck.md", b"slide one slide two", category="decks")
    b = _upload(client, "report.md", b"audit kpi numbers", category="reports")

    res = client.get("/api/files", params={"category": "decks"})
    assert res.status_code == 200
    body = res.json()
    ids = {f["id"] for f in body["items"]}
    assert a["id"] in ids
    assert b["id"] not in ids


def test_patch_tags_and_pin(client: TestClient) -> None:
    f = _upload(client, "x.md", b"hello world")
    res = client.patch(
        f"/api/files/{f['id']}",
        json={"tags": ["confidential", "lp"], "pinned": True},
    )
    assert res.status_code == 200
    body = res.json()["file"]
    assert "confidential" in body["tags"]
    assert "lp" in body["tags"]
    assert body["pinned"] is True


def test_bulk_tag_add_remove_replace(client: TestClient) -> None:
    a = _upload(client, "a.md", b"one")
    b = _upload(client, "b.md", b"two")
    ids = [a["id"], b["id"]]

    add = client.post(
        "/api/files/bulk-tag",
        json={"ids": ids, "tags": ["q1", "lp"], "operation": "add"},
    )
    assert add.status_code == 200
    assert add.json()["updated"] == 2
    for f in add.json()["files"]:
        assert "q1" in f["tags"]
        assert "lp" in f["tags"]

    remove = client.post(
        "/api/files/bulk-tag",
        json={"ids": ids, "tags": ["q1"], "operation": "remove"},
    )
    assert remove.status_code == 200
    for f in remove.json()["files"]:
        assert "q1" not in f["tags"]
        assert "lp" in f["tags"]

    replace = client.post(
        "/api/files/bulk-tag",
        json={"ids": ids, "tags": ["only"], "operation": "replace"},
    )
    assert replace.status_code == 200
    for f in replace.json()["files"]:
        assert f["tags"] == ["only"]


def test_bulk_categorize(client: TestClient) -> None:
    a = _upload(client, "term-sheet.md", b"binding")
    b = _upload(client, "audit.md", b"compliance")
    res = client.post(
        "/api/files/bulk-categorize",
        json={"ids": [a["id"], b["id"]], "category": "contracts"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == 2
    for f in body["files"]:
        assert f["category"] == "contracts"


def test_bulk_delete_skips_pinned(client: TestClient) -> None:
    a = _upload(client, "keep.md", b"important")
    b = _upload(client, "drop.md", b"trash")
    # Pin the keep file.
    pin = client.patch(f"/api/files/{a['id']}", json={"pinned": True})
    assert pin.status_code == 200

    res = client.post(
        "/api/files/bulk-delete",
        json={"ids": [a["id"], b["id"]], "reason": "spring cleaning"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["deleted"] == 1
    assert any(s["id"] == a["id"] and s["reason"] == "pinned" for s in body["skipped"])


def test_stats_aggregates_by_category(client: TestClient) -> None:
    _upload(client, "deck.md", b"alpha", category="decks")
    _upload(client, "deck2.md", b"alpha2", category="decks")
    _upload(client, "rep.md", b"audit", category="reports")
    res = client.get("/api/files/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["total_count"] == 3
    assert body["by_category"].get("decks") == 2
    assert body["by_category"].get("reports") == 1
    assert body["total_bytes"] > 0


def test_get_single_file_returns_chunks_preview(client: TestClient) -> None:
    f = _upload(client, "doc.md", b"# heading\nbody body body")
    res = client.get(f"/api/files/{f['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["file"]["id"] == f["id"]
    assert body["chunk_count"] >= 1
    assert isinstance(body["chunks_preview"], list)


def test_delete_then_restore(client: TestClient) -> None:
    f = _upload(client, "ephemeral.md", b"go away")
    drop = client.delete(f"/api/files/{f['id']}", params={"reason": "test"})
    assert drop.status_code == 200
    assert drop.json()["file"]["deleted_at"] is not None

    # Default list excludes deleted.
    listing = client.get("/api/files")
    ids = {item["id"] for item in listing.json()["items"]}
    assert f["id"] not in ids

    restore = client.post(f"/api/files/{f['id']}/restore")
    assert restore.status_code == 200
    assert restore.json()["file"]["deleted_at"] is None


def test_hil_gate_fires_on_delete_when_required(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = _upload(client, "to-be-protected.md", b"shielded bytes")
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    res = client.delete(f"/api/files/{f['id']}", params={"reason": "x"})
    # Confirm token absent → policy_gate raises 401.
    assert res.status_code in (401, 403)


def test_auto_categorize_falls_back_to_heuristic(client: TestClient) -> None:
    f = _upload(client, "term-sheet-acme.md", b"the company agrees", category="uncategorized")
    res = client.post("/api/files/auto-categorize", json={"id": f["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == 1
    assert body["results"][0]["category"] == "contracts"


def test_filter_by_pinned(client: TestClient) -> None:
    a = _upload(client, "keep.md", b"keep")
    b = _upload(client, "drop.md", b"drop")
    client.patch(f"/api/files/{a['id']}", json={"pinned": True})

    listing = client.get("/api/files", params={"pinned": True})
    ids = {f["id"] for f in listing.json()["items"]}
    assert a["id"] in ids
    assert b["id"] not in ids


def test_filter_by_since(client: TestClient) -> None:
    _upload(client, "old.md", b"old data")
    cutoff = time.time()
    time.sleep(0.01)
    new = _upload(client, "new.md", b"new data")
    listing = client.get("/api/files", params={"since": cutoff})
    ids = {f["id"] for f in listing.json()["items"]}
    assert new["id"] in ids
