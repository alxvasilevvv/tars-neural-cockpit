"""OAuth2 authorization-code (initial consent) flow for SMTP outbound.

Companion to :mod:`backend.core.domains.packs.business.oauth` (the
refresh-token flow). That module assumes the operator has already
provisioned a refresh token and stuffed it into
``TARS_SMTP_OAUTH_REFRESH_TOKEN``; this module is the missing piece
that *produces* the refresh token in the first place.

Flow (RFC 6749 §4.1 + RFC 7636 PKCE for native clients):

1. ``build_consent_url(...)`` — returns a ``ConsentURL`` carrying the
   provider's authorization endpoint URL with ``client_id``,
   ``redirect_uri``, ``scope``, signed ``state``, and a PKCE
   ``code_challenge``. The matching ``code_verifier`` is in
   ``ConsentURL.code_verifier`` and MUST be retained until the
   callback (operator stashes it in vault, or the runner keeps it
   in process for a short-lived consent server).
2. Operator opens the URL in their browser, logs in, grants the
   requested scopes, and is redirected back to ``redirect_uri`` with
   ``?code=...&state=...``.
3. ``verify_state(state, expected_provider=None) -> StateClaims`` —
   constant-time HMAC-SHA256 verification. Fails on tamper, fails
   when the provider doesn't match the URL the operator clicked.
4. ``exchange_authorization_code(code, code_verifier, redirect_uri,
   provider=...)`` — POSTs the code + verifier to the token endpoint
   and returns ``{ok, refresh_token, access_token, expires_in,
   scope, token_type}``. The operator persists the refresh_token
   into ``TARS_SMTP_OAUTH_REFRESH_TOKEN`` and the SMTP path picks
   it up from the next request onward.

Stdlib-only on purpose: no ``requests``, no ``msal``, no
``google-auth-oauthlib``. The flow is just two HTTP requests and a
URL builder; pulling in 50 MB of OAuth helper code for that is
overkill for a sidecar that already commits to ``urllib`` for the
refresh side.

State signing:

- ``HMAC-SHA256(state_secret, payload)`` where ``state_secret`` comes
  from ``TARS_OAUTH_STATE_SECRET`` (or a process-lifetime random
  fallback so dev installs don't have to set anything).
- Payload encodes ``provider`` + ``nonce`` + ``issued_at`` so a stale
  consent URL gets refused after ``STATE_MAX_AGE_S`` (default 600 s
  = 10 min, configurable via ``TARS_OAUTH_STATE_MAX_AGE_S``).
- Stateless: TARS doesn't need a database row per pending consent —
  the signed token IS the pending state.

Provider shorthand mirrors ``oauth.py``:

- ``gmail`` / ``google`` — Google's auth + token endpoints, default
  scope ``https://mail.google.com/`` (full Gmail SMTP scope), uses
  ``access_type=offline`` + ``prompt=consent`` so a refresh token
  always comes back.
- ``office365`` / ``outlook`` / ``o365`` — Microsoft v2.0 endpoints
  on the configured tenant (default ``common``), default scope
  includes ``offline_access`` so a refresh token always comes back.

HTTP surface lives in :mod:`web_extras.routers.oauth_consent`
(``POST /api/oauth/smtp/{start,exchange}``). The
:func:`persist_refresh_token` helper below auto-writes the freshly
minted token into the vault (Keychain on macOS, env fallback
elsewhere) so the operator's only step is "click consent, paste env
line if you're on Linux".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from backend.core.vault import (
    SecretRef,
    get_secret,
    set_secret,
)


log = logging.getLogger("tars.business.smtp.oauth_consent")


# Vault key the SMTP path reads in `oauth.py` — keep these constants
# as the single source of truth so a rename only edits one line.
VAULT_KEY_REFRESH_TOKEN = "TARS_SMTP_OAUTH_REFRESH_TOKEN"
VAULT_KEY_CLIENT_ID = "TARS_SMTP_OAUTH_CLIENT_ID"
VAULT_KEY_CLIENT_SECRET = "TARS_SMTP_OAUTH_CLIENT_SECRET"
VAULT_KEY_PROVIDER = "TARS_SMTP_PROVIDER"
VAULT_KEY_TENANT = "TARS_SMTP_OAUTH_TENANT"


# Provider shorthand → (auth endpoint, token endpoint template). Same
# keys as ``_PROVIDER_TOKEN_URLS`` in ``oauth.py``; keep them in sync.
_PROVIDER_AUTH_URLS: dict[str, str] = {
    "gmail": "https://accounts.google.com/o/oauth2/v2/auth",
    "googlemail": "https://accounts.google.com/o/oauth2/v2/auth",
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
    "office365": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
    "o365": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
    "outlook": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
}

_PROVIDER_TOKEN_URLS: dict[str, str] = {
    "gmail": "https://oauth2.googleapis.com/token",
    "googlemail": "https://oauth2.googleapis.com/token",
    "google": "https://oauth2.googleapis.com/token",
    "office365": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    "o365": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    "outlook": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
}

# Default scopes per provider — chosen so the resulting refresh token
# can do SMTP-only sending and nothing else (least-privilege).
_PROVIDER_DEFAULT_SCOPES: dict[str, str] = {
    "gmail": "https://mail.google.com/",
    "googlemail": "https://mail.google.com/",
    "google": "https://mail.google.com/",
    "office365": "https://outlook.office.com/SMTP.Send offline_access",
    "o365": "https://outlook.office.com/SMTP.Send offline_access",
    "outlook": "https://outlook.office.com/SMTP.Send offline_access",
}


STATE_MAX_AGE_S = 600.0


# -------------------------------------------------------------------- helpers


def _b64url(data: bytes) -> str:
    """Base64URL without padding (RFC 7636)."""

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _provider_url(
    table: dict[str, str], provider: str | None, tenant: str | None
) -> str | None:
    if not provider:
        return None
    template = table.get(provider.strip().lower())
    if not template:
        return None
    return template.replace(
        "{tenant}", (tenant or "common").strip() or "common"
    )


def _state_secret() -> bytes:
    """Long-lived secret used to sign state tokens.

    Resolution order:
    1. ``TARS_OAUTH_STATE_SECRET`` from vault.
    2. ``TARS_OAUTH_STATE_SECRET`` from env.
    3. Process-lifetime random fallback so dev installs don't have to
       set anything (state tokens become invalid after restart, which
       is fine for the operator's interactive flow).
    """

    cached = _STATE_SECRET_CACHE.get("secret")
    if cached is not None:
        return cached
    raw = (
        get_secret("TARS_OAUTH_STATE_SECRET")
        or os.getenv("TARS_OAUTH_STATE_SECRET")
    )
    if raw and isinstance(raw, str) and raw.strip():
        secret = raw.strip().encode("utf-8")
    else:
        secret = secrets.token_bytes(32)
    _STATE_SECRET_CACHE["secret"] = secret
    return secret


_STATE_SECRET_CACHE: dict[str, bytes] = {}


def _reset_state_secret_for_tests() -> None:
    """Drop the cached state secret (test fixtures only)."""

    _STATE_SECRET_CACHE.pop("secret", None)


def _state_max_age() -> float:
    raw = (
        get_secret("TARS_OAUTH_STATE_MAX_AGE_S")
        or os.getenv("TARS_OAUTH_STATE_MAX_AGE_S")
    )
    if raw is None:
        return STATE_MAX_AGE_S
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return STATE_MAX_AGE_S
    return v if v > 0 else STATE_MAX_AGE_S


# ----------------------------------------------------------- data shapes


@dataclass(frozen=True)
class ConsentURL:
    """Result of :func:`build_consent_url` — the URL the operator
    visits and the matching PKCE verifier they have to retain until
    the callback hits."""

    url: str
    state: str
    code_verifier: str
    provider: str | None


@dataclass(frozen=True)
class StateClaims:
    """Decoded + verified state payload."""

    provider: str | None
    nonce: str
    issued_at: float


@dataclass(frozen=True)
class TokenExchangeResult:
    """Result of :func:`exchange_authorization_code`. ``ok=False``
    cases carry ``reason`` + ``error`` and never raise."""

    ok: bool
    refresh_token: str | None = None
    access_token: str | None = None
    expires_in: float | None = None
    scope: str | None = None
    token_type: str | None = None
    reason: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok}
        if self.refresh_token is not None:
            out["refresh_token"] = self.refresh_token
        if self.access_token is not None:
            out["access_token"] = self.access_token
        if self.expires_in is not None:
            out["expires_in"] = self.expires_in
        if self.scope is not None:
            out["scope"] = self.scope
        if self.token_type is not None:
            out["token_type"] = self.token_type
        if self.reason is not None:
            out["reason"] = self.reason
        if self.error is not None:
            out["error"] = self.error
        return out


# ----------------------------------------------------------- state tokens


def _sign_state(payload: dict[str, Any]) -> str:
    """Encode + HMAC-SHA256 sign a payload. Returns ``<b64body>.<b64sig>``."""

    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body_b64 = _b64url(body)
    sig = hmac.new(_state_secret(), body_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{body_b64}.{_b64url(sig)}"


def verify_state(
    state: str, *, expected_provider: str | None = None, now: float | None = None
) -> StateClaims:
    """Verify a state token: HMAC tag, freshness, optional provider match.

    Raises :class:`ValueError` on any mismatch. The error message is
    intentionally generic ("invalid state") to avoid leaking which
    check failed — the OAuth callback handler should log the inner
    detail server-side and surface a constant-time-friendly response
    to the operator.
    """

    if not state or "." not in state:
        raise ValueError("invalid state")
    body_b64, sig_b64 = state.rsplit(".", 1)
    expected_sig = hmac.new(
        _state_secret(), body_b64.encode("ascii"), hashlib.sha256
    ).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
    except (ValueError, TypeError, base64.binascii.Error):  # type: ignore[attr-defined]
        raise ValueError("invalid state")
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("invalid state")
    try:
        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        raise ValueError("invalid state")
    if not isinstance(payload, dict):
        raise ValueError("invalid state")
    issued_at = payload.get("iat")
    if not isinstance(issued_at, (int, float)):
        raise ValueError("invalid state")
    ts = now if now is not None else time.time()
    if ts - float(issued_at) > _state_max_age():
        raise ValueError("invalid state")
    provider = payload.get("provider")
    if expected_provider is not None and provider != expected_provider:
        raise ValueError("invalid state")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise ValueError("invalid state")
    return StateClaims(
        provider=str(provider) if isinstance(provider, str) else None,
        nonce=nonce,
        issued_at=float(issued_at),
    )


# ----------------------------------------------------------- consent URL


def build_consent_url(
    *,
    client_id: str,
    redirect_uri: str,
    provider: str | None = None,
    auth_url: str | None = None,
    scope: str | None = None,
    tenant: str | None = None,
    extra_params: Mapping[str, str] | None = None,
    nonce: str | None = None,
    issued_at: float | None = None,
) -> ConsentURL:
    """Build the authorization URL the operator visits.

    Resolves the auth endpoint from explicit override → provider
    shorthand. Generates a fresh PKCE verifier (43-byte URL-safe
    random → SHA-256 challenge per RFC 7636) and a signed state
    token (HMAC-SHA256). Provider-specific quirks are applied
    automatically: Google needs ``access_type=offline`` +
    ``prompt=consent`` so a refresh token comes back on every consent.

    Raises :class:`ValueError` on missing/invalid ``client_id``,
    ``redirect_uri``, or unresolvable auth endpoint — bad config
    should fail loudly here, not later when the browser hits a 404.
    """

    if not client_id or not isinstance(client_id, str):
        raise ValueError("client_id is required")
    if not redirect_uri or not isinstance(redirect_uri, str):
        raise ValueError("redirect_uri is required")

    resolved_auth = auth_url or _provider_url(_PROVIDER_AUTH_URLS, provider, tenant)
    if not resolved_auth:
        raise ValueError(
            f"unable to resolve auth endpoint: provider={provider!r}, "
            f"tenant={tenant!r}, auth_url override missing"
        )

    resolved_scope = scope
    if resolved_scope is None and provider:
        resolved_scope = _PROVIDER_DEFAULT_SCOPES.get(provider.strip().lower())

    code_verifier = _b64url(secrets.token_bytes(32))
    code_challenge = _b64url(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    )
    nonce_value = nonce or _b64url(secrets.token_bytes(16))
    iat = issued_at if issued_at is not None else time.time()
    state = _sign_state(
        {
            "provider": provider,
            "nonce": nonce_value,
            "iat": float(iat),
        }
    )

    params: dict[str, str] = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    if resolved_scope:
        params["scope"] = resolved_scope

    # Provider-specific tweaks so the consent dance returns a refresh
    # token. Without these the operator's browser tab silently completes
    # the flow but the token endpoint hands back access_token only.
    pl = (provider or "").strip().lower()
    if pl in {"gmail", "google", "googlemail"}:
        params["access_type"] = "offline"
        # `prompt=consent` forces re-issuance of refresh token even if
        # the operator already granted scopes for this client_id —
        # otherwise re-authing the same account silently drops the
        # refresh field.
        params["prompt"] = "consent"

    if extra_params:
        for k, v in extra_params.items():
            if v is None:
                continue
            params[str(k)] = str(v)

    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{resolved_auth}?{qs}"
    return ConsentURL(
        url=url,
        state=state,
        code_verifier=code_verifier,
        provider=provider,
    )


# --------------------------------------------------------- code exchange


def _post_form(
    url: str, data: dict[str, str], *, timeout_s: float
) -> dict[str, Any]:
    """Stdlib urlopen + form-encoded POST. Returns parsed JSON.

    Mirrors the helper in ``oauth.py`` so refresh + consent share the
    same transport surface (same timeout semantics, same error
    propagation, same Accept header).
    """

    body = urllib.parse.urlencode(
        {k: v for k, v in data.items() if v is not None}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw or "{}")


def exchange_authorization_code(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str | None = None,
    provider: str | None = None,
    token_url: str | None = None,
    tenant: str | None = None,
    timeout_s: float = 10.0,
) -> TokenExchangeResult:
    """Swap an authorization code for refresh + access tokens.

    Returns a :class:`TokenExchangeResult`. Never raises — transport
    failures, JSON decode errors, and OAuth ``error``/`error_description``
    responses all return ``ok=False`` so the caller can surface a
    structured error to the operator.

    The returned ``refresh_token`` is what goes into
    ``TARS_SMTP_OAUTH_REFRESH_TOKEN`` (vault) so the
    :mod:`backend.core.domains.packs.business.oauth` refresh path
    picks it up on the next request. ``access_token`` is also
    returned so the operator can sanity-check the consent worked
    end-to-end without waiting for the next email send.
    """

    if not code:
        return TokenExchangeResult(ok=False, reason="missing_code", error="code is required")
    if not code_verifier:
        return TokenExchangeResult(
            ok=False, reason="missing_verifier", error="code_verifier is required"
        )

    resolved_token_url = token_url or _provider_url(
        _PROVIDER_TOKEN_URLS, provider, tenant
    )
    if not resolved_token_url:
        return TokenExchangeResult(
            ok=False,
            reason="missing_token_url",
            error=(
                f"unable to resolve token endpoint: provider={provider!r}, "
                f"tenant={tenant!r}, token_url override missing"
            ),
        )

    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    try:
        response = _post_form(resolved_token_url, payload, timeout_s=timeout_s)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        log.warning("oauth consent transport failed: %s", exc)
        return TokenExchangeResult(
            ok=False, reason="transport_error", error=str(exc)
        )
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("oauth consent decode failed: %s", exc)
        return TokenExchangeResult(
            ok=False, reason="decode_error", error=str(exc)
        )

    err = response.get("error") if isinstance(response, dict) else None
    if err:
        desc = response.get("error_description") or ""
        return TokenExchangeResult(
            ok=False,
            reason="oauth_error",
            error=f"{err} {desc}".strip(),
        )

    access_token = response.get("access_token") if isinstance(response, dict) else None
    if not access_token:
        return TokenExchangeResult(
            ok=False,
            reason="no_access_token",
            error=str(response)[:200],
        )

    refresh_token = response.get("refresh_token")
    if not refresh_token:
        # The provider returned an access token but no refresh token
        # — for Google this means the consent flow forgot
        # `access_type=offline + prompt=consent`; for Microsoft it
        # means the requested scopes didn't include `offline_access`.
        # Surface it explicitly so the operator knows the consent
        # has to be re-done with the right params.
        log.warning(
            "oauth consent: access_token returned but no refresh_token "
            "(provider=%s); operator must re-consent with refresh-enabling params.",
            provider,
        )

    expires_in = response.get("expires_in")
    try:
        expires_in_f = float(expires_in) if expires_in is not None else None
    except (TypeError, ValueError):
        expires_in_f = None

    return TokenExchangeResult(
        ok=True,
        refresh_token=str(refresh_token) if refresh_token else None,
        access_token=str(access_token),
        expires_in=expires_in_f,
        scope=str(response.get("scope")) if response.get("scope") else None,
        token_type=str(response.get("token_type")) if response.get("token_type") else None,
    )


# ============================================================ persistence


@dataclass(frozen=True)
class PersistedConsent:
    """Result of :func:`persist_refresh_token` — list of vault keys the
    helper wrote and where each one landed (``"keychain"`` / ``"env"``).
    The returned shape is intentionally value-free so logs / HTTP
    responses don't leak secret material."""

    persisted: tuple[SecretRef, ...]
    skipped: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "persisted": [
                {"key": ref.key, "source": ref.source}
                for ref in self.persisted
            ],
            "skipped": list(self.skipped),
        }


def persist_refresh_token(
    result: TokenExchangeResult,
    *,
    client_id: str,
    client_secret: str | None = None,
    provider: str | None = None,
    tenant: str | None = None,
) -> PersistedConsent:
    """Write the freshly-minted credentials into the vault.

    Skips any field that's empty / None so an operator who already had
    one piece set (e.g. ``TARS_SMTP_PROVIDER`` in ``.env``) doesn't
    have it overwritten unnecessarily. Tenant defaults to ``"common"``
    upstream and is only persisted when explicitly provided so the
    Keychain entry stays absent for default Microsoft consumer flow.

    Returns a :class:`PersistedConsent` describing what landed where —
    callers (HTTP handler / CLI helper) surface this so the operator
    sees per-key destinations without ever seeing the values
    themselves.

    Raises :class:`ValueError` only when ``result.ok=False`` — refusing
    to persist a failed exchange is a defensive guard against partial
    writes (an operator must explicitly re-run the consent dance).
    """

    if not result.ok:
        raise ValueError(
            "persist_refresh_token: refusing to persist a failed "
            f"TokenExchangeResult (reason={result.reason!r})"
        )
    if not result.refresh_token:
        # Without a refresh token there's nothing durable to write —
        # the access_token expires in ~1h and is meaningless to
        # persist alone. Surface the skip explicitly.
        return PersistedConsent(persisted=(), skipped=(VAULT_KEY_REFRESH_TOKEN,))

    persisted: list[SecretRef] = []
    skipped: list[str] = []

    persisted.append(set_secret(VAULT_KEY_REFRESH_TOKEN, result.refresh_token))

    # Mirror the operator-facing values that the SMTP path reads on
    # every send — without these, the refresh exchange in oauth.py
    # would not know which client / endpoint to talk to.
    if client_id:
        persisted.append(set_secret(VAULT_KEY_CLIENT_ID, client_id))
    else:
        skipped.append(VAULT_KEY_CLIENT_ID)

    if client_secret:
        persisted.append(set_secret(VAULT_KEY_CLIENT_SECRET, client_secret))
    else:
        skipped.append(VAULT_KEY_CLIENT_SECRET)

    if provider:
        persisted.append(set_secret(VAULT_KEY_PROVIDER, provider))
    else:
        skipped.append(VAULT_KEY_PROVIDER)

    # Only write tenant when it's non-default — keeps the Keychain
    # tidy for the common Gmail / consumer-MS case where the default
    # ``common`` already covers the request.
    if tenant and tenant.strip().lower() != "common":
        persisted.append(set_secret(VAULT_KEY_TENANT, tenant))
    else:
        skipped.append(VAULT_KEY_TENANT)

    return PersistedConsent(
        persisted=tuple(persisted), skipped=tuple(skipped)
    )
