"""Tests for the periodic memory-purge background loop.

Mirrors the structure of ``tests/test_message_embed_loop.py`` and
``tests/test_saved_search_auto_poll.py``: env var helpers, single
tick semantics, and lifespan integration. The loop itself is small
on purpose — most of the heavy lifting is in
``MemoryStore.purge_expired``, which is already pinned by
``tests/test_memory_store.py``.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_memory_db(monkeypatch, tmp_path: Path):
    db = tmp_path / "memory.sqlite"
    monkeypatch.setenv("TARS_MEMORY_DB_PATH", str(db))
    monkeypatch.setenv("MEEET_STORE", "disabled")
    from backend.core.memory import store as memory_store_mod
    monkeypatch.setattr(memory_store_mod, "_SINGLETON", None, raising=False)
    yield
    monkeypatch.setattr(memory_store_mod, "_SINGLETON", None, raising=False)


# ---------------------------------------------------------------------
# Env helper
# ---------------------------------------------------------------------


def test_memory_purge_interval_default_is_off(monkeypatch):
    from web_extras.app import _memory_purge_interval_s

    monkeypatch.delenv("TARS_MEMORY_PURGE_INTERVAL_S", raising=False)
    assert _memory_purge_interval_s() == 0.0


def test_memory_purge_interval_parses_positive(monkeypatch):
    from web_extras.app import _memory_purge_interval_s

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "30")
    assert _memory_purge_interval_s() == 30.0


def test_memory_purge_interval_clamps_negative(monkeypatch):
    from web_extras.app import _memory_purge_interval_s

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "-5")
    assert _memory_purge_interval_s() == 0.0


def test_memory_purge_interval_garbage_falls_back_to_zero(monkeypatch):
    from web_extras.app import _memory_purge_interval_s

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "not-a-number")
    assert _memory_purge_interval_s() == 0.0


# ---------------------------------------------------------------------
# Loop short-circuits
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_returns_immediately_when_disabled(monkeypatch):
    from web_extras.app import _memory_purge_loop

    monkeypatch.delenv("TARS_MEMORY_PURGE_INTERVAL_S", raising=False)
    # Should return without sleeping or hanging.
    await asyncio.wait_for(_memory_purge_loop(), timeout=0.5)


@pytest.mark.asyncio
async def test_loop_returns_when_store_disabled(monkeypatch):
    from web_extras.app import _memory_purge_loop

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "1")
    monkeypatch.setenv("MEMORY_STORE", "disabled")
    from backend.core.memory import store as memory_store_mod
    monkeypatch.setattr(
        memory_store_mod, "_SINGLETON", None, raising=False
    )
    await asyncio.wait_for(_memory_purge_loop(), timeout=0.5)


# ---------------------------------------------------------------------
# Single-tick behaviour
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_purges_expired_rows_on_tick(monkeypatch):
    """One tick of the loop drops past-TTL rows. We patch
    ``asyncio.sleep`` so the test doesn't actually wait the
    configured interval, and cancel after the first tick.
    """

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "60")
    from backend.core.memory import get_memory_store

    store = get_memory_store()
    assert store.enabled

    # Seed an already-expired row + a live row.
    await store.upsert(
        pack_slug="test", key="expired", value=1, ttl_until=1.0,
    )
    await store.upsert(pack_slug="test", key="live", value=2)

    from web_extras import app as app_module

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        # First call: yield once so purge can run after; second call:
        # cancel so the loop exits cleanly.
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise asyncio.CancelledError()
        # Yield control briefly so the awaited purge gets to run.
        await asyncio.sleep(0)

    # Need the *real* asyncio.sleep for the inner ``await asyncio.sleep(0)``.
    # Patch only the first reference the loop sees.
    real_sleep = asyncio.sleep

    async def fake_sleep_v2(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise asyncio.CancelledError()
        await real_sleep(0)

    monkeypatch.setattr(app_module.asyncio, "sleep", fake_sleep_v2)

    with pytest.raises(asyncio.CancelledError):
        await app_module._memory_purge_loop()

    assert sleeps[0] == 60.0
    assert len(sleeps) == 2
    # Expired gone, live intact.
    listed = await store.list(pack_slug="test", include_expired=True)
    keys = {e.key for e in listed}
    assert keys == {"live"}


@pytest.mark.asyncio
async def test_loop_swallows_purge_failures(monkeypatch, caplog):
    """If the store raises on ``purge_expired`` the loop logs a
    warning and keeps ticking.
    """

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "5")
    from backend.core.memory import get_memory_store

    store = get_memory_store()
    assert store.enabled

    async def boom(*, pack_slug: str | None = None):  # noqa: ARG001
        raise RuntimeError("simulated sqlite error")

    monkeypatch.setattr(store, "purge_expired", boom)

    from web_extras import app as app_module

    ticks: list[int] = []
    cancel_after = 2

    async def fake_sleep(seconds: float) -> None:  # noqa: ARG001
        ticks.append(1)
        if len(ticks) >= cancel_after:
            raise asyncio.CancelledError()

    monkeypatch.setattr(app_module.asyncio, "sleep", fake_sleep)

    with caplog.at_level("WARNING", logger="tars.app"):
        with pytest.raises(asyncio.CancelledError):
            await app_module._memory_purge_loop()

    assert any("memory purge loop tick failed" in m for m in caplog.messages)
    assert len(ticks) == 2  # loop ticked twice despite the error


# ---------------------------------------------------------------------
# Lifespan integration
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_spawns_memory_purge_task(monkeypatch):
    """``_lifespan`` should create the memory-purge task alongside
    the other background loops, and cancel it cleanly on shutdown.
    """

    monkeypatch.setenv("TARS_MEMORY_PURGE_INTERVAL_S", "0")  # off, just check spawn

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

    assert "memory-purge-loop" in spawned
