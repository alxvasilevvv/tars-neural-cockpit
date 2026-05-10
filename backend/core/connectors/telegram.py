"""Telegram bridge connector (Wave 108).

Bot-API based: the operator creates a bot via @BotFather, drops the
bot token into the env (``TELEGRAM_BOT_TOKEN``), and TARS uses it as
a delivery channel for outgoing notifications.

This is intentionally NOT an OAuth flow -- Telegram Bot API uses a
single fixed bot token, no consent dance. As a result the connector
shape diverges slightly from Slack/Gmail/Calendar:

* ``get_auth_url`` returns the BotFather URL (operator-facing
  bootstrap link), not a real consent URL.
* ``exchange_code`` is a no-op compatibility shim that simply
  validates the token via ``getMe`` and stores it.

Public surface:

* :func:`is_configured` -- bool, ``TELEGRAM_BOT_TOKEN`` present.
* :func:`has_token` -- bool, JSON file on disk.
* :func:`get_bot_info` -- module-level convenience wrapper.
* :func:`save_self_chat_id` / :func:`get_self_chat_id` -- operator's
  saved chat ID for "send a notification to me" use.
* :class:`TelegramClient` -- thin Bot API client (send_message,
  list_recent_chats, get_bot_info).
* :func:`health_check` -- registry hook.
* :func:`disconnect` -- delete stored token + self chat id.

Tokens are persisted via :mod:`backend.core.connectors._storage` at
``~/.tars/connectors/telegram.json`` (mode 600). The blob shape::

    {
        "bot_token": "123:ABC...",
        "bot_username": "tars_bot",
        "self_chat_id": 12345678,         # optional
        "stored_at": 1715000000
    }

Env:

* ``TELEGRAM_BOT_TOKEN`` (required)
* ``TELEGRAM_OPERATOR_CHAT_ID`` (optional; takes precedence over
  saved blob field).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import (
    ConnectorAuthError,
    ConnectorNotConfigured,
    ConnectorTransportError,
)
from . import _storage


_NAME = "telegram"

_API_BASE = "https://api.telegram.org"
_BOTFATHER_URL = "https://t.me/BotFather"
_TIMEOUT_S = 12.0
_USER_AGENT = "TARS-cockpit/9.2.0 (+https://tars.meeet.world)"


# -- env / config --------------------------------------------------------


def _env_token() -> str | None:
    raw = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    return raw or None


def _env_operator_chat_id() -> int | None:
    raw = (os.getenv("TELEGRAM_OPERATOR_CHAT_ID") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def is_configured() -> bool:
    """True iff a bot token is available (env OR stored blob)."""

    if _env_token():
        return True
    blob = _storage.load_token(_NAME)
    if blob and isinstance(blob.get("bot_token"), str) and blob["bot_token"]:
        return True
    return False


def has_token() -> bool:
    return _storage.has_token(_NAME)


def _resolve_token() -> str:
    """Prefer the env var (operator can rotate without touching disk)."""

    tok = _env_token()
    if tok:
        return tok
    blob = _storage.load_token(_NAME)
    if blob and isinstance(blob.get("bot_token"), str) and blob["bot_token"]:
        return str(blob["bot_token"])
    raise ConnectorNotConfigured(
        "Telegram connector requires TELEGRAM_BOT_TOKEN (env) or a "
        "stored telegram.json blob with a bot_token field"
    )


# -- OAuth-shaped shims -------------------------------------------------


def get_auth_url(state: str | None = None) -> str:
    """Return the BotFather URL.

    Telegram has no OAuth flow for bots -- the operator creates a bot
    interactively in @BotFather and copies the token. We return the
    BotFather URL so the FE can render a "Create bot" button uniformly
    with Slack/Gmail/Calendar.
    """

    # state is ignored; included for registry signature compatibility.
    _ = state
    return _BOTFATHER_URL


def exchange_code(code: str) -> dict[str, Any]:
    """Treat the supplied "code" as a bot token, validate, and store.

    The FE submits the bot token via the same /callback endpoint
    pattern the OAuth connectors use, with ``{code: "<bot_token>"}``.
    We call ``getMe`` to validate it before persisting.
    """

    if not isinstance(code, str) or not code.strip():
        raise ConnectorAuthError("Telegram exchange_code requires a non-empty bot token")
    token = code.strip()
    info = _bot_get_me(token)
    blob: dict[str, Any] = {
        "bot_token": token,
        "bot_id": info.get("id"),
        "bot_username": info.get("username"),
        "bot_first_name": info.get("first_name"),
    }
    _storage.save_token(_NAME, blob)
    return {
        "ok": True,
        "bot_id": info.get("id"),
        "bot_username": info.get("username"),
    }


def disconnect() -> bool:
    return _storage.delete_token(_NAME)


# -- self chat id helpers -----------------------------------------------


def save_self_chat_id(chat_id: int) -> dict[str, Any]:
    """Persist the operator's chat ID into the stored blob."""

    if not isinstance(chat_id, int) or chat_id == 0:
        raise ValueError("chat_id must be a non-zero integer")
    blob = _storage.load_token(_NAME) or {}
    if not blob.get("bot_token") and not _env_token():
        raise ConnectorNotConfigured(
            "Telegram bot token must be configured before saving self chat id"
        )
    # Make sure the bot_token survives in the blob even if it currently
    # only lives in the env (so save-self works on first call).
    if not blob.get("bot_token"):
        try:
            blob["bot_token"] = _resolve_token()
        except ConnectorNotConfigured:
            pass
    blob["self_chat_id"] = int(chat_id)
    _storage.save_token(_NAME, blob)
    return {"ok": True, "self_chat_id": int(chat_id)}


def get_self_chat_id() -> int | None:
    """Operator chat ID -- env wins over stored blob."""

    env_id = _env_operator_chat_id()
    if env_id is not None:
        return env_id
    blob = _storage.load_token(_NAME)
    if not blob:
        return None
    val = blob.get("self_chat_id")
    if isinstance(val, int) and val != 0:
        return val
    return None


# -- module-level convenience ------------------------------------------


def get_bot_info() -> dict[str, Any]:
    token = _resolve_token()
    return _bot_get_me(token)


def health_check() -> dict[str, Any]:
    """Registry hook -- never raises."""

    if not is_configured():
        return {"ok": False, "error": "not_configured"}
    try:
        info = get_bot_info()
        return {
            "ok": True,
            "bot_id": info.get("id"),
            "bot_username": info.get("username"),
            "self_chat_id_set": get_self_chat_id() is not None,
        }
    except (ConnectorNotConfigured, ConnectorAuthError, ConnectorTransportError) as exc:
        return {"ok": False, "error": str(exc)}


# -- HTTP --------------------------------------------------------------


def _bot_url(token: str, method: str) -> str:
    return f"{_API_BASE}/bot{token}/{method}"


def _bot_get_me(token: str) -> dict[str, Any]:
    payload = _http_post(_bot_url(token, "getMe"), body=b"")
    if not payload.get("ok"):
        raise ConnectorAuthError(
            f"Telegram getMe failed: {payload.get('description') or 'unknown'}"
        )
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ConnectorTransportError("Telegram getMe: malformed result")
    return result


def _http_post(url: str, *, body: bytes) -> dict[str, Any]:
    headers = {
        "user-agent": _USER_AGENT,
        "accept": "application/json",
    }
    if body:
        headers["content-type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        # Telegram returns JSON error bodies on 4xx -- surface the text.
        try:
            body_raw = exc.read().decode("utf-8") if exc.fp else ""
        except Exception:
            body_raw = ""
        raise ConnectorTransportError(
            f"Telegram HTTP {exc.code}: {exc.reason}: {body_raw[:200]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorTransportError(f"Telegram transport error: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectorTransportError(f"Telegram response not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConnectorTransportError("Telegram response was not a JSON object")
    return payload


# -- Client ------------------------------------------------------------


class TelegramClient:
    """Bot-API client.

    Construct directly with a token (tests + ad-hoc) or via
    :meth:`from_stored_token` / :meth:`from_env` factories.
    """

    def __init__(self, bot_token: str) -> None:
        if not bot_token or not isinstance(bot_token, str):
            raise ConnectorAuthError("TelegramClient requires a non-empty bot token")
        self._token = bot_token.strip()

    @classmethod
    def from_stored_token(cls) -> "TelegramClient":
        return cls(_resolve_token())

    @classmethod
    def from_env(cls) -> "TelegramClient":
        tok = _env_token()
        if not tok:
            raise ConnectorNotConfigured("TELEGRAM_BOT_TOKEN not set")
        return cls(tok)

    # -- API ---------------------------------------------------------

    def get_bot_info(self) -> dict[str, Any]:
        return _bot_get_me(self._token)

    def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
    ) -> dict[str, Any]:
        """POST sendMessage. Returns Telegram's ``result`` object."""

        if chat_id in (None, "", 0):
            raise ValueError("chat_id is required")
        if not isinstance(text, str) or not text:
            raise ValueError("text must be a non-empty string")
        params: dict[str, Any] = {
            "chat_id": str(chat_id),
            "text": text,
            "disable_web_page_preview": "true" if disable_web_page_preview else "false",
        }
        if parse_mode:
            params["parse_mode"] = parse_mode
        body = urllib.parse.urlencode(params).encode("utf-8")
        payload = _http_post(_bot_url(self._token, "sendMessage"), body=body)
        if not payload.get("ok"):
            raise ConnectorTransportError(
                f"Telegram sendMessage failed: {payload.get('description') or 'unknown'}"
            )
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    def send_message_to_self(
        self,
        text: str,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        """Look up the operator's saved chat ID and POST sendMessage.

        Raises :class:`ConnectorNotConfigured` if the operator hasn't
        called ``save_self_chat_id`` (or set
        ``TELEGRAM_OPERATOR_CHAT_ID``) yet.
        """

        chat_id = get_self_chat_id()
        if chat_id is None:
            raise ConnectorNotConfigured(
                "operator chat_id not set -- call save_self_chat_id "
                "or set TELEGRAM_OPERATOR_CHAT_ID"
            )
        return self.send_message(chat_id, text, parse_mode=parse_mode)

    def list_recent_chats(self, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent chats via getUpdates.

        Returns a list of unique ``{chat_id, type, title|username, last_message_at}``
        dicts ordered by most-recent-first. Bot must NOT be in webhook
        mode for this to return updates.
        """

        params = urllib.parse.urlencode(
            {"limit": max(1, min(int(limit) * 5, 100)), "timeout": 0}
        ).encode("utf-8")
        payload = _http_post(_bot_url(self._token, "getUpdates"), body=params)
        if not payload.get("ok"):
            raise ConnectorTransportError(
                f"Telegram getUpdates failed: {payload.get('description') or 'unknown'}"
            )
        updates = payload.get("result") or []
        if not isinstance(updates, list):
            return []

        seen: dict[int, dict[str, Any]] = {}
        for upd in updates:
            if not isinstance(upd, dict):
                continue
            msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post")
            if not isinstance(msg, dict):
                continue
            chat = msg.get("chat")
            if not isinstance(chat, dict):
                continue
            cid = chat.get("id")
            if not isinstance(cid, int):
                continue
            ts = msg.get("date")
            existing = seen.get(cid)
            if existing and isinstance(existing.get("last_message_at"), int) and isinstance(ts, int):
                if existing["last_message_at"] >= ts:
                    continue
            seen[cid] = {
                "chat_id": cid,
                "type": chat.get("type"),
                "title": chat.get("title"),
                "username": chat.get("username"),
                "first_name": chat.get("first_name"),
                "last_message_at": ts if isinstance(ts, int) else None,
            }
        ordered = sorted(
            seen.values(),
            key=lambda r: r.get("last_message_at") or 0,
            reverse=True,
        )
        return ordered[: max(1, int(limit))]


__all__ = [
    "TelegramClient",
    "is_configured",
    "has_token",
    "get_auth_url",
    "exchange_code",
    "disconnect",
    "get_bot_info",
    "save_self_chat_id",
    "get_self_chat_id",
    "health_check",
]
