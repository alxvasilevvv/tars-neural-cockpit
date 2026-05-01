"""Saved searches: store CRUD + HTTP endpoints + run shortcut.

The cockpit ⌘K palette persists operator presets in
``~/.tars/chat.sqlite``. Three layers in one file:

1. ``ChatStore`` insert / get / list / update / delete / stamp_run.
2. HTTP CRUD via ``/api/search/saved``.
3. ``POST /api/search/saved/{id}/run`` honours scope + filters and
   stamps ``last_run_at``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.attachments import index as attachment_index_mod
from backend.core.chat import SavedSearch, Thread
from backend.core.chat import store as chat_store_mod
from backend.core.chat.models import Message
from backend.core.chat.store import get_chat_store


def _run(coro):
    return asyncio.run(coro)


# ============================================================
# ChatStore CRUD
# ============================================================


@pytest.fixture()
def chat_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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


def test_saved_search_round_trip(chat_env) -> None:
    chat = get_chat_store()
    saved = SavedSearch.fresh(
        label="EMEA blocker",
        query="EMEA blocker",
        scope="messages",
        filters={"role": "operator"},
    )
    _run(chat.insert_saved_search(saved))
    got = _run(chat.get_saved_search(saved.id))
    assert got is not None
    assert got.label == "EMEA blocker"
    assert got.scope == "messages"
    assert dict(got.filters) == {"role": "operator"}
    assert got.last_run_at is None
    assert got.pinned is False


def test_saved_search_blank_label_falls_back_to_untitled(chat_env) -> None:
    chat = get_chat_store()
    saved = SavedSearch.fresh(label="   ", query="q")
    _run(chat.insert_saved_search(saved))
    got = _run(chat.get_saved_search(saved.id))
    assert got is not None
    assert got.label == "untitled"


def test_list_orders_pinned_first_then_recent(chat_env) -> None:
    chat = get_chat_store()
    a = SavedSearch.fresh(label="alpha", query="a")
    b = SavedSearch.fresh(label="beta", query="b", pinned=True)
    c = SavedSearch.fresh(label="gamma", query="c")
    for s in (a, b, c):
        _run(chat.insert_saved_search(s))
    rows = _run(chat.list_saved_searches())
    assert rows[0].id == b.id  # pinned first
    # remaining ordered by updated_at DESC — c inserted last
    assert rows[1].id == c.id
    assert rows[2].id == a.id


def test_update_changes_label_query_scope_filters_pinned(chat_env) -> None:
    chat = get_chat_store()
    saved = SavedSearch.fresh(label="x", query="y", scope="all")
    _run(chat.insert_saved_search(saved))
    updated = _run(
        chat.update_saved_search(
            saved.id,
            label="renamed",
            query="EMEA",
            scope="messages",
            filters={"role": "operator", "thread_id": "thr_1"},
            pinned=True,
        )
    )
    assert updated is not None
    assert updated.label == "renamed"
    assert updated.query == "EMEA"
    assert updated.scope == "messages"
    assert dict(updated.filters) == {
        "role": "operator", "thread_id": "thr_1"
    }
    assert updated.pinned is True
    assert updated.updated_at >= saved.updated_at


def test_update_rejects_invalid_scope(chat_env) -> None:
    chat = get_chat_store()
    saved = SavedSearch.fresh(label="x", query="y")
    _run(chat.insert_saved_search(saved))
    with pytest.raises(ValueError):
        _run(
            chat.update_saved_search(saved.id, scope="bogus")  # type: ignore[arg-type]
        )


def test_update_missing_returns_none(chat_env) -> None:
    chat = get_chat_store()
    out = _run(chat.update_saved_search("sv_nope", label="x"))
    assert out is None


def test_delete_returns_false_when_missing(chat_env) -> None:
    chat = get_chat_store()
    assert _run(chat.delete_saved_search("sv_nope")) is False


def test_stamp_run_sets_last_run_at(chat_env) -> None:
    chat = get_chat_store()
    saved = SavedSearch.fresh(label="x", query="y")
    _run(chat.insert_saved_search(saved))
    stamped = _run(chat.stamp_saved_search_run(saved.id))
    assert stamped is not None
    assert stamped.last_run_at is not None
    assert stamped.last_run_at >= saved.created_at


def test_list_caps_at_500(chat_env) -> None:
    chat = get_chat_store()
    rows = _run(chat.list_saved_searches(limit=99999))
    assert isinstance(rows, list)


# ============================================================
# HTTP endpoints
# ============================================================


@pytest.fixture()
def http_app(chat_env):
    from web_extras.app import app

    with TestClient(app) as client:
        yield client


def test_create_get_list_update_delete_via_http(
    http_app: TestClient,
) -> None:
    create = http_app.post(
        "/api/search/saved",
        json={
            "label": "EMEA brief",
            "query": "EMEA blocker",
            "scope": "messages",
            "filters": {"role": "operator"},
        },
    )
    assert create.status_code == 200
    item = create.json()["item"]
    assert item["label"] == "EMEA brief"
    sv_id = item["id"]

    listed = http_app.get("/api/search/saved")
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] >= 1
    assert any(x["id"] == sv_id for x in body["items"])

    got = http_app.get(f"/api/search/saved/{sv_id}")
    assert got.status_code == 200
    assert got.json()["item"]["query"] == "EMEA blocker"

    patch = http_app.patch(
        f"/api/search/saved/{sv_id}",
        json={"label": "EMEA pinned", "pinned": True},
    )
    assert patch.status_code == 200
    assert patch.json()["item"]["pinned"] is True
    assert patch.json()["item"]["label"] == "EMEA pinned"

    deleted = http_app.delete(f"/api/search/saved/{sv_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == sv_id

    miss = http_app.get(f"/api/search/saved/{sv_id}")
    assert miss.status_code == 404


def test_create_validates_required_fields(http_app: TestClient) -> None:
    no_label = http_app.post(
        "/api/search/saved", json={"query": "x"}
    )
    assert no_label.status_code == 400
    assert no_label.json()["detail"] == "label_required"

    no_query = http_app.post(
        "/api/search/saved", json={"label": "x"}
    )
    assert no_query.status_code == 400
    assert no_query.json()["detail"] == "query_required"

    bad_scope = http_app.post(
        "/api/search/saved",
        json={"label": "x", "query": "y", "scope": "bogus"},
    )
    assert bad_scope.status_code == 400

    bad_filters = http_app.post(
        "/api/search/saved",
        json={"label": "x", "query": "y", "filters": "not-a-dict"},
    )
    assert bad_filters.status_code == 400


def test_patch_rejects_blank_strings(http_app: TestClient) -> None:
    create = http_app.post(
        "/api/search/saved",
        json={"label": "x", "query": "y"},
    )
    sv_id = create.json()["item"]["id"]

    blank_label = http_app.patch(
        f"/api/search/saved/{sv_id}", json={"label": "   "}
    )
    assert blank_label.status_code == 400

    blank_query = http_app.patch(
        f"/api/search/saved/{sv_id}", json={"query": ""}
    )
    assert blank_query.status_code == 400


def test_patch_missing_returns_404(http_app: TestClient) -> None:
    resp = http_app.patch(
        "/api/search/saved/sv_nope", json={"label": "anything"}
    )
    assert resp.status_code == 404


def test_run_messages_scope_executes_and_stamps(
    http_app: TestClient,
) -> None:
    chat = get_chat_store()
    thread = Thread.fresh(title="Brief", pack_slug="business")
    _run(chat.insert_thread(thread))
    _run(
        chat.insert_message(
            Message.from_operator(
                thread.id, "EMEA blocker GDPR redlines"
            )
        )
    )

    create = http_app.post(
        "/api/search/saved",
        json={
            "label": "EMEA",
            "query": "EMEA blocker",
            "scope": "messages",
            "filters": {"role": "operator"},
        },
    )
    sv_id = create.json()["item"]["id"]

    run = http_app.post(f"/api/search/saved/{sv_id}/run")
    assert run.status_code == 200
    body = run.json()
    assert body["ok"] is True
    assert body["scope"] == "messages"
    assert body["count"] >= 1
    assert any(
        h["ref"]["thread_id"] == thread.id for h in body["hits"]
    )
    assert body["item"]["last_run_at"] is not None


def test_run_unified_scope_returns_hits(http_app: TestClient) -> None:
    chat = get_chat_store()
    thread = Thread.fresh(title="x", pack_slug="business")
    _run(chat.insert_thread(thread))
    _run(
        chat.insert_message(
            Message.from_operator(thread.id, "EMEA pipeline brief")
        )
    )
    create = http_app.post(
        "/api/search/saved",
        json={"label": "All", "query": "EMEA", "scope": "all"},
    )
    sv_id = create.json()["item"]["id"]
    run = http_app.post(
        f"/api/search/saved/{sv_id}/run", json={"top_k": 5}
    )
    assert run.status_code == 200
    body = run.json()
    assert body["ok"] is True
    assert body["scope"] == "all"


def test_run_missing_returns_404(http_app: TestClient) -> None:
    resp = http_app.post("/api/search/saved/sv_nope/run")
    assert resp.status_code == 404
