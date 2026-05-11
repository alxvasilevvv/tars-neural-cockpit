"""Tests for ``SessionPool`` (Wave M6) and the pooled
handler path in ``BridgedPack``."""

from __future__ import annotations

import asyncio
import sys
import time

import pytest

from backend.core.mcp_bridge import (
    BridgedPack,
    SessionPool,
    aboot_mcp_bridges,
    get_default_pool,
    reset_default_pool,
    unregister_bridges,
)
from backend.core.mcp_bridge.cache import ToolCache
from backend.mcp.client.registry import ClientRegistry, ServerConfig


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


def _mock_config(name: str = "mock") -> ServerConfig:
    return ServerConfig(
        name=name,
        command=sys.executable,
        args=("-m", "tests.mcp_fixtures.mock_mcp_server"),
    )


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _reset_state():
    unregister_bridges()
    reset_default_pool()
    yield
    unregister_bridges()
    reset_default_pool()


# ---------------------------------------------------------------------
# SessionPool — basics
# ---------------------------------------------------------------------


def test_pool_get_or_create_returns_same_session_for_same_config() -> None:
    async def go():
        pool = SessionPool()
        s1 = await pool.get_or_create(_mock_config())
        s2 = await pool.get_or_create(_mock_config())
        try:
            assert s1 is s2
            assert "mock" in pool
            assert len(pool) == 1
        finally:
            await pool.close_all()
    _run(go())


def test_pool_separate_servers_get_separate_sessions() -> None:
    async def go():
        pool = SessionPool()
        s_a = await pool.get_or_create(_mock_config("a"))
        s_b = await pool.get_or_create(_mock_config("b"))
        try:
            assert s_a is not s_b
            assert len(pool) == 2
        finally:
            await pool.close_all()
    _run(go())


def test_pool_concurrent_get_or_create_returns_one_session() -> None:
    """Race two coroutines for the same server name. The lock
    must serialise construction so only one subprocess gets
    spawned."""

    async def go():
        pool = SessionPool()
        cfg = _mock_config()
        try:
            s_a, s_b = await asyncio.gather(
                pool.get_or_create(cfg), pool.get_or_create(cfg)
            )
            assert s_a is s_b
            assert len(pool) == 1
        finally:
            await pool.close_all()
    _run(go())


def test_pool_close_all_returns_count_then_idempotent() -> None:
    async def go():
        pool = SessionPool()
        await pool.get_or_create(_mock_config("a"))
        await pool.get_or_create(_mock_config("b"))
        assert await pool.close_all() == 2
        assert await pool.close_all() == 0
        assert len(pool) == 0
    _run(go())


def test_pool_evict_returns_false_when_missing() -> None:
    async def go():
        pool = SessionPool()
        assert await pool.evict("ghost") is False
    _run(go())


def test_pool_evict_after_get_drops_session() -> None:
    async def go():
        pool = SessionPool()
        await pool.get_or_create(_mock_config())
        try:
            assert await pool.evict("mock") is True
            assert "mock" not in pool
            assert len(pool) == 0
        finally:
            await pool.close_all()
    _run(go())


# ---------------------------------------------------------------------
# Idle eviction
# ---------------------------------------------------------------------


def test_pool_evict_idle_drops_only_old_sessions() -> None:
    async def go():
        pool = SessionPool()
        await pool.get_or_create(_mock_config("a"))
        await pool.get_or_create(_mock_config("b"))
        # Force `a` to look stale by rewriting its last_used.
        pool._entries["a"].last_used_at = time.monotonic() - 600.0
        try:
            evicted = await pool.evict_idle(max_idle_seconds=300.0)
            assert evicted == 1
            assert "a" not in pool
            assert "b" in pool
        finally:
            await pool.close_all()
    _run(go())


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------


def test_pool_stats_after_create() -> None:
    async def go():
        pool = SessionPool()
        await pool.get_or_create(_mock_config())
        try:
            stats = pool.stats()
            assert stats["count"] == 1
            row = stats["sessions"][0]
            assert row["name"] == "mock"
            assert row["server_info"]["name"] == "mock-mcp"
            assert row["tool_count"] == 2
            assert row["age_seconds"] >= 0
            assert row["idle_seconds"] >= 0
        finally:
            await pool.close_all()
    _run(go())


def test_pool_stats_empty() -> None:
    pool = SessionPool()
    stats = pool.stats()
    assert stats["count"] == 0
    assert stats["sessions"] == []
    # Wave M7 — sweeper + concurrency surfaces are always
    # present so the cockpit can render a stable shape.
    assert stats["sweeper"]["running"] is False
    assert stats["sweeper"]["runs_total"] == 0
    assert stats["default_max_concurrency"] is None


# ---------------------------------------------------------------------
# Cross-loop guard
# ---------------------------------------------------------------------


def test_pool_rejects_cross_loop_use() -> None:
    """A pool bound to loop A must refuse calls from loop B
    so we don't double-await the same StreamReader from two
    loops."""

    pool = SessionPool()

    _run(pool.get_or_create(_mock_config()))
    # Pool is now bound to the loop that just exited. Any new
    # asyncio.run() creates a different loop — calls must
    # raise.
    with pytest.raises(RuntimeError, match="event loop"):
        _run(pool.get_or_create(_mock_config()))

    # Cleanup — close in a new loop with a fresh pool object
    # so our parent test doesn't hang on a leaked subprocess.
    pool._loop = None
    _run(pool.close_all())


# ---------------------------------------------------------------------
# get_default_pool / reset_default_pool
# ---------------------------------------------------------------------


def test_get_default_pool_returns_singleton() -> None:
    p1 = get_default_pool()
    p2 = get_default_pool()
    assert p1 is p2


def test_reset_default_pool_drops_singleton() -> None:
    p1 = get_default_pool()
    reset_default_pool()
    p2 = get_default_pool()
    assert p1 is not p2


# ---------------------------------------------------------------------
# BridgedPack — pooled handler integration
# ---------------------------------------------------------------------


def test_bridged_pack_marks_pooled_when_pool_passed() -> None:
    pack_per_call = BridgedPack(
        _mock_config(),
        [{"name": "x", "description": "", "inputSchema": {}}],
    )
    pack_pooled = BridgedPack(
        _mock_config(),
        [{"name": "x", "description": "", "inputSchema": {}}],
        pool=SessionPool(),
    )
    assert pack_per_call.pooled is False
    assert pack_pooled.pooled is True


def test_pooled_handler_reuses_session_across_calls() -> None:
    """Run two handler calls back-to-back. Pool should still
    hold exactly one session (reuse, not respawn)."""

    async def go():
        pool = SessionPool()
        pack = BridgedPack(
            _mock_config(),
            [{"name": "echo", "description": "", "inputSchema": {}}],
            pool=pool,
        )
        handler = next(iter(pack.actions())).handler
        try:
            r1 = await handler({"value": "a"})
            r2 = await handler({"value": "b"})
            assert r1["ok"] is True
            assert r2["ok"] is True
            assert r1["echo"] == {"value": "a"}
            assert r2["echo"] == {"value": "b"}
            assert len(pool) == 1
        finally:
            await pool.close_all()
    _run(go())


def test_pooled_handler_recovers_after_session_eviction() -> None:
    """Manually evict the cached session between two calls;
    second call should transparently reconnect."""

    async def go():
        pool = SessionPool()
        pack = BridgedPack(
            _mock_config(),
            [{"name": "echo", "description": "", "inputSchema": {}}],
            pool=pool,
        )
        handler = next(iter(pack.actions())).handler
        try:
            r1 = await handler({"value": "first"})
            assert r1["ok"] is True
            await pool.evict("mock")
            r2 = await handler({"value": "second"})
            assert r2["ok"] is True
            assert r2["echo"] == {"value": "second"}
            assert len(pool) == 1
        finally:
            await pool.close_all()
    _run(go())


def test_pooled_handler_subprocess_failure_surfaces_envelope() -> None:
    async def go():
        pool = SessionPool()
        bad = ServerConfig(name="ghost", command="/no/such/binary-please")
        pack = BridgedPack(
            bad,
            [{"name": "x", "description": "", "inputSchema": {}}],
            pool=pool,
        )
        handler = next(iter(pack.actions())).handler
        try:
            result = await handler({})
            assert result["ok"] is False
            assert result["error"] == "mcp_bridge_call_failed"
        finally:
            await pool.close_all()
    _run(go())


# ---------------------------------------------------------------------
# aboot_mcp_bridges — async entry path
# ---------------------------------------------------------------------


def test_aboot_works_inside_running_loop(tmp_path) -> None:
    """The whole point of the async variant — must not raise
    'asyncio.run() cannot be called from a running event loop'."""

    async def go():
        reg = ClientRegistry(tmp_path / "servers.json")
        reg.add(_mock_config())
        cache = ToolCache(tmp_path / "cache")
        pool = SessionPool()
        try:
            result = await aboot_mcp_bridges(
                client_registry=reg, cache=cache, pool=pool
            )
            assert len(result.registered) == 1
            assert result.registered[0].pooled is True
            assert result.discovered == ("mock",)
        finally:
            await pool.close_all()

    _run(go())


def test_aboot_with_no_pool_falls_back_to_per_call(tmp_path) -> None:
    async def go():
        reg = ClientRegistry(tmp_path / "servers.json")
        reg.add(_mock_config())
        cache = ToolCache(tmp_path / "cache")
        result = await aboot_mcp_bridges(
            client_registry=reg, cache=cache, pool=None
        )
        assert len(result.registered) == 1
        assert result.registered[0].pooled is False

    _run(go())
