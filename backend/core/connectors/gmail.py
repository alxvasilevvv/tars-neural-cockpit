"""Gmail OAuth + read connector (Wave 91).

Replaces the empty-stub ``_fetch_gmail`` from
``backend/core/domains/packs/business/awareness.py``. Uses Google's
OAuth 2.0 (offline access, refresh-token flow) and the Gmail REST API
(``gmail.googleapis.com/gmail/v1/users/me``).

Scopes: ``https://www.googleapis.com/auth/gmail.readonly`` -- read-only
on purpose; the writeable scopes graduate later.

Env (all required, otherwise ``ConnectorNotConfigured``):

* ``GOOGLE_CLIENT_ID``
* ``GOOGLE_CLIENT_SECRET``
* ``GOOGLE_REDIRECT_URI``

Optional:

* ``GMAIL_DEFAULT_QUERY`` -- search expression for ``summarize_unread``
  (defaults to ``is:unread``)

The Calendar connector reuses the same Google token (see
:mod:`backend.core.connectors.calendar`) -- that's why the storage key
is ``google`` rather than ``gmail``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from . import (
    ConnectorAuthError,
    ConnectorNotConfigured,
    ConnectorTransportError,
)
from . import _storage


_NAME = "google"  # shared with calendar

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_TIMEOUT_S = 12.0
_USER_AGENT = "TARS-cockpit/9.2.0 (+https://tars.meeet.world)"

_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

# Refresh ~60s before expiry to avoid edge-case 401s.
_REFRESH_LEEWAY_S = 60


# -- env / config --------------------------------------------------------


def _client_id() -> str | None:
    return os.getenv("GOOGLE_CLIENT_ID") or None


def _client_secret() -> str | None:
    return os.getenv("GOOGLE_CLIENT_SECRET") or None


def _redirect_uri() -> str | None:
    return os.getenv("GOOGLE_REDIRECT_URI") or None


def is_configured() -> bool:
    return bool(_client_id() and _client_secret() and _redirect_uri())


def _require_config() -> tuple[str, str, str]:
    cid, sec, ru = _client_id(), _client_secret(), _redirect_uri()
    if not (cid and sec and ru):
        raise ConnectorNotConfigured(
            "Gmail connector requires GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI"
        )
    return cid, sec, ru


def has_token() -> bool:
    return _storage.has_token(_NAME)


# -- OAuth ---------------------------------------------------------------


def get_auth_url(
    state: str | None = None, scopes: list[str] | None = None
) -> str:
    cid, _sec, ru = _require_config()
    scope_list = scopes or [_GMAIL_SCOPE, _CALENDAR_SCOPE]
    params = {
        "client_id": cid,
        "response_type": "code",
        "scope": " ".join(scope_list),
        "redirect_uri": ru,
        "access_type": "offline",
        "prompt": "consent",  # forces refresh_token on re-auth
        "include_granted_scopes": "true",
    }
    if state:
        params["state"] = state
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    cid, sec, ru = _require_config()
    body = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": sec,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": ru,
        }
    ).encode("utf-8")
    payload = _http_post(_TOKEN_URL, body=body, token=None)
    if "access_token" not in payload:
        raise ConnectorAuthError(
            f"Google token exchange failed: {payload.get('error') or 'unknown'}"
        )
    payload["expires_at"] = int(time.time()) + int(payload.get("expires_in") or 3600)
    _storage.save_token(_NAME, payload)
    return payload


def refresh_access_token(refresh_token: str | None = None) -> dict[str, Any]:
    cid, sec, _ru = _require_config()
    rt = refresh_token
    if not rt:
        blob = _storage.load_token(_NAME) or {}
        rt = blob.get("refresh_token")
    if not rt:
        raise ConnectorAuthError(
            "No refresh_token available -- re-run OAuth with prompt=consent"
        )
    body = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": sec,
            "refresh_token": rt,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    payload = _http_post(_TOKEN_URL, body=body, token=None)
    if "access_token" not in payload:
        raise ConnectorAuthError(
            f"Google refresh failed: {payload.get('error') or 'unknown'}"
        )
    # Merge: keep refresh_token from previous blob if Google didn't return one.
    existing = _storage.load_token(_NAME) or {}
    merged = dict(existing)
    merged.update(payload)
    if "refresh_token" not in payload and "refresh_token" in existing:
        merged["refresh_token"] = existing["refresh_token"]
    merged["expires_at"] = int(time.time()) + int(payload.get("expires_in") or 3600)
    _storage.save_token(_NAME, merged)
    return merged


def disconnect() -> bool:
    blob = _storage.load_token(_NAME)
    revoked = False
    if blob:
        token = blob.get("refresh_token") or blob.get("access_token")
        if token:
            try:
                body = urllib.parse.urlencode({"token": token}).encode("utf-8")
                _http_post(_REVOKE_URL, body=body, token=None)
                revoked = True
            except (ConnectorAuthError, ConnectorTransportError):
                revoked = False
    deleted = _storage.delete_token(_NAME)
    return deleted or revoked


# -- HTTP ----------------------------------------------------------------


def _http_request(
    method: str,
    url: str,
    *,
    token: str | None,
    body: bytes | None = None,
) -> dict[str, Any]:
    headers: dict[str, str] = {
        "user-agent": _USER_AGENT,
        "accept": "application/json",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    if body is not None:
        headers["content-type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            err = {"error": str(exc.reason)}
        raise ConnectorTransportError(
            f"Google HTTP {exc.code}: {err.get('error') or err}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorTransportError(f"Google transport error: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectorTransportError(f"Google response not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConnectorTransportError("Google response was not a JSON object")
    return payload


def _http_post(url: str, *, body: bytes, token: str | None) -> dict[str, Any]:
    return _http_request("POST", url, token=token, body=body)


def _http_get(url: str, token: str) -> dict[str, Any]:
    return _http_request("GET", url, token=token)


# -- Client --------------------------------------------------------------


class GmailClient:
    """Read-only Gmail client.

    The constructor takes the raw token blob (same shape Google returns
    plus ``expires_at``). It auto-refreshes when the access_token is
    near expiry.
    """

    def __init__(self, token_blob: Mapping[str, Any]) -> None:
        if not isinstance(token_blob, Mapping):
            raise ConnectorAuthError("GmailClient requires a token blob")
        if not token_blob.get("access_token"):
            raise ConnectorAuthError("Token blob missing access_token")
        self._blob: dict[str, Any] = dict(token_blob)

    @classmethod
    def from_stored_token(cls) -> "GmailClient":
        if not is_configured():
            raise ConnectorNotConfigured("Gmail env vars missing")
        blob = _storage.load_token(_NAME)
        if not blob:
            raise ConnectorAuthError("Google token not stored -- run OAuth flow first")
        return cls(blob)

    def _ensure_fresh(self) -> str:
        expires_at = int(self._blob.get("expires_at") or 0)
        if expires_at and (time.time() + _REFRESH_LEEWAY_S) >= expires_at:
            if self._blob.get("refresh_token"):
                refreshed = refresh_access_token(self._blob["refresh_token"])
                self._blob = dict(refreshed)
        return self._blob["access_token"]

    # -- API ---------------------------------------------------------

    def list_threads(
        self, query: str = "is:unread", max_results: int = 20
    ) -> list[dict[str, Any]]:
        token = self._ensure_fresh()
        params = urllib.parse.urlencode(
            {"q": query, "maxResults": max(1, min(int(max_results), 100))}
        )
        payload = _http_get(f"{_API_BASE}/threads?{params}", token=token)
        threads = payload.get("threads") or []
        if not isinstance(threads, list):
            return []
        return [t for t in threads if isinstance(t, dict)]

    def read_thread(self, thread_id: str) -> dict[str, Any]:
        if not thread_id:
            raise ValueError("thread_id is required")
        token = self._ensure_fresh()
        payload = _http_get(
            f"{_API_BASE}/threads/{urllib.parse.quote(thread_id)}?format=full",
            token=token,
        )
        return payload

    def summarize_unread(self, max_results: int = 10) -> dict[str, Any]:
        """Briefing-friendly summary used by the awareness fallback."""

        query = os.getenv("GMAIL_DEFAULT_QUERY") or "is:unread"
        threads = self.list_threads(query=query, max_results=max_results)
        items: list[dict[str, Any]] = []
        token = self._ensure_fresh()
        for thread in threads[:max_results]:
            tid = thread.get("id")
            if not tid:
                continue
            try:
                detail = _http_get(
                    f"{_API_BASE}/threads/{urllib.parse.quote(str(tid))}?format=metadata",
                    token=token,
                )
            except ConnectorTransportError:
                continue
            messages = detail.get("messages") or []
            head = messages[0] if messages else {}
            headers = {
                h.get("name", "").lower(): h.get("value", "")
                for h in (head.get("payload") or {}).get("headers", [])
                if isinstance(h, dict)
            }
            items.append(
                {
                    "thread_id": tid,
                    "snippet": head.get("snippet"),
                    "from": headers.get("from"),
                    "subject": headers.get("subject"),
                    "date": headers.get("date"),
                    "label_ids": head.get("labelIds"),
                    "message_count": len(messages),
                }
            )
        return {
            "ok": True,
            "kind": "live",
            "as_of": int(time.time()),
            "query": query,
            "count": len(items),
            "messages": items,
        }


__all__ = [
    "GmailClient",
    "is_configured",
    "has_token",
    "get_auth_url",
    "exchange_code",
    "refresh_access_token",
    "disconnect",
]
