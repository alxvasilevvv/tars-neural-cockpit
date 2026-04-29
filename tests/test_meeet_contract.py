"""Contract tests for the meeet event schema.

These tests pin the on-the-wire shape: every event emitted through the
MeeetClient must carry the same top-level keys, and the durable store
must preserve session/route tagging end-to-end. If you intentionally
break the contract you also need to bump ``contract_version`` and
update this file in the same commit — that's the point.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.core.meeet import (
    MeeetClient,
    MeeetStore,
    TARSEvent,
    session_scope,
    set_route,
    start_trace,
    trace_scope,
)
from backend.core.meeet.config import MeeetConfig

CONTRACT_KEYS = {
    "trace_id",
    "kind",
    "source",
    "contract_version",
    "ts",
    "payload",
}
OPTIONAL_KEYS = {"session_id", "route"}


def _client(tmp_path: Path) -> tuple[MeeetClient, MeeetStore, Path]:
    log_path = tmp_path / "events.jsonl"
    cfg = MeeetConfig(
        ingest_url=None,
        contract_version="1.0.0",
        api_key=None,
        source="tars",
        local_log_path=str(log_path),
    )
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    return MeeetClient(cfg, store=store), store, log_path


def test_event_carries_required_keys() -> None:
    e = TARSEvent(trace_id="trc_x", kind="test.evt", payload={"a": 1})
    body = e.to_dict()
    assert CONTRACT_KEYS.issubset(body.keys())
    # Optional keys absent when not set — keeps payload minimal on the wire.
    assert not OPTIONAL_KEYS.intersection(body.keys())


def test_event_includes_session_and_route_when_set() -> None:
    e = TARSEvent(
        trace_id="trc_x",
        kind="test.evt",
        payload={},
        session_id="ses_y",
        route="cloud",
    )
    body = e.to_dict()
    assert body["session_id"] == "ses_y"
    assert body["route"] == "cloud"


def test_emitted_event_keys_match_contract(tmp_path: Path) -> None:
    client, _store, log_path = _client(tmp_path)

    async def run() -> dict:
        start_trace(parent="trc_test")
        return await client.emit("test.kind", {"x": 1})

    body = asyncio.run(run())
    assert CONTRACT_KEYS.issubset(body.keys())
    # Local jsonl must mirror the wire body verbatim (one line per event).
    line = log_path.read_text().strip()
    parsed = json.loads(line)
    assert CONTRACT_KEYS.issubset(parsed.keys())
    assert parsed["kind"] == "test.kind"


def test_session_scope_propagates_to_event(tmp_path: Path) -> None:
    client, store, _ = _client(tmp_path)

    async def run() -> None:
        with session_scope("ses_alpha"):
            with trace_scope(parent="trc_a", route="edge"):
                await client.emit("a.evt", {})
            with trace_scope(parent="trc_b"):
                set_route("cloud")
                await client.emit("b.evt", {})

    asyncio.run(run())
    events = asyncio.run(store.list_events(limit=10))
    by_kind = {e.kind: e for e in events}
    assert by_kind["a.evt"].session_id == "ses_alpha"
    assert by_kind["a.evt"].route == "edge"
    assert by_kind["b.evt"].session_id == "ses_alpha"
    assert by_kind["b.evt"].route == "cloud"


def test_replay_body_preserves_session_and_route(tmp_path: Path) -> None:
    """Replay must not drop the K1 dimensions."""

    cfg = MeeetConfig(
        ingest_url="https://example.invalid/meeet",
        contract_version="1.0.0",
        api_key=None,
        source="tars",
        local_log_path=None,
    )
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    seen: list[dict] = []

    async def fake_push(body):
        seen.append(body)

    async def run():
        await store.insert(
            {
                "kind": "x.evt",
                "trace_id": "trc",
                "ts": 1.0,
                "payload": {},
                "source": "tars",
                "contract_version": "1.0.0",
                "session_id": "ses_1",
                "route": "fallback",
            }
        )
        await store.replay_unpushed(fake_push)

    asyncio.run(run())
    assert seen, "replay should have pushed the buffered event"
    assert seen[0]["session_id"] == "ses_1"
    assert seen[0]["route"] == "fallback"


def test_session_id_filter_on_list_events(tmp_path: Path) -> None:
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))

    async def run() -> None:
        for sid, kind in [
            ("ses_1", "a"),
            ("ses_1", "b"),
            ("ses_2", "c"),
        ]:
            await store.insert(
                {
                    "kind": kind,
                    "trace_id": "trc",
                    "ts": 1.0,
                    "payload": {},
                    "source": "tars",
                    "contract_version": "1.0.0",
                    "session_id": sid,
                }
            )
        only_one = await store.list_events(session_id="ses_1")
        assert {e.kind for e in only_one} == {"a", "b"}

    asyncio.run(run())
