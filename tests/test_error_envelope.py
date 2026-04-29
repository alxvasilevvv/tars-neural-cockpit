"""Unified error envelope contract tests (Phase O1).

Every error response MUST carry:

- ``ok: false``
- ``error_code`` from the taxonomy in ``web_extras/errors.py``
- ``message`` (free-form)
- ``detail`` (legacy FastAPI field, equal to ``message``)
- optional ``hint`` for actionable codes

Cockpit / agents / mobile companions read ``error_code`` to branch
behaviour without parsing English. ``detail`` is preserved so older
tests and clients that rely on FastAPI's default shape keep working.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.wallet import reset_wallet_service_for_tests


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_err_")
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


def _assert_envelope(body: dict, expected_code: str) -> None:
    assert body["ok"] is False, body
    assert body["error_code"] == expected_code, body
    assert isinstance(body["message"], str)
    assert body["detail"] == body["message"], body
    # `hint` is optional but, if present, must be a non-empty string.
    if "hint" in body:
        assert isinstance(body["hint"], str) and body["hint"], body


def test_wallet_not_found_returns_envelope(client: TestClient) -> None:
    r = client.get("/api/wallet/wlt_deadbeef")
    assert r.status_code == 404
    body = r.json()
    _assert_envelope(body, expected_code="wallet_not_found")
    assert "hint" in body  # registered hint exists


def test_wallet_chain_mismatch_returns_envelope(client: TestClient) -> None:
    # Mint a Solana wallet, try to call EVM-tx-signing on it.
    create = client.post("/api/wallet", json={"label": "sol", "chain": "solana"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
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
    assert r.status_code == 400
    body = r.json()
    # The wallet service raises "sign_evm_transaction requires evm wallet, ..."
    # which maps to a generic 400. We at least get the envelope shape.
    assert body["ok"] is False
    assert "error_code" in body
    assert body["detail"] == body["message"]


def test_validation_error_returns_envelope(client: TestClient) -> None:
    """Pydantic / FastAPI validation surfaces as a 422 with a stable code."""
    r = client.post("/api/wallet", json={"label": ""})  # missing chain
    assert r.status_code == 422
    body = r.json()
    _assert_envelope(body, expected_code="validation_error")
    assert "errors" in body  # per-field breakdown


def test_unknown_route_returns_404_envelope(client: TestClient) -> None:
    r = client.get("/api/wallet/this/does/not/exist")
    assert r.status_code == 404
    body = r.json()
    assert body["ok"] is False
    # FastAPI's default 404 has detail="Not Found".
    assert body["error_code"] in {"not_found", "http_404"}


def test_method_not_allowed_returns_envelope(client: TestClient) -> None:
    """``DELETE /api/wallet`` (no id) is not registered → 405."""
    r = client.delete("/api/wallet")
    assert r.status_code == 405
    body = r.json()
    assert body["ok"] is False
    assert body["error_code"] in {"method_not_allowed", "http_405"}


def test_envelope_preserves_legacy_detail_field(client: TestClient) -> None:
    """Older clients / tests inspect `detail` directly. Preserve it."""
    r = client.get("/api/wallet/wlt_does_not_exist")
    body = r.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


def test_taxonomy_is_complete() -> None:
    """Every code referenced from a hint must exist in ERROR_CODES."""
    from web_extras.errors import ERROR_CODES, ERROR_HINTS

    for code in ERROR_HINTS:
        assert code in ERROR_CODES, code


def test_tarsapierror_carries_explicit_hint() -> None:
    from web_extras.errors import TARSAPIError

    err = TARSAPIError(
        status_code=400,
        error_code="wallet_invalid_amount",
        message="amount could not be parsed: 'foo'",
    )
    assert err.error_code == "wallet_invalid_amount"
    # Auto-fills hint from ERROR_HINTS.
    assert err.hint and "digits" in err.hint
