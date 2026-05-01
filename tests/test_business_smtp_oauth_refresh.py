"""SMTP OAuth refresh-token flow (continuation of PR #40).

Three layers under test:

1. ``OAuthRefreshConfig.load`` — vault-key parsing + provider-shorthand
   token URL resolution + explicit override.
2. ``get_fresh_access_token`` — in-memory cache hit, refresh path,
   force-refresh, transport / decode failure isolation.
3. ``SmtpConfig.load`` integration — refresh token wins over no-token,
   manual ``SMTP_OAUTH_TOKEN`` still beats refresh, refresh failure
   degrades gracefully (no crash, manual fallback used when present).
"""

from __future__ import annotations

import json
import time
import urllib.error
from typing import Any
from unittest import mock

import pytest

from backend.core.domains.packs.business import oauth as oauth_mod
from backend.core.domains.packs.business import smtp as smtp_mod
from backend.core.domains.packs.business.oauth import (
    OAuthRefreshConfig,
    REFRESH_LEAD_S,
    cache_size,
    get_fresh_access_token,
    reset_oauth_cache,
)
from backend.core.domains.packs.business.smtp import SmtpConfig


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    """Wipe vault env vars + OAuth cache between tests."""

    for var in (
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_OAUTH_TOKEN",
        "SMTP_OAUTH_REFRESH_TOKEN",
        "SMTP_OAUTH_CLIENT_ID",
        "SMTP_OAUTH_CLIENT_SECRET",
        "SMTP_OAUTH_TOKEN_URL",
        "SMTP_OAUTH_TENANT",
        "SMTP_OAUTH_SCOPE",
        "SMTP_PROVIDER",
        "SMTP_FROM",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_oauth_cache()
    yield
    reset_oauth_cache()


# ---------------------------------------------------------------------
# OAuthRefreshConfig.load
# ---------------------------------------------------------------------


def test_load_returns_none_without_refresh_token(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN_URL", "https://example/token")
    assert OAuthRefreshConfig.load() is None


def test_load_returns_none_without_client_id(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN_URL", "https://example/token")
    assert OAuthRefreshConfig.load() is None


def test_load_returns_none_when_token_url_unresolvable(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    # No provider, no explicit URL → can't resolve.
    assert OAuthRefreshConfig.load() is None


def test_load_uses_provider_shorthand_for_gmail(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    cfg = OAuthRefreshConfig.load(provider="gmail")
    assert cfg is not None
    assert cfg.token_url == "https://oauth2.googleapis.com/token"
    assert cfg.tenant == "common"


def test_load_uses_provider_shorthand_for_office365(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("SMTP_OAUTH_TENANT", "contoso")
    cfg = OAuthRefreshConfig.load(provider="office365")
    assert cfg is not None
    assert (
        cfg.token_url
        == "https://login.microsoftonline.com/contoso/oauth2/v2.0/token"
    )


def test_load_explicit_token_url_beats_provider(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN_URL", "https://example/token")
    cfg = OAuthRefreshConfig.load(provider="gmail")
    assert cfg is not None
    assert cfg.token_url == "https://example/token"


def test_load_strips_whitespace_in_secrets(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "  rt  ")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "  cid  ")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_SECRET", "  sec  ")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN_URL", "https://example/token")
    cfg = OAuthRefreshConfig.load()
    assert cfg.refresh_token == "rt"
    assert cfg.client_id == "cid"
    assert cfg.client_secret == "sec"


# ---------------------------------------------------------------------
# get_fresh_access_token
# ---------------------------------------------------------------------


def _config(**overrides) -> OAuthRefreshConfig:
    base = dict(
        refresh_token="refresh-XYZ",
        client_id="client-1",
        client_secret="secret-1",
        token_url="https://example.test/token",
        scope=None,
        tenant=None,
        provider="gmail",
    )
    base.update(overrides)
    return OAuthRefreshConfig(**base)


def _stub_post_form(monkeypatch, response: dict[str, Any] | Exception) -> None:
    calls = {"count": 0}

    def fake(url: str, data: dict[str, str], *, timeout_s: float):
        calls["count"] += 1
        if isinstance(response, Exception):
            raise response
        return dict(response)

    monkeypatch.setattr(oauth_mod, "_post_form", fake)
    return calls


def test_refresh_exchanges_token_and_caches_it(monkeypatch) -> None:
    calls = _stub_post_form(
        monkeypatch,
        {"access_token": "tok-1", "expires_in": 3600},
    )
    cfg = _config()
    res = get_fresh_access_token(cfg)
    assert res["ok"] is True
    assert res["access_token"] == "tok-1"
    assert res["source"] == "refresh"
    assert res["cached"] is False
    assert 3500 < res["expires_in"] <= 3601
    assert calls["count"] == 1
    assert cache_size() == 1


def test_refresh_returns_cache_hit_on_second_call(monkeypatch) -> None:
    calls = _stub_post_form(
        monkeypatch,
        {"access_token": "tok-1", "expires_in": 3600},
    )
    cfg = _config()
    get_fresh_access_token(cfg)
    res2 = get_fresh_access_token(cfg)
    assert res2["source"] == "cache"
    assert res2["cached"] is True
    assert calls["count"] == 1  # second call did NOT hit the wire


def test_force_refresh_bypasses_cache(monkeypatch) -> None:
    counter = {"n": 0}

    def fake_post(url, data, *, timeout_s):
        counter["n"] += 1
        return {"access_token": f"tok-{counter['n']}", "expires_in": 3600}

    monkeypatch.setattr(oauth_mod, "_post_form", fake_post)
    cfg = _config()
    r1 = get_fresh_access_token(cfg)
    r2 = get_fresh_access_token(cfg, force_refresh=True)
    assert r1["access_token"] == "tok-1"
    assert r2["access_token"] == "tok-2"
    assert r2["source"] == "refresh"
    assert counter["n"] == 2


def test_refresh_when_cache_almost_expired(monkeypatch) -> None:
    """When the cached token has < REFRESH_LEAD_S seconds left,
    the next call refreshes."""

    counter = {"n": 0}

    def fake_post(url, data, *, timeout_s):
        counter["n"] += 1
        # First call → expires soon. Second call → fresh hour.
        expires_in = 60 if counter["n"] == 1 else 3600
        return {
            "access_token": f"tok-{counter['n']}",
            "expires_in": expires_in,
        }

    monkeypatch.setattr(oauth_mod, "_post_form", fake_post)
    cfg = _config()
    r1 = get_fresh_access_token(cfg)
    assert r1["access_token"] == "tok-1"
    # 60s < REFRESH_LEAD_S (300) → cached value is "expiring" → refresh.
    r2 = get_fresh_access_token(cfg)
    assert r2["access_token"] == "tok-2"
    assert counter["n"] == 2


def test_refresh_isolates_transport_errors(monkeypatch) -> None:
    _stub_post_form(
        monkeypatch,
        urllib.error.URLError("connection refused"),
    )
    cfg = _config()
    res = get_fresh_access_token(cfg)
    assert res["ok"] is False
    assert res["reason"] == "transport_error"
    assert "connection refused" in res["error"]
    assert cache_size() == 0  # no garbage cached on failure


def test_refresh_handles_oauth_error_response(monkeypatch) -> None:
    _stub_post_form(
        monkeypatch,
        {
            "error": "invalid_grant",
            "error_description": "refresh token expired",
        },
    )
    cfg = _config()
    res = get_fresh_access_token(cfg)
    assert res["ok"] is False
    assert res["reason"] == "decode_error"
    assert "invalid_grant" in res["error"]


def test_refresh_handles_missing_expires_in_field(monkeypatch) -> None:
    """Some providers return tokens with no ``expires_in``; default
    to 3600 seconds rather than crashing."""

    _stub_post_form(monkeypatch, {"access_token": "tok-1"})
    cfg = _config()
    res = get_fresh_access_token(cfg)
    assert res["ok"] is True
    assert 3500 < res["expires_in"] <= 3601


# ---------------------------------------------------------------------
# SmtpConfig.load integration
# ---------------------------------------------------------------------


def test_smtp_config_uses_refresh_when_no_manual_token(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "refresh-XYZ")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SMTP_PROVIDER", "gmail")

    _stub_post_form(
        monkeypatch,
        {"access_token": "fresh-tok", "expires_in": 3500},
    )
    cfg = SmtpConfig.load()
    assert cfg is not None
    assert cfg.oauth_token == "fresh-tok"
    assert cfg.oauth_token_source == "refresh"
    assert cfg.oauth_expires_in is not None and cfg.oauth_expires_in > 3000
    assert cfg.auth_method == "xoauth2"


def test_smtp_config_manual_token_beats_refresh(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "manual-tok")
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "refresh-XYZ")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("SMTP_PROVIDER", "gmail")

    # Stub _post_form to detect that we did NOT call it.
    calls = _stub_post_form(monkeypatch, {"access_token": "should-not-use"})
    cfg = SmtpConfig.load()
    assert cfg.oauth_token == "manual-tok"
    assert cfg.oauth_token_source == "manual"
    assert calls["count"] == 0


def test_smtp_config_falls_back_when_refresh_fails(monkeypatch) -> None:
    """Refresh transport error → no token, no crash. Operator sees
    auth fall back to password (or none)."""

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password-fallback")
    monkeypatch.setenv("SMTP_OAUTH_REFRESH_TOKEN", "refresh-bad")
    monkeypatch.setenv("SMTP_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("SMTP_PROVIDER", "gmail")

    _stub_post_form(monkeypatch, urllib.error.URLError("boom"))
    cfg = SmtpConfig.load()
    assert cfg is not None
    assert cfg.oauth_token is None  # refresh failed → no XOAUTH2 token
    assert cfg.oauth_token_source == "none"
    assert cfg.auth_method == "password"  # password fallback survives


def test_smtp_config_oauth_metadata_surfaces_in_send_dict() -> None:
    from backend.core.domains.packs.business.smtp import SmtpResult

    res = SmtpResult(
        sent=True,
        via="smtp_ssl",
        server="smtp.gmail.com:465",
        from_addr="alice@example.com",
        to_addr="bob@example.com",
        response_code=250,
        elapsed_ms=12.345,
        auth_method="xoauth2",
        oauth_token_source="refresh",
        oauth_expires_in=3500.0,
    )
    out = res.to_dict()
    assert out["oauth_token_source"] == "refresh"
    assert out["oauth_expires_in"] == 3500.0
