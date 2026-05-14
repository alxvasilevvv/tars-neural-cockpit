"""Connector registry (Wave 91).

Single source of truth for the cockpit's "Status" surface. Each
connector exposes a uniform ``is_configured`` / ``has_token`` /
``disconnect`` set; this module wraps them in a per-name lookup so the
``/api/connectors`` router and the awareness fallback share one
implementation.

The registry is import-time static -- adding a connector means editing
``CONNECTORS`` here. That's deliberate: we want a typo to fail loudly,
not silently miss from the Status page.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from . import (
    ConnectorAuthError,
    ConnectorNotConfigured,
    ConnectorTransportError,
)
from . import _storage
from . import calendar as _calendar
from . import gmail as _gmail
from . import slack as _slack
from . import telegram as _telegram


@dataclass(frozen=True)
class ConnectorSpec:
    name: str
    label: str
    env_vars: tuple[str, ...]
    is_configured: Callable[[], bool]
    has_token: Callable[[], bool]
    get_auth_url: Callable[..., str]
    exchange_code: Callable[[str], dict[str, Any]]
    disconnect: Callable[[], bool]
    health_check: Callable[[], dict[str, Any]]


def _slack_health() -> dict[str, Any]:
    if not _slack.is_configured():
        return {"ok": False, "error": "not_configured"}
    if not _slack.has_token():
        return {"ok": False, "error": "no_token"}
    try:
        client = _slack.SlackClient.from_stored_token()
        result = client.auth_test()
        return {
            "ok": True,
            "team": result.get("team"),
            "user": result.get("user"),
            "as_of": int(time.time()),
        }
    except (ConnectorNotConfigured, ConnectorAuthError, ConnectorTransportError) as exc:
        return {"ok": False, "error": str(exc)}


def _gmail_health() -> dict[str, Any]:
    if not _gmail.is_configured():
        return {"ok": False, "error": "not_configured"}
    if not _gmail.has_token():
        return {"ok": False, "error": "no_token"}
    try:
        client = _gmail.GmailClient.from_stored_token()
        # cheap call -- list 1 thread
        threads = client.list_threads(query="in:inbox", max_results=1)
        return {
            "ok": True,
            "thread_count_sample": len(threads),
            "as_of": int(time.time()),
        }
    except (ConnectorNotConfigured, ConnectorAuthError, ConnectorTransportError) as exc:
        return {"ok": False, "error": str(exc)}


def _calendar_health() -> dict[str, Any]:
    if not _calendar.is_configured():
        return {"ok": False, "error": "not_configured"}
    if not _calendar.has_token():
        return {"ok": False, "error": "no_token"}
    try:
        summary = _calendar.upcoming_summary(days=1)
        return {
            "ok": True,
            "events_today_plus_one": summary.get("events", []) and len(summary["events"]),
            "as_of": int(time.time()),
        }
    except (ConnectorNotConfigured, ConnectorAuthError, ConnectorTransportError) as exc:
        return {"ok": False, "error": str(exc)}


CONNECTORS: dict[str, ConnectorSpec] = {
    "slack": ConnectorSpec(
        name="slack",
        label="Slack",
        env_vars=("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI"),
        is_configured=_slack.is_configured,
        has_token=_slack.has_token,
        get_auth_url=_slack.get_auth_url,
        exchange_code=_slack.exchange_code,
        disconnect=_slack.disconnect,
        health_check=_slack_health,
    ),
    "gmail": ConnectorSpec(
        name="gmail",
        label="Gmail",
        env_vars=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"),
        is_configured=_gmail.is_configured,
        has_token=_gmail.has_token,
        get_auth_url=_gmail.get_auth_url,
        exchange_code=_gmail.exchange_code,
        disconnect=_gmail.disconnect,
        health_check=_gmail_health,
    ),
    "calendar": ConnectorSpec(
        name="calendar",
        label="Google Calendar",
        env_vars=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"),
        is_configured=_calendar.is_configured,
        has_token=_calendar.has_token,
        get_auth_url=_calendar.get_auth_url,
        exchange_code=_calendar.exchange_code,
        disconnect=_calendar.disconnect,
        health_check=_calendar_health,
    ),
    # Wave 108 — Telegram bridge connector. Bot-API based (no OAuth);
    # ``get_auth_url`` returns the BotFather bootstrap URL and
    # ``exchange_code`` accepts a bot token in the ``code`` slot.
    "telegram": ConnectorSpec(
        name="telegram",
        label="Telegram",
        env_vars=("TELEGRAM_BOT_TOKEN",),
        is_configured=_telegram.is_configured,
        has_token=_telegram.has_token,
        get_auth_url=_telegram.get_auth_url,
        exchange_code=_telegram.exchange_code,
        disconnect=_telegram.disconnect,
        health_check=_telegram.health_check,
    ),
}


def list_connectors() -> list[str]:
    return sorted(CONNECTORS.keys())


def get(name: str) -> ConnectorSpec:
    spec = CONNECTORS.get(name)
    if spec is None:
        raise KeyError(f"unknown connector: {name}")
    return spec


# W144/W231 — honest maturity badge per connector. \"real\" means
# the OAuth flow + read endpoints have been live-tested; \"beta\" is
# wired but expected to have gaps; \"stub\" means not yet implemented.
_BADGES: dict[str, str] = {
    "slack": "real",
    "gmail": "real",
    "calendar": "real",
    "telegram": "beta",
}


def get_status() -> dict[str, Any]:
    """Status overview for all registered connectors -- no network."""

    items: list[dict[str, Any]] = []
    now = int(time.time())
    for name in list_connectors():
        spec = CONNECTORS[name]
        configured = bool(spec.is_configured())
        connected = bool(spec.has_token())
        items.append(
            {
                "name": spec.name,
                "label": spec.label,
                "env_vars": list(spec.env_vars),
                "configured": configured,
                "connected": connected,
                "badge": _BADGES.get(name, "beta"),
                "token_age_s": _storage.token_age_s(_token_storage_key(name)),
                "last_check_at": now,
            }
        )
    return {"ok": True, "as_of": now, "connectors": items}


def health_check(name: str) -> dict[str, Any]:
    spec = get(name)
    return spec.health_check()


def _token_storage_key(name: str) -> str:
    """Map connector name to the key used by ``_storage`` (gmail and
    calendar share ``google``)."""

    if name in {"gmail", "calendar"}:
        return "google"
    return name


__all__ = [
    "ConnectorSpec",
    "CONNECTORS",
    "list_connectors",
    "get",
    "get_status",
    "health_check",
]
