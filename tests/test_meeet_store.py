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
