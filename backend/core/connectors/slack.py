"""Slack OAuth + read connector (Wave 91).

Replaces the empty-list stub that the awareness pack was returning for
Slack. Implements:

* Slack OAuth v2 (``oauth.v2.access``) -- ``get_auth_url`` +
  ``exchange_code``.
* Token persistence via :mod:`backend.core.connectors._storage`.
* Minimal read API: ``list_channels``, ``recent_messages``,
  ``mentions_for_user``.
* ``post_message`` is intentionally a stub returning
  ``{"ok": False, "error": "post_disabled"}`` -- writes graduate in a
  later wave once Slack app review is finished.

All HTTP is stdlib ``urllib`` so we don't add a new runtime dep
(matches the pattern used by ``backend.core.council.llm`` and the
GitHub connector router).

Env (all three required, otherwise ``ConnectorNotConfigured`` from
every method):

* ``SLACK_CLIENT_ID``
* ``SLACK_CLIENT_SECRET``
* ``SLACK_REDIRECT_URI``

Optional:

* ``SLACK_DEFAULT_SCOPES`` (defaults to a sensible read-only set)
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


_NAME = "slack"

_API_BASE = "https://slack.com/api"
_AUTH_URL = "https://slack.com/oauth/v2/authorize"
_TIMEOUT_S = 12.0
_USER_AGENT = "TARS-cockpit/9.2.0 (+https://tars.meeet.world)"

_DEFAULT_SCOPES = (
    "channels:read,"
    "channels:history,"
    "groups:read,"
    "groups:history,"
    "im:read,"
    "im:history,"
    "search:read,"
    "users:read"
)


# -- env / config --------------------------------------------------------


def _client_id() -> str | None:
    return os.getenv("SLACK_CLIENT_ID") or None


def _client_secret() -> str | None:
    return os.getenv("SLACK_CLIENT_SECRET") or None


def _redirect_uri() -> str | None:
    return os.getenv("SLACK_REDIRECT_URI") or None


def is_configured() -> bool:
    return bool(_client_id() and _client_secret() and _redirect_uri())


def _require_config() -> tuple[str, str, str]:
    cid, sec, ru = _client_id(), _client_secret(), _redirect_uri()
    if not (cid and sec and ru):
        raise ConnectorNotConfigured(
            "Slack connector requires SLACK_CLIENT_ID, "
            "SLACK_CLIENT_SECRET, SLACK_REDIRECT_URI"
        )
    return cid, sec, ru


def has_token() -> bool:
    return _storage.has_token(_NAME)


# -- OAuth ---------------------------------------------------------------


def get_auth_url(state: str | None = None, scopes: str | None = None) -> str:
    cid, _sec, ru = _require_config()
    params = {
        "client_id": cid,
        "scope": scopes or os.getenv("SLACK_DEFAULT_SCOPES") or _DEFAULT_SCOPES,
        "redirect_uri": ru,
    }
    if state:
        params["state"] = state
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an authorization code for an access token.

    Returns the token blob as Slack returns it (with ``access_token``,
    ``team``, ``authed_user``, ...) plus a ``stored_at`` epoch added by
    the storage layer.
    """

    cid, sec, ru = _require_config()
    body = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": sec,
            "code": code,
            "redirect_uri": ru,
        }
    ).encode("utf-8")
    payload = _http_post(f"{_API_BASE}/oauth.v2.access", body=body, token=None)
    if not payload.get("ok"):
        raise ConnectorAuthError(
            f"Slack token exchange failed: {payload.get('error') or 'unknown'}"
        )
    _storage.save_token(_NAME, payload)
    return payload


def disconnect() -> bool:
    """Revoke (best-effort) and delete the local token."""

    blob = _storage.load_token(_NAME)
    revoked = False
    if blob:
        token = _extract_access_token(blob)
        if token:
            try:
                resp = _http_post(f"{_API_BASE}/auth.revoke", body=b"", token=token)
                revoked = bool(resp.get("ok"))
            except (ConnectorAuthError, ConnectorTransportError):
                revoked = False
    deleted = _storage.delete_token(_NAME)
    return deleted or revoked


# -- token helpers -------------------------------------------------------


def _extract_access_token(blob: Mapping[str, Any]) -> str | None:
    direct = blob.get("access_token")
    if isinstance(direct, str) and direct:
        return direct
    authed = blob.get("authed_user") if isinstance(blob, dict) else None
    if isinstance(authed, dict):
        ut = authed.get("access_token")
        if isinstance(ut, str) and ut:
            return ut
    return None


# -- HTTP ----------------------------------------------------------------


def _http_get(url: str, token: str | None) -> dict[str, Any]:
    return _http_request("GET", url, token=token)


def _http_post(
    url: str, *, body: bytes, token: str | None
) -> dict[str, Any]:
    return _http_request("POST", url, token=token, body=body)


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
        raise ConnectorTransportError(
            f"Slack HTTP {exc.code}: {exc.reason}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorTransportError(f"Slack transport error: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectorTransportError(f"Slack response not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConnectorTransportError("Slack response was not a JSON object")
    return payload


# -- Client --------------------------------------------------------------


class SlackClient:
    """Read-only Slack client.

    Construct with :meth:`from_stored_token` after the user finished
    OAuth, or pass an explicit token in tests. Methods raise
    :class:`ConnectorNotConfigured` /
    :class:`ConnectorTransportError` -- never return raw stub payloads
    (the legacy fallback is the caller's job).
    """

    def __init__(self, access_token: str) -> None:
        if not access_token:
            raise ConnectorAuthError("SlackClient requires an access token")
        self._token = access_token

    @classmethod
    def from_stored_token(cls) -> "SlackClient":
        if not is_configured():
            raise ConnectorNotConfigured("Slack env vars missing")
        blob = _storage.load_token(_NAME)
        if not blob:
            raise ConnectorAuthError("Slack token not stored -- run OAuth flow first")
        token = _extract_access_token(blob)
        if not token:
            raise ConnectorAuthError("Stored Slack blob has no access_token")
        return cls(token)

    # -- API ---------------------------------------------------------

    def auth_test(self) -> dict[str, Any]:
        payload = _http_get(f"{_API_BASE}/auth.test", token=self._token)
        if not payload.get("ok"):
            raise ConnectorAuthError(
                f"Slack auth.test failed: {payload.get('error') or 'unknown'}"
            )
        return payload

    def list_channels(
        self,
        types: str = "public_channel,private_channel,im",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {"types": types, "limit": max(1, min(int(limit), 1000)), "exclude_archived": "true"}
        )
        payload = _http_get(
            f"{_API_BASE}/conversations.list?{params}", token=self._token
        )
        if not payload.get("ok"):
            raise ConnectorTransportError(
                f"Slack conversations.list: {payload.get('error') or 'unknown'}"
            )
        channels = payload.get("channels") or []
        if not isinstance(channels, list):
            return []
        return [c for c in channels if isinstance(c, dict)]

    def recent_messages(
        self, channel_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not channel_id:
            raise ValueError("channel_id is required")
        params = urllib.parse.urlencode(
            {"channel": channel_id, "limit": max(1, min(int(limit), 200))}
        )
        payload = _http_get(
            f"{_API_BASE}/conversations.history?{params}", token=self._token
        )
        if not payload.get("ok"):
            raise ConnectorTransportError(
                f"Slack conversations.history: {payload.get('error') or 'unknown'}"
            )
        msgs = payload.get("messages") or []
        if not isinstance(msgs, list):
            return []
        return [m for m in msgs if isinstance(m, dict)]

    def mentions_for_user(self, limit: int = 20) -> list[dict[str, Any]]:
        """Use search.messages for mentions to me.

        Note: requires a user token (not bot token) with ``search:read``.
        """

        params = urllib.parse.urlencode(
            {"query": "@me", "count": max(1, min(int(limit), 100)), "sort": "timestamp"}
        )
        payload = _http_get(
            f"{_API_BASE}/search.messages?{params}", token=self._token
        )
        if not payload.get("ok"):
            raise ConnectorTransportError(
                f"Slack search.messages: {payload.get('error') or 'unknown'}"
            )
        matches = (payload.get("messages") or {}).get("matches") or []
        if not isinstance(matches, list):
            return []
        return [m for m in matches if isinstance(m, dict)]

    def post_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Stub -- write surface graduates after Slack app review.

        Kept on the class so downstream code can import a stable
        signature today.
        """

        return {
            "ok": False,
            "error": "post_disabled",
            "hint": (
                "Slack write surface is intentionally disabled until "
                "Wave 92+ when app review is complete. Use the read "
                "API (recent_messages, list_channels) for now."
            ),
            "would_post": {"channel": channel, "text": text, "blocks": blocks},
            "as_of": int(time.time()),
        }


__all__ = [
    "SlackClient",
    "is_configured",
    "has_token",
    "get_auth_url",
    "exchange_code",
    "disconnect",
]
