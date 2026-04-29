"""Phase L5 — meeet contract 1.0.0 ↔ 1.1.0 round-trip tests.

The contract is **strictly additive** at 1.1.0:

- A 1.0.0 event is one *without* ``ciphertext`` + ``envelope``. Wire shape
  is identical to before; ``contract_version`` stays ``1.0.0``.
- A 1.1.0 event is one *with* both fields. ``contract_version`` auto-bumps
  to ``1.1.0`` regardless of the configured baseline.

These tests pin both flows so a future agent can drop in real crypto
without breaking older consumers.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from backend.core.meeet import (
    BASELINE_CONTRACT_VERSION,
    ENCRYPTED_CONTRACT_VERSION,
    MeeetConfig,
    MeeetStore,
    TARSEvent,
)
from backend.core.meeet.client import MeeetClient


# ---------------------------------------------------------------------
# TARSEvent shape
# ---------------------------------------------------------------------


def test_tars_event_baseline_does_not_carry_encryption_fields() -> None:
    e = TARSEvent(trace_id="trc_x", kind="test.evt", payload={"a": 1})
    body = e.to_dict()
    assert body["contract_version"] == BASELINE_CONTRACT_VERSION
    assert "ciphertext" not in body
    assert "envelope" not in body
    assert e.is_encrypted is False


def test_tars_event_with_envelope_bumps_contract_to_1_1_0() -> None:
    envelope = {
        "scheme": "xchacha20-poly1305-x25519-v1",
        "nonce": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "epk": "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "recipient_keys": [
            {"device_id": "dev_a", "wrapped_key": "CCCCCCCCCCCCCCCC"}
        ],
    }
    e = TARSEvent(
        trace_id="trc_x",
        kind="chat.message.completed",
        payload={},  # empty — real data is sealed in ciphertext
        ciphertext="zzzzzzzzzzzzzzzzzzzzzzzz",
        envelope=envelope,
    )
    body = e.to_dict()
    assert body["contract_version"] == ENCRYPTED_CONTRACT_VERSION
    assert body["ciphertext"] == "zzzzzzzzzzzzzzzzzzzzzzzz"
    assert body["envelope"]["scheme"].startswith("xchacha20")
    assert e.is_encrypted is True


def test_tars_event_envelope_alone_does_not_bump_contract() -> None:
    e = TARSEvent(
        trace_id="trc_x",
        kind="test.evt",
        envelope={"scheme": "no-cipher"},
    )
    assert e.is_encrypted is False
    assert e.to_dict()["contract_version"] == BASELINE_CONTRACT_VERSION
    assert "ciphertext" not in e.to_dict()


def test_tars_event_ciphertext_alone_does_not_bump_contract() -> None:
    e = TARSEvent(
        trace_id="trc_x",
        kind="test.evt",
        ciphertext="zzz",
    )
    assert e.is_encrypted is False
    assert e.to_dict()["contract_version"] == BASELINE_CONTRACT_VERSION
    assert "envelope" not in e.to_dict()


# ---------------------------------------------------------------------
# Store round-trip
# ---------------------------------------------------------------------


def test_store_round_trips_encryption_fields(tmp_path: Path) -> None:
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))

    event = {
        "kind": "chat.message.completed",
        "trace_id": "trc_round_trip",
        "ts": 1.0,
        "payload": {},
        "source": "tars",
        "contract_version": ENCRYPTED_CONTRACT_VERSION,
        "session_id": "ses_a",
        "route": "edge",
        "ciphertext": "deadbeef" * 4,
        "envelope": {
            "scheme": "xchacha20-poly1305-x25519-v1",
            "nonce": "n" * 32,
            "epk": "e" * 32,
            "recipient_keys": [{"device_id": "dev_a", "wrapped_key": "w" * 16}],
        },
    }
    asyncio.run(store.insert(event))
    rows = asyncio.run(store.list_events(limit=10, kind="chat.message.completed"))
    assert len(rows) == 1
    row = rows[0]
    assert row.contract_version == ENCRYPTED_CONTRACT_VERSION
    assert row.ciphertext == event["ciphertext"]
    assert row.envelope == event["envelope"]
    assert row.session_id == "ses_a"
    assert row.route == "edge"


def test_store_replay_preserves_envelope(tmp_path: Path) -> None:
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    seen: list[dict] = []

    async def push(body: dict) -> None:
        seen.append(body)

    async def run() -> None:
        await store.insert(
            {
                "kind": "chat.message.completed",
                "trace_id": "trc",
                "ts": 1.0,
                "payload": {},
                "source": "tars",
                "contract_version": ENCRYPTED_CONTRACT_VERSION,
                "ciphertext": "ZZZZ",
                "envelope": {"scheme": "xchacha20-poly1305-x25519-v1"},
            }
        )
        await store.replay_unpushed(push)

    asyncio.run(run())
    assert seen[0]["ciphertext"] == "ZZZZ"
    assert seen[0]["envelope"]["scheme"].startswith("xchacha20")
    assert seen[0]["contract_version"] == ENCRYPTED_CONTRACT_VERSION


def test_store_keeps_legacy_events_untouched(tmp_path: Path) -> None:
    """A 1.0.0 event MUST not gain the new fields after a store round-trip."""

    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    asyncio.run(
        store.insert(
            {
                "kind": "chat.message.completed",
                "trace_id": "trc",
                "ts": 1.0,
                "payload": {"text": "hello"},
                "source": "tars",
                "contract_version": BASELINE_CONTRACT_VERSION,
            }
        )
    )
    rows = asyncio.run(store.list_events(limit=10))
    assert rows[0].ciphertext is None
    assert rows[0].envelope is None
    assert rows[0].payload == {"text": "hello"}


# ---------------------------------------------------------------------
# Client emit
# ---------------------------------------------------------------------


def test_client_emit_with_envelope_bumps_contract_on_wire(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    cfg = MeeetConfig(
        ingest_url=None,
        contract_version=BASELINE_CONTRACT_VERSION,
        api_key=None,
        source="tars",
        local_log_path=str(log_path),
    )
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    client = MeeetClient(cfg, store=store)

    async def run() -> dict:
        return await client.emit(
            "chat.message.completed",
            payload={},
            ciphertext="abc",
            envelope={"scheme": "xchacha20-poly1305-x25519-v1"},
        )

    body = asyncio.run(run())
    assert body["contract_version"] == ENCRYPTED_CONTRACT_VERSION
    assert body["ciphertext"] == "abc"
    assert body["envelope"]["scheme"].startswith("xchacha20")

    # Mirrored to local-log + SQLite store too.
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["contract_version"] == ENCRYPTED_CONTRACT_VERSION
    assert parsed["ciphertext"] == "abc"


def test_client_emit_without_envelope_stays_1_0_0(tmp_path: Path) -> None:
    cfg = MeeetConfig(
        ingest_url=None,
        contract_version=BASELINE_CONTRACT_VERSION,
        api_key=None,
        source="tars",
        local_log_path=None,
    )
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    client = MeeetClient(cfg, store=store)

    body = asyncio.run(client.emit("chat.message.completed", payload={"text": "x"}))
    assert body["contract_version"] == BASELINE_CONTRACT_VERSION
    assert "ciphertext" not in body
    assert "envelope" not in body
