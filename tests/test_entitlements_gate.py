"""Bug #2 enforcement contract — cloud-LLM cap gates the 4 cloud paths.

The system audit found that ``can_run`` existed but was invoked
nowhere in the cloud-LLM call sites. This module pins the
:func:`require_cloud_budget` HTTP-edge gate added in
``web_extras/entitlements_gate.py`` to four representative
endpoints:

- ``POST /api/voice/speak``         (Bug #2 surface ``voice.speak``)
- ``POST /api/council/deliberate``  (Bug #2 surface ``council.deliberate``)
- ``POST /api/planner/{id}/run``    (Bug #2 surface ``planner.run``)
- ``POST /api/chat/threads/{id}/messages``
                                    (Bug #2 surface ``chat.post_message``)

Each endpoint must return HTTP 402 + ``error_code="payment_required"``
when the FREE-tier cap is hit, and emit ``entitlements.cap_hit``
to the meeet store with the right ``surface`` label.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_state(monkeypatch: pytest.MonkeyPatch):
    """Each test gets a fresh meeet store + entitlements DB so the
    cap state can't leak across tests. Cap enforcement is
    explicitly enabled (default behaviour, but pinned)."""

    with tempfile.TemporaryDirectory(prefix="tars-gate-") as tmp:
        monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
        monkeypatch.setenv(
            "TARS_ENTITLEMENTS_DB", os.path.join(tmp, "ent.sqlite")
        )
        monkeypatch.setenv("TARS_CAP_ENFORCEMENT", "on")
        monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
        # Operator .env may enable remote billing; force the local
        # checker so tests don't hit the meeet.world snapshot endpoint
        # and degrade to ``billing_unreachable``.
        for key in (
            "TARS_BILLING_SOURCE",
            "MEEET_BILLING_BASE_URL",
            "MEEET_BILLING_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)

        # Reset module singletons so they pick up the new paths.
        from backend.core.meeet import client as client_mod
        from backend.core.meeet import store as store_mod

        client_mod._SINGLETON = None
        store_mod._SINGLETON = None

        # Drop the entitlements store singleton so it picks up the
        # fresh DB path on first read.
        from backend.core.entitlements import store as ent_store

        if hasattr(ent_store, "_SINGLETON"):
            ent_store._SINGLETON = None

        # Reset to FREE so the cap is $0 (any cloud call → 402).
        from backend.core.entitlements import Tier, get_store

        get_store().set_tier(Tier.FREE)
        get_store().set_byo(False)

        yield tmp


@pytest.fixture()
def client(isolated_state):
    from web_extras.app import app

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _expect_402(response):
    """Assert the response carries the canonical cap-hit envelope."""
    assert response.status_code == 402, (
        f"expected 402, got {response.status_code}: {response.text[:200]}"
    )
    body = response.json()
    assert body.get("ok") is False
    assert body.get("error_code") == "payment_required"
    assert "context" in body, f"context missing from 402 envelope: {body}"
    ctx = body["context"]
    assert ctx.get("tier") == "free"
    assert ctx.get("kind") == "cloud"
    return body


# ---------------------------------------------------------------------
# Per-route enforcement tests
# ---------------------------------------------------------------------


def test_voice_speak_blocks_at_cap(client: TestClient) -> None:
    r = client.post(
        "/api/voice/speak",
        json={"text": "hello", "provider": "elevenlabs"},
    )
    body = _expect_402(r)
    assert body["context"]["surface"] == "voice.speak"


def test_council_deliberate_blocks_at_cap(client: TestClient) -> None:
    r = client.post(
        "/api/council/deliberate",
        json={"prompt": "what is the market doing?", "context": {}},
    )
    body = _expect_402(r)
    assert body["context"]["surface"] == "council.deliberate"


def test_planner_run_blocks_at_cap(client: TestClient) -> None:
    # Mint a plan via the synthesiser using a registered playbook
    # name (synthesis is local — doesn't trip the gate). The exact
    # playbook is irrelevant; we never let the runner execute it.
    plan_resp = client.post(
        "/api/planner/plan",
        json={"goal": "traders.morning_check"},
    )
    assert plan_resp.status_code == 200, plan_resp.text
    plan_body = plan_resp.json()
    plan_id = plan_body.get("plan", {}).get("id") or plan_body.get("id")
    assert plan_id, f"plan id missing: {plan_body}"

    # Now /run should 402 immediately, BEFORE the runner executes.
    r = client.post(f"/api/planner/{plan_id}/run", json={})
    body = _expect_402(r)
    assert body["context"]["surface"] == "planner.run"


def test_chat_post_message_blocks_at_cap(client: TestClient) -> None:
    # Mint a thread first.
    thread_resp = client.post("/api/chat/threads", json={"title": "audit"})
    assert thread_resp.status_code == 200, thread_resp.text
    thread_id = thread_resp.json().get("thread", {}).get("id") or \
        thread_resp.json().get("id")
    assert thread_id, f"thread id missing: {thread_resp.json()}"

    r = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"text": "hello"},
    )
    # NOTE: 402 must arrive BEFORE the SSE pipe opens — i.e. as a
    # plain JSON error envelope, not a stream of SSE frames.
    body = _expect_402(r)
    assert body["context"]["surface"] == "chat.post_message"


# ---------------------------------------------------------------------
# Pro tier should NOT block (cap > 0, no spend yet)
# ---------------------------------------------------------------------


def test_voice_speak_allows_pro_tier_under_cap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke: bumping to PRO + zero spend must lift the cap, even
    though the call may still fail downstream (no real provider).
    The point is: status code MUST NOT be 402."""

    from backend.core.entitlements import Tier, get_store

    get_store().set_tier(Tier.PRO)

    r = client.post(
        "/api/voice/speak",
        json={"text": "hello", "provider": "macsay"},
    )
    # Anything except 402 means the gate let us through. Real
    # providers may not be available in CI → 503 / 400 are fine here;
    # what we're pinning is "no payment_required".
    assert r.status_code != 402, (
        f"PRO tier with $0 spend must not 402, got {r.status_code}: {r.text[:200]}"
    )


# ---------------------------------------------------------------------
# Kill-switch behaviour — TARS_CAP_ENFORCEMENT=off bypasses the gate
# ---------------------------------------------------------------------


def test_cap_enforcement_kill_switch_bypasses_gate(
    isolated_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operators in dev / test can flip ``TARS_CAP_ENFORCEMENT=off``
    to bypass the gate entirely (e.g. local FREE tier dev shell)."""

    monkeypatch.setenv("TARS_CAP_ENFORCEMENT", "off")
    from web_extras.app import app

    with TestClient(app) as c:
        r = c.post(
            "/api/council/deliberate",
            json={"prompt": "is the gate off?", "context": {}},
        )
        # Whatever happens, it MUST NOT be 402 — the kill switch is on.
        assert r.status_code != 402


# ---------------------------------------------------------------------
# Cap_hit event is emitted with the right surface label
# ---------------------------------------------------------------------


def test_cap_hit_emits_entitlements_event_with_surface(
    client: TestClient,
) -> None:
    # Trigger a 402 from voice.speak.
    r = client.post(
        "/api/voice/speak",
        json={"text": "hello", "provider": "elevenlabs"},
    )
    assert r.status_code == 402

    # Inspect the meeet store: the latest entitlements.cap_hit event
    # should carry surface="voice.speak".
    from backend.core.meeet import get_client

    rows = TestClient_run_async(
        get_client().store.list_events(kind="entitlements.cap_hit", limit=5)
    )
    assert rows, "no entitlements.cap_hit event in store after 402"
    payload = rows[0].payload or {}
    assert payload.get("surface") == "voice.speak"
    assert payload.get("tier") == "free"
    assert payload.get("kind") == "cloud"


def TestClient_run_async(coro):
    """Tiny helper — run an awaitable synchronously inside a sync test."""
    import asyncio

    return asyncio.run(coro)
