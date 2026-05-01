"""Tests for the periodic policy-expire background loop and the
matching ``policy.expired`` event surface.

Pre-PR ``PolicyStore.expire_stale`` returned only a count, the
``POST /api/policy/expire`` endpoint emitted no meeet event, and
nothing reaped stale ``pending`` confirmations automatically — the
cockpit's "approval inbox" could fill up with abandoned tokens
forever. This module pins:

- the new ``expire_stale -> list[PendingConfirmation]`` shape;
- per-token ``policy.expired`` emission from both the HTTP route
  and the new background loop;
- env var helper parsing for ``TARS_POLICY_EXPIRE_INTERVAL_S``;
- short-circuit + crash-isolation semantics of the loop;
- lifespan registration so the task actually spawns.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from backend.core.policy import PolicyStore


@pytest.fixture(autouse=True)
def isolated_policy_db(monkeypatch, tmp_path: Path):
    """Park each test's policy + meeet stores in tmp dirs."""

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    from backend.core.meeet import reset_client, reset_store
    from backend.core.policy import store as policy_store_mod

    reset_store()
    reset_client()
    monkeypatch.setattr(policy_store_mod, "_SINGLETON", None, raising=False)
    yield
    reset_store()
    reset_client()
    monkeypatch.setattr(policy_store_mod, "_SINGLETON", None, raising=False)


def _store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(str(tmp_path / "policy.sqlite"))


# ---------------------------------------------------------------------------
# expire_stale shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expire_stale_returns_empty_list_when_nothing_pending(tmp_path):
    store = _store(tmp_path)
    out = await store.expire_stale()
    assert out == []


@pytest.mark.asyncio
async def test_expire_stale_returns_only_past_ttl_rows(tmp_path):
    store = _store(tmp_path)
    fresh = await store.create(slug="x", action_id="y", args={}, ttl_s=60)
    stale = await store.create(slug="x", action_id="y", args={}, ttl_s=-10)

    expired = await store.expire_stale()
    tokens = {c.token for c in expired}
    assert tokens == {stale}
    assert fresh not in tokens
    assert all(c.status == "expired" for c in expired)


@pytest.mark.asyncio
async def test_expire_stale_skips_already_resolved_rows(tmp_path):
    """A confirmed / cancelled row whose TTL passed must not be flipped
    back to ``expired`` — that would corrupt the audit trail."""

    store = _store(tmp_path)
    confirmed = await store.create(slug="x", action_id="y", args={}, ttl_s=-10)
    await store.resolve(confirmed, status="confirmed", result={"r": 1})
    expired = await store.expire_stale()
    assert expired == []

    # And the original row is still confirmed, not expired.
    row = await store.get(confirmed)
    assert row is not None and row.status == "confirmed"


@pytest.mark.asyncio
async def test_expire_stale_handles_null_expires_at(tmp_path):
    """Rows with ``expires_at IS NULL`` must never be reaped — TTL is
    optional, so a NULL means "never expire automatically"."""

    store = _store(tmp_path)
    # Force a row with NULL expires_at via the raw connection.
    import sqlite3

    conn = sqlite3.connect(store.db_path)
    try:
        conn.execute(
            """INSERT INTO confirmations
               (token, created_at, slug, action_id, args, status, expires_at)
               VALUES ('cfm_no_ttl', ?, 'x', 'y', '{}', 'pending', NULL)""",
            (time.time() - 9999,),
        )
        conn.commit()
    finally:
        conn.close()

    expired = await store.expire_stale()
    assert expired == []
    row = await store.get("cfm_no_ttl")
    assert row is not None and row.status == "pending"


@pytest.mark.asyncio
async def test_expire_stale_is_idempotent(tmp_path):
    store = _store(tmp_path)
    await store.create(slug="x", action_id="y", args={}, ttl_s=-1)
    first = await store.expire_stale()
    assert len(first) == 1
    second = await store.expire_stale()
    assert second == []


# ---------------------------------------------------------------------------
# Env helper for TARS_POLICY_EXPIRE_INTERVAL_S
# ---------------------------------------------------------------------------


def test_policy_expire_interval_default_is_off(monkeypatch):
    from web_extras.app import _policy_expire_interval_s

    monkeypatch.delenv("TARS_POLICY_EXPIRE_INTERVAL_S", raising=False)
    assert _policy_expire_interval_s() == 0.0


def test_policy_expire_interval_parses_positive(monkeypatch):
    from web_extras.app import _policy_expire_interval_s

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "30")
    assert _policy_expire_interval_s() == 30.0


def test_policy_expire_interval_clamps_negative(monkeypatch):
    from web_extras.app import _policy_expire_interval_s

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "-5")
    assert _policy_expire_interval_s() == 0.0


def test_policy_expire_interval_garbage_falls_back_to_zero(monkeypatch):
    from web_extras.app import _policy_expire_interval_s

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "not-a-number")
    assert _policy_expire_interval_s() == 0.0


# ---------------------------------------------------------------------------
# Loop short-circuits & tick semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_returns_immediately_when_disabled(monkeypatch):
    from web_extras.app import _policy_expire_loop

    monkeypatch.delenv("TARS_POLICY_EXPIRE_INTERVAL_S", raising=False)
    await asyncio.wait_for(_policy_expire_loop(), timeout=0.5)


@pytest.mark.asyncio
async def test_loop_emits_event_per_expired_token(monkeypatch):
    """One tick of the loop expires each past-TTL token AND emits a
    matching ``policy.expired`` meeet event so the cockpit gold-pill
    audit lane sees the auto-reap."""

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "60")

    from backend.core.meeet import get_client
    from backend.core.policy import get_policy_store
    from web_extras import app as app_module

    store = get_policy_store()
    t1 = await store.create(slug="traders", action_id="cancel_alert", args={"id": 1}, ttl_s=-5)
    t2 = await store.create(slug="business", action_id="update_deal", args={"id": "d-1"}, ttl_s=-2)
    await store.create(slug="x", action_id="y", args={}, ttl_s=120)  # fresh, must NOT expire

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

    # Exactly one tick of work.
    assert sleeps[0] == 60.0
    assert len(sleeps) == 2

    # Both stale rows now expired; the fresh (TTL+120s) row stays pending.
    pending_tokens = {p.token for p in await store.list_pending()}
    assert t1 not in pending_tokens
    assert t2 not in pending_tokens
    assert len(pending_tokens) == 1
    recent = await store.list_recent()
    by_token = {r.token: r.status for r in recent}
    assert by_token[t1] == "expired"
    assert by_token[t2] == "expired"

    # And we emitted one policy.expired event per token.
    client = get_client()
    events = await client.store.list_events(kind="policy.expired", limit=50)
    payloads = {e.payload["token"] for e in events}
    assert payloads == {t1, t2}
    by_token = {e.payload["token"]: e.payload for e in events}
    assert by_token[t1]["slug"] == "traders"
    assert by_token[t1]["action"] == "cancel_alert"
    assert by_token[t2]["slug"] == "business"
    assert by_token[t2]["action"] == "update_deal"
    # ``expired_at`` populated from PolicyStore.resolved_at.
    assert all(p["expired_at"] is not None for p in by_token.values())


@pytest.mark.asyncio
async def test_loop_skips_emit_when_nothing_expired(monkeypatch):
    """Healthy machine: no pending tokens past TTL → no emit, no log."""

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "60")

    from backend.core.meeet import get_client
    from backend.core.policy import get_policy_store
    from web_extras import app as app_module

    # Fresh row that won't expire on this tick.
    await get_policy_store().create(
        slug="x", action_id="y", args={}, ttl_s=120
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

    client = get_client()
    events = await client.store.list_events(kind="policy.expired", limit=10)
    assert events == []


@pytest.mark.asyncio
async def test_loop_swallows_store_failure(monkeypatch, caplog):
    """A SQLite blip on expire_stale must NOT crash the host."""

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "5")

    from backend.core.policy import get_policy_store
    from web_extras import app as app_module

    store = get_policy_store()

    async def boom():
        raise RuntimeError("simulated sqlite error")

    monkeypatch.setattr(store, "expire_stale", boom)

    ticks: list[int] = []

    async def fake_sleep(seconds: float) -> None:  # noqa: ARG001
        ticks.append(1)
        if len(ticks) >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(app_module.asyncio, "sleep", fake_sleep)

    with caplog.at_level("WARNING", logger="tars.app"):
        with pytest.raises(asyncio.CancelledError):
            await app_module._policy_expire_loop()

    assert any("policy expire loop tick failed" in m for m in caplog.messages)
    assert len(ticks) == 2  # loop kept ticking despite the raise


# ---------------------------------------------------------------------------
# HTTP surface emits the same event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_expire_endpoint_emits_per_token_event(monkeypatch):
    """The manual ``POST /api/policy/expire`` route must emit the same
    event shape as the background loop, so the cockpit treats both
    paths uniformly."""

    from backend.core.meeet import get_client
    from backend.core.policy import get_policy_store
    from web_extras.routers.policy import expire_stale as expire_route

    store = get_policy_store()
    t1 = await store.create(slug="x", action_id="y", args={}, ttl_s=-1)
    t2 = await store.create(slug="x", action_id="z", args={}, ttl_s=-1)
    await store.create(slug="x", action_id="live", args={}, ttl_s=120)

    out = await expire_route()
    assert out["ok"] is True
    assert out["expired"] == 2
    assert set(out["tokens"]) == {t1, t2}

    events = await get_client().store.list_events(kind="policy.expired", limit=10)
    assert {e.payload["token"] for e in events} == {t1, t2}


# ---------------------------------------------------------------------------
# Lifespan registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_spawns_policy_expire_task(monkeypatch):
    """The lifespan should register the task even when the loop is
    disabled (interval=0); the task short-circuits internally."""

    monkeypatch.setenv("TARS_POLICY_EXPIRE_INTERVAL_S", "0")

    from web_extras import app as app_module

    spawned: list[str] = []
    real_create_task = asyncio.create_task

    def tracking_create_task(coro, *args, **kwargs):
        name = kwargs.get("name") or ""
        spawned.append(name)
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(app_module.asyncio, "create_task", tracking_create_task)

    async with app_module._lifespan(app_module.app):
        pass

    assert "policy-expire-loop" in spawned
