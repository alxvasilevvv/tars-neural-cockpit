"""Tests for the per-IP rate limit on recovery challenge endpoints.

The 3-of-24 challenge endpoints are anonymous (no auth, no policy
gate) and back the destructive rotate-identity path, so they need
the same in-memory token bucket the pairing/begin endpoint uses.

This suite pins:

- 429 envelopes match the unified TARSAPIError shape
  (`error_code: "recovery_rate_limited"`, Retry-After header).
- A `recovery.rate_limited` event fires on each block so the
  cockpit audit lane can spot brute-force attempts.
- The `start` and `verify` buckets are independent — exhausting
  one does not block the other.
- Different source IPs are isolated.
- `X-Forwarded-For` is honoured only when
  `TARS_TRUST_FORWARDED_FOR=1`.
- Env knobs `TARS_RECOVERY_CHALLENGE_{START,VERIFY}_BURST` /
  `…_RATE_PER_S` change the defaults.
"""

from __future__ import annotations

import asyncio

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
from web_extras.app import app
from web_extras.rate_limit import reset_rate_limiter
from web_extras.routers.recovery import (
    RECOVERY_CHALLENGE_START_BUCKET,
    RECOVERY_CHALLENGE_VERIFY_BUCKET,
)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("MEEET_INGEST_URL", "")
    from backend.core.meeet import client as meeet_client_mod
    from backend.core.meeet import store as meeet_store_mod

    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(meeet_client_mod, "_SINGLETON", None, raising=False)
    reset_challenge_store()
    reset_rate_limiter()
    yield
    reset_challenge_store()
    reset_rate_limiter()
    monkeypatch.setattr(meeet_store_mod, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(meeet_client_mod, "_SINGLETON", None, raising=False)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tight_buckets(monkeypatch):
    """Force a 2-burst, 0-refill bucket so the test can exhaust it
    in two POSTs without sleeping."""

    monkeypatch.setenv("TARS_RECOVERY_CHALLENGE_START_BURST", "2")
    monkeypatch.setenv("TARS_RECOVERY_CHALLENGE_START_RATE_PER_S", "0")
    monkeypatch.setenv("TARS_RECOVERY_CHALLENGE_VERIFY_BURST", "2")
    monkeypatch.setenv("TARS_RECOVERY_CHALLENGE_VERIFY_RATE_PER_S", "0")


@pytest.fixture
def fresh_seed():
    return make_recovery_seed()


def _passed_challenge_id(seed_mnemonic: str) -> str:
    challenge = mint_challenge(seed_mnemonic, count=3, ttl_s=300)
    answers = [challenge.expected_words[i] for i in range(len(challenge.positions))]
    outcome = verify_challenge(challenge, answers)
    assert outcome.ok, outcome.to_dict()
    get_challenge_store().put(outcome.challenge)
    return outcome.challenge.challenge_id


async def _list_meeet_events():
    from backend.core.meeet import get_store

    return await get_store().list_events(limit=200)


# ---------------------------------------------------------------------
# /api/recovery/challenge/start
# ---------------------------------------------------------------------


def test_start_rate_limited_after_burst(
    client: TestClient, fresh_seed, tight_buckets
) -> None:
    payload = {"mnemonic": fresh_seed.mnemonic}
    first = client.post("/api/recovery/challenge/start", json=payload)
    second = client.post("/api/recovery/challenge/start", json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    blocked = client.post("/api/recovery/challenge/start", json=payload)
    assert blocked.status_code == 429, blocked.text
    body = blocked.json()
    assert body["ok"] is False
    assert body["error_code"] == "recovery_rate_limited"
    assert "retry in" in body["message"]
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "X-RateLimit-Bucket" in blocked.headers
    assert blocked.headers["X-RateLimit-Bucket"] == RECOVERY_CHALLENGE_START_BUCKET


def test_start_emits_rate_limited_event_on_block(
    client: TestClient, fresh_seed, tight_buckets
) -> None:
    payload = {"mnemonic": fresh_seed.mnemonic}
    for _ in range(2):
        ok = client.post("/api/recovery/challenge/start", json=payload)
        assert ok.status_code == 200

    blocked = client.post("/api/recovery/challenge/start", json=payload)
    assert blocked.status_code == 429

    events = asyncio.new_event_loop().run_until_complete(_list_meeet_events())
    rate_events = [e for e in events if e.kind == "recovery.rate_limited"]
    assert len(rate_events) == 1
    payload_evt = rate_events[0].payload
    assert payload_evt["bucket_id"] == RECOVERY_CHALLENGE_START_BUCKET
    assert payload_evt["route"] == "recovery.challenge.start"


# ---------------------------------------------------------------------
# /api/recovery/challenge/verify
# ---------------------------------------------------------------------


def test_verify_rate_limited_after_burst(
    client: TestClient, fresh_seed, tight_buckets
) -> None:
    chal_id = _passed_challenge_id(fresh_seed.mnemonic)
    body = {"challenge_id": "chal_does_not_exist", "words": ["a", "b", "c"]}

    first = client.post("/api/recovery/challenge/verify", json=body)
    second = client.post("/api/recovery/challenge/verify", json=body)
    assert first.status_code == 404
    assert second.status_code == 404

    blocked = client.post("/api/recovery/challenge/verify", json=body)
    assert blocked.status_code == 429, blocked.text
    body_429 = blocked.json()
    assert body_429["error_code"] == "recovery_rate_limited"
    assert blocked.headers["X-RateLimit-Bucket"] == RECOVERY_CHALLENGE_VERIFY_BUCKET
    _ = chal_id  # the helper is invoked to exercise the seed path


# ---------------------------------------------------------------------
# Bucket isolation
# ---------------------------------------------------------------------


def test_start_and_verify_buckets_are_independent(
    client: TestClient, fresh_seed, tight_buckets
) -> None:
    payload = {"mnemonic": fresh_seed.mnemonic}
    for _ in range(2):
        ok = client.post("/api/recovery/challenge/start", json=payload)
        assert ok.status_code == 200
    # start is now exhausted; verify must still work because they're
    # separate buckets.
    body = {"challenge_id": "chal_does_not_exist", "words": ["a", "b", "c"]}
    res = client.post("/api/recovery/challenge/verify", json=body)
    assert res.status_code == 404


def test_subjects_are_isolated_when_xff_trusted(
    client: TestClient, fresh_seed, tight_buckets, monkeypatch
) -> None:
    monkeypatch.setenv("TARS_TRUST_FORWARDED_FOR", "1")
    payload = {"mnemonic": fresh_seed.mnemonic}
    headers_a = {"X-Forwarded-For": "203.0.113.10"}
    headers_b = {"X-Forwarded-For": "203.0.113.20"}

    for _ in range(2):
        ok = client.post(
            "/api/recovery/challenge/start", json=payload, headers=headers_a
        )
        assert ok.status_code == 200
    blocked = client.post(
        "/api/recovery/challenge/start", json=payload, headers=headers_a
    )
    assert blocked.status_code == 429

    ok_b = client.post(
        "/api/recovery/challenge/start", json=payload, headers=headers_b
    )
    assert ok_b.status_code == 200, ok_b.text


def test_xff_ignored_when_not_trusted(
    client: TestClient, fresh_seed, tight_buckets, monkeypatch
) -> None:
    monkeypatch.delenv("TARS_TRUST_FORWARDED_FOR", raising=False)
    payload = {"mnemonic": fresh_seed.mnemonic}
    # Two different X-Forwarded-For values must collapse onto the
    # same bucket because we ignore the header.
    headers_a = {"X-Forwarded-For": "203.0.113.10"}
    headers_b = {"X-Forwarded-For": "203.0.113.20"}

    for _ in range(2):
        ok = client.post(
            "/api/recovery/challenge/start", json=payload, headers=headers_a
        )
        assert ok.status_code == 200
    blocked = client.post(
        "/api/recovery/challenge/start", json=payload, headers=headers_b
    )
    assert blocked.status_code == 429


# ---------------------------------------------------------------------
# Defaults from env
# ---------------------------------------------------------------------


def test_env_overrides_default_burst(
    client: TestClient, fresh_seed, monkeypatch
) -> None:
    """A 1-burst quota mode bucket should block the second call
    immediately, regardless of refill."""

    monkeypatch.setenv("TARS_RECOVERY_CHALLENGE_START_BURST", "1")
    monkeypatch.setenv("TARS_RECOVERY_CHALLENGE_START_RATE_PER_S", "0")

    payload = {"mnemonic": fresh_seed.mnemonic}
    first = client.post("/api/recovery/challenge/start", json=payload)
    assert first.status_code == 200
    second = client.post("/api/recovery/challenge/start", json=payload)
    assert second.status_code == 429
