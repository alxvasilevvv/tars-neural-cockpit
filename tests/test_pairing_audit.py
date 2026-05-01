"""Tests for the operator-facing pairing audit feed.

`GET /api/pairing/audit` is the cockpit's gold-pill audit lane —
it merges `pair.*` and `recovery.*` events from the meeet store
into one newest-first list. These tests pin:

- the prefix filter on `MeeetStore.list_events()` (sqlite LIKE
  with defensive escaping),
- the `kind_prefix` query param on `GET /api/meeet/events`,
- the merged + deduped pairing audit endpoint,
- public-safe payload shape (no `pushed`, `last_error`, `source`).
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.meeet import client as meeet_client_mod
from backend.core.meeet import get_client, get_store
from backend.core.meeet import store as meeet_store_mod
from backend.core.pairing.store import _reset_singleton_for_tests
from web_extras.app import app
from web_extras.rate_limit import reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(meeet_client_mod, "_SINGLETON", None, raising=False)
    _reset_singleton_for_tests()
    reset_rate_limiter()
    yield
    _reset_singleton_for_tests()
    reset_rate_limiter()
    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(meeet_client_mod, "_SINGLETON", None, raising=False)


@pytest.fixture
def client():
    return TestClient(app)


def _emit(kind: str, payload: dict) -> None:
    """Synchronously emit a meeet event via the client singleton."""

    asyncio.new_event_loop().run_until_complete(get_client().emit(kind, payload))


def _seed_audit_events() -> None:
    _emit("pair.attempted", {"pair_id": "pid-1"})
    _emit("pair.linked", {"device_id": "dev-1", "kind": "mobile_ios"})
    _emit("recovery.shown", {"fingerprint": "AAAA-BBBB-CCCC"})
    _emit("recovery.challenge.started", {"challenge_id": "chal-1"})
    _emit("usage.tokens", {"tokens": 42})
    _emit("pair.revoked", {"device_id": "dev-1"})
    _emit("pair.host_rotated", {"host_id": "host-1"})
    _emit("recovery.challenge.passed", {"challenge_id": "chal-1"})


# ---------------------------------------------------------------------
# Store-level: kind_prefix filter
# ---------------------------------------------------------------------


def test_list_events_kind_prefix_filters_to_pair_events():
    _seed_audit_events()
    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=100, kind_prefix="pair.")
    )

    kinds = {e.kind for e in events}
    assert kinds == {
        "pair.attempted",
        "pair.linked",
        "pair.revoked",
        "pair.host_rotated",
    }


def test_list_events_kind_prefix_filters_to_recovery_events():
    _seed_audit_events()
    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=100, kind_prefix="recovery.")
    )
    kinds = {e.kind for e in events}
    assert kinds == {
        "recovery.shown",
        "recovery.challenge.started",
        "recovery.challenge.passed",
    }


def test_list_events_kind_prefix_excludes_unrelated_events():
    _seed_audit_events()
    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=100, kind_prefix="pair.")
    )
    assert all(not e.kind.startswith("usage.") for e in events)


def test_list_events_kind_prefix_combined_with_kind_is_logical_and():
    _seed_audit_events()
    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(
            limit=100, kind="pair.linked", kind_prefix="pair."
        )
    )
    assert {e.kind for e in events} == {"pair.linked"}


def test_list_events_kind_prefix_escapes_like_metachars():
    """Prefix containing a literal ``%`` must not be interpreted as a
    SQLite wildcard. We seed an event whose kind contains ``%`` only
    in the actual stored value, then verify a prefix probe with ``%``
    behaves as a literal (no false positives)."""

    _emit("pair.linked", {})
    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=100, kind_prefix="pair%")
    )
    assert events == []
    events_underscore = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=100, kind_prefix="pa_r.")
    )
    assert events_underscore == []


# ---------------------------------------------------------------------
# /api/meeet/events?kind_prefix=
# ---------------------------------------------------------------------


def test_meeet_events_endpoint_supports_kind_prefix(client: TestClient) -> None:
    _seed_audit_events()

    res = client.get("/api/meeet/events", params={"kind_prefix": "pair."})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    kinds = {e["kind"] for e in body["events"]}
    assert kinds <= {
        "pair.attempted",
        "pair.linked",
        "pair.revoked",
        "pair.host_rotated",
    }
    assert "usage.tokens" not in kinds


# ---------------------------------------------------------------------
# /api/pairing/audit
# ---------------------------------------------------------------------


def test_pairing_audit_returns_pair_and_recovery_only(client: TestClient) -> None:
    _seed_audit_events()

    res = client.get("/api/pairing/audit")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert set(body["prefixes"]) == {"pair.", "recovery."}

    kinds = {e["kind"] for e in body["events"]}
    assert "usage.tokens" not in kinds
    expected = {
        "pair.attempted",
        "pair.linked",
        "pair.revoked",
        "pair.host_rotated",
        "recovery.shown",
        "recovery.challenge.started",
        "recovery.challenge.passed",
    }
    assert kinds == expected


def test_pairing_audit_is_newest_first(client: TestClient) -> None:
    _emit("pair.attempted", {"step": 1})
    time.sleep(0.005)
    _emit("recovery.shown", {"step": 2})
    time.sleep(0.005)
    _emit("pair.linked", {"step": 3})

    res = client.get("/api/pairing/audit")
    body = res.json()
    timestamps = [e["ts"] for e in body["events"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_pairing_audit_event_shape_is_public_safe(client: TestClient) -> None:
    _emit("pair.linked", {"device_id": "dev-1"})

    body = client.get("/api/pairing/audit").json()
    assert body["count"] == 1
    ev = body["events"][0]
    assert set(ev.keys()) == {"id", "ts", "trace_id", "kind", "payload"}
    # Internal-only fields must not bleed into the operator feed.
    assert "pushed" not in ev
    assert "last_error" not in ev
    assert "source" not in ev


def test_pairing_audit_supports_since_filter(client: TestClient) -> None:
    _emit("pair.attempted", {"slot": "before"})
    time.sleep(0.01)
    cutoff = time.time()
    time.sleep(0.01)
    _emit("pair.linked", {"slot": "after"})

    body = client.get("/api/pairing/audit", params={"since": cutoff}).json()
    slots = [e["payload"].get("slot") for e in body["events"]]
    assert "before" not in slots
    assert "after" in slots


def test_pairing_audit_respects_limit(client: TestClient) -> None:
    for i in range(7):
        _emit("pair.attempted", {"i": i})
    body = client.get("/api/pairing/audit", params={"limit": 3}).json()
    assert body["count"] == 3
    assert len(body["events"]) == 3


def test_pairing_audit_dedupes_events_seen_in_both_buckets(
    client: TestClient,
) -> None:
    """A single event id must appear at most once in the combined feed,
    even though the pair / recovery prefixes are queried separately."""

    _emit("pair.attempted", {})
    _emit("recovery.shown", {})

    res = client.get("/api/pairing/audit")
    body = res.json()
    ids = [e["id"] for e in body["events"] if e["id"] is not None]
    assert len(ids) == len(set(ids))
