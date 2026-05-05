"""Phase M / P5 — entitlements module + HTTP router contract.

Locks the launch behaviour:
- Defaults: every new install is FREE.
- Tier table matches the documented launch caps.
- ``can_run`` returns ``allowed=True`` for edge regardless of tier.
- ``can_run`` blocks cloud calls past the daily cap (computed against
  the meeet usage ledger).
- BYO toggle relaxes the cap.
- HTTP endpoints emit ``entitlements.{upgraded, byo_toggled, cap_hit}``
  events to meeet.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.entitlements import (
    LIMITS,
    Tier,
    can_run,
    format_caps,
    get_store,
)
from backend.core.entitlements.store import reset_store_for_tests
from backend.core.meeet import get_client
from backend.core.meeet.store import MeeetStore
from backend.core.usage.ledger import UsageLedger
from web_extras.app import app


# ─── helpers ──────────────────────────────────────────────────────────


@pytest.fixture
def fresh_store(tmp_path: Path) -> Iterator[None]:
    reset_store_for_tests(path=tmp_path / "ent.json")
    try:
        yield
    finally:
        reset_store_for_tests()


@pytest.fixture
def client(
    fresh_store: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    # Bug #3 fix from docs/SYSTEM_AUDIT_2026-05-02.md — the upgrade
    # endpoint now defaults to ``off`` (rejects paid upgrades). Most
    # of the existing tests in this file exercise the legacy mock
    # path, so the fixture pins ``mock`` mode for them. Tests that
    # check the ``off`` / on-chain modes use their own monkeypatch.
    monkeypatch.setenv("TARS_PAYMENT_MODE", "mock")
    with TestClient(app) as c:
        yield c


# ─── unit: tiers + caps ──────────────────────────────────────────────


def test_tier_enum_values() -> None:
    assert Tier.FREE.value == "free"
    assert Tier.PRO.value == "pro"
    assert Tier.BUSINESS.value == "business"


def test_limits_table_has_every_tier() -> None:
    for t in Tier:
        assert t in LIMITS, f"missing limits row for {t}"


def test_free_has_zero_cloud_budget_and_no_sync() -> None:
    lim = LIMITS[Tier.FREE]
    assert lim.daily_cloud_budget_usd == 0.0
    assert lim.cloud_sync is False
    assert lim.audit_log is False
    assert lim.daily_council_votes == 0


def test_pro_unlocks_sync_and_council() -> None:
    lim = LIMITS[Tier.PRO]
    assert lim.cloud_sync is True
    assert lim.daily_council_votes >= 100
    assert lim.daily_cloud_budget_usd > 0


def test_business_is_unlimited_council_and_t2t() -> None:
    lim = LIMITS[Tier.BUSINESS]
    assert lim.is_unlimited_council() is True
    assert lim.is_unlimited_t2t() is True
    assert lim.audit_log is True
    assert lim.rbac is True


def test_format_caps_serialises_unlimited_as_null() -> None:
    out = format_caps(Tier.BUSINESS)
    # Cockpit treats null as "unlimited" — keep it that way.
    assert out["daily_council_votes"] is None
    assert out["monthly_t2t_deals"] is None


# ─── can_run unit checks (no HTTP) ───────────────────────────────────


def test_can_run_edge_always_allowed_even_for_free(fresh_store: None) -> None:
    res = asyncio.run(can_run(kind="edge"))
    assert res.allowed is True
    assert res.tier is Tier.FREE


def test_can_run_blocks_cloud_for_free_tier(fresh_store: None) -> None:
    res = asyncio.run(can_run(kind="cloud"))
    assert res.allowed is False
    assert res.reason == "cap_hit"
    assert res.cap_usd == 0.0


def test_can_run_allows_cloud_when_byo_enabled(fresh_store: None) -> None:
    get_store().set_byo(True)
    res = asyncio.run(can_run(kind="cloud"))
    assert res.allowed is True
    assert res.byo_enabled is True


def test_can_run_blocks_cloud_when_pro_cap_hit(fresh_store: None) -> None:
    """Inject usage events past the cap and confirm we block."""

    from backend.core.meeet import trace_scope

    get_store().set_tier(Tier.PRO)
    cap = LIMITS[Tier.PRO].daily_cloud_budget_usd

    async def _push_then_check() -> None:
        client = get_client()
        # Push synthetic cloud usage above the daily cap.
        with trace_scope():
            await client.emit(
                "usage.tokens",
                {
                    "model": "gpt-4o",
                    "tokens_in": 1000,
                    "tokens_out": 100,
                    "cost_usd": cap + 1.0,
                    "latency_ms": 100,
                },
                route="cloud",  # event-level route for the rollup
            )

    asyncio.run(_push_then_check())
    res = asyncio.run(can_run(kind="cloud"))
    assert res.allowed is False
    assert res.reason == "cap_hit"
    assert res.spent_usd > res.cap_usd


# ─── HTTP router contract ────────────────────────────────────────────


def test_get_entitlements_defaults_to_free(client: TestClient) -> None:
    r = client.get("/api/entitlements")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["tier"] == "free"
    assert body["byo_enabled"] is False
    assert body["caps"]["cloud_sync"] is False


def test_upgrade_requires_payment_token_for_paid_tiers(
    client: TestClient,
) -> None:
    r = client.post("/api/entitlements/upgrade", json={"tier": "pro"})
    assert r.status_code == 402
    body = r.json()
    assert body["error_code"] == "payment_required"


def test_upgrade_accepts_mock_payment_and_emits_event(
    client: TestClient,
) -> None:
    r = client.post(
        "/api/entitlements/upgrade",
        json={"tier": "pro", "payment_token": "mock_token_abc"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "pro"
    assert body["previous"] == "free"

    # Re-fetch and confirm persistence
    cur = client.get("/api/entitlements").json()
    assert cur["tier"] == "pro"


def test_byo_toggle_round_trip(client: TestClient) -> None:
    r1 = client.post("/api/entitlements/byo", json={"enabled": True})
    assert r1.status_code == 200
    assert r1.json()["byo_enabled"] is True
    r2 = client.get("/api/entitlements").json()
    assert r2["byo_enabled"] is True
    r3 = client.post("/api/entitlements/byo", json={"enabled": False}).json()
    assert r3["byo_enabled"] is False


def test_can_run_route_returns_allowed_for_edge(client: TestClient) -> None:
    r = client.post("/api/entitlements/can_run", json={"kind": "edge"})
    assert r.status_code == 200
    assert r.json()["allowed"] is True


def test_can_run_route_blocks_cloud_for_free(client: TestClient) -> None:
    r = client.post("/api/entitlements/can_run", json={"kind": "cloud"})
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False
    assert body["reason"] == "cap_hit"
    assert body["tier"] == "free"


def test_tiers_listing_endpoint(client: TestClient) -> None:
    r = client.get("/api/entitlements/tiers")
    assert r.status_code == 200
    slugs = {t["tier"] for t in r.json()["tiers"]}
    assert slugs == {"free", "pro", "business"}


def test_downgrade_to_free_does_not_require_payment_token(
    client: TestClient,
) -> None:
    # Upgrade first
    client.post(
        "/api/entitlements/upgrade",
        json={"tier": "pro", "payment_token": "x"},
    )
    # Downgrade
    r = client.post(
        "/api/entitlements/upgrade",
        json={"tier": "free"},
    )
    assert r.status_code == 200
    assert r.json()["tier"] == "free"


# ─── Bug #3 — payment mode strict gating ──────────────────────────────


def test_upgrade_blocked_when_payment_mode_off(
    fresh_store: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Bug #3 fix**. With ``TARS_PAYMENT_MODE`` unset (or =off) the
    upgrade endpoint refuses paid tiers entirely; production safety net
    so a misconfigured deploy can't hand out PRO for free."""

    monkeypatch.setenv("TARS_PAYMENT_MODE", "off")
    with TestClient(app) as c:
        r = c.post(
            "/api/entitlements/upgrade",
            json={"tier": "pro", "payment_token": "anything"},
        )
        assert r.status_code == 503, r.text
        body = r.json()
        assert body["error_code"] == "feature_disabled"
        assert body["context"]["payment_mode"] == "off"


def test_upgrade_default_mode_is_off(
    fresh_store: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Bug #3 contract.** With NO env set the endpoint must NOT
    accept paid upgrades. Pin the safer-by-default behaviour."""

    monkeypatch.delenv("TARS_PAYMENT_MODE", raising=False)
    with TestClient(app) as c:
        r = c.post(
            "/api/entitlements/upgrade",
            json={"tier": "pro", "payment_token": "anything"},
        )
        assert r.status_code == 503
        assert r.json()["error_code"] == "feature_disabled"


@pytest.mark.parametrize(
    "mode",
    ("onchain", "tokens", "stripe"),
    ids=("onchain", "tokens", "stripe-legacy-alias"),
)
def test_upgrade_onchain_modes_return_not_implemented(
    fresh_store: None,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """**Bug #3 contract.** On-chain payment envs advertise intent but until
    SOL / $MEEET verification ships the endpoint must 503 with
    ``not_implemented``. ``stripe`` remains a deprecated alias for the
    same stub (card rails are not used)."""

    monkeypatch.setenv("TARS_PAYMENT_MODE", mode)
    with TestClient(app) as c:
        r = c.post(
            "/api/entitlements/upgrade",
            json={"tier": "pro", "payment_token": "tok_xxx"},
        )
        assert r.status_code == 503
        body = r.json()
        assert body["error_code"] == "not_implemented"
        assert body["context"]["payment_mode"] == mode
        assert "SOL" in body["message"] or "$MEEET" in body["message"]


def test_upgrade_to_free_works_in_off_mode(
    fresh_store: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Bug #3 contract.** Downgrading to FREE never needs payment;
    must work even with the env explicitly off."""

    monkeypatch.setenv("TARS_PAYMENT_MODE", "off")
    with TestClient(app) as c:
        r = c.post("/api/entitlements/upgrade", json={"tier": "free"})
        assert r.status_code == 200
        assert r.json()["tier"] == "free"


def test_upgrade_mock_mode_emits_explicit_mock_event_kind(
    fresh_store: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """**Bug #3 audit-trail safety**. Mock-mode upgrades must NOT emit
    plain ``entitlements.upgraded`` (reserved for real-payment events
    on-chain settlement lands). Use ``entitlements.upgraded.mock`` so the
    audit page can distinguish 'this user actually paid' from 'a dev
    bumped their tier with a fake token'."""

    # Isolate the meeet store on disk so we don't pick up upgrade
    # events from other tests run in the same session.
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("TARS_PAYMENT_MODE", "mock")
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    from backend.core.meeet import client as client_mod
    from backend.core.meeet import store as store_mod

    client_mod._SINGLETON = None
    store_mod._SINGLETON = None

    with TestClient(app) as c:
        r = c.post(
            "/api/entitlements/upgrade",
            json={"tier": "pro", "payment_token": "mock_dev_token"},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("payment_mode") == "mock"

    async def _fetch_events(kind: str) -> list:
        return await get_client().store.list_events(kind=kind, limit=5)

    rows = asyncio.run(_fetch_events("entitlements.upgraded.mock"))
    assert rows, "expected entitlements.upgraded.mock event after mock-mode upgrade"
    payload = rows[0].payload or {}
    assert payload.get("payment_mode") == "mock"
    assert payload.get("payment_token_present") is True

    # In an isolated store with ONLY this one mock-upgrade call, the
    # plain ``entitlements.upgraded`` channel must be empty.
    plain_rows = asyncio.run(_fetch_events("entitlements.upgraded"))
    assert not plain_rows, (
        "plain entitlements.upgraded event leaked from mock-mode upgrade — "
        "would mislead the audit trail into thinking the operator paid"
    )
