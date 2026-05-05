"""meeet.world remote billing mirror — TARS side (see docs/contracts/TARS_MEEET_BILLING.md)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.entitlements.store import reset_store_for_tests
from backend.core.meeet_billing.client import clear_operator_cache
from web_extras.app import app


@pytest.fixture(autouse=True)
def _billing_env_cleanup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TARS_BILLING_SOURCE", raising=False)
    monkeypatch.delenv("MEEET_BILLING_BASE_URL", raising=False)
    monkeypatch.delenv("MEEET_BILLING_API_KEY", raising=False)
    clear_operator_cache()
    yield
    clear_operator_cache()


@pytest.fixture
def fresh_ent(monkeypatch: pytest.MonkeyPatch, tmp_path):
    reset_store_for_tests(path=tmp_path / "ent.json")
    monkeypatch.setenv("TARS_PAYMENT_MODE", "mock")
    try:
        yield
    finally:
        reset_store_for_tests()


def _remote_ok_payload() -> dict:
    return {
        "ok": True,
        "contract_version": "1.0.0",
        "tier": "pro",
        "byo_enabled": False,
        "live": {
            "spent_usd_24h": 0.5,
            "cap_usd_daily": 5.0,
            "remaining_usd": 4.5,
            "allowed_cloud": True,
            "reason": None,
        },
        "checkout": {
            "pro": "https://meeet.world/billing/tars?plan=pro",
            "business": "https://meeet.world/billing/tars?plan=business",
        },
        "account_url": "https://meeet.world/account",
    }


def test_get_entitlements_reflects_remote_operator(
    monkeypatch: pytest.MonkeyPatch, fresh_ent: None
) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/api/v1")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(_remote_ok_payload()).encode()

    with patch("urllib.request.urlopen", return_value=_Resp()):
        with TestClient(app) as c:
            r = c.get("/api/entitlements")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tier"] == "pro"
    assert body["billing"]["authority"] == "meeet.world"
    assert body["billing"]["remote_ok"] is True
    assert body["live"]["allowed_cloud"] is True
    assert body["live"]["spent_usd_24h"] == 0.5


def test_can_run_cloud_denied_when_remote_unreachable(
    monkeypatch: pytest.MonkeyPatch, fresh_ent: None
) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/api/v1")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")

    def boom(*a, **kw):
        raise OSError("simulated network failure")

    with patch("urllib.request.urlopen", side_effect=boom):
        with TestClient(app) as c:
            r = c.post("/api/entitlements/can_run", json={"kind": "cloud"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["allowed"] is False
    assert out["reason"] == "billing_unreachable"


def test_upgrade_delegates_to_meeet_checkout(
    monkeypatch: pytest.MonkeyPatch, fresh_ent: None
) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/api/v1")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(_remote_ok_payload()).encode()

    with patch("urllib.request.urlopen", return_value=_Resp()):
        with TestClient(app) as c:
            r = c.post(
                "/api/entitlements/upgrade",
                json={"tier": "pro", "payment_token": "ignored"},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delegated"] is True
    assert body["redirect"].startswith("https://meeet.world/")


def test_byo_rejected_in_remote_mode(
    monkeypatch: pytest.MonkeyPatch, fresh_ent: None
) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/api/v1")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")

    with TestClient(app) as c:
        r = c.post("/api/entitlements/byo", json={"enabled": True})
    assert r.status_code == 503
    assert r.json()["error_code"] == "feature_disabled"
