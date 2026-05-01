"""Per-pack memory partitions — store + HTTP.

Three layers under test:

1. ``MemoryStore`` direct CRUD: upsert (insert + update), get, list,
   delete, purge_expired, stats.
2. Partitioning invariants: business and science don't see each
   other's keys; a fact in pack A doesn't leak into pack B.
3. HTTP wiring: every endpoint at ``/api/packs/{slug}/memory`` and
   the global stats / purge endpoints.

Each test uses a tmp DB so we never touch the operator's
``~/.tars/memory.sqlite``.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from backend.core.memory import (
    MemoryEntry,
    get_memory_store,
    reset_memory_store,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TARS_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    reset_memory_store()
    yield
    reset_memory_store()


def _client():
    from fastapi.testclient import TestClient

    from web_extras.app import app

    return TestClient(app)


# ---------------------------------------------------------------------
# Store basics
# ---------------------------------------------------------------------


def test_store_enables_with_db_path(isolated_store) -> None:
    store = get_memory_store()
    assert store.enabled is True
    assert store.db_path is not None


def test_store_disabled_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEMORY_STORE", "disabled")
    reset_memory_store()
    store = get_memory_store()
    assert store.enabled is False


def test_upsert_inserts_new_row(isolated_store) -> None:
    store = get_memory_store()
    e = _run(store.upsert(
        pack_slug="business", key="emea_owner",
        value={"name": "Alice"},
        kind="preference",
    ))
    assert isinstance(e, MemoryEntry)
    assert e.pack_slug == "business"
    assert e.key == "emea_owner"
    assert e.value == {"name": "Alice"}
    assert e.kind == "preference"


def test_upsert_updates_existing_row(isolated_store) -> None:
    store = get_memory_store()
    e1 = _run(store.upsert(
        pack_slug="business", key="emea_owner", value="Alice",
    ))
    e2 = _run(store.upsert(
        pack_slug="business", key="emea_owner", value="Bob",
        kind="preference",
    ))
    assert e1.id == e2.id  # same row, value updated
    assert e2.value == "Bob"
    assert e2.kind == "preference"
    assert e2.updated_at >= e1.updated_at


def test_get_returns_none_when_missing(isolated_store) -> None:
    store = get_memory_store()
    out = _run(store.get(pack_slug="business", key="missing"))
    assert out is None


def test_list_returns_recent_first(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1))
    _run(store.upsert(pack_slug="business", key="b", value=2))
    _run(store.upsert(pack_slug="business", key="c", value=3))
    rows = _run(store.list(pack_slug="business"))
    assert [r.key for r in rows[:3]] == ["c", "b", "a"]


def test_list_filters_by_kind(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1, kind="fact"))
    _run(store.upsert(pack_slug="business", key="b", value=2, kind="draft"))
    rows = _run(store.list(pack_slug="business", kind="fact"))
    assert len(rows) == 1 and rows[0].key == "a"


def test_list_filters_by_key_prefix(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="okr.q1", value=1))
    _run(store.upsert(pack_slug="business", key="okr.q2", value=2))
    _run(store.upsert(pack_slug="business", key="kpi.cac", value=3))
    rows = _run(store.list(pack_slug="business", key_prefix="okr."))
    assert sorted(r.key for r in rows) == ["okr.q1", "okr.q2"]


def test_delete_returns_true_then_false(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1))
    assert _run(store.delete(pack_slug="business", key="a")) is True
    assert _run(store.delete(pack_slug="business", key="a")) is False


# ---------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------


def test_pack_partitions_dont_leak(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="okr_q1", value="biz"))
    _run(store.upsert(pack_slug="science", key="okr_q1", value="sci"))

    biz = _run(store.get(pack_slug="business", key="okr_q1"))
    sci = _run(store.get(pack_slug="science", key="okr_q1"))
    assert biz.value == "biz"
    assert sci.value == "sci"
    biz_list = _run(store.list(pack_slug="business"))
    assert len(biz_list) == 1


def test_unique_index_collapses_same_key_within_pack(
    isolated_store,
) -> None:
    store = get_memory_store()
    e1 = _run(store.upsert(pack_slug="business", key="a", value=1))
    e2 = _run(store.upsert(pack_slug="business", key="a", value=2))
    rows = _run(store.list(pack_slug="business"))
    assert len(rows) == 1
    assert e1.id == e2.id


# ---------------------------------------------------------------------
# TTL
# ---------------------------------------------------------------------


def test_expired_entry_hidden_by_default(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="cache_a", value=1,
        ttl_until=time.time() - 5,
    ))
    out = _run(store.get(pack_slug="business", key="cache_a"))
    assert out is None
    rows = _run(store.list(pack_slug="business"))
    assert rows == []


def test_expired_entry_visible_with_include_expired(
    isolated_store,
) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="cache_a", value=1,
        ttl_until=time.time() - 5,
    ))
    out = _run(store.get(
        pack_slug="business", key="cache_a", include_expired=True,
    ))
    assert out is not None
    rows = _run(store.list(pack_slug="business", include_expired=True))
    assert len(rows) == 1


def test_purge_expired_drops_only_dead_rows(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="dead", value=1,
        ttl_until=time.time() - 5,
    ))
    _run(store.upsert(pack_slug="business", key="live", value=2))
    out = _run(store.purge_expired())
    assert out["ok"] is True
    assert out["deleted"] == 1
    rows = _run(store.list(pack_slug="business", include_expired=True))
    assert [r.key for r in rows] == ["live"]


def test_purge_expired_can_scope_to_pack(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="x", value=1,
        ttl_until=time.time() - 5,
    ))
    _run(store.upsert(
        pack_slug="science", key="y", value=2,
        ttl_until=time.time() - 5,
    ))
    out = _run(store.purge_expired(pack_slug="business"))
    assert out["deleted"] == 1
    # science still has the dead row.
    sci = _run(store.list(
        pack_slug="science", include_expired=True
    ))
    assert len(sci) == 1


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------


def test_stats_returns_kind_breakdown(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1, kind="fact"))
    _run(store.upsert(pack_slug="business", key="b", value=2, kind="fact"))
    _run(store.upsert(pack_slug="business", key="c", value=3, kind="draft"))
    s = _run(store.stats(pack_slug="business"))
    assert s["total"] == 3
    assert s["live"] == 3
    assert s["expired"] == 0
    assert s["kinds"]["fact"] == 2
    assert s["kinds"]["draft"] == 1


# ---------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------


def test_http_upsert_then_get(isolated_store) -> None:
    with _client() as client:
        r = client.post(
            "/api/packs/business/memory",
            json={"key": "owner", "value": "Alice", "kind": "preference"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["entry"]["value"] == "Alice"
        r2 = client.get("/api/packs/business/memory/owner")
        assert r2.status_code == 200
        assert r2.json()["entry"]["value"] == "Alice"


def test_http_upsert_validates_required_fields(isolated_store) -> None:
    with _client() as client:
        r = client.post(
            "/api/packs/business/memory",
            json={"value": "Alice"},  # no key
        )
    assert r.status_code == 400


def test_http_upsert_with_ttl_seconds(isolated_store) -> None:
    with _client() as client:
        r = client.post(
            "/api/packs/business/memory",
            json={"key": "k", "value": "v", "ttl_seconds": 3600},
        )
        body = r.json()
        assert body["entry"]["ttl_until"] is not None
        assert body["entry"]["ttl_until"] > time.time()


def test_http_get_returns_404_for_missing(isolated_store) -> None:
    with _client() as client:
        r = client.get("/api/packs/business/memory/does_not_exist")
    assert r.status_code == 404


def test_http_list_returns_only_live_by_default(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="dead", value=1,
        ttl_until=time.time() - 5,
    ))
    _run(store.upsert(pack_slug="business", key="live", value=2))
    with _client() as client:
        r = client.get("/api/packs/business/memory")
        keys = [e["key"] for e in r.json()["entries"]]
    assert keys == ["live"]


def test_http_list_with_include_expired(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="dead", value=1,
        ttl_until=time.time() - 5,
    ))
    with _client() as client:
        r = client.get(
            "/api/packs/business/memory?include_expired=true"
        )
        keys = [e["key"] for e in r.json()["entries"]]
    assert keys == ["dead"]


def test_http_delete_removes_entry(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1))
    with _client() as client:
        r = client.delete("/api/packs/business/memory/a")
        assert r.status_code == 200
        r2 = client.get("/api/packs/business/memory/a")
        assert r2.status_code == 404


def test_http_purge_expired_endpoint(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="dead", value=1,
        ttl_until=time.time() - 5,
    ))
    with _client() as client:
        r = client.post(
            "/api/packs/business/memory/_purge_expired"
        )
    body = r.json()
    assert body["ok"] is True
    assert body["deleted"] == 1


def test_http_pack_stats_endpoint(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1, kind="fact"))
    _run(store.upsert(pack_slug="business", key="b", value=2, kind="draft"))
    with _client() as client:
        r = client.get("/api/packs/business/memory/_stats")
    body = r.json()
    assert body["pack_slug"] == "business"
    assert body["total"] == 2
    assert body["kinds"]["fact"] == 1


def test_http_global_stats_endpoint(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(pack_slug="business", key="a", value=1))
    _run(store.upsert(pack_slug="science", key="b", value=2))
    with _client() as client:
        r = client.get("/api/memory/stats")
    body = r.json()
    assert body["total"] == 2
    assert body["pack_slug"] is None


def test_http_global_purge_endpoint(isolated_store) -> None:
    store = get_memory_store()
    _run(store.upsert(
        pack_slug="business", key="x", value=1,
        ttl_until=time.time() - 5,
    ))
    _run(store.upsert(
        pack_slug="science", key="y", value=2,
        ttl_until=time.time() - 5,
    ))
    with _client() as client:
        r = client.post("/api/memory/_purge_expired")
    body = r.json()
    assert body["deleted"] == 2


def test_http_partitions_isolate(isolated_store) -> None:
    """Cross-pack listing only returns the requested pack."""

    with _client() as client:
        client.post(
            "/api/packs/business/memory",
            json={"key": "shared", "value": "biz"},
        )
        client.post(
            "/api/packs/science/memory",
            json={"key": "shared", "value": "sci"},
        )
        biz = client.get("/api/packs/business/memory").json()
        sci = client.get("/api/packs/science/memory").json()
    assert {e["value"] for e in biz["entries"]} == {"biz"}
    assert {e["value"] for e in sci["entries"]} == {"sci"}
