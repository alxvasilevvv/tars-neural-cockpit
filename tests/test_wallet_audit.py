"""Wallet audit log contract tests (Phase O4).

Verifies that:

- By default (``TARS_AUDIT_RAW_TX`` unset), ``wallet.*_signed`` Meeet
  events do NOT carry the raw broadcastable bytes — only the
  metadata (tx_signature / hash / body_hash). Privacy-by-default.
- With ``TARS_AUDIT_RAW_TX=1``, raw fields are attached to the same
  events.
- ``POST /api/wallet/audit/prune`` drops events older than the
  retention window.
- ``enrich_signed_event`` is purely additive (never strips base
  fields, never raises on missing raw fields).
- ``retention_seconds`` honours the ``TARS_AUDIT_RETENTION_DAYS``
  env variable.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.meeet import get_store as get_meeet_store
from backend.core.wallet import reset_wallet_service_for_tests
from backend.core.wallet.audit import (
    enrich_signed_event,
    is_enabled,
    prune_signed_events,
    retention_seconds,
)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_audit_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("TARS_CHAT_STORE", "disabled")
    monkeypatch.delenv("TARS_AUDIT_RAW_TX", raising=False)
    monkeypatch.delenv("TARS_AUDIT_RETENTION_DAYS", raising=False)
    reset_wallet_service_for_tests()
    reset_meeet_store()
    reset_meeet_client()
    yield


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


# ---------- module-level behaviour -------------------------------------


def test_is_enabled_reads_env(monkeypatch) -> None:
    assert is_enabled() is False
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    assert is_enabled() is True
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "yes")
    assert is_enabled() is True
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "0")
    assert is_enabled() is False


def test_retention_seconds_default_30_days() -> None:
    assert retention_seconds() == 30 * 24 * 60 * 60


def test_retention_seconds_honours_env(monkeypatch) -> None:
    monkeypatch.setenv("TARS_AUDIT_RETENTION_DAYS", "7")
    assert retention_seconds() == 7 * 24 * 60 * 60


def test_retention_seconds_falls_back_on_garbage(monkeypatch) -> None:
    monkeypatch.setenv("TARS_AUDIT_RETENTION_DAYS", "definitely-not-a-number")
    assert retention_seconds() == 30 * 24 * 60 * 60


def test_enrich_disabled_strips_raw_fields() -> None:
    out = enrich_signed_event(
        base={"wallet_id": "w", "tx_signature": "sig"},
        signed={"raw_b64": "AAAA", "tx_signature": "sig"},
    )
    assert out["wallet_id"] == "w"
    assert out["tx_signature"] == "sig"
    assert "raw_b64" not in out
    assert out["audit_raw_attached"] is False


def test_enrich_enabled_attaches_raw_fields(monkeypatch) -> None:
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    out = enrich_signed_event(
        base={"wallet_id": "w"},
        signed={"raw_b64": "ZZZZ", "raw_hex": "0xff", "boc": "AAA"},
    )
    assert out["raw_b64"] == "ZZZZ"
    assert out["raw_hex"] == "0xff"
    assert out["boc"] == "AAA"
    assert out["audit_raw_attached"] is True


def test_enrich_respects_raw_keys_filter(monkeypatch) -> None:
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    out = enrich_signed_event(
        base={"wallet_id": "w"},
        signed={"raw": "0x1234", "hash": "0xabcd", "secret": "leaked!"},
        raw_keys=("raw", "hash"),
    )
    assert out["raw"] == "0x1234"
    assert "secret" not in out


# ---------- HTTP integration: privacy-by-default -----------------------


def test_evm_signed_event_does_not_leak_raw_by_default(
    client: TestClient,
) -> None:
    create = client.post("/api/wallet", json={"label": "evm", "chain": "evm"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json={
            "to": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            "value": "1000000000000000000",
            "gas": "21000",
            "nonce": "0",
            "chainId": 1,
            "maxFeePerGas": "30000000000",
            "maxPriorityFeePerGas": "1000000000",
            "type": 2,
        },
    )
    assert r.status_code == 200
    # Response itself still has the raw — the operator just signed
    # it, they obviously want to see it.
    assert "raw" in r.json()["signed"]
    # But the meeet event for this wallet must NOT carry the raw.
    store = get_meeet_store()
    events = asyncio.run(store.list_events(kind="wallet.evm_tx_signed"))
    assert events
    payload = events[0].payload
    assert payload["audit_raw_attached"] is False
    assert "raw" not in payload


def test_evm_signed_event_attaches_raw_when_audit_on(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    create = client.post("/api/wallet", json={"label": "evm", "chain": "evm"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json={
            "to": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            "value": "1000000000000000000",
            "gas": "21000",
            "nonce": "0",
            "chainId": 1,
            "maxFeePerGas": "30000000000",
            "maxPriorityFeePerGas": "1000000000",
            "type": 2,
        },
    )
    assert r.status_code == 200
    store = get_meeet_store()
    events = asyncio.run(store.list_events(kind="wallet.evm_tx_signed"))
    assert events
    payload = events[0].payload
    assert payload["audit_raw_attached"] is True
    assert payload["raw"]
    assert payload["hash"]


def test_solana_signed_event_attaches_raw_when_audit_on(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    create = client.post(
        "/api/wallet", json={"label": "sol", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_solana_transfer",
        json={
            "to": "11111111111111111111111111111112",
            "amount": "0.1",
            "recent_blockhash": "11111111111111111111111111111111",
        },
    )
    assert r.status_code == 200
    store = get_meeet_store()
    events = asyncio.run(store.list_events(kind="wallet.solana_transfer_signed"))
    assert events
    p = events[0].payload
    assert p["audit_raw_attached"] is True
    assert p["raw_b64"]
    assert p["raw_hex"].startswith("0x")


def test_ton_signed_event_attaches_boc_when_audit_on(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    create = client.post("/api/wallet", json={"label": "ton", "chain": "ton"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_ton_transfer",
        json={
            "to": "EQDk-73OzZiv_ffXAbZVEGZOcjbIwBA-6CzHu9U46xUjmnZY",
            "amount": "0.1",
            "seqno": 0,
        },
    )
    assert r.status_code == 200
    store = get_meeet_store()
    events = asyncio.run(store.list_events(kind="wallet.ton_transfer_signed"))
    assert events
    p = events[0].payload
    assert p["audit_raw_attached"] is True
    assert p["boc"]
    assert p["body_hash"].startswith("0x")


# ---------- prune endpoint --------------------------------------------


def test_audit_prune_drops_old_events(monkeypatch, client: TestClient) -> None:
    """Manually insert an old wallet.*_signed event and prune."""
    monkeypatch.setenv("TARS_AUDIT_RETENTION_DAYS", "1")
    store = get_meeet_store()
    # Inject an event with a timestamp older than the retention window.
    import sqlite3

    conn = sqlite3.connect(store.db_path)
    old_ts = time.time() - (3 * 24 * 60 * 60)  # 3 days ago, > 1-day window
    conn.execute(
        "INSERT INTO events (ts, trace_id, kind, source, contract_version, "
        "payload) VALUES (?, ?, ?, ?, ?, ?)",
        (old_ts, "trace_old", "wallet.evm_tx_signed", "tars", "1.0.0", "{}"),
    )
    conn.commit()
    conn.close()

    r = client.post("/api/wallet/audit/prune")
    assert r.status_code == 200, r.text
    assert r.json()["pruned"] >= 1


def test_audit_prune_leaves_recent_events(
    monkeypatch, client: TestClient
) -> None:
    """Recent events stay even when prune is called."""
    monkeypatch.setenv("TARS_AUDIT_RETENTION_DAYS", "30")
    monkeypatch.setenv("TARS_AUDIT_RAW_TX", "1")
    create = client.post("/api/wallet", json={"label": "evm", "chain": "evm"}).json()
    wid = create["wallet"]["id"]
    client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json={
            "to": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            "value": "0",
            "gas": "21000",
            "nonce": "0",
            "chainId": 1,
            "maxFeePerGas": "1",
            "maxPriorityFeePerGas": "1",
        },
    )
    r = client.post("/api/wallet/audit/prune")
    assert r.status_code == 200
    # Should have pruned 0 (the event we just emitted is far younger
    # than 30 days).
    assert r.json()["pruned"] == 0


def test_prune_signed_events_no_op_when_store_disabled(
    monkeypatch,
) -> None:
    """Direct module call should be safe when meeet store is off."""
    monkeypatch.setenv("MEEET_STORE", "disabled")
    reset_meeet_store()
    out = asyncio.run(prune_signed_events())
    assert out == 0
