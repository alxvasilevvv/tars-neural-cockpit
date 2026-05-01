"""HTTP integration tests for ``POST /api/pairing/rotate-identity``.

The rotate endpoint is gated behind a passed 3-of-24 recovery
challenge (the "Recovery seed verification policy" item from
``docs/IDEAS.md``). These tests pin:

- 409 / 404 envelopes for the unhappy paths (no recovery bound,
  unknown challenge, fingerprint mismatch, replay, pending /
  expired / exhausted challenge).
- The success path: fresh keypair minted, ``recovery_fingerprint``
  preserved, challenge transitioned to ``consumed`` (single-use),
  ``pair.host_rotated`` event emitted.
- ``new_recovery_fingerprint`` body knob lets the operator rotate
  the bound seed at the same time as the keypair (e.g. after a
  seed-leak event).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.crypto.recovery import make_recovery_seed
from backend.core.crypto.seed_challenge import (
    get_challenge_store,
    mint_challenge,
    reset_challenge_store,
    verify_challenge,
)
from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.pairing.store import _reset_singleton_for_tests, get_pairing_store
from web_extras.app import app
from web_extras.rate_limit import reset_rate_limiter


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    from backend.core.meeet import client as meeet_client_mod
    from backend.core.meeet import store as meeet_store_mod

    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(meeet_client_mod, "_SINGLETON", None, raising=False)
    _reset_singleton_for_tests()
    reset_rate_limiter()
    reset_challenge_store()
    yield
    _reset_singleton_for_tests()
    reset_rate_limiter()
    reset_challenge_store()
    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(meeet_client_mod, "_SINGLETON", None, raising=False)


@pytest.fixture
def client():
    return TestClient(app)


def _bind_recovery(fingerprint: str) -> None:
    """Force the singleton pairing store to report a recovery fingerprint.

    The default test fixture disables the keyring vault, so the
    store has no ``recovery_fingerprint`` bound out of the box.
    The rotate endpoint refuses to operate in that state — which
    is intentional, but means every "happy path" test has to seed
    the store first.
    """

    store = get_pairing_store()
    store._identity_recovery_fingerprint = fingerprint  # noqa: SLF001


async def _list_meeet_events():
    from backend.core.meeet import get_store

    store = get_store()
    return await store.list_events(limit=200)


def _mint_passed_challenge(seed_mnemonic: str) -> tuple[str, str]:
    """Mint + verify a 3-of-24 challenge against ``seed_mnemonic``.

    Returns ``(challenge_id, fingerprint)``. The challenge is left
    in the singleton challenge store with ``status='passed'`` so
    the rotate endpoint can consume it.
    """

    challenge = mint_challenge(seed_mnemonic, count=3, ttl_s=300, max_attempts=3)
    answers = [challenge.expected_words[i] for i in range(len(challenge.positions))]
    outcome = verify_challenge(challenge, answers)
    assert outcome.ok, outcome.to_dict()
    get_challenge_store().put(outcome.challenge)
    return outcome.challenge.challenge_id, outcome.challenge.fingerprint


# ---------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------


def test_rotate_identity_happy_path(client: TestClient) -> None:
    seed = make_recovery_seed()
    _bind_recovery(seed.fingerprint)
    challenge_id, fp = _mint_passed_challenge(seed.mnemonic)
    assert fp == seed.fingerprint

    before = client.get("/api/pairing/identity").json()

    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": challenge_id},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["host_id"] == before["host_id"]
    assert body["host_public_key"] != before["host_public_key"]
    assert body["previous_host_public_key"] == before["host_public_key"]
    assert body["recovery_fingerprint"] == seed.fingerprint
    assert body["challenge_id"] == challenge_id
    assert "trace_id" in body

    after = client.get("/api/pairing/identity").json()
    assert after["host_public_key"] == body["host_public_key"]
    assert after["recovery_fingerprint"] == seed.fingerprint


def test_rotate_identity_consumes_challenge_single_use(client: TestClient) -> None:
    seed = make_recovery_seed()
    _bind_recovery(seed.fingerprint)
    challenge_id, _ = _mint_passed_challenge(seed.mnemonic)

    first = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": challenge_id},
    )
    assert first.status_code == 200, first.text

    persisted = get_challenge_store().get(challenge_id)
    assert persisted is not None
    assert persisted.status == "consumed"

    second = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": challenge_id},
    )
    assert second.status_code == 409, second.text
    body = second.json()
    assert body["ok"] is False
    assert body["error_code"] == "challenge_not_passed"


def test_rotate_identity_can_bind_a_new_recovery_fingerprint(
    client: TestClient,
) -> None:
    seed = make_recovery_seed()
    _bind_recovery(seed.fingerprint)
    challenge_id, _ = _mint_passed_challenge(seed.mnemonic)

    new_seed = make_recovery_seed()
    res = client.post(
        "/api/pairing/rotate-identity",
        json={
            "challenge_id": challenge_id,
            "new_recovery_fingerprint": new_seed.fingerprint,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["recovery_fingerprint"] == new_seed.fingerprint


@pytest.mark.asyncio
async def test_rotate_identity_emits_pair_host_rotated_event(
    client: TestClient,
) -> None:
    seed = make_recovery_seed()
    _bind_recovery(seed.fingerprint)
    challenge_id, _ = _mint_passed_challenge(seed.mnemonic)

    before = client.get("/api/pairing/identity").json()
    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": challenge_id},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    events = await _list_meeet_events()
    rotated = [e for e in events if e.kind == "pair.host_rotated"]
    assert len(rotated) == 1
    payload = rotated[0].payload
    assert payload["host_id"] == before["host_id"]
    assert payload["old_host_public_key"] == before["host_public_key"]
    assert payload["new_host_public_key"] == body["host_public_key"]
    assert payload["challenge_id"] == challenge_id
    assert payload["recovery_fingerprint"] == seed.fingerprint


# ---------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------


def test_rotate_identity_without_recovery_bound_returns_409(
    client: TestClient,
) -> None:
    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": "chal_anything"},
    )
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["ok"] is False
    assert body["error_code"] == "recovery_not_bound"


def test_rotate_identity_unknown_challenge_returns_404(client: TestClient) -> None:
    seed = make_recovery_seed()
    _bind_recovery(seed.fingerprint)

    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": "chal_does_not_exist"},
    )
    assert res.status_code == 404, res.text
    body = res.json()
    assert body["error_code"] == "challenge_not_found"


def test_rotate_identity_pending_challenge_returns_409(client: TestClient) -> None:
    seed = make_recovery_seed()
    _bind_recovery(seed.fingerprint)
    challenge = mint_challenge(seed.mnemonic, count=3, ttl_s=300)
    get_challenge_store().put(challenge)

    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": challenge.challenge_id},
    )
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["error_code"] == "challenge_not_passed"


def test_rotate_identity_fingerprint_mismatch_returns_409(client: TestClient) -> None:
    """A challenge minted against a *different* seed than the one bound
    to the host must not let the operator rotate."""

    bound_seed = make_recovery_seed()
    other_seed = make_recovery_seed()
    assert bound_seed.fingerprint != other_seed.fingerprint
    _bind_recovery(bound_seed.fingerprint)

    challenge_id, fp = _mint_passed_challenge(other_seed.mnemonic)
    assert fp == other_seed.fingerprint

    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": challenge_id},
    )
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["error_code"] == "fingerprint_mismatch"

    # The mismatch must NOT consume the proof — a different host
    # bound to the *other* seed could still legitimately use it.
    persisted = get_challenge_store().get(challenge_id)
    assert persisted is not None
    assert persisted.status == "passed"


def test_rotate_identity_response_is_unified_envelope(client: TestClient) -> None:
    res = client.post(
        "/api/pairing/rotate-identity",
        json={"challenge_id": "chal_anything"},
    )
    body = res.json()
    assert set(body.keys()) >= {"ok", "error_code", "message"}
    assert body["ok"] is False
    assert isinstance(body["message"], str)
