"""Background trace-summary rebuild loop wiring.

The materialised ``trace_summary`` view is rebuilt on demand via
``POST /api/meeet/traces/refresh`` and from a periodic lifespan loop
(``TARS_TRACE_SUMMARY_INTERVAL_S``, default 300 s, ``0`` disables).
This module pins the loop's wiring so the rebuild fires automatically
in production and so future regressions can't silently swallow the
periodic refresh.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


# ---------------------------------------------------------------- env helper


def test_interval_helper_defaults_to_300(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_TRACE_SUMMARY_INTERVAL_S", raising=False)
    from web_extras.app import _trace_summary_interval_s

    assert _trace_summary_interval_s() == pytest.approx(300.0)


def test_interval_helper_parses_float(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "45")
    from web_extras.app import _trace_summary_interval_s

    assert _trace_summary_interval_s() == pytest.approx(45.0)


def test_interval_helper_clamps_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "-15")
    from web_extras.app import _trace_summary_interval_s

    assert _trace_summary_interval_s() == 0.0


def test_interval_helper_falls_back_to_default_on_garbage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "not-a-number")
    from web_extras.app import _trace_summary_interval_s

    # Garbage falls back to the default (300), not to 0 — stays consistent
    # with the rest of the env helper conventions in this module.
    assert _trace_summary_interval_s() == pytest.approx(300.0)


def test_interval_helper_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "0")
    from web_extras.app import _trace_summary_interval_s

    assert _trace_summary_interval_s() == 0.0


# ------------------------------------------------------------------ loop body


def test_loop_short_circuits_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interval ``0`` returns immediately, doesn't hang the runner."""

    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "0")
    from web_extras.app import _trace_summary_loop

    asyncio.run(asyncio.wait_for(_trace_summary_loop(), timeout=2.0))


def test_loop_short_circuits_when_store_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero interval still no-ops when the durable store is off."""

    monkeypatch.setenv("MEEET_STORE", "disabled")
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "noop.sqlite"))
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "0.05")

    from backend.core.meeet import reset_store, reset_trace_summary_store

    reset_store()
    reset_trace_summary_store()
    try:
        from web_extras.app import _trace_summary_loop

        # The loop returns as soon as it sees the disabled store; no tick.
        asyncio.run(asyncio.wait_for(_trace_summary_loop(), timeout=2.0))
    finally:
        reset_store()
        reset_trace_summary_store()


def test_loop_runs_one_tick_then_cancels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single tick walks the events table and writes the rollup row.

    Spin the loop with a tiny interval, insert events, wait for the
    rollup to materialise, then cancel cleanly.
    """

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_LOCAL_LOG", raising=False)
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "0.05")

    from backend.core.meeet import (
        get_store,
        get_trace_summary_store,
        reset_client,
        reset_store,
        reset_trace_summary_store,
    )

    reset_store()
    reset_client()
    reset_trace_summary_store()

    async def scenario() -> None:
        store = get_store()
        await store.insert(
            {
                "ts": 1_700_000_000.0,
                "trace_id": "trc_loop",
                "kind": "domain.action.invoked",
                "payload": {},
                "route": "edge",
                "session_id": "ses_loop",
            }
        )
        await store.insert(
            {
                "ts": 1_700_000_001.0,
                "trace_id": "trc_loop",
                "kind": "usage.tokens",
                "payload": {
                    "tokens_in": 30,
                    "tokens_out": 15,
                    "cost_usd": 0.0007,
                },
                "route": "edge",
                "session_id": "ses_loop",
            }
        )

        from web_extras.app import _trace_summary_loop

        summary_store = get_trace_summary_store()
        # Sanity: rollup is empty before the loop ticks.
        assert await summary_store.get("trc_loop") is None

        task = asyncio.create_task(_trace_summary_loop())
        try:
            for _ in range(40):
                await asyncio.sleep(0.05)
                summary = await summary_store.get("trc_loop")
                if summary is not None and summary.event_count >= 2:
                    break
            summary = await summary_store.get("trc_loop")
            assert summary is not None
            assert summary.event_count == 2
            assert summary.tokens_in == 30
            assert summary.tokens_out == 15
            assert summary.total_cost_usd == pytest.approx(0.0007, rel=1e-6)
            assert summary.last_session_id == "ses_loop"
            assert summary.primary_route == "edge"
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    try:
        asyncio.run(scenario())
    finally:
        reset_store()
        reset_client()
        reset_trace_summary_store()


def test_loop_keeps_ticking_after_internal_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a single rebuild raises, the loop logs and keeps ticking.

    The contract documented in the loop's docstring says
    ``never propagates exceptions`` — pin it so a future refactor
    can't reintroduce a crash that would cancel the lifespan task.
    """

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "0.05")

    from backend.core.meeet import (
        get_trace_summary_store,
        reset_client,
        reset_store,
        reset_trace_summary_store,
    )

    reset_store()
    reset_client()
    reset_trace_summary_store()

    summary_store = get_trace_summary_store()
    call_count = {"n": 0}

    async def boom_then_ok(**_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("synthetic rebuild failure")
        return {"ok": True, "scanned_events": 0, "traces": 0, "elapsed_ms": 0.1}

    monkeypatch.setattr(summary_store, "rebuild", boom_then_ok, raising=False)

    async def scenario() -> None:
        from web_extras.app import _trace_summary_loop

        task = asyncio.create_task(_trace_summary_loop())
        try:
            for _ in range(40):
                await asyncio.sleep(0.05)
                if call_count["n"] >= 2:
                    break
            assert call_count["n"] >= 2, (
                "loop must survive the first failure and tick again"
            )
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    try:
        asyncio.run(scenario())
    finally:
        reset_store()
        reset_client()
        reset_trace_summary_store()


# ----------------------------------------------------------------- lifespan


def test_lifespan_starts_and_cancels_trace_summary_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The FastAPI lifespan must spin the trace-summary loop alongside the
    other periodic tasks without crashing — TestClient explodes on
    startup error.
    """

    monkeypatch.setenv("TARS_TRACE_SUMMARY_INTERVAL_S", "0")  # disabled = no I/O

    from fastapi.testclient import TestClient

    from web_extras.app import app

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
