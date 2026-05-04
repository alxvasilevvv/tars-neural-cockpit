"""HTTP contract for ``POST /api/oauth/smtp/{start,exchange}`` and
the supporting :func:`persist_refresh_token` helper.

The router is the cockpit's path through the SMTP OAuth initial-consent
dance. Three things must stay green for any future cockpit refactor:

1. ``/start`` builds a usable consent URL + returns the PKCE
   ``code_verifier`` the cockpit caches.
2. ``/exchange`` verifies state, swaps code → tokens, persists into
   the vault when ``persist=True``, never echoes the refresh token
   when persistence succeeded (the vault is the canonical store and
   echoing would leak it into browser history / proxy logs).
3. Every consent attempt — success or failure — emits a
   ``business.smtp.oauth.consent.*`` event into the meeet store
   so the audit trail captures revocation incidents.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.packs.business import oauth_consent as consent_mod
from backend.core.domains.packs.business.oauth_consent import (
    PersistedConsent,
    TokenExchangeResult,
    VAULT_KEY_CLIENT_ID,
    VAULT_KEY_CLIENT_SECRET,
    VAULT_KEY_PROVIDER,
    VAULT_KEY_REFRESH_TOKEN,
    VAULT_KEY_TENANT,
    _reset_state_secret_for_tests,
    persist_refresh_token,
)
from backend.core.meeet import MeeetStore, get_store, reset_client, reset_store
from backend.core.vault import get_secret
from backend.core.vault import keychain as kc_module


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Pin the state secret + isolate the durable meeet store + clean
    any vault env spillover between cases."""

    monkeypatch.setenv("TARS_OAUTH_STATE_SECRET", "test-secret-please-rotate")
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_LOCAL_LOG", raising=False)
    for k in (
        VAULT_KEY_REFRESH_TOKEN,
        VAULT_KEY_CLIENT_ID,
        VAULT_KEY_CLIENT_SECRET,
        VAULT_KEY_PROVIDER,
        VAULT_KEY_TENANT,
    ):
        monkeypatch.delenv(k, raising=False)
    # Force the env-fallback path so tests don't actually touch the
    # operator's macOS Keychain.
    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)
    monkeypatch.setattr(kc_module, "_delete_keychain", lambda *a, **k: False)
    _reset_state_secret_for_tests()
    reset_store()
    reset_client()
    yield
    reset_store()
    reset_client()
    _reset_state_secret_for_tests()


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app  # imported here so MEEET_STORE_PATH wins
    return TestClient(app)


# -------------------------------------------------------------- /start


def test_start_builds_gmail_consent_url(client: TestClient) -> None:
    r = client.post(
        "/api/oauth/smtp/start",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "redirect_uri": "http://127.0.0.1:8765/cb",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["provider"] == "gmail"
    assert body["url"].startswith(
        "https://accounts.google.com/o/oauth2/v2/auth?"
    )
    assert body["state"]
    assert body["code_verifier"]
    assert body["trace_id"]


def test_start_normalises_provider_case(client: TestClient) -> None:
    r = client.post(
        "/api/oauth/smtp/start",
        json={
            "provider": "GMAIL",
            "client_id": "cid",
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 200
    assert r.json()["provider"] == "gmail"


def test_start_rejects_unknown_provider(client: TestClient) -> None:
    r = client.post(
        "/api/oauth/smtp/start",
        json={
            "provider": "yahoo",  # not in SUPPORTED_PROVIDERS
            "client_id": "cid",
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 400
    assert "unsupported provider" in r.json()["detail"]


def test_start_rejects_missing_client_id(client: TestClient) -> None:
    r = client.post(
        "/api/oauth/smtp/start",
        json={
            "provider": "gmail",
            "client_id": "",
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 422


def test_start_emits_consent_started_event(client: TestClient) -> None:
    import asyncio

    r = client.post(
        "/api/oauth/smtp/start",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 200
    rows = asyncio.run(get_store().list_events(kind="business.smtp.oauth.consent.started"))
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["provider"] == "gmail"
    assert payload["client_id_tail"] == "345678"
    # Full client_id MUST NOT appear anywhere — only the tail.
    assert "cid-12345678" not in str(payload)


# -------------------------------------------------------------- /exchange


def _stub_post_form(monkeypatch, response: Any) -> dict[str, Any]:
    calls = {"count": 0, "data": None}

    def fake(url, data, *, timeout_s):
        calls["count"] += 1
        calls["data"] = dict(data)
        if isinstance(response, Exception):
            raise response
        return dict(response)

    monkeypatch.setattr(consent_mod, "_post_form", fake)
    return calls


def _kickoff_consent(client: TestClient, **overrides) -> dict[str, Any]:
    body = {
        "provider": "gmail",
        "client_id": "cid-12345678",
        "redirect_uri": "http://127.0.0.1/cb",
    }
    body.update(overrides)
    r = client.post("/api/oauth/smtp/start", json=body)
    assert r.status_code == 200
    return r.json()


def test_exchange_happy_path_persists_refresh_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _kickoff_consent(client)
    _stub_post_form(
        monkeypatch,
        {
            "access_token": "at-1",
            "refresh_token": "rt-1",
            "expires_in": 3600,
            "scope": "https://mail.google.com/",
            "token_type": "Bearer",
        },
    )

    r = client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "client_secret": "sec",
            "code": "auth-code-1",
            "code_verifier": started["code_verifier"],
            "state": started["state"],
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["had_refresh_token"] is True
    assert body["expires_in"] == 3600.0
    # Refresh token MUST NOT be echoed when persistence succeeded.
    assert "refresh_token" not in body
    assert "rt-1" not in str(body)

    # Vault now holds the persisted refresh token (env fallback path
    # because we mocked _to_keychain to return False).
    assert get_secret(VAULT_KEY_REFRESH_TOKEN) == "rt-1"
    assert get_secret(VAULT_KEY_CLIENT_ID) == "cid-12345678"
    assert get_secret(VAULT_KEY_CLIENT_SECRET) == "sec"
    assert get_secret(VAULT_KEY_PROVIDER) == "gmail"
    # No tenant on Gmail → not persisted.
    assert get_secret(VAULT_KEY_TENANT) is None

    persisted_keys = {p["key"] for p in body["persisted"]["persisted"]}
    assert VAULT_KEY_REFRESH_TOKEN in persisted_keys
    assert VAULT_KEY_TENANT in body["persisted"]["skipped"]


def test_exchange_dry_run_echoes_refresh_token_and_skips_vault(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``persist=False`` → operator wants a one-shot inspection
    without touching the vault. The response carries the refresh
    token explicitly so the operator can decide what to do with it."""

    started = _kickoff_consent(client)
    _stub_post_form(
        monkeypatch,
        {"access_token": "at-2", "refresh_token": "rt-dry", "expires_in": 3600},
    )

    r = client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "code": "c",
            "code_verifier": started["code_verifier"],
            "state": started["state"],
            "redirect_uri": "http://127.0.0.1/cb",
            "persist": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["refresh_token"] == "rt-dry"
    assert "persisted" not in body
    # Vault was NOT touched.
    assert get_secret(VAULT_KEY_REFRESH_TOKEN) is None


def test_exchange_rejects_tampered_state(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _kickoff_consent(client)
    body, sig = started["state"].split(".")
    bad_state = f"{body}.{'A' * len(sig)}"

    counter = _stub_post_form(monkeypatch, {"access_token": "should-not-be-called"})

    r = client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "code": "c",
            "code_verifier": started["code_verifier"],
            "state": bad_state,
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid state"
    # Token endpoint was never hit — defense in depth.
    assert counter["count"] == 0


def test_exchange_rejects_provider_mismatch(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A state issued for Gmail must not be replayable as Office365."""

    started = _kickoff_consent(client)  # provider=gmail
    counter = _stub_post_form(monkeypatch, {"access_token": "x"})

    r = client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "office365",
            "client_id": "cid",
            "code": "c",
            "code_verifier": started["code_verifier"],
            "state": started["state"],
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 400
    assert counter["count"] == 0


def test_exchange_propagates_oauth_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = _kickoff_consent(client)
    _stub_post_form(
        monkeypatch,
        {"error": "invalid_grant", "error_description": "code already used"},
    )

    r = client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "code": "reused",
            "code_verifier": started["code_verifier"],
            "state": started["state"],
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    # 200 with ok=False so the cockpit can render a structured error
    # without going through HTTP error handling.
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["reason"] == "oauth_error"
    assert "invalid_grant" in body["error"]


def test_exchange_emits_completed_event_on_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    started = _kickoff_consent(client)
    _stub_post_form(
        monkeypatch,
        {"access_token": "at", "refresh_token": "rt", "expires_in": 3600},
    )
    client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "gmail",
            "client_id": "cid-12345678",
            "code": "c",
            "code_verifier": started["code_verifier"],
            "state": started["state"],
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    rows = asyncio.run(
        get_store().list_events(kind="business.smtp.oauth.consent.completed")
    )
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["provider"] == "gmail"
    assert payload["had_refresh_token"] is True
    # Persisted destination metadata is captured but values aren't —
    # only the key name (which contains "refresh_token") and the
    # storage destination ("env" / "keychain") leak into the audit
    # event. The actual token value "rt" must NOT.
    flat = str(payload)
    assert "'rt'" not in flat
    assert '"rt"' not in flat
    # Sanity: the persisted block IS there with destination metadata.
    persisted_keys = {p["key"] for p in payload["persisted"]["persisted"]}
    assert VAULT_KEY_REFRESH_TOKEN in persisted_keys


def test_exchange_emits_failed_event_on_state_mismatch(
    client: TestClient,
) -> None:
    import asyncio

    r = client.post(
        "/api/oauth/smtp/exchange",
        json={
            "provider": "gmail",
            "client_id": "cid",
            "code": "c",
            "code_verifier": "v" * 43,
            "state": "garbage.value",
            "redirect_uri": "http://127.0.0.1/cb",
        },
    )
    assert r.status_code == 400
    rows = asyncio.run(
        get_store().list_events(kind="business.smtp.oauth.consent.failed")
    )
    assert len(rows) == 1
    assert rows[0].payload["stage"] == "state_verify"


# ============================================== persist_refresh_token


def test_persist_refresh_token_skips_when_no_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)
    result = TokenExchangeResult(ok=True, access_token="at", refresh_token=None)
    out = persist_refresh_token(result, client_id="cid", provider="gmail")
    assert out.persisted == ()
    assert VAULT_KEY_REFRESH_TOKEN in out.skipped


def test_persist_refresh_token_refuses_failed_result() -> None:
    bad = TokenExchangeResult(ok=False, reason="oauth_error", error="bad")
    with pytest.raises(ValueError, match="failed TokenExchangeResult"):
        persist_refresh_token(bad, client_id="cid", provider="gmail")


def test_persist_refresh_token_omits_default_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)
    result = TokenExchangeResult(ok=True, refresh_token="rt", access_token="at")
    out = persist_refresh_token(
        result, client_id="cid", provider="office365", tenant="common"
    )
    keys = {ref.key for ref in out.persisted}
    assert VAULT_KEY_TENANT not in keys
    assert VAULT_KEY_TENANT in out.skipped


def test_persist_refresh_token_writes_non_default_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)
    result = TokenExchangeResult(ok=True, refresh_token="rt", access_token="at")
    out = persist_refresh_token(
        result, client_id="cid", provider="office365", tenant="contoso"
    )
    keys = {ref.key for ref in out.persisted}
    assert VAULT_KEY_TENANT in keys
    assert get_secret(VAULT_KEY_TENANT) == "contoso"
