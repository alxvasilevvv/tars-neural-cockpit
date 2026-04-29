"""HTTP policy gate contract tests (Phase O2).

Verifies the opt-in confirm-token flow that protects destructive
wallet endpoints when ``TARS_REQUIRE_OPERATOR_CONFIRM=1``.

Coverage:

- Gate is OFF by default — destructive endpoints work without a
  token (preserved dev-flow ergonomics).
- Gate ON without token → ``428 precondition_required`` with the
  registered hint.
- Gate ON + valid token → success.
- Gate ON + token bound to a different wallet / action / params →
  ``412 precondition_failed`` with a discriminating message.
- Token signature tamper detection.
- Expired tokens rejected.
- ``GET /api/wallet/policy/status`` reflects the env state.
- Token shape: HMAC-SHA256 over canonical JSON payload, b64url
  encoded payload + signature segments.
- ``POST /api/wallet/{id}/confirm`` returns the token + expiry.
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.wallet import reset_wallet_service_for_tests
from web_extras import policy_gate


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_pgate_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("TARS_CHAT_STORE", "disabled")
    monkeypatch.delenv("TARS_REQUIRE_OPERATOR_CONFIRM", raising=False)
    monkeypatch.setenv("TARS_CONFIRM_KEY", "test-fixed-key-32bytes-padding-xx")
    reset_wallet_service_for_tests()
    reset_meeet_store()
    reset_meeet_client()
    yield


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


def _mint_evm_wallet(client: TestClient) -> str:
    return client.post(
        "/api/wallet", json={"label": "evm", "chain": "evm"}
    ).json()["wallet"]["id"]


def _evm_tx_body() -> dict:
    return {
        "to": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "value": "1000000000000000000",
        "gas": "21000",
        "nonce": "0",
        "chainId": 1,
        "maxFeePerGas": "30000000000",
        "maxPriorityFeePerGas": "1000000000",
        "type": 2,
    }


# ---------- gate disabled by default ----------------------------------


def test_gate_disabled_destructive_works_without_token(
    client: TestClient,
) -> None:
    wid = _mint_evm_wallet(client)
    r = client.post(f"/api/wallet/{wid}/sign_evm_tx", json=_evm_tx_body())
    assert r.status_code == 200, r.text


def test_gate_status_reflects_env(monkeypatch, client: TestClient) -> None:
    r1 = client.get("/api/wallet/policy/status")
    assert r1.json() == {"ok": True, "required": False}
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    r2 = client.get("/api/wallet/policy/status")
    assert r2.json() == {"ok": True, "required": True}


# ---------- gate enabled flow ----------------------------------------


def test_gate_enabled_without_token_returns_428(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    r = client.post(f"/api/wallet/{wid}/sign_evm_tx", json=_evm_tx_body())
    assert r.status_code == 428
    body = r.json()
    assert body["error_code"] == "precondition_required"
    assert "X-TARS-Confirm" in body["message"]


def test_confirm_endpoint_mints_token(client: TestClient) -> None:
    wid = _mint_evm_wallet(client)
    r = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.sign_evm_tx", "params": _evm_tx_body()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["token"]
    assert body["expires_at"] > int(time.time())
    # Token shape: <b64url payload>.<b64url sig>
    assert "." in body["token"]


def test_gate_enabled_valid_token_succeeds(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    tx = _evm_tx_body()
    confirm = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.sign_evm_tx", "params": tx},
    ).json()
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json=tx,
        headers={"X-TARS-Confirm": confirm["token"]},
    )
    assert r.status_code == 200, r.text


def test_gate_token_bound_to_different_action_rejected(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    tx = _evm_tx_body()
    # Mint a token for `wallet.delete`, send it on `sign_evm_tx`.
    confirm = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.delete", "params": None},
    ).json()
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json=tx,
        headers={"X-TARS-Confirm": confirm["token"]},
    )
    assert r.status_code == 412
    assert r.json()["error_code"] == "precondition_failed"
    assert "action_mismatch" in r.json()["message"]


def test_gate_token_bound_to_different_wallet_rejected(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid_a = _mint_evm_wallet(client)
    wid_b = _mint_evm_wallet(client)
    tx = _evm_tx_body()
    confirm = client.post(
        f"/api/wallet/{wid_a}/confirm",
        json={"action": "wallet.sign_evm_tx", "params": tx},
    ).json()
    r = client.post(
        f"/api/wallet/{wid_b}/sign_evm_tx",
        json=tx,
        headers={"X-TARS-Confirm": confirm["token"]},
    )
    assert r.status_code == 412
    assert "wallet_mismatch" in r.json()["message"]


def test_gate_token_with_changed_params_rejected(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    tx = _evm_tx_body()
    confirm = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.sign_evm_tx", "params": tx},
    ).json()
    # Bump value to a different amount → params hash changes.
    tampered = {**tx, "value": "999999999999999999"}
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json=tampered,
        headers={"X-TARS-Confirm": confirm["token"]},
    )
    assert r.status_code == 412
    assert "params_mismatch" in r.json()["message"]


def test_gate_token_signature_tamper_rejected(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    tx = _evm_tx_body()
    confirm = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.sign_evm_tx", "params": tx},
    ).json()
    payload, sig = confirm["token"].split(".", 1)
    # Flip a base64 char in the *middle* of the signature. Flipping
    # the last char can land inside base64 padding bits and decode
    # to the same byte string, masking the tamper. The middle is
    # always inside the encoded HMAC bytes.
    mid = len(sig) // 2
    new_char = "A" if sig[mid] != "A" else "B"
    flipped_sig = sig[:mid] + new_char + sig[mid + 1 :]
    bad = f"{payload}.{flipped_sig}"
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json=tx,
        headers={"X-TARS-Confirm": bad},
    )
    assert r.status_code == 412
    assert "signature_invalid" in r.json()["message"]


def test_gate_token_expired_rejected(monkeypatch, client: TestClient) -> None:
    """Mint with ttl=1, sleep past expiry."""
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    tx = _evm_tx_body()
    confirm = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.sign_evm_tx", "params": tx, "ttl_s": 1},
    ).json()
    # Sleep long enough that the 1-second TTL has definitely expired
    # even when the test runs under load (full suite, slow CI).
    time.sleep(2.5)
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json=tx,
        headers={"X-TARS-Confirm": confirm["token"]},
    )
    assert r.status_code == 412
    assert "expired" in r.json()["message"]


def test_gate_malformed_token_rejected(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json=_evm_tx_body(),
        headers={"X-TARS-Confirm": "garbage-no-dot"},
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "precondition_failed"


def test_delete_with_gate_requires_confirm(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    r = client.delete(f"/api/wallet/{wid}")
    assert r.status_code == 428


def test_delete_with_gate_succeeds_with_token(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    wid = _mint_evm_wallet(client)
    confirm = client.post(
        f"/api/wallet/{wid}/confirm",
        json={"action": "wallet.delete", "params": None},
    ).json()
    r = client.delete(
        f"/api/wallet/{wid}",
        headers={"X-TARS-Confirm": confirm["token"]},
    )
    assert r.status_code == 200, r.text


# ---------- direct module API ----------------------------------------


def test_params_hash_is_deterministic_and_order_independent() -> None:
    a = policy_gate.params_hash({"to": "0x1", "value": "1"})
    b = policy_gate.params_hash({"value": "1", "to": "0x1"})
    assert a == b


def test_mint_token_respects_ttl_cap() -> None:
    out = policy_gate.mint_token(
        wallet_id="w", action="x", params_hash_hex="0", ttl_s=99999
    )
    # Capped at one hour.
    assert out["expires_at"] - int(time.time()) <= 3601


def test_verify_token_missing_returns_precondition_required() -> None:
    from web_extras.errors import TARSAPIError

    with pytest.raises(TARSAPIError) as exc:
        policy_gate.verify_token(
            token=None, wallet_id="w", action="x", params_hash_hex="0"
        )
    assert exc.value.status_code == 428
    assert exc.value.error_code == "precondition_required"


def test_is_required_reads_env(monkeypatch) -> None:
    monkeypatch.delenv("TARS_REQUIRE_OPERATOR_CONFIRM", raising=False)
    assert policy_gate.is_required() is False
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "1")
    assert policy_gate.is_required() is True
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "yes")
    assert policy_gate.is_required() is True
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "0")
    assert policy_gate.is_required() is False
