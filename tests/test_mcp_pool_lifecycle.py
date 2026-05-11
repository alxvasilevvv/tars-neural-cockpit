"""Wave M7 — SessionPool sweeper + per-server concurrency limits.

The Wave M6 ``SessionPool`` (PR #180) ships with manual lifecycle:
operators must call ``evict_idle()`` themselves on a timer, and there
is no protection against a misbehaving caller flooding one MCP server
with concurrent requests.

Wave M7 adds two opt-in, no-overhead-when-disabled mechanisms:

1. **Background sweeper** — ``SessionPool.start_sweeper()`` spawns
   a coroutine that calls ``evict_idle`` on a fixed interval.
   ``stop_sweeper()`` cancels it cleanly. Stats are surfaced via
   ``pool.stats()["sweeper"]`` so the cockpit panel can show
   "evicted 3 idle sessions in last 4 runs".

2. **Per-server concurrency cap** — ``ServerConfig.max_concurrency``
   declares "no more than N concurrent ``call_tool`` invocations
   against this server". The bridge handler (``_build_pooled_handler``)
   wraps every call in ``pool.acquire_slot(config)``; without a cap
   it's a near-zero-cost no-op that still increments the call
   counter. ``set_concurrency_limit`` lets operators flip caps at
   runtime without restart.

These tests pin the lifecycle: start/stop/idempotent, sweeper
actually evicts, semaphore actually serialises, counters tick.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.core.mcp_bridge.pool import (
    PoolSweeperStats,
    SessionPool,
    _PoolEntry,
)
from backend.mcp.client import ServerConfig


# ---------------------------------------------------------------------
# Test scaffolding — synthetic sessions/transports we can poke at
# ---------------------------------------------------------------------


class _FakeTransport:
    def __init__(self) -> None:
        self._closed = False

    async def close(self) -> None:
        self._closed = True


class _FakeSession:
    server_info = {"name": "fake", "version": "0.0.1"}
    server_capabilities = {"tools": {"_count": 0}}


def _inject_entry(
    pool: SessionPool, name: str, *, last_used_ago: float
) -> _PoolEntry:
    """Inject a fake entry so we can drive the sweeper without
    actually spawning subprocesses."""

    now = time.monotonic()
    entry = _PoolEntry(
        session=_FakeSession(),  # type: ignore[arg-type]
        transport=_FakeTransport(),  # type: ignore[arg-type]
        created_at=now - last_used_ago - 1.0,
        last_used_at=now - last_used_ago,
    )
    pool._entries[name] = entry
    return entry


# ---------------------------------------------------------------------
# Sweeper start/stop lifecycle
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sweeper_start_stop_idempotent() -> None:
    pool = SessionPool()
    assert pool.sweeper_running is False

    await pool.start_sweeper(interval_seconds=0.05, max_idle_seconds=0.01)
    assert pool.sweeper_running is True
    assert pool.stats()["sweeper"]["running"] is True

    # Starting twice must surface the misuse, not silently drop.
    with pytest.raises(RuntimeError):
        await pool.start_sweeper(interval_seconds=0.05)

    stopped = await pool.stop_sweeper()
    assert stopped is True
    assert pool.sweeper_running is False
    assert pool.stats()["sweeper"]["running"] is False

    # stop on an already-stopped pool is a no-op returning False
    assert await pool.stop_sweeper() is False


@pytest.mark.asyncio
async def test_sweeper_rejects_invalid_intervals() -> None:
    pool = SessionPool()
    with pytest.raises(ValueError):
        await pool.start_sweeper(interval_seconds=0)
    with pytest.raises(ValueError):
        await pool.start_sweeper(interval_seconds=1.0, max_idle_seconds=-1.0)


@pytest.mark.asyncio
async def test_sweeper_evicts_idle_sessions() -> None:
    pool = SessionPool()
    pool._loop = asyncio.get_running_loop()
    fresh = _inject_entry(pool, "fresh", last_used_ago=0.001)
    stale = _inject_entry(pool, "stale", last_used_ago=10.0)

    await pool.start_sweeper(
        interval_seconds=0.05, max_idle_seconds=1.0
    )
    # Wait for the sweeper to make at least one pass. We poll on
    # the stale name disappearing rather than sleeping a fixed
    # number of seconds, because a fixed sleep makes the test
    # both slow AND flaky on busy CI runners.
    deadline = time.monotonic() + 3.0
    while "stale" in pool and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    await pool.stop_sweeper()

    assert "stale" not in pool, "sweeper failed to evict stale session"
    assert "fresh" in pool, "sweeper evicted a non-idle session"
    assert stale.transport._closed is True  # type: ignore[attr-defined]
    assert fresh.transport._closed is False  # type: ignore[attr-defined]

    stats = pool.stats()["sweeper"]
    assert stats["sessions_evicted_total"] >= 1
    assert stats["runs_total"] >= 1


@pytest.mark.asyncio
async def test_sweeper_continues_after_evict_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient evict_idle failure must NOT crash the sweeper.
    Operators rely on it running for the lifetime of the host."""

    pool = SessionPool()
    pool._loop = asyncio.get_running_loop()

    calls = {"n": 0}
    real_evict = pool.evict_idle

    async def _flaky_evict(*, max_idle_seconds: float = 300.0) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return await real_evict(max_idle_seconds=max_idle_seconds)

    monkeypatch.setattr(pool, "evict_idle", _flaky_evict)

    await pool.start_sweeper(interval_seconds=0.02, max_idle_seconds=0.01)
    deadline = time.monotonic() + 3.0
    while calls["n"] < 3 and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    await pool.stop_sweeper()

    assert calls["n"] >= 2, "sweeper stopped after the first failure"


@pytest.mark.asyncio
async def test_sweeper_stats_to_dict_shape() -> None:
    """Cockpit panel reads pool.stats()['sweeper']. Pin the shape."""

    pool = SessionPool()
    snapshot = pool.stats()["sweeper"]
    for key in (
        "running",
        "interval_seconds",
        "max_idle_seconds",
        "runs_total",
        "sessions_evicted_total",
        "last_run_evicted",
        "uptime_seconds",
        "seconds_since_last_run",
    ):
        assert key in snapshot, f"sweeper stats missing key {key!r}"
    assert snapshot["running"] is False


# ---------------------------------------------------------------------
# Per-server concurrency limit
# ---------------------------------------------------------------------


def _config(name: str, *, max_concurrency: int | None = None) -> ServerConfig:
    return ServerConfig(
        name=name,
        command="echo",
        args=("hello",),
        max_concurrency=max_concurrency,
    )


@pytest.mark.asyncio
async def test_concurrency_limit_serialises_calls() -> None:
    pool = SessionPool()
    config = _config("filesystem", max_concurrency=2)

    in_flight = 0
    peak = 0
    started = asyncio.Event()

    async def _job() -> None:
        nonlocal in_flight, peak
        async with pool.acquire_slot(config):
            in_flight += 1
            peak = max(peak, in_flight)
            started.set()
            await asyncio.sleep(0.05)
            in_flight -= 1

    await asyncio.gather(*(_job() for _ in range(6)))
    await started.wait()
    assert peak <= 2, f"semaphore failed to cap at 2 (peak was {peak})"


@pytest.mark.asyncio
async def test_concurrency_limit_default_none_means_no_cap() -> None:
    pool = SessionPool()
    config = _config("unbounded")

    in_flight = 0
    peak = 0

    async def _job() -> None:
        nonlocal in_flight, peak
        async with pool.acquire_slot(config):
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.02)
            in_flight -= 1

    await asyncio.gather(*(_job() for _ in range(8)))
    assert peak >= 4, (
        "without a cap, several jobs should have run truly "
        f"concurrently (peak was {peak})"
    )


@pytest.mark.asyncio
async def test_default_max_concurrency_applies_when_config_unspecified() -> None:
    pool = SessionPool(default_max_concurrency=3)
    config = _config("server")

    in_flight = 0
    peak = 0

    async def _job() -> None:
        nonlocal in_flight, peak
        async with pool.acquire_slot(config):
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.05)
            in_flight -= 1

    await asyncio.gather(*(_job() for _ in range(6)))
    assert peak <= 3, f"default cap not honoured (peak was {peak})"


@pytest.mark.asyncio
async def test_set_concurrency_limit_overrides_at_runtime() -> None:
    pool = SessionPool()
    config = _config("server")
    pool.set_concurrency_limit("server", 1)

    order: list[str] = []

    async def _job(label: str) -> None:
        async with pool.acquire_slot(config):
            order.append(f"start:{label}")
            await asyncio.sleep(0.02)
            order.append(f"end:{label}")

    await asyncio.gather(_job("a"), _job("b"))
    # With a cap of 1, the second job cannot start until the first
    # finishes — pin that contract.
    assert order in (
        ["start:a", "end:a", "start:b", "end:b"],
        ["start:b", "end:b", "start:a", "end:a"],
    ), f"cap=1 did not serialise: {order!r}"


@pytest.mark.asyncio
async def test_set_concurrency_limit_rejects_zero_and_negatives() -> None:
    pool = SessionPool()
    with pytest.raises(ValueError):
        pool.set_concurrency_limit("server", 0)
    with pytest.raises(ValueError):
        pool.set_concurrency_limit("server", -3)


@pytest.mark.asyncio
async def test_acquire_slot_increments_counters_even_without_entry() -> None:
    """Counters live on the entry when the session exists; before
    that they're absorbed by the no-op path. Cover both branches."""

    pool = SessionPool()
    config = _config("server", max_concurrency=2)

    # No entry yet — should not raise, just yield.
    async with pool.acquire_slot(config):
        pass

    pool._loop = asyncio.get_running_loop()
    entry = _inject_entry(pool, "server", last_used_ago=0.0)

    async with pool.acquire_slot(config):
        assert entry.in_flight == 1
        assert entry.inflight_peak == 1

    assert entry.in_flight == 0
    assert entry.calls_total == 1


# ---------------------------------------------------------------------
# ServerConfig parsing
# ---------------------------------------------------------------------


def test_server_config_parses_max_concurrency() -> None:
    cfg = ServerConfig.from_dict(
        "github",
        {
            "command": "uv",
            "args": ["run", "github-mcp"],
            "max_concurrency": 4,
        },
    )
    assert cfg.max_concurrency == 4
    assert "max_concurrency" in cfg.to_dict()


def test_server_config_omits_max_concurrency_when_unset() -> None:
    cfg = ServerConfig.from_dict(
        "fs", {"command": "node", "args": ["fs.js"]}
    )
    assert cfg.max_concurrency is None
    assert "max_concurrency" not in cfg.to_dict()


def test_server_config_rejects_invalid_max_concurrency() -> None:
    with pytest.raises(ValueError):
        ServerConfig.from_dict(
            "bad", {"command": "x", "max_concurrency": "many"}
        )
    with pytest.raises(ValueError):
        ServerConfig.from_dict("bad", {"command": "x", "max_concurrency": 0})
    with pytest.raises(ValueError):
        ServerConfig.from_dict("bad", {"command": "x", "max_concurrency": -1})
    with pytest.raises(ValueError):
        ServerConfig.from_dict("bad", {"command": "x", "max_concurrency": True})


# ---------------------------------------------------------------------
# PoolSweeperStats dataclass
# ---------------------------------------------------------------------


def test_pool_sweeper_stats_to_dict_handles_nones() -> None:
    snap = PoolSweeperStats().to_dict()
    assert snap["uptime_seconds"] is None
    assert snap["seconds_since_last_run"] is None
    assert snap["running"] is False


def test_pool_sweeper_stats_with_started_at_reports_uptime() -> None:
    s = PoolSweeperStats(started_at=time.monotonic() - 0.1, running=True)
    snap = s.to_dict()
    assert snap["uptime_seconds"] is not None
    assert snap["uptime_seconds"] >= 0.0
