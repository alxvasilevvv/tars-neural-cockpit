"""Bug #4 contract — per-IP throttle on expensive cloud routes.

Pins :class:`ExpensiveRoutesRateLimitMiddleware`:

- 429 + ``Retry-After`` once the burst is exhausted.
- Exempt routes (e.g. ``GET /api/chat``) are never throttled.
- Per-IP isolation — one client at the cap doesn't starve another.
- Env kill switch ``TARS_RATE_LIMIT_EXPENSIVE=off`` bypasses entirely.
- Env-driven burst override.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_state(monkeypatch: pytest.MonkeyPatch):
    """Each test gets a fresh meeet store, the rate limiter is
    reset between tests, and enforcement is pinned ON. The chat
    cap-enforcement gate is also kept off (default for the suite)
    so we exercise the rate limiter, not the entitlements gate."""

    with tempfile.TemporaryDirectory(prefix="tars-rl-") as tmp:
        monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
        monkeypatch.setenv("TARS_RATE_LIMIT_EXPENSIVE", "on")
        # Pin the buckets to a tiny burst so tests don't have to
        # spam 30 requests to fill up.
        monkeypatch.setenv("TARS_RATE_LIMIT_VOICE_SPEAK_BURST", "2")
        monkeypatch.setenv("TARS_RATE_LIMIT_VOICE_SPEAK_PER_MINUTE", "0")
        monkeypatch.setenv("TARS_RATE_LIMIT_COUNCIL_DELIBERATE_BURST", "2")
        monkeypatch.setenv("TARS_RATE_LIMIT_COUNCIL_DELIBERATE_PER_MINUTE", "0")

        # Reset the rate limiter singleton so the tighter buckets
        # take effect for THIS test (the singleton is otherwise
        # process-global).
        from web_extras.rate_limit import reset_rate_limiter

        reset_rate_limiter()

        # Reset meeet singletons.
        from backend.core.meeet import client as client_mod
        from backend.core.meeet import store as store_mod

        client_mod._SINGLETON = None
        store_mod._SINGLETON = None

        yield tmp


@pytest.fixture()
def client(isolated_state):
    from web_extras.app import app

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------
# 429 once the burst is exhausted
# ---------------------------------------------------------------------


def test_voice_speak_429_after_burst(client: TestClient) -> None:
    # Burst = 2; the 3rd request must 429.
    for i in range(2):
        r = client.post(
            "/api/voice/speak",
            json={"text": f"hello {i}", "provider": "macsay"},
        )
        # Status may be anything except 429 here (likely 503 since
        # macsay isn't installed in CI). What matters: not throttled
        # yet.
        assert r.status_code != 429, (
            f"request {i} prematurely throttled: {r.status_code}"
        )

    # 3rd request: 429 + Retry-After.
    r = client.post(
        "/api/voice/speak",
        json={"text": "third", "provider": "macsay"},
    )
    assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text}"
    assert "Retry-After" in r.headers
    body = r.json()
    assert body.get("error_code") == "rate_limited"
    assert body.get("context", {}).get("bucket_id") == "voice.speak"
    assert body.get("context", {}).get("retry_after_s") >= 1


def test_council_deliberate_429_after_burst(client: TestClient) -> None:
    for i in range(2):
        r = client.post(
            "/api/council/deliberate",
            json={"prompt": f"prompt {i}", "context": {}},
        )
        assert r.status_code != 429

    r = client.post(
        "/api/council/deliberate",
        json={"prompt": "third", "context": {}},
    )
    assert r.status_code == 429
    body = r.json()
    assert body["error_code"] == "rate_limited"
    assert body["context"]["bucket_id"] == "council.deliberate"


# ---------------------------------------------------------------------
# Exempt routes are never throttled
# ---------------------------------------------------------------------


def test_get_endpoints_not_throttled(client: TestClient) -> None:
    """GET /api/voice/personas shares the prefix with the throttled
    POST /api/voice/speak — middleware must not match."""
    for _ in range(20):
        r = client.get("/api/voice/personas")
        assert r.status_code != 429


def test_health_endpoint_never_throttled(client: TestClient) -> None:
    for _ in range(50):
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------


def test_kill_switch_bypasses_middleware(
    isolated_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TARS_RATE_LIMIT_EXPENSIVE", "off")
    from web_extras.app import app

    with TestClient(app) as c:
        # 10 requests, no 429 anywhere.
        for i in range(10):
            r = c.post(
                "/api/voice/speak",
                json={"text": f"hello {i}", "provider": "macsay"},
            )
            assert r.status_code != 429, (
                f"kill switch ignored at request {i}: {r.status_code}"
            )


# ---------------------------------------------------------------------
# Bucket isolation per IP — uses TestClient header injection
# ---------------------------------------------------------------------


def test_per_ip_isolation(
    isolated_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two distinct ``X-Forwarded-For`` clients each get their own
    burst budget. The middleware honours XFF when ``TARS_TRUST_FORWARDED_FOR``
    is on."""

    monkeypatch.setenv("TARS_TRUST_FORWARDED_FOR", "1")
    from web_extras.app import app

    with TestClient(app) as c:
        # Client A — exhaust burst.
        for _ in range(2):
            c.post(
                "/api/voice/speak",
                json={"text": "A", "provider": "macsay"},
                headers={"x-forwarded-for": "10.0.0.1"},
            )
        r_a = c.post(
            "/api/voice/speak",
            json={"text": "A throttled", "provider": "macsay"},
            headers={"x-forwarded-for": "10.0.0.1"},
        )
        assert r_a.status_code == 429

        # Client B — fresh burst, must succeed (no 429).
        r_b = c.post(
            "/api/voice/speak",
            json={"text": "B fresh", "provider": "macsay"},
            headers={"x-forwarded-for": "10.0.0.2"},
        )
        assert r_b.status_code != 429, (
            f"client B starved by client A: {r_b.status_code}"
        )
