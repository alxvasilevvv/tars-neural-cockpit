"""OAuth2 refresh-token flow for SMTP outbound (continuation of #40).

PR #40 added SASL XOAUTH2 to ``smtp.py`` but expected an externally-
refreshed access token sitting in ``TARS_SMTP_OAUTH_TOKEN``. That works
for one-shot tests (paste a fresh token, send an email), but real
deployments need automatic refresh — Gmail tokens expire after one
hour, Microsoft after roughly the same.

This module is the smallest possible delta on top of #40: stdlib-only
(no ``requests`` / ``requests-oauthlib`` / ``msal``), in-memory token
cache, refresh ~5 minutes before the access token expires.

Design:

- Vault keys (any of the ``TARS_`` / unprefixed pair, env fallback):
  - ``TARS_SMTP_OAUTH_REFRESH_TOKEN`` — long-lived refresh token.
  - ``TARS_SMTP_OAUTH_CLIENT_ID`` — OAuth app client id.
  - ``TARS_SMTP_OAUTH_CLIENT_SECRET`` — OAuth app client secret
    (Gmail: required; Microsoft public clients: empty string OK).
  - ``TARS_SMTP_OAUTH_TOKEN_URL`` — explicit token endpoint
    (overrides the provider-shorthand mapping).
  - ``TARS_SMTP_OAUTH_TENANT`` — Microsoft tenant id; defaults to
    ``common`` for multi-tenant apps.
- When all three (refresh-token, client-id, token-url) are present,
  :func:`get_fresh_access_token` exchanges the refresh token for a
  new access token via the OAuth2 token endpoint
  (``grant_type=refresh_token``).
- Cached in-process: subsequent ``send_email`` calls reuse the
  cached access token until it's within ``REFRESH_LEAD_S`` of expiry
  (default 300 s). The cache is keyed on ``(client_id, refresh_token,
  token_url)`` so multiple providers can coexist in the same process.
- Refresh failures fall back to whatever is in
  ``TARS_SMTP_OAUTH_TOKEN`` (the manual paste path from #40), so
  bringing this module up doesn't regress the existing flow.

Provider shorthand (mirrors ``smtp.py`` ``_PROVIDERS``):

- ``gmail`` → ``https://oauth2.googleapis.com/token``.
- ``office365`` / ``outlook`` →
  ``https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token``.

Other providers can override with ``TARS_SMTP_OAUTH_TOKEN_URL``.

Out of scope (separate slice):

- Persisting the refreshed access token back into the vault. The
  in-memory cache is sufficient as long as TARS lives in one process
  per machine; a future slot can wire vault write-back when we add a
  vault adapter that supports updates.
- Initial consent / authorization-code flow. This module assumes the
  refresh token is already provisioned (operator does the consent
  dance once via the cloud provider's helper).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from backend.core.vault import get_secret


log = logging.getLogger("tars.business.smtp.oauth")


REFRESH_LEAD_S = 300.0  # refresh 5 min before expiry


# Provider shorthand → token endpoint template. ``{tenant}`` is
# substituted from TARS_SMTP_OAUTH_TENANT (default "common"). Add
# more entries here as we onboard providers.
_PROVIDER_TOKEN_URLS: dict[str, str] = {
    "gmail": "https://oauth2.googleapis.com/token",
    "googlemail": "https://oauth2.googleapis.com/token",
    "google": "https://oauth2.googleapis.com/token",
    "office365": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    "o365": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    "outlook": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
}


@dataclass(frozen=True)
class OAuthRefreshConfig:
    """Refresh-token credentials read from the vault.

    ``token_url`` is resolved from explicit override, then provider
    shorthand, then ``None`` when nothing matches (the caller must
    treat the missing URL as "no refresh available").
    """

    refresh_token: str
    client_id: str
    client_secret: str | None
    token_url: str
    scope: str | None
    tenant: str | None
    provider: str | None

    @classmethod
    def load(
        cls, *, provider: str | None = None
    ) -> "OAuthRefreshConfig | None":
        refresh_token = (
            get_secret("TARS_SMTP_OAUTH_REFRESH_TOKEN")
            or get_secret("SMTP_OAUTH_REFRESH_TOKEN")
            or os.getenv("SMTP_OAUTH_REFRESH_TOKEN")
        )
        if not refresh_token:
            return None
        client_id = (
            get_secret("TARS_SMTP_OAUTH_CLIENT_ID")
            or get_secret("SMTP_OAUTH_CLIENT_ID")
            or os.getenv("SMTP_OAUTH_CLIENT_ID")
        )
        if not client_id:
            return None
        client_secret = (
            get_secret("TARS_SMTP_OAUTH_CLIENT_SECRET")
            or get_secret("SMTP_OAUTH_CLIENT_SECRET")
            or os.getenv("SMTP_OAUTH_CLIENT_SECRET")
        )
        scope = (
            get_secret("TARS_SMTP_OAUTH_SCOPE")
            or get_secret("SMTP_OAUTH_SCOPE")
            or os.getenv("SMTP_OAUTH_SCOPE")
        )
        tenant = (
            get_secret("TARS_SMTP_OAUTH_TENANT")
            or get_secret("SMTP_OAUTH_TENANT")
            or os.getenv("SMTP_OAUTH_TENANT")
            or "common"
        )
        explicit = (
            get_secret("TARS_SMTP_OAUTH_TOKEN_URL")
            or get_secret("SMTP_OAUTH_TOKEN_URL")
            or os.getenv("SMTP_OAUTH_TOKEN_URL")
        )
        token_url = explicit or _provider_token_url(provider, tenant)
        if not token_url:
            return None
        return cls(
            refresh_token=str(refresh_token).strip(),
            client_id=str(client_id).strip(),
            client_secret=(
                str(client_secret).strip()
                if isinstance(client_secret, str)
                else None
            ),
            token_url=str(token_url).strip(),
            scope=str(scope).strip() if isinstance(scope, str) else None,
            tenant=str(tenant).strip() if isinstance(tenant, str) else None,
            provider=provider,
        )


def _provider_token_url(provider: str | None, tenant: str | None) -> str | None:
    if not provider:
        return None
    template = _PROVIDER_TOKEN_URLS.get(provider.strip().lower())
    if not template:
        return None
    return template.replace("{tenant}", (tenant or "common").strip() or "common")


# ---------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float
    refreshed_at: float


_CACHE: dict[str, _CachedToken] = {}
_CACHE_LOCK = threading.Lock()


def _cache_key(cfg: OAuthRefreshConfig) -> str:
    return f"{cfg.client_id}|{cfg.token_url}|{cfg.refresh_token[:20]}"


def reset_oauth_cache() -> None:
    """Test helper — drop every cached token."""

    with _CACHE_LOCK:
        _CACHE.clear()


def cache_size() -> int:
    """Test helper — number of cached tokens."""

    with _CACHE_LOCK:
        return len(_CACHE)


# ---------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------


def _post_form(
    url: str, data: dict[str, str], *, timeout_s: float
) -> dict[str, Any]:
    """Stdlib urlopen + form-encoded POST. Returns parsed JSON.

    Raises :class:`urllib.error.URLError` /
    :class:`urllib.error.HTTPError` on transport / HTTP failures, and
    :class:`json.JSONDecodeError` on non-JSON responses; the caller
    should catch and convert into a structured error.
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


def _exchange_refresh_token_sync(
    cfg: OAuthRefreshConfig,
    *,
    timeout_s: float,
) -> _CachedToken:
    payload: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": cfg.refresh_token,
        "client_id": cfg.client_id,
    }
    if cfg.client_secret:
        payload["client_secret"] = cfg.client_secret
    if cfg.scope:
        payload["scope"] = cfg.scope
    response = _post_form(cfg.token_url, payload, timeout_s=timeout_s)
    access_token = response.get("access_token")
    if not access_token:
        # Surface the OAuth error verbatim — providers return
        # ``error`` + ``error_description`` per RFC 6749.
        err = response.get("error") or "no_access_token"
        desc = response.get("error_description") or ""
        raise RuntimeError(
            f"oauth_refresh_failed: {err} {desc}".strip()
        )
    expires_in = response.get("expires_in")
    try:
        expires_in_f = float(expires_in) if expires_in is not None else 3600.0
    except (TypeError, ValueError):
        expires_in_f = 3600.0
    now = time.time()
    return _CachedToken(
        access_token=str(access_token),
        expires_at=now + expires_in_f,
        refreshed_at=now,
    )


def get_fresh_access_token(
    cfg: OAuthRefreshConfig,
    *,
    force_refresh: bool = False,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Return a still-valid access token, refreshing if needed.

    Returns
    ``{ok, access_token, source, expires_in, refreshed_at, cached}``:

    - ``source`` is ``"cache"`` when the cached token was reused,
      ``"refresh"`` when an exchange happened.
    - ``expires_in`` is seconds until the token expires (clamped to
      0 for already-expired tokens).
    - ``cached=True`` means the response came straight from
      ``_CACHE`` without a network call.

    On failure returns
    ``{ok: False, reason, error, source: 'refresh'}`` and *never*
    raises, so the SMTP path can fall back to the manual
    ``TARS_SMTP_OAUTH_TOKEN`` paste flow.
    """

    key = _cache_key(cfg)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if (
        not force_refresh
        and cached is not None
        and cached.expires_at - now > REFRESH_LEAD_S
    ):
        return {
            "ok": True,
            "access_token": cached.access_token,
            "source": "cache",
            "expires_in": max(0.0, cached.expires_at - now),
            "refreshed_at": cached.refreshed_at,
            "cached": True,
        }
    try:
        fresh = _exchange_refresh_token_sync(cfg, timeout_s=timeout_s)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        log.warning("oauth refresh transport failed: %s", exc)
        return {
            "ok": False,
            "reason": "transport_error",
            "error": str(exc),
            "source": "refresh",
        }
    except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
        log.warning("oauth refresh decode failed: %s", exc)
        return {
            "ok": False,
            "reason": "decode_error",
            "error": str(exc),
            "source": "refresh",
        }
    with _CACHE_LOCK:
        _CACHE[key] = fresh
    return {
        "ok": True,
        "access_token": fresh.access_token,
        "source": "refresh",
        "expires_in": max(0.0, fresh.expires_at - now),
        "refreshed_at": fresh.refreshed_at,
        "cached": False,
    }
