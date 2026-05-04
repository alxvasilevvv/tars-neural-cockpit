"""SMTP OAuth authorization-code (initial consent) flow.

Companion to ``tests/test_business_smtp_oauth_refresh.py`` — that suite
covers the refresh side; this one covers the *first* consent that
mints the refresh token in the first place.

Three layers under test:

1. ``build_consent_url`` — provider URL resolution, scope defaults,
   PKCE generation (43-byte verifier + base64url-encoded SHA-256
   challenge), Google-specific access_type/prompt params, state token
   shape.

2. ``verify_state`` — HMAC-SHA256 round-trip, tamper detection, expiry,
   provider mismatch rejection. Generic error messages so the callback
   handler can't accidentally leak which check failed.

3. ``exchange_authorization_code`` — happy path (refresh + access
   tokens), no-refresh-token warning path, OAuth ``error`` propagation,
   transport / decode error isolation, missing-input early returns.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.parse
from typing import Any

import pytest

from backend.core.domains.packs.business import oauth_consent as consent_mod
from backend.core.domains.packs.business.oauth_consent import (
    ConsentURL,
    StateClaims,
    TokenExchangeResult,
    _reset_state_secret_for_tests,
    build_consent_url,
    exchange_authorization_code,
    verify_state,
)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    """Pin the state secret so consent URLs are reproducible; clear
    OAuth-related env vars between tests."""

    monkeypatch.setenv("TARS_OAUTH_STATE_SECRET", "test-secret-please-rotate")
    monkeypatch.delenv("TARS_OAUTH_STATE_MAX_AGE_S", raising=False)
    _reset_state_secret_for_tests()
    yield
    _reset_state_secret_for_tests()


# ============================================================ build_consent_url


def test_build_consent_url_resolves_gmail_endpoint() -> None:
    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1:8765/cb", provider="gmail"
    )
    assert out.url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    parsed = dict(urllib.parse.parse_qsl(out.url.split("?", 1)[1]))
    assert parsed["client_id"] == "cid"
    assert parsed["response_type"] == "code"
    assert parsed["redirect_uri"] == "http://127.0.0.1:8765/cb"
    assert parsed["code_challenge_method"] == "S256"
    assert parsed["scope"] == "https://mail.google.com/"
    # Google-specific quirks for refresh-token issuance:
    assert parsed["access_type"] == "offline"
    assert parsed["prompt"] == "consent"


def test_build_consent_url_resolves_office365_endpoint_and_tenant() -> None:
    out = build_consent_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1:8765/cb",
        provider="office365",
        tenant="contoso",
    )
    assert out.url.startswith(
        "https://login.microsoftonline.com/contoso/oauth2/v2.0/authorize?"
    )
    parsed = dict(urllib.parse.parse_qsl(out.url.split("?", 1)[1]))
    assert parsed["scope"] == (
        "https://outlook.office.com/SMTP.Send offline_access"
    )
    # Microsoft does NOT need access_type=offline; offline_access scope handles it.
    assert "access_type" not in parsed


def test_build_consent_url_explicit_auth_url_overrides_provider() -> None:
    out = build_consent_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1:8765/cb",
        provider="gmail",
        auth_url="https://example.test/auth",
    )
    assert out.url.startswith("https://example.test/auth?")


def test_build_consent_url_explicit_scope_overrides_default() -> None:
    out = build_consent_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1:8765/cb",
        provider="gmail",
        scope="custom scope",
    )
    parsed = dict(urllib.parse.parse_qsl(out.url.split("?", 1)[1]))
    assert parsed["scope"] == "custom scope"


def test_build_consent_url_pkce_challenge_matches_verifier() -> None:
    """PKCE: code_challenge must be base64url(SHA256(code_verifier))
    per RFC 7636 — without padding."""

    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    parsed = dict(urllib.parse.parse_qsl(out.url.split("?", 1)[1]))
    expected_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(out.code_verifier.encode("ascii")).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )
    assert parsed["code_challenge"] == expected_challenge


def test_build_consent_url_each_call_yields_fresh_verifier_and_state() -> None:
    a = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    b = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    assert a.code_verifier != b.code_verifier
    assert a.state != b.state


def test_build_consent_url_extra_params_passthrough() -> None:
    out = build_consent_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1/cb",
        provider="gmail",
        extra_params={"login_hint": "alice@example.com"},
    )
    parsed = dict(urllib.parse.parse_qsl(out.url.split("?", 1)[1]))
    assert parsed["login_hint"] == "alice@example.com"


def test_build_consent_url_rejects_empty_client_id() -> None:
    with pytest.raises(ValueError, match="client_id"):
        build_consent_url(client_id="", redirect_uri="http://x", provider="gmail")


def test_build_consent_url_rejects_empty_redirect_uri() -> None:
    with pytest.raises(ValueError, match="redirect_uri"):
        build_consent_url(client_id="cid", redirect_uri="", provider="gmail")


def test_build_consent_url_rejects_unresolvable_provider() -> None:
    with pytest.raises(ValueError, match="auth endpoint"):
        build_consent_url(
            client_id="cid",
            redirect_uri="http://127.0.0.1/cb",
            provider="madeup-provider",
        )


# ================================================================ verify_state


def test_verify_state_round_trip_succeeds() -> None:
    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    claims = verify_state(out.state)
    assert isinstance(claims, StateClaims)
    assert claims.provider == "gmail"
    assert claims.nonce


def test_verify_state_provider_match_succeeds() -> None:
    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    claims = verify_state(out.state, expected_provider="gmail")
    assert claims.provider == "gmail"


def test_verify_state_provider_mismatch_raises_generic_error() -> None:
    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    with pytest.raises(ValueError, match="invalid state"):
        verify_state(out.state, expected_provider="office365")


def test_verify_state_tampered_payload_fails() -> None:
    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    body, sig = out.state.split(".")
    # Flip a single character in the body — sig won't match.
    flipped_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    bad_state = f"{flipped_body}.{sig}"
    with pytest.raises(ValueError, match="invalid state"):
        verify_state(bad_state)


def test_verify_state_tampered_signature_fails() -> None:
    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    body, sig = out.state.split(".")
    bad_state = f"{body}.{'A' * len(sig)}"
    with pytest.raises(ValueError, match="invalid state"):
        verify_state(bad_state)


def test_verify_state_expired_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens older than STATE_MAX_AGE_S are rejected."""

    monkeypatch.setenv("TARS_OAUTH_STATE_MAX_AGE_S", "1.0")
    out = build_consent_url(
        client_id="cid",
        redirect_uri="http://127.0.0.1/cb",
        provider="gmail",
        issued_at=time.time() - 5.0,
    )
    with pytest.raises(ValueError, match="invalid state"):
        verify_state(out.state)


def test_verify_state_rejects_garbage_input() -> None:
    for garbage in ("", "no-dot", "....", "a.b", "x.YWJj"):
        with pytest.raises(ValueError, match="invalid state"):
            verify_state(garbage)


def test_state_secret_change_invalidates_old_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rotating ``TARS_OAUTH_STATE_SECRET`` invalidates pending consents
    — useful operator escape hatch when a state secret leaks."""

    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    # Rotate the secret as if the operator regenerated it.
    monkeypatch.setenv("TARS_OAUTH_STATE_SECRET", "rotated-secret")
    _reset_state_secret_for_tests()
    with pytest.raises(ValueError, match="invalid state"):
        verify_state(out.state)


# ============================================ exchange_authorization_code


def _stub_post_form(monkeypatch, response: Any):
    """Patch ``oauth_consent._post_form`` to return ``response`` (or
    raise it if it's an Exception). Returns a counter dict."""

    calls = {"count": 0, "url": None, "data": None}

    def fake(url: str, data: dict[str, str], *, timeout_s: float):
        calls["count"] += 1
        calls["url"] = url
        calls["data"] = dict(data)
        if isinstance(response, Exception):
            raise response
        return dict(response)

    monkeypatch.setattr(consent_mod, "_post_form", fake)
    return calls


def test_exchange_authorization_code_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_post_form(
        monkeypatch,
        {
            "access_token": "at-1",
            "refresh_token": "rt-1",
            "expires_in": 3600,
            "scope": "https://mail.google.com/",
            "token_type": "Bearer",
        },
    )
    res = exchange_authorization_code(
        code="auth-code-1",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        client_secret="sec",
        provider="gmail",
    )
    assert res.ok is True
    assert res.refresh_token == "rt-1"
    assert res.access_token == "at-1"
    assert res.expires_in == 3600.0
    assert res.scope == "https://mail.google.com/"
    assert res.token_type == "Bearer"
    # Verify the token endpoint was hit with the right body shape.
    assert calls["count"] == 1
    assert calls["url"] == "https://oauth2.googleapis.com/token"
    body = calls["data"]
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "auth-code-1"
    assert body["code_verifier"] == "v" * 43
    assert body["redirect_uri"] == "http://127.0.0.1/cb"
    assert body["client_id"] == "cid"
    assert body["client_secret"] == "sec"


def test_exchange_authorization_code_omits_client_secret_for_public_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Microsoft public clients (mobile, native) don't have a client
    secret; the helper must not send an empty string (would
    invalidate the request)."""

    calls = _stub_post_form(
        monkeypatch,
        {"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
    )
    res = exchange_authorization_code(
        code="auth-code-1",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="office365",
        tenant="common",
    )
    assert res.ok is True
    assert "client_secret" not in calls["data"]


def test_exchange_authorization_code_resolves_office365_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_post_form(
        monkeypatch,
        {"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
    )
    exchange_authorization_code(
        code="c",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="office365",
        tenant="contoso",
    )
    assert calls["url"] == (
        "https://login.microsoftonline.com/contoso/oauth2/v2.0/token"
    )


def test_exchange_authorization_code_explicit_token_url_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_post_form(
        monkeypatch,
        {"access_token": "at-1", "refresh_token": "rt-1", "expires_in": 3600},
    )
    exchange_authorization_code(
        code="c",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",  # would resolve to googleapis
        token_url="https://example.test/token",
    )
    assert calls["url"] == "https://example.test/token"


def test_exchange_authorization_code_no_refresh_token_still_returns_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gmail without ``access_type=offline``: provider returns just an
    access token. Helper still returns ok=True so the operator sees
    the consent worked, but ``refresh_token`` is None (and a warning
    is logged)."""

    _stub_post_form(
        monkeypatch, {"access_token": "at-only", "expires_in": 3600}
    )
    res = exchange_authorization_code(
        code="c",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",
    )
    assert res.ok is True
    assert res.access_token == "at-only"
    assert res.refresh_token is None


def test_exchange_authorization_code_propagates_oauth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_post_form(
        monkeypatch,
        {
            "error": "invalid_grant",
            "error_description": "code already used",
        },
    )
    res = exchange_authorization_code(
        code="reused",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",
    )
    assert res.ok is False
    assert res.reason == "oauth_error"
    assert "invalid_grant" in (res.error or "")
    assert "code already used" in (res.error or "")


def test_exchange_authorization_code_handles_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_post_form(
        monkeypatch, urllib.error.URLError("connection refused")
    )
    res = exchange_authorization_code(
        code="c",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",
    )
    assert res.ok is False
    assert res.reason == "transport_error"
    assert "connection refused" in (res.error or "")


def test_exchange_authorization_code_handles_decode_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_post_form(monkeypatch, json.JSONDecodeError("expecting", "", 0))
    res = exchange_authorization_code(
        code="c",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",
    )
    assert res.ok is False
    assert res.reason == "decode_error"


def test_exchange_authorization_code_rejects_missing_code() -> None:
    res = exchange_authorization_code(
        code="",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",
    )
    assert res.ok is False
    assert res.reason == "missing_code"


def test_exchange_authorization_code_rejects_missing_verifier() -> None:
    res = exchange_authorization_code(
        code="c",
        code_verifier="",
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="gmail",
    )
    assert res.ok is False
    assert res.reason == "missing_verifier"


def test_exchange_authorization_code_rejects_unresolvable_provider() -> None:
    res = exchange_authorization_code(
        code="c",
        code_verifier="v" * 43,
        redirect_uri="http://127.0.0.1/cb",
        client_id="cid",
        provider="madeup",
    )
    assert res.ok is False
    assert res.reason == "missing_token_url"


def test_token_exchange_result_to_dict_drops_none_fields() -> None:
    """Serialising for the HTTP / cockpit surface should not leak
    ``null`` fields the caller didn't ask for."""

    ok_res = TokenExchangeResult(
        ok=True, refresh_token="rt", access_token="at", expires_in=3600
    )
    d = ok_res.to_dict()
    assert "scope" not in d  # scope was None
    assert "token_type" not in d
    assert "reason" not in d
    assert d["refresh_token"] == "rt"

    err_res = TokenExchangeResult(ok=False, reason="oauth_error", error="bad")
    d2 = err_res.to_dict()
    assert d2 == {"ok": False, "reason": "oauth_error", "error": "bad"}


# ===================================================== integration sanity


def test_consent_url_state_can_be_round_tripped_after_url_parse() -> None:
    """The state parameter survives the ``urlencode`` → browser →
    ``parse_qs`` round-trip the operator's browser performs."""

    out = build_consent_url(
        client_id="cid", redirect_uri="http://127.0.0.1/cb", provider="gmail"
    )
    parsed = dict(urllib.parse.parse_qsl(out.url.split("?", 1)[1]))
    state_after = parsed["state"]
    claims = verify_state(state_after, expected_provider="gmail")
    assert claims.provider == "gmail"
