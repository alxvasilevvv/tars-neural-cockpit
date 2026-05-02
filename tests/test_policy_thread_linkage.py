"""Tests for the ``x-tars-thread-id`` linkage through the policy gate.

Pre-PR every ``policy.*`` event flowed without a ``thread_id`` field,
which meant the per-thread cockpit timeline could never surface
"action queued" / "operator confirmed" / "operator cancelled" /
"auto-expired" rows for the conversation that originated them.

The ``backend/core/search/timeline.py`` allow-list already includes
all the policy events; the missing piece was carrying ``thread_id``
across:

1. The HTTP entry — ``POST /api/domains/{slug}/actions/{action_id}``
   accepts an ``x-tars-thread-id`` header and threads it into the
   gate + ``policy.allowed`` / ``policy.queued`` / ``policy.blocked``
   event payloads.
2. The policy store — `confirmations.thread_id` column persists the
   value (additive migration on top of the existing schema).
3. The follow-up router — ``POST /api/policy/confirm/{token}`` and
   ``POST /api/policy/cancel/{token}`` re-attach the row's
   ``thread_id`` to the ``policy.confirm`` / ``policy.cancelled``
   events.
4. The expire path — both ``POST /api/policy/expire`` and the
   background ``_policy_expire_loop`` re-attach ``thread_id`` to
   the ``policy.expired`` event.

This module pins all four legs.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.policy import PolicyStore


@pytest.fixture(autouse=True)
def isolated_policy_db(monkeypatch, tmp_path: Path):
    """Park each test in its own ~/.tars sandbox."""

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    from backend.core.chat import store as chat_store_mod
    from backend.core.meeet import reset_client, reset_store
    from backend.core.policy import store as policy_store_mod

    reset_store()
    reset_client()
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(policy_store_mod, "_SINGLETON", None, raising=False)
    yield
    reset_store()
    reset_client()
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(policy_store_mod, "_SINGLETON", None, raising=False)


def _store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(str(tmp_path / "policy.sqlite"))


# ---------------------------------------------------------------------------
# PolicyStore: thread_id column, additive migration, round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_persists_thread_id_when_provided(tmp_path):
    store = _store(tmp_path)
    token = await store.create(
        slug="traders",
        action_id="cancel_alert",
        args={"id": "x"},
        thread_id="thr_abc",
    )
    row = await store.get(token)
    assert row is not None
    assert row.thread_id == "thr_abc"


@pytest.mark.asyncio
async def test_create_defaults_thread_id_to_none(tmp_path):
    """The new kwarg must stay optional so old call-sites keep working."""

    store = _store(tmp_path)
    token = await store.create(slug="x", action_id="y", args={})
    row = await store.get(token)
    assert row is not None
    assert row.thread_id is None


_LEGACY_SCHEMA = """
CREATE TABLE confirmations (
    token TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    slug TEXT NOT NULL,
    action_id TEXT NOT NULL,
    args TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at REAL,
    result TEXT,
    expires_at REAL,
    requested_by TEXT,
    trace_id TEXT
);
"""


@pytest.mark.asyncio
async def test_old_db_schema_gets_additive_migration(tmp_path):
    """Open a DB created without the ``thread_id`` column and verify
    the store backfills it via ``ALTER TABLE`` on first connect."""

    legacy_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(legacy_path)
    try:
        conn.executescript(_LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO confirmations "
            "(token, created_at, slug, action_id, args, status, expires_at) "
            "VALUES ('cfm_legacy', ?, 'x', 'y', '{}', 'pending', ?)",
            (time.time(), time.time() + 3600),
        )
        conn.commit()
    finally:
        conn.close()

    store = PolicyStore(str(legacy_path))  # triggers migration

    inspect_conn = sqlite3.connect(legacy_path)
    try:
        cols = inspect_conn.execute("PRAGMA table_info(confirmations)").fetchall()
    finally:
        inspect_conn.close()
    col_names = {c[1] for c in cols}
    assert "thread_id" in col_names

    # Legacy row still readable; thread_id materialises as None.
    row = await store.get("cfm_legacy")
    assert row is not None
    assert row.thread_id is None


@pytest.mark.asyncio
async def test_expire_stale_carries_thread_id_through(tmp_path):
    store = _store(tmp_path)
    await store.create(
        slug="x",
        action_id="y",
        args={},
        ttl_s=-5,
        thread_id="thr_zzz",
    )
    expired = await store.expire_stale()
    assert len(expired) == 1
    assert expired[0].thread_id == "thr_zzz"


# ---------------------------------------------------------------------------
# HTTP entry: x-tars-thread-id header → policy.queued / policy.allowed payload
# ---------------------------------------------------------------------------


def _make_app_client():
    """Build a minimal FastAPI app mounting only the domains router so
    we can drive the gate end-to-end in the testclient. We avoid the
    full ``web_extras.app`` to skip lifespan side-effects."""

    from fastapi import FastAPI
    from web_extras.routers.domains import router as domains_router

    app = FastAPI()
    app.include_router(domains_router)
    return TestClient(app)


def test_action_endpoint_threads_x_tars_thread_id_into_policy_queued(
    monkeypatch,
):
    """Confirm-mode invocation of a destructive action with the
    ``x-tars-thread-id`` header should produce a ``policy.queued`` event
    whose payload carries the same thread id, and persist that thread
    id on the confirmation row."""

    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")

    from backend.core.meeet import get_client
    from backend.core.policy import get_policy_store

    client = _make_app_client()
    resp = client.post(
        "/api/domains/traders/actions/cancel_alert",
        json={"alert_id": "local-alert-9999"},
        headers={"x-tars-thread-id": "thr_link_001"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    token = body["result"]["policy"]["confirmation_token"]
    assert token

    # The persisted confirmation row carries the thread id.
    store = get_policy_store()
    row = asyncio.run(store.get(token))
    assert row is not None
    assert row.thread_id == "thr_link_001"

    # The policy.queued event carries it too.
    events = asyncio.run(get_client().store.list_events(kind="policy.queued", limit=10))
    assert any(e.payload.get("thread_id") == "thr_link_001" for e in events)


def test_action_endpoint_omits_thread_id_when_header_absent(monkeypatch):
    """Without the header, the event must NOT add a stray empty
    ``thread_id`` field — the timeline filter is exact-match."""

    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")

    from backend.core.meeet import get_client

    client = _make_app_client()
    resp = client.post(
        "/api/domains/traders/actions/cancel_alert",
        json={"alert_id": "x"},
    )
    assert resp.status_code == 200

    events = asyncio.run(
        get_client().store.list_events(kind="policy.queued", limit=10)
    )
    assert events
    for e in events:
        assert "thread_id" not in e.payload


def test_action_endpoint_threads_thread_id_into_policy_allowed_when_autopilot(
    monkeypatch,
):
    """Autopilot mode skips the queue and goes straight to
    policy.allowed — the thread id must still ride along."""

    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    from backend.core.meeet import get_client

    client = _make_app_client()
    resp = client.post(
        "/api/domains/traders/actions/cancel_alert",
        json={"alert_id": "x"},
        headers={"x-tars-thread-id": "thr_link_002"},
    )
    assert resp.status_code == 200

    events = asyncio.run(
        get_client().store.list_events(kind="policy.allowed", limit=10)
    )
    assert any(e.payload.get("thread_id") == "thr_link_002" for e in events)


def test_action_endpoint_threads_thread_id_into_policy_blocked_in_dry_run(
    monkeypatch,
):
    """Dry-run mode emits policy.blocked instead of policy.queued. The
    thread id must still ride along."""

    monkeypatch.setenv("TARS_POLICY_MODE", "dry_run")

    from backend.core.meeet import get_client

    client = _make_app_client()
    resp = client.post(
        "/api/domains/traders/actions/cancel_alert",
        json={"alert_id": "x"},
        headers={"x-tars-thread-id": "thr_link_003"},
    )
    assert resp.status_code == 200

    events = asyncio.run(
        get_client().store.list_events(kind="policy.blocked", limit=10)
    )
    assert any(e.payload.get("thread_id") == "thr_link_003" for e in events)


# ---------------------------------------------------------------------------
# Confirm / cancel / expire all re-attach thread_id from the row
# ---------------------------------------------------------------------------


def _make_full_app_client():
    from fastapi import FastAPI
    from web_extras.routers.domains import router as domains_router
    from web_extras.routers.policy import router as policy_router

    app = FastAPI()
    app.include_router(domains_router)
    app.include_router(policy_router)
    return TestClient(app)


def test_policy_confirm_route_reattaches_thread_id(monkeypatch):
    """Operator hits POST /api/policy/confirm/{token} → the resulting
    policy.confirm event must carry the originating thread_id."""

    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")

    from backend.core.meeet import get_client

    client = _make_full_app_client()
    queued = client.post(
        "/api/domains/traders/actions/cancel_alert",
        json={"alert_id": "local-alert-9999"},
        headers={"x-tars-thread-id": "thr_link_004"},
    )
    token = queued.json()["result"]["policy"]["confirmation_token"]

    confirm = client.post(f"/api/policy/confirm/{token}")
    # The action handler may surface a 500 on a missing alert id —
    # what we care about is that the policy.confirm event was emitted
    # before the handler ran.
    assert confirm.status_code in {200, 500}

    events = asyncio.run(
        get_client().store.list_events(kind="policy.confirm", limit=10)
    )
    assert any(e.payload.get("thread_id") == "thr_link_004" for e in events)


def test_policy_cancel_route_reattaches_thread_id(monkeypatch):
    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")

    from backend.core.meeet import get_client

    client = _make_full_app_client()
    queued = client.post(
        "/api/domains/traders/actions/cancel_alert",
        json={"alert_id": "x"},
        headers={"x-tars-thread-id": "thr_link_005"},
    )
    token = queued.json()["result"]["policy"]["confirmation_token"]

    cancelled = client.post(f"/api/policy/cancel/{token}")
    assert cancelled.status_code == 200

    events = asyncio.run(
        get_client().store.list_events(kind="policy.cancelled", limit=10)
    )
    assert any(e.payload.get("thread_id") == "thr_link_005" for e in events)


@pytest.mark.asyncio
async def test_expire_loop_reattaches_thread_id(monkeypatch):
    """Background _policy_expire_loop must include thread_id when the
    expiring row carries one."""

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "30")

    from backend.core.meeet import get_client
    from backend.core.policy import get_policy_store
    from web_extras import app as app_module

    store = get_policy_store()
    await store.create(
        slug="x",
        action_id="y",
        args={},
        ttl_s=-5,
        thread_id="thr_link_006",
    )

    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise asyncio.CancelledError()
        await real_sleep(0)

    monkeypatch.setattr(app_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await app_module._policy_expire_loop()

    events = await get_client().store.list_events(kind="policy.expired", limit=10)
    assert any(e.payload.get("thread_id") == "thr_link_006" for e in events)


@pytest.mark.asyncio
async def test_expire_loop_omits_thread_id_when_unset(monkeypatch):
    """A confirmation that was created without a thread id must NOT
    inject a stray ``thread_id: None`` field — the timeline filter is
    exact-match."""

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "30")

    from backend.core.meeet import get_client
    from backend.core.policy import get_policy_store
    from web_extras import app as app_module

    await get_policy_store().create(
        slug="x",
        action_id="y",
        args={},
        ttl_s=-5,
    )

    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise asyncio.CancelledError()
        await real_sleep(0)

    monkeypatch.setattr(app_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await app_module._policy_expire_loop()

    events = await get_client().store.list_events(kind="policy.expired", limit=10)
    assert events
    for e in events:
        assert "thread_id" not in e.payload
