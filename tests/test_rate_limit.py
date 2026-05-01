"""Tests for the in-memory token-bucket rate limiter and the
``/api/pairing/begin`` HTTP integration.
"""

from __future__ import annotations

import base64
import time

import pytest


# ---------------------------------------------------------------------
# Pure unit tests
# ---------------------------------------------------------------------


def test_token_bucket_starts_full():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=3, rate=1.0)
    assert b.tokens == 3.0


def test_token_bucket_drains_one_per_acquire():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=3, rate=0.0)  # quota mode
    assert b.acquire() is True
    assert b.acquire() is True
    assert b.acquire() is True
    assert b.acquire() is False  # exhausted, never refills


def test_token_bucket_refills_at_rate():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=2, rate=10.0)  # 10 tokens / sec
    now = time.time()
    b.acquire(now=now)
    b.acquire(now=now)
    assert b.acquire(now=now) is False
    # 0.5 seconds → 5 tokens but capped at 2.
    assert b.acquire(now=now + 0.5) is True


def test_token_bucket_caps_at_capacity():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=2, rate=1.0)
    base = time.time()
    b.acquire(now=base)  # 1 left
    # Wait long enough that ``rate * elapsed`` exceeds capacity.
    b.acquire(now=base + 1000)  # bucket should be capped at 2 tokens then drained to 1
    assert b.tokens == pytest.approx(1.0)


def test_token_bucket_retry_after_zero_when_full():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=2, rate=1.0)
    assert b.retry_after() == 0.0


def test_token_bucket_retry_after_when_drained():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=1, rate=2.0)  # 2 tokens / sec
    base = time.time()
    b.acquire(now=base)
    # Need (1 - 0) / 2 = 0.5s for next token.
    assert b.retry_after(now=base) == pytest.approx(0.5)


def test_token_bucket_quota_retry_after_is_inf():
    from web_extras.rate_limit import TokenBucket

    b = TokenBucket(capacity=1, rate=0.0)
    assert b.acquire() is True
    assert b.retry_after() == float("inf")


def test_token_bucket_rejects_zero_capacity():
    from web_extras.rate_limit import TokenBucket

    with pytest.raises(ValueError):
        TokenBucket(capacity=0, rate=1.0)


# ---------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------


def test_unconfigured_bucket_allows_everything():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    out = rl.acquire(bucket_id="missing", subject="1.2.3.4")
    assert out.allowed is True
    assert out.remaining == float("inf")


def test_configured_bucket_isolates_subjects():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("test", capacity=2, rate=0.0)

    a = rl.acquire(bucket_id="test", subject="ip-a")
    b = rl.acquire(bucket_id="test", subject="ip-b")
    assert a.allowed and b.allowed
    # Each IP gets its own bucket; isolation is the whole point.
    assert a.remaining == 1.0
    assert b.remaining == 1.0


def test_configured_bucket_rejects_after_capacity():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("burst", capacity=2, rate=0.0)
    rl.acquire(bucket_id="burst", subject="x")
    rl.acquire(bucket_id="burst", subject="x")
    out = rl.acquire(bucket_id="burst", subject="x")
    assert out.allowed is False
    assert out.remaining == 0.0
    assert out.retry_after == float("inf")


def test_anonymous_subject_substituted():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("a", capacity=1, rate=0.0)
    out = rl.acquire(bucket_id="a", subject="")
    assert out.subject == "__anonymous__"


def test_reset_subject_clears_just_one_pair():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("b", capacity=1, rate=0.0)
    rl.acquire(bucket_id="b", subject="ip-a")  # drained
    rl.acquire(bucket_id="b", subject="ip-b")  # drained

    cleared = rl.reset_subject(bucket_id="b", subject="ip-a")
    assert cleared is True
    out_a = rl.acquire(bucket_id="b", subject="ip-a")
    out_b = rl.acquire(bucket_id="b", subject="ip-b")
    assert out_a.allowed is True   # bucket recreated
    assert out_b.allowed is False  # still drained


def test_reset_bucket_clears_all_subjects():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("c", capacity=1, rate=0.0)
    rl.acquire(bucket_id="c", subject="x")
    rl.acquire(bucket_id="c", subject="y")
    cleared = rl.reset_bucket("c")
    assert cleared == 2


def test_stats_counts_subjects_per_bucket():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter()
    rl.configure("d", capacity=2, rate=0.0)
    rl.configure("e", capacity=2, rate=0.0)
    rl.acquire(bucket_id="d", subject="x")
    rl.acquire(bucket_id="d", subject="y")
    rl.acquire(bucket_id="e", subject="x")
    stats = rl.stats()
    assert stats["d"] == 2
    assert stats["e"] == 1
    assert stats["total"] == 3
    assert stats["configured"] == 2


def test_singleton_helpers():
    from web_extras.rate_limit import (
        get_rate_limiter,
        reset_rate_limiter,
    )

    a = get_rate_limiter()
    b = get_rate_limiter()
    assert a is b
    reset_rate_limiter()
    c = get_rate_limiter()
    assert c is not a


def test_idle_buckets_swept():
    from web_extras.rate_limit import RateLimiter

    rl = RateLimiter(idle_ttl=60)
    rl.configure("x", capacity=2, rate=10.0)
    base = time.time()
    rl.acquire(bucket_id="x", subject="ip-1", now=base)
    # ip-1's bucket is at 1 token; refilling for 99999s would push it
    # back to capacity. Sweep happens when a different subject's
    # acquire finds it idle past the TTL with tokens >= capacity.
    rl.acquire(bucket_id="x", subject="ip-2", now=base + 99999)
    # ip-1's bucket got swept (idle + full). Only ip-2 remains.
    stats = rl.stats()
    assert stats["x"] == 1


# ---------------------------------------------------------------------
# Pairing HTTP integration
# ---------------------------------------------------------------------


@pytest.fixture()
def pairing_client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from backend.core.pairing.store import _reset_singleton_for_tests
    from web_extras.app import app
    from web_extras.rate_limit import reset_rate_limiter

    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("MEEET_INGEST_URL", "")

    import backend.core.meeet.client as client_mod
    import backend.core.meeet.store as store_mod

    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]

    _reset_singleton_for_tests()
    reset_rate_limiter()
    yield TestClient(app)
    reset_rate_limiter()
    _reset_singleton_for_tests()


def _fresh_epk_b64() -> str:
    from nacl.public import PrivateKey

    return base64.b64encode(
        bytes(PrivateKey.generate().public_key)
    ).decode("ascii")


def test_pairing_begin_includes_rate_limit_envelope(pairing_client):
    res = pairing_client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "rate_limit" in body
    rl = body["rate_limit"]
    assert "remaining" in rl
    assert "reset_at" in rl
    assert rl["capacity"] >= 1


def test_pairing_begin_rate_limited_after_burst(pairing_client, monkeypatch):
    monkeypatch.setenv("TARS_PAIRING_RATE_BURST", "3")
    monkeypatch.setenv("TARS_PAIRING_RATE_PER_S", "0")  # quota mode

    # Reset limiter so it picks up the new env on next call.
    from web_extras.rate_limit import reset_rate_limiter

    reset_rate_limiter()

    payload = {"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"}

    for _ in range(3):
        res = pairing_client.post("/api/pairing/begin", json=payload)
        assert res.status_code == 200

    blocked = pairing_client.post("/api/pairing/begin", json=payload)
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["ok"] is False
    assert body["error_code"] == "pair_rate_limited"
    assert "retry in" in body["message"]
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "X-RateLimit-Remaining" in blocked.headers
    assert "X-RateLimit-Reset" in blocked.headers


def test_pairing_begin_emits_rate_limited_event(
    pairing_client, monkeypatch
):
    monkeypatch.setenv("TARS_PAIRING_RATE_BURST", "1")
    monkeypatch.setenv("TARS_PAIRING_RATE_PER_S", "0")

    from web_extras.rate_limit import reset_rate_limiter

    reset_rate_limiter()

    payload = {"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"}
    pairing_client.post("/api/pairing/begin", json=payload)
    pairing_client.post("/api/pairing/begin", json=payload)

    import asyncio

    from backend.core.meeet.store import get_store

    events = asyncio.new_event_loop().run_until_complete(
        get_store().list_events(limit=200)
    )
    kinds = {e.kind for e in events}
    assert "pair.rate_limited" in kinds


def test_x_forwarded_for_used_when_trusted(pairing_client, monkeypatch):
    """Two distinct X-Forwarded-For values get distinct buckets."""

    monkeypatch.setenv("TARS_TRUST_FORWARDED_FOR", "1")
    monkeypatch.setenv("TARS_PAIRING_RATE_BURST", "1")
    monkeypatch.setenv("TARS_PAIRING_RATE_PER_S", "0")

    from web_extras.rate_limit import reset_rate_limiter

    reset_rate_limiter()

    payload = {"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"}

    res_a = pairing_client.post(
        "/api/pairing/begin",
        json=payload,
        headers={"x-forwarded-for": "10.0.0.1"},
    )
    res_b = pairing_client.post(
        "/api/pairing/begin",
        json=payload,
        headers={"x-forwarded-for": "10.0.0.2"},
    )
    # Both succeed because they hit separate buckets.
    assert res_a.status_code == 200
    assert res_b.status_code == 200

    # A second call from 10.0.0.1 should hit its quota.
    res_a2 = pairing_client.post(
        "/api/pairing/begin",
        json=payload,
        headers={"x-forwarded-for": "10.0.0.1"},
    )
    assert res_a2.status_code == 429


def test_x_forwarded_for_ignored_when_not_trusted(
    pairing_client, monkeypatch
):
    """All requests share the TestClient's loopback IP without the env flag."""

    monkeypatch.delenv("TARS_TRUST_FORWARDED_FOR", raising=False)
    monkeypatch.setenv("TARS_PAIRING_RATE_BURST", "1")
    monkeypatch.setenv("TARS_PAIRING_RATE_PER_S", "0")

    from web_extras.rate_limit import reset_rate_limiter

    reset_rate_limiter()

    payload = {"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"}

    res_a = pairing_client.post(
        "/api/pairing/begin",
        json=payload,
        headers={"x-forwarded-for": "10.0.0.1"},
    )
    res_b = pairing_client.post(
        "/api/pairing/begin",
        json=payload,
        headers={"x-forwarded-for": "10.0.0.2"},
    )
    # First succeeds, second 429: same loopback subject.
    assert res_a.status_code == 200
    assert res_b.status_code == 429
