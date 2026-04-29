"""Recovery router × policy-gate integration tests (Phase O5 cleanup).

Locks the contract that
``POST /api/recovery/generate`` and ``POST /api/recovery/verify`` flow
through the same HMAC confirm-token gate as the wallet routes when
``TARS_REQUIRE_OPERATOR_CONFIRM=1``. Default-off behaviour stays
intact so the existing first-launch flow doesn't regress.
"""

from __future__ import annotations

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from web_extras.app import app


@pytest.fixture
def client_gate_disabled() -> Iterator[TestClient]:
    os.environ.pop("TARS_REQUIRE_OPERATOR_CONFIRM", None)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_gate_enabled() -> Iterator[TestClient]:
    os.environ["TARS_REQUIRE_OPERATOR_CONFIRM"] = "1"
    try:
        with TestClient(app) as c:
            yield c
    finally:
        os.environ.pop("TARS_REQUIRE_OPERATOR_CONFIRM", None)


# ─── default-off: existing flow keeps working ──────────────────────────


def test_generate_works_without_token_when_gate_disabled(
    client_gate_disabled: TestClient,
) -> None:
    r = client_gate_disabled.post("/api/recovery/generate")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    # 24-word phrase
    assert len(body["mnemonic"].split()) == body["word_count"] == 24


def test_confirm_route_returns_disabled_marker_when_gate_off(
    client_gate_disabled: TestClient,
) -> None:
    r = client_gate_disabled.post(
        "/api/recovery/confirm",
        json={"action": "recovery.generate"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["policy_required"] is False
    assert "token" not in body  # no token because gate is off


# ─── gate enabled: must mint a token first ─────────────────────────────


def test_generate_requires_confirm_token_when_gate_enabled(
    client_gate_enabled: TestClient,
) -> None:
    # No confirm header → policy-gate fails the precondition check.
    r = client_gate_enabled.post("/api/recovery/generate")
    assert r.status_code == 428, r.text  # 428 Precondition Required
    body = r.json()
    assert body["ok"] is False
    assert body["error_code"] == "precondition_required"


def test_generate_succeeds_with_minted_token(
    client_gate_enabled: TestClient,
) -> None:
    confirm = client_gate_enabled.post(
        "/api/recovery/confirm",
        json={"action": "recovery.generate"},
    ).json()
    assert confirm["policy_required"] is True
    token = confirm["token"]
    assert isinstance(token, str) and token.count(".") == 1

    r = client_gate_enabled.post(
        "/api/recovery/generate",
        headers={"X-TARS-Confirm": token},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert len(body["mnemonic"].split()) == 24


def test_verify_requires_confirm_token_when_gate_enabled(
    client_gate_enabled: TestClient,
) -> None:
    # First mint a fresh phrase (which itself needs a token in this
    # mode). We do that by toggling the gate off-then-on so we can get
    # a real BIP-39 mnemonic to feed into verify.
    os.environ.pop("TARS_REQUIRE_OPERATOR_CONFIRM", None)
    seed = client_gate_enabled.post("/api/recovery/generate").json()
    os.environ["TARS_REQUIRE_OPERATOR_CONFIRM"] = "1"

    # Without token → 428 precondition_required
    r1 = client_gate_enabled.post(
        "/api/recovery/verify",
        json={"mnemonic": seed["mnemonic"]},
    )
    assert r1.status_code == 428
    assert r1.json()["error_code"] == "precondition_required"

    # Mint a token bound to the same body
    confirm = client_gate_enabled.post(
        "/api/recovery/confirm",
        json={
            "action": "recovery.verify",
            "params": {"mnemonic": seed["mnemonic"]},
        },
    ).json()
    token = confirm["token"]

    r2 = client_gate_enabled.post(
        "/api/recovery/verify",
        headers={"X-TARS-Confirm": token},
        json={"mnemonic": seed["mnemonic"]},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["ok"] is True
    # Fingerprint round-trip
    assert r2.json()["fingerprint"] == seed["fingerprint"]


def test_verify_token_bound_to_params_hash(
    client_gate_enabled: TestClient,
) -> None:
    """A token minted for one mnemonic must NOT verify another."""
    os.environ.pop("TARS_REQUIRE_OPERATOR_CONFIRM", None)
    seed_a = client_gate_enabled.post("/api/recovery/generate").json()
    seed_b = client_gate_enabled.post("/api/recovery/generate").json()
    os.environ["TARS_REQUIRE_OPERATOR_CONFIRM"] = "1"
    assert seed_a["mnemonic"] != seed_b["mnemonic"]

    # Mint for A
    confirm = client_gate_enabled.post(
        "/api/recovery/confirm",
        json={
            "action": "recovery.verify",
            "params": {"mnemonic": seed_a["mnemonic"]},
        },
    ).json()
    token = confirm["token"]

    # Try to use it for B
    r = client_gate_enabled.post(
        "/api/recovery/verify",
        headers={"X-TARS-Confirm": token},
        json={"mnemonic": seed_b["mnemonic"]},
    )
    assert r.status_code == 412
    assert r.json()["error_code"] == "precondition_failed"


def test_confirm_rejects_unknown_action(
    client_gate_enabled: TestClient,
) -> None:
    r = client_gate_enabled.post(
        "/api/recovery/confirm",
        json={"action": "wallet.delete"},
    )
    assert r.status_code == 400
    body = r.json()
    assert "unsupported action" in body["detail"].lower()


def test_wordlist_info_remains_open(
    client_gate_enabled: TestClient,
) -> None:
    """Read-only metadata never gates."""
    r = client_gate_enabled.get("/api/recovery/wordlist/info")
    assert r.status_code == 200
    assert r.json()["size"] == 2048
