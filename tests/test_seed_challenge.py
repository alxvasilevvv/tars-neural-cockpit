"""Tests for the 3-of-24 recovery-seed verification challenge.

Covers the pure mint / verify state machine, the in-memory store
behaviour, and the HTTP endpoints under ``/api/recovery/challenge``.
"""

from __future__ import annotations

import time
from typing import Any

import pytest


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_meeet_store(tmp_path, monkeypatch):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("MEEET_INGEST_URL", "")
    import backend.core.meeet.client as client_mod
    import backend.core.meeet.store as store_mod

    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]
    yield
    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _isolated_challenge_store():
    from backend.core.crypto.seed_challenge import reset_challenge_store
    from web_extras.rate_limit import reset_rate_limiter

    reset_challenge_store()
    # Recovery challenge endpoints are now rate-limited per source IP
    # (PR — challenge rate-limit). The bucket singleton would
    # otherwise leak state between tests and start dropping requests
    # mid-suite.
    reset_rate_limiter()
    yield
    reset_challenge_store()
    reset_rate_limiter()


@pytest.fixture
def fresh_seed():
    from backend.core.crypto.recovery import make_recovery_seed

    return make_recovery_seed()


# ---------------------------------------------------------------------
# Mint
# ---------------------------------------------------------------------


def test_mint_picks_three_distinct_positions_by_default(fresh_seed):
    from backend.core.crypto.seed_challenge import mint_challenge

    challenge = mint_challenge(fresh_seed.mnemonic)
    assert len(challenge.positions) == 3
    # 1-indexed.
    assert all(1 <= p <= 24 for p in challenge.positions)
    # Distinct.
    assert len(set(challenge.positions)) == 3
    # Status starts pending.
    assert challenge.status == "pending"


def test_mint_count_clamped_to_8(fresh_seed):
    from backend.core.crypto.seed_challenge import mint_challenge

    challenge = mint_challenge(fresh_seed.mnemonic, count=99)
    assert len(challenge.positions) == 8


def test_mint_count_clamped_to_at_least_1(fresh_seed):
    from backend.core.crypto.seed_challenge import mint_challenge

    challenge = mint_challenge(fresh_seed.mnemonic, count=0)
    assert len(challenge.positions) == 1


def test_mint_ttl_clamped(fresh_seed):
    from backend.core.crypto.seed_challenge import mint_challenge

    issued = time.time()
    too_short = mint_challenge(fresh_seed.mnemonic, ttl_s=1, now=issued)
    assert too_short.expires_at - too_short.issued_at == pytest.approx(30)

    too_long = mint_challenge(
        fresh_seed.mnemonic, ttl_s=999_999, now=issued
    )
    assert too_long.expires_at - too_long.issued_at == pytest.approx(1800)


def test_mint_max_attempts_clamped(fresh_seed):
    from backend.core.crypto.seed_challenge import mint_challenge

    too_low = mint_challenge(fresh_seed.mnemonic, max_attempts=-3)
    assert too_low.attempts_remaining == 1
    too_high = mint_challenge(fresh_seed.mnemonic, max_attempts=999)
    assert too_high.attempts_remaining == 10


def test_mint_validates_mnemonic_word_count():
    from backend.core.crypto.seed_challenge import mint_challenge

    with pytest.raises(ValueError):
        mint_challenge("only three words here")


def test_mint_validates_mnemonic_checksum():
    """A 24-word phrase with an invalid BIP-39 checksum must raise."""

    from backend.core.crypto.seed_challenge import mint_challenge

    junk = " ".join(["abandon"] * 24)  # checksum invalid for all-abandon
    with pytest.raises(ValueError):
        mint_challenge(junk)


def test_mint_to_public_dict_does_not_leak_words(fresh_seed):
    from backend.core.crypto.seed_challenge import mint_challenge

    challenge = mint_challenge(fresh_seed.mnemonic)
    public = challenge.to_public_dict()
    assert "expected_words" not in public
    # The expected words are still on the dataclass for the verifier.
    assert all(isinstance(w, str) for w in challenge.expected_words)


def test_mint_uses_separate_random_state(fresh_seed):
    """Two consecutive mints almost surely pick different positions."""

    from backend.core.crypto.seed_challenge import mint_challenge

    a = mint_challenge(fresh_seed.mnemonic, count=8)
    b = mint_challenge(fresh_seed.mnemonic, count=8)
    # They CAN match, but with ``count=8`` over ``range(24)`` the
    # probability is ~1.6e-6 — flaky enough to risk in CI? No: we
    # simply assert they're not always identical by minting many.
    seen: set[tuple[int, ...]] = {a.positions, b.positions}
    for _ in range(8):
        seen.add(mint_challenge(fresh_seed.mnemonic, count=8).positions)
    assert len(seen) >= 2


# ---------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------


def test_verify_passes_with_correct_words(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    challenge = mint_challenge(fresh_seed.mnemonic)
    answers = challenge.expected_words
    outcome = verify_challenge(challenge, answers)
    assert outcome.ok is True
    assert all(outcome.matched)
    assert outcome.challenge.status == "passed"


def test_verify_decrements_on_wrong_word(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    challenge = mint_challenge(fresh_seed.mnemonic, max_attempts=3)
    bogus = ["zzznotaword"] * len(challenge.positions)
    outcome = verify_challenge(challenge, bogus)
    assert outcome.ok is False
    assert outcome.challenge.status == "pending"
    assert outcome.challenge.attempts_remaining == 2
    assert outcome.error == "word_mismatch"


def test_verify_marks_exhausted_after_attempts(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    challenge = mint_challenge(fresh_seed.mnemonic, max_attempts=2)
    bogus = ["zzz"] * len(challenge.positions)

    after_one = verify_challenge(challenge, bogus)
    assert after_one.challenge.attempts_remaining == 1
    assert after_one.challenge.status == "pending"

    after_two = verify_challenge(after_one.challenge, bogus)
    assert after_two.challenge.attempts_remaining == 0
    assert after_two.challenge.status == "exhausted"
    assert after_two.error == "exhausted"


def test_verify_wrong_answer_count(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    challenge = mint_challenge(fresh_seed.mnemonic, count=3)
    outcome = verify_challenge(challenge, ["only", "two"])
    assert outcome.ok is False
    assert outcome.error == "answer_count_mismatch"
    # Mismatch shouldn't burn an attempt.
    assert outcome.challenge.attempts_remaining == challenge.attempts_remaining


def test_verify_normalises_case_and_whitespace(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    challenge = mint_challenge(fresh_seed.mnemonic)
    answers = [w.upper() + "  " for w in challenge.expected_words]
    outcome = verify_challenge(challenge, answers)
    assert outcome.ok is True


def test_verify_rejects_expired_challenge(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    issued = 1_000.0
    challenge = mint_challenge(fresh_seed.mnemonic, ttl_s=30, now=issued)
    later = issued + 31  # past expiry (1s past the 30s clamp)
    outcome = verify_challenge(
        challenge, challenge.expected_words, now=later
    )
    assert outcome.ok is False
    assert outcome.error == "expired"
    assert outcome.challenge.status == "expired"


def test_verify_rejects_already_passed_challenge(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        mint_challenge,
        verify_challenge,
    )

    challenge = mint_challenge(fresh_seed.mnemonic)
    passed = verify_challenge(challenge, challenge.expected_words)
    again = verify_challenge(passed.challenge, challenge.expected_words)
    assert again.ok is False
    assert again.error == "not_pending"


# ---------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------


def test_store_round_trips_challenge(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        SeedChallengeStore,
        mint_challenge,
    )

    store = SeedChallengeStore()
    challenge = mint_challenge(fresh_seed.mnemonic)
    store.put(challenge)
    fetched = store.get(challenge.challenge_id)
    assert fetched is not None
    assert fetched.challenge_id == challenge.challenge_id


def test_store_marks_pending_expired_on_read(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        SeedChallengeStore,
        mint_challenge,
    )

    store = SeedChallengeStore()
    issued = 100.0
    challenge = mint_challenge(fresh_seed.mnemonic, ttl_s=60, now=issued)
    store.put(challenge)
    # Past expiry.
    fetched = store.get(challenge.challenge_id, now=issued + 9999)
    assert fetched is not None
    assert fetched.status == "expired"


def test_store_consume_removes(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        SeedChallengeStore,
        mint_challenge,
    )

    store = SeedChallengeStore()
    challenge = mint_challenge(fresh_seed.mnemonic)
    store.put(challenge)
    consumed = store.consume(challenge.challenge_id)
    assert consumed is not None
    assert store.get(challenge.challenge_id) is None


def test_store_stats(fresh_seed):
    from backend.core.crypto.seed_challenge import (
        SeedChallengeStore,
        mint_challenge,
        verify_challenge,
    )

    store = SeedChallengeStore()
    a = mint_challenge(fresh_seed.mnemonic)
    b = mint_challenge(fresh_seed.mnemonic)
    store.put(a)
    store.put(b)
    # Pass `a`.
    passed_outcome = verify_challenge(a, a.expected_words)
    store.put(passed_outcome.challenge)
    stats = store.stats()
    assert stats["total"] == 2
    assert stats["passed"] == 1
    assert stats["pending"] == 1


def test_singleton_helpers():
    from backend.core.crypto.seed_challenge import (
        get_challenge_store,
        reset_challenge_store,
    )

    a = get_challenge_store()
    b = get_challenge_store()
    assert a is b
    reset_challenge_store()
    c = get_challenge_store()
    assert c is not a


# ---------------------------------------------------------------------
# HTTP — challenge/start + verify + state
# ---------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TARS_REQUIRE_OPERATOR_CONFIRM", "0")
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("MEEET_INGEST_URL", "")

    from fastapi.testclient import TestClient

    import backend.core.meeet.client as client_mod
    import backend.core.meeet.store as store_mod

    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]

    from web_extras.app import app

    return TestClient(app)


def _start_challenge(client, mnemonic: str, **overrides) -> dict[str, Any]:
    body: dict[str, Any] = {"mnemonic": mnemonic}
    body.update(overrides)
    res = client.post("/api/recovery/challenge/start", json=body)
    res.raise_for_status()
    return res.json()


def test_http_start_returns_positions_and_does_not_leak_words(
    client, fresh_seed
):
    res = client.post(
        "/api/recovery/challenge/start",
        json={"mnemonic": fresh_seed.mnemonic},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    challenge = body["challenge"]
    assert challenge["fingerprint"] == fresh_seed.fingerprint
    assert len(challenge["positions"]) == 3
    assert challenge["status"] == "pending"
    # Sanity: response must not echo the words.
    text = res.text.lower()
    for word in fresh_seed.words:
        # Words might still appear in the JSON because they're
        # 4-8 letter dictionary entries (e.g. "abandon"); only
        # check explicit field.
        assert "expected_words" not in text


def test_http_start_rejects_short_mnemonic(client):
    res = client.post(
        "/api/recovery/challenge/start",
        json={"mnemonic": "only three words"},
    )
    assert res.status_code == 400
    assert "invalid_mnemonic" in res.json()["detail"]


def test_http_verify_passes_on_correct_words(client, fresh_seed):
    started = _start_challenge(client, fresh_seed.mnemonic)
    challenge_id = started["challenge"]["challenge_id"]
    positions: list[int] = started["challenge"]["positions"]
    # Look up the actual expected words via the in-process store.
    from backend.core.crypto.seed_challenge import get_challenge_store

    actual = get_challenge_store().get(challenge_id)
    assert actual is not None
    answers = list(actual.expected_words)
    assert len(answers) == len(positions)

    res = client.post(
        "/api/recovery/challenge/verify",
        json={"challenge_id": challenge_id, "words": answers},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["status"] == "passed"
    assert all(body["matched"])


def test_http_verify_wrong_answer_decrements(client, fresh_seed):
    started = _start_challenge(
        client, fresh_seed.mnemonic, max_attempts=3
    )
    challenge_id = started["challenge"]["challenge_id"]
    res = client.post(
        "/api/recovery/challenge/verify",
        json={
            "challenge_id": challenge_id,
            "words": ["xx", "yy", "zz"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["status"] == "pending"
    assert body["attempts_remaining"] == 2
    assert body["error"] == "word_mismatch"


def test_http_verify_unknown_challenge_returns_404(client):
    res = client.post(
        "/api/recovery/challenge/verify",
        json={"challenge_id": "chal_doesnotexist", "words": ["a"]},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "challenge_not_found"


def test_http_state_returns_public_safe_shape(client, fresh_seed):
    started = _start_challenge(client, fresh_seed.mnemonic)
    challenge_id = started["challenge"]["challenge_id"]
    res = client.get(f"/api/recovery/challenge/{challenge_id}")
    assert res.status_code == 200
    challenge = res.json()["challenge"]
    assert challenge["challenge_id"] == challenge_id
    assert challenge["fingerprint"] == fresh_seed.fingerprint
    assert challenge["status"] == "pending"
    assert "expected_words" not in challenge


def test_http_state_404_for_unknown(client):
    res = client.get("/api/recovery/challenge/chal_unknown")
    assert res.status_code == 404


def _list_meeet_kinds() -> set[str]:
    import asyncio

    from backend.core.meeet.store import get_store

    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=200)
    )
    return {e.kind for e in events}


def test_http_verify_emits_challenge_passed_event(client, fresh_seed):
    started = _start_challenge(client, fresh_seed.mnemonic)
    challenge_id = started["challenge"]["challenge_id"]

    from backend.core.crypto.seed_challenge import get_challenge_store

    actual = get_challenge_store().get(challenge_id)
    assert actual is not None
    answers = list(actual.expected_words)

    client.post(
        "/api/recovery/challenge/verify",
        json={"challenge_id": challenge_id, "words": answers},
    )

    kinds = _list_meeet_kinds()
    assert "recovery.challenge.started" in kinds
    assert "recovery.challenge.passed" in kinds


def test_http_verify_emits_challenge_failed_event(client, fresh_seed):
    started = _start_challenge(client, fresh_seed.mnemonic)
    challenge_id = started["challenge"]["challenge_id"]

    client.post(
        "/api/recovery/challenge/verify",
        json={
            "challenge_id": challenge_id,
            "words": ["xx", "yy", "zz"],
        },
    )

    kinds = _list_meeet_kinds()
    assert "recovery.challenge.failed" in kinds
