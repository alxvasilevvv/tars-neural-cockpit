"""Unit tests for :func:`consume_passed_challenge`.

The consume helper is the bridge between the proof-of-knowledge
state machine in ``backend.core.crypto.seed_challenge`` and the
destructive HTTP routes that should require a fresh proof — today
``POST /api/pairing/rotate-identity``, tomorrow any other
"rotate the keyring" / "wipe paired devices" / "export plaintext
seed" flow that the cockpit might add.

Scope:

- ``passed`` proof transitions cleanly to ``consumed`` (single-use).
- Wrong fingerprint, missing id, non-passed status all surface
  structured ``error`` codes the HTTP layer can map to a 4xx.
- The store-level invariants stay intact (the consumed challenge
  is still readable for audit, the singleton is unaffected).
"""

from __future__ import annotations

import time

import pytest

from backend.core.crypto.recovery import make_recovery_seed
from backend.core.crypto.seed_challenge import (
    ConsumeOutcome,
    SeedChallenge,
    SeedChallengeStore,
    consume_passed_challenge,
    get_challenge_store,
    mint_challenge,
    reset_challenge_store,
    verify_challenge,
)


@pytest.fixture(autouse=True)
def _reset_challenge_singleton():
    reset_challenge_store()
    yield
    reset_challenge_store()


def _passed_challenge(store: SeedChallengeStore) -> SeedChallenge:
    """Mint, verify, and persist a passed challenge against a fresh seed."""

    seed = make_recovery_seed()
    challenge = mint_challenge(seed.mnemonic, count=3, ttl_s=300, max_attempts=3)
    answers = [challenge.expected_words[i] for i in range(len(challenge.positions))]
    outcome = verify_challenge(challenge, answers)
    assert outcome.ok, outcome.to_dict()
    store.put(outcome.challenge)
    return outcome.challenge


# ---------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------


def test_consume_passed_challenge_returns_ok_and_marks_consumed():
    store = SeedChallengeStore()
    challenge = _passed_challenge(store)

    outcome = consume_passed_challenge(store, challenge.challenge_id)

    assert outcome.ok is True
    assert outcome.error is None
    assert outcome.challenge is not None
    assert outcome.challenge.challenge_id == challenge.challenge_id
    assert outcome.challenge.status == "consumed"

    # The store now holds the consumed shape; subsequent reads see it.
    persisted = store.get(challenge.challenge_id)
    assert persisted is not None
    assert persisted.status == "consumed"


def test_consume_passed_challenge_with_matching_fingerprint_succeeds():
    store = SeedChallengeStore()
    challenge = _passed_challenge(store)

    outcome = consume_passed_challenge(
        store,
        challenge.challenge_id,
        expected_fingerprint=challenge.fingerprint,
    )

    assert outcome.ok is True
    assert outcome.challenge is not None
    assert outcome.challenge.fingerprint == challenge.fingerprint


def test_consume_outcome_to_dict_shape():
    store = SeedChallengeStore()
    challenge = _passed_challenge(store)
    outcome = consume_passed_challenge(store, challenge.challenge_id)

    body = outcome.to_dict()
    assert body["ok"] is True
    assert body["status"] == "consumed"
    assert body["challenge_id"] == challenge.challenge_id
    assert body["fingerprint"] == challenge.fingerprint


# ---------------------------------------------------------------------
# Single-use enforcement
# ---------------------------------------------------------------------


def test_replay_consumed_challenge_returns_not_passed():
    store = SeedChallengeStore()
    challenge = _passed_challenge(store)

    first = consume_passed_challenge(store, challenge.challenge_id)
    assert first.ok is True

    second = consume_passed_challenge(store, challenge.challenge_id)
    assert second.ok is False
    assert second.error == "challenge_not_passed"
    assert second.challenge is not None
    assert second.challenge.status == "consumed"


# ---------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------


def test_consume_unknown_challenge_returns_not_found():
    store = SeedChallengeStore()

    outcome = consume_passed_challenge(store, "chal_does_not_exist")

    assert outcome.ok is False
    assert outcome.error == "challenge_not_found"
    assert outcome.challenge is None


def test_consume_pending_challenge_blocked():
    store = SeedChallengeStore()
    seed = make_recovery_seed()
    challenge = mint_challenge(seed.mnemonic, count=3, ttl_s=300)
    store.put(challenge)

    outcome = consume_passed_challenge(store, challenge.challenge_id)

    assert outcome.ok is False
    assert outcome.error == "challenge_not_passed"
    assert outcome.challenge is not None
    assert outcome.challenge.status == "pending"


def test_consume_failed_challenge_blocked():
    store = SeedChallengeStore()
    seed = make_recovery_seed()
    challenge = mint_challenge(seed.mnemonic, count=3, ttl_s=300, max_attempts=1)
    wrong_answers = ["wrongword"] * len(challenge.positions)
    outcome_v = verify_challenge(challenge, wrong_answers)
    assert outcome_v.challenge.status in {"exhausted"}
    store.put(outcome_v.challenge)

    outcome = consume_passed_challenge(store, challenge.challenge_id)

    assert outcome.ok is False
    assert outcome.error == "challenge_not_passed"
    assert outcome.challenge is not None
    assert outcome.challenge.status == "exhausted"


def test_consume_expired_challenge_blocked():
    store = SeedChallengeStore()
    seed = make_recovery_seed()
    challenge = mint_challenge(
        seed.mnemonic, count=3, ttl_s=60, now=time.time() - 1000
    )
    store.put(challenge)

    # The store sweep transitions the pending+expired record before
    # consume looks at it.
    _ = store.get(challenge.challenge_id)

    outcome = consume_passed_challenge(store, challenge.challenge_id)

    assert outcome.ok is False
    assert outcome.error == "challenge_not_passed"
    assert outcome.challenge is not None
    assert outcome.challenge.status == "expired"


def test_consume_with_wrong_fingerprint_blocked():
    store = SeedChallengeStore()
    challenge = _passed_challenge(store)

    outcome = consume_passed_challenge(
        store,
        challenge.challenge_id,
        expected_fingerprint="not-the-right-fp",
    )

    assert outcome.ok is False
    assert outcome.error == "fingerprint_mismatch"
    assert outcome.challenge is not None
    # Mismatch must NOT consume — the proof is still available for the
    # right caller to redeem.
    persisted = store.get(challenge.challenge_id)
    assert persisted is not None
    assert persisted.status == "passed"


# ---------------------------------------------------------------------
# Singleton wiring
# ---------------------------------------------------------------------


def test_consume_against_module_singleton_round_trip():
    store = get_challenge_store()
    challenge = _passed_challenge(store)

    outcome = consume_passed_challenge(store, challenge.challenge_id)

    assert outcome.ok is True
    assert isinstance(outcome, ConsumeOutcome)
    persisted = get_challenge_store().get(challenge.challenge_id)
    assert persisted is not None
    assert persisted.status == "consumed"
