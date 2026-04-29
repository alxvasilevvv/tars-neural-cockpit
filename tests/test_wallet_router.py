"""HTTP contract for /api/wallet/*."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.meeet import get_store as get_meeet_store
from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.wallet import reset_wallet_service_for_tests


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_wallet_router_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("TARS_CHAT_STORE", "disabled")
    reset_wallet_service_for_tests()
    reset_meeet_store()
    reset_meeet_client()
    yield
    reset_wallet_service_for_tests()
    reset_meeet_store()
    reset_meeet_client()


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


def test_create_wallet_returns_mnemonic_once(client: TestClient) -> None:
    r = client.post(
        "/api/wallet", json={"label": "primary", "chain": "solana"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mnemonic"]
    assert len(body["mnemonic"].split()) == 24
    assert "wallet" in body
    assert body["wallet"]["chain"] == "solana"


def test_get_wallet_does_not_return_mnemonic(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "primary", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.get(f"/api/wallet/{wid}").json()
    assert "mnemonic" not in r
    assert r["wallet"]["id"] == wid


def test_list_filters_by_chain(client: TestClient) -> None:
    client.post("/api/wallet", json={"label": "s", "chain": "solana"})
    client.post("/api/wallet", json={"label": "e", "chain": "evm"})
    listed = client.get("/api/wallet?chain=solana").json()
    assert listed["count"] == 1
    assert listed["wallets"][0]["chain"] == "solana"


def test_import_wallet_round_trips(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "src", "chain": "solana"}
    ).json()
    mnemonic = create["mnemonic"]
    addr = create["wallet"]["address"]
    imported = client.post(
        "/api/wallet/import",
        json={"label": "dst", "chain": "solana", "mnemonic": mnemonic},
    ).json()
    assert imported["wallet"]["address"] == addr


def test_sign_round_trip(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "x", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(f"/api/wallet/{wid}/sign", json={"message": "hi"})
    assert r.status_code == 200
    assert r.json()["signature_b64"]


def test_sign_ton_round_trips(client: TestClient) -> None:
    """TON personal_sign works end-to-end (Phase N4)."""
    create = client.post(
        "/api/wallet", json={"label": "ton", "chain": "ton"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(f"/api/wallet/{wid}/sign", json={"message": "hi"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["signature_b64"]


def test_sign_evm_round_trips(client: TestClient) -> None:
    """EVM personal_sign now works end-to-end via eth-account."""
    create = client.post(
        "/api/wallet", json={"label": "evm", "chain": "evm"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(f"/api/wallet/{wid}/sign", json={"message": "hi"})
    assert r.status_code == 200, r.text
    assert r.json()["signature_b64"]


def test_build_send_envelope(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "x", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/build_send",
        json={"to": "Sendr111…", "amount": "0.1"},
    ).json()
    assert r["envelope"]["chain"] == "solana"
    assert r["envelope"]["signing_supported"] is True


def test_delete_removes_wallet(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "x", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.delete(f"/api/wallet/{wid}")
    assert r.status_code == 200
    again = client.get(f"/api/wallet/{wid}")
    assert again.status_code == 404


def test_meeet_event_emitted_on_create(client: TestClient) -> None:
    import asyncio

    client.post("/api/wallet", json={"label": "x", "chain": "solana"})
    events = asyncio.run(get_meeet_store().list_events(limit=20))
    kinds = [e.kind for e in events]
    assert "wallet.created" in kinds


def test_create_rejects_unknown_chain(client: TestClient) -> None:
    r = client.post("/api/wallet", json={"label": "x", "chain": "doge"})
    assert r.status_code == 400
