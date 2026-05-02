"""Tests for the SQLite durable buffer + replay flow."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.meeet import (
    MeeetClient,
    MeeetStore,
    start_trace,
)
from backend.core.meeet.config import MeeetConfig


def _store_at(tmp_path: Path) -> MeeetStore:
    return MeeetStore(str(tmp_path / "meeet.sqlite"))


def test_store_inserts_and_lists(tmp_path: Path) -> None:
    store = _store_at(tmp_path)

    async def run() -> None:
        eid = await store.insert(
            {
                "trace_id": "trc_a",
                "kind": "test.event",
                "source": "tars",
                "contract_version": "1.0.0",
                "ts": 1000.0,
                "payload": {"hi": 1},
            }
        )
        assert eid is not None and eid > 0
        events = await store.list_events()
        assert len(events) == 1
        assert events[0].kind == "test.event"
        assert events[0].pushed is False

    asyncio.run(run())


def test_disabled_store_is_noop(tmp_path: Path) -> None:
    store = MeeetStore(str(tmp_path / "x.sqlite"), enabled=False)

    async def run() -> None:
        eid = await store.insert({"kind": "x", "ts": 0.0, "payload": {}})
        assert eid is None
        events = await store.list_events()
        assert events == []
        stats = await store.stats()
        assert stats == {"enabled": False}

    asyncio.run(run())


def test_store_filters_by_kind_and_trace(tmp_path: Path) -> None:
    store = _store_at(tmp_path)

    async def run() -> None:
        await store.insert(
            {"kind": "alpha", "trace_id": "trc_x", "ts": 1.0, "payload": {}}
        )
        await store.insert(
            {"kind": "beta", "trace_id": "trc_x", "ts": 2.0, "payload": {}}
        )
        await store.insert(
            {"kind": "alpha", "trace_id": "trc_y", "ts": 3.0, "payload": {}}
        )
        only_alpha = await store.list_events(kind="alpha")
        assert {e.trace_id for e in only_alpha} == {"trc_x", "trc_y"}
        only_x = await store.list_events(trace_id="trc_x")
        assert {e.kind for e in only_x} == {"alpha", "beta"}

    asyncio.run(run())


def test_client_emit_inserts_into_store_when_disabled(tmp_path: Path) -> None:
    cfg = MeeetConfig(
        ingest_url=None,
        contract_version="1.0.0",
        api_key=None,
        source="tars",
        local_log_path=None,
    )
    store = _store_at(tmp_path)
    client = MeeetClient(cfg, store=store)

    async def run() -> dict:
        start_trace(parent="trc_emit")
        await client.emit("domain.action.invoked", {"slug": "traders"})
        events = await store.list_events()
        assert len(events) == 1
        assert events[0].kind == "domain.action.invoked"
        assert events[0].trace_id == "trc_emit"
        # Disabled ingest → row stays unpushed.
        assert events[0].pushed is False
        return await store.stats()

    stats = asyncio.run(run())
    assert stats["unpushed"] == 1


def test_replay_unpushed_pushes_in_order(tmp_path: Path) -> None:
    cfg = MeeetConfig(
        ingest_url="https://example.invalid/meeet",
        contract_version="1.0.0",
        api_key=None,
        source="tars",
        local_log_path=None,
    )
    store = _store_at(tmp_path)
    pushed_kinds: list[str] = []

    async def fake_push(body):
        pushed_kinds.append(body["kind"])

    async def run():
        # Pre-seed three unpushed events.
        for k, ts in [("a.evt", 1.0), ("b.evt", 2.0), ("c.evt", 3.0)]:
            await store.insert(
                {"kind": k, "trace_id": "trc", "ts": ts, "payload": {}, "source": "tars", "contract_version": "1.0.0"}
            )
        # Pretend ingest is reachable: drive replay via the store directly.
        result = await store.replay_unpushed(fake_push, limit=10)
        assert result["pushed"] == 3
        assert result["failed"] == 0
        # Oldest → newest.
        assert pushed_kinds == ["a.evt", "b.evt", "c.evt"]
        # All marked pushed now.
        events = await store.list_events()
        assert all(e.pushed for e in events)

    asyncio.run(run())


def test_replay_records_failures(tmp_path: Path) -> None:
    store = _store_at(tmp_path)

    async def fake_push(body):
        raise RuntimeError("ingest down")

    async def run():
        await store.insert(
            {"kind": "x.evt", "trace_id": "trc", "ts": 1.0, "payload": {}, "source": "tars", "contract_version": "1.0.0"}
        )
        result = await store.replay_unpushed(fake_push)
        assert result["failed"] == 1
        assert result["pushed"] == 0
        events = await store.list_events()
        assert events[0].pushed is False
        assert events[0].last_error == "ingest down"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# repush_trace — force-push every event for one trace
# ---------------------------------------------------------------------------


def test_repush_trace_pushes_all_matching_rows_regardless_of_pushed_flag(
    tmp_path: Path,
) -> None:
    """``repush_trace`` ignores the ``pushed`` flag and pushes every
    event whose ``trace_id`` matches. Use case: meeet ingest
    contract bump — we already pushed the rows once, but the
    upstream needs them re-emitted under the new contract.
    """

    store = _store_at(tmp_path)
    pushed_bodies: list[dict] = []

    async def fake_push(body):
        pushed_bodies.append(body)

    async def run():
        # Two events on the target trace + one decoy on another trace.
        await store.insert(
            {
                "kind": "plan.run.started",
                "trace_id": "trc_target",
                "ts": 1.0,
                "payload": {"plan_id": "pln_x"},
                "source": "tars",
                "contract_version": "1.0.0",
            }
        )
        await store.insert(
            {
                "kind": "plan.run.completed",
                "trace_id": "trc_target",
                "ts": 2.0,
                "payload": {"plan_id": "pln_x"},
                "source": "tars",
                "contract_version": "1.0.0",
            }
        )
        await store.insert(
            {
                "kind": "plan.run.started",
                "trace_id": "trc_decoy",
                "ts": 3.0,
                "payload": {},
                "source": "tars",
                "contract_version": "1.0.0",
            }
        )
        # Pre-mark all rows as pushed so we exercise the
        # "force regardless of pushed flag" branch.
        all_events = await store.list_events()
        for ev in all_events:
            await store.mark_pushed(ev.id)

        result = await store.repush_trace(
            fake_push, trace_id="trc_target", limit=10
        )
        assert result["enabled"] is True
        assert result["trace_id"] == "trc_target"
        assert result["pushed"] == 2, "both target rows must re-emit"
        assert result["failed"] == 0
        # Decoy row was NOT re-pushed.
        assert all(b["trace_id"] == "trc_target" for b in pushed_bodies)
        # Oldest-first ordering preserved (same as replay_unpushed).
        assert [b["kind"] for b in pushed_bodies] == [
            "plan.run.started",
            "plan.run.completed",
        ]

    asyncio.run(run())


def test_repush_trace_with_no_match_returns_zero_counts(
    tmp_path: Path,
) -> None:
    """Unknown trace ⇒ pushed=0, failed=0, no rows touched. The
    operator's CLI should treat this as a clean "nothing to do"
    not an error.
    """

    store = _store_at(tmp_path)
    pushed_bodies: list[dict] = []

    async def fake_push(body):
        pushed_bodies.append(body)

    async def run():
        await store.insert(
            {
                "kind": "x.evt",
                "trace_id": "trc_known",
                "ts": 1.0,
                "payload": {},
                "source": "tars",
                "contract_version": "1.0.0",
            }
        )
        result = await store.repush_trace(
            fake_push, trace_id="trc_unknown", limit=10
        )
        assert result["pushed"] == 0
        assert result["failed"] == 0
        assert result["scanned"] == 0
        assert pushed_bodies == []

    asyncio.run(run())


def test_repush_trace_records_failures_without_clearing_pushed_flag(
    tmp_path: Path,
) -> None:
    """When the upstream is down during a repush, the event row's
    ``pushed`` flag must NOT be flipped to 0 (it was 1 before the
    repush; flipping it would let it leak into the next
    ``replay_unpushed`` flush, double-pushing it once the upstream
    recovers). Only ``last_error`` should change.
    """

    store = _store_at(tmp_path)

    async def boom_push(body):
        raise RuntimeError("ingest down")

    async def run():
        eid = await store.insert(
            {
                "kind": "plan.completed",
                "trace_id": "trc_repush",
                "ts": 5.0,
                "payload": {},
                "source": "tars",
                "contract_version": "1.0.0",
            }
        )
        # Pre-mark as pushed (the "this row was already shipped"
        # state that matters for the contract).
        await store.mark_pushed(eid or 0)
        events_before = await store.list_events(trace_id="trc_repush")
        assert events_before[0].pushed is True

        result = await store.repush_trace(
            boom_push, trace_id="trc_repush", limit=5
        )
        assert result["pushed"] == 0
        assert result["failed"] == 1

        events_after = await store.list_events(trace_id="trc_repush")
        # pushed flag stays True (we DON'T regress it on repush failure)
        assert events_after[0].pushed is True, (
            "repush failure must not clear the pushed flag — "
            "otherwise the row would leak into the next "
            "replay_unpushed and double-push once ingest recovers"
        )
        assert events_after[0].last_error == "ingest down"

    asyncio.run(run())


def test_repush_trace_disabled_store_returns_disabled_envelope(
    tmp_path: Path,
) -> None:
    store = MeeetStore(str(tmp_path / "disabled.sqlite"), enabled=False)

    async def fake_push(body):  # pragma: no cover - never called
        raise AssertionError("must not be invoked when store disabled")

    async def run():
        out = await store.repush_trace(fake_push, trace_id="trc_x")
        assert out == {
            "enabled": False,
            "trace_id": "trc_x",
            "pushed": 0,
            "failed": 0,
            "remaining": 0,
        }

    asyncio.run(run())


def test_repush_trace_rejects_empty_trace_id(tmp_path: Path) -> None:
    """An empty / falsy ``trace_id`` is a guard-rail violation —
    otherwise the underlying ``list_events(trace_id="")`` would
    silently return zero rows (so the "matched nothing" branch
    fires) and the operator wouldn't notice they typed it wrong.
    The error envelope makes the misuse loud.
    """

    store = _store_at(tmp_path)

    async def fake_push(body):  # pragma: no cover - never called
        raise AssertionError("push must not run with empty trace_id")

    async def run():
        out = await store.repush_trace(fake_push, trace_id="")
        assert out["enabled"] is True
        assert out["error"] == "trace_id_required"
        assert out["pushed"] == 0
        assert out["failed"] == 0

    asyncio.run(run())
