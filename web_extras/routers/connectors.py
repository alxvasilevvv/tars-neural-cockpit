"""Connectors HTTP surface (Wave 91).

Endpoints:

    GET    /api/connectors                                   status of all
    GET    /api/connectors/{name}/auth-url                   start OAuth
    POST   /api/connectors/{name}/callback   {code,state}    finish OAuth
    POST   /api/connectors/{name}/disconnect                 revoke + delete
    GET    /api/connectors/{name}/health                     ping API

    GET    /api/connectors/slack/channels
    GET    /api/connectors/slack/channels/{id}/messages
    GET    /api/connectors/gmail/threads
    GET    /api/connectors/gmail/threads/{id}
    GET    /api/connectors/calendar/today
    GET    /api/connectors/calendar/upcoming?days=7

503 ``connector_not_configured`` when env vars are missing -- with the
exact env var names in the ``hint`` so the operator can fix it without
reading docs.

Note: ``/api/connectors/github/*`` is owned by
``web_extras/routers/github.py`` (Wave 73) -- this router intentionally
does NOT collide with that prefix.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from backend.core.connectors import (
    ConnectorAuthError,
    ConnectorNotConfigured,
    ConnectorTransportError,
)
from backend.core.connectors import calendar as calendar_conn
from backend.core.connectors import gmail as gmail_conn
from backend.core.connectors import registry
from backend.core.connectors import slack as slack_conn
from backend.core.connectors import telegram as telegram_conn
from backend.core.privacy import check_can_call


log = logging.getLogger("tars.connectors")

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


# -- helpers -------------------------------------------------------------


def _get_spec(name: str) -> registry.ConnectorSpec:
    try:
        return registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_connector", "name": name},
        )


def _not_configured(spec: registry.ConnectorSpec) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "error": "connector_not_configured",
            "name": spec.name,
            "hint": f"set {', '.join(spec.env_vars)}",
        },
    )


def _privacy_gate(name: str) -> None:
    """W244 -- block outbound connector calls under privacy/strict mode."""
    allowed, reason = check_can_call(name.lower(), source=f"connectors.{name}")
    if not allowed:
        raise HTTPException(
            status_code=451,
            detail={
                "ok": False,
                "error": "privacy_block",
                "reason": reason,
                "connector": name,
            },
        )


def _wrap(spec: registry.ConnectorSpec, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ConnectorNotConfigured:
        raise _not_configured(spec)
    except ConnectorAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "connector_auth_error", "message": str(exc)},
        )
    except ConnectorTransportError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "connector_upstream_error", "message": str(exc)},
        )


# -- generic endpoints ---------------------------------------------------


@router.get("")
async def status_all() -> dict[str, Any]:
    return registry.get_status()


@router.get("/{name}/auth-url")
async def auth_url(name: str, state: str | None = Query(default=None)) -> dict[str, Any]:
    spec = _get_spec(name)
    if not spec.is_configured():
        raise _not_configured(spec)
    url = _wrap(spec, spec.get_auth_url, state=state)
    return {"ok": True, "name": spec.name, "auth_url": url}


@router.post("/{name}/callback")
async def callback(
    name: str,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    spec = _get_spec(name)
    if not spec.is_configured():
        raise _not_configured(spec)
    code = payload.get("code")
    if not isinstance(code, str) or not code:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_code", "hint": "POST {code, state}"},
        )
    blob = _wrap(spec, spec.exchange_code, code)
    # Don't surface raw access_token in the response. Confirm-only.
    return {
        "ok": True,
        "name": spec.name,
        "connected": True,
        "scope": blob.get("scope"),
        "team_id": (blob.get("team") or {}).get("id") if isinstance(blob.get("team"), dict) else None,
    }


@router.post("/{name}/disconnect")
async def disconnect(name: str) -> dict[str, Any]:
    spec = _get_spec(name)
    deleted = _wrap(spec, spec.disconnect)
    return {"ok": True, "name": spec.name, "deleted": bool(deleted)}


@router.get("/{name}/health")
async def health(name: str) -> dict[str, Any]:
    spec = _get_spec(name)
    return {"ok": True, "name": spec.name, "result": spec.health_check()}


# -- Slack reads ---------------------------------------------------------


@router.get("/slack/channels")
async def slack_channels(
    types: str = Query(default="public_channel,private_channel,im"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    spec = _get_spec("slack")
    _privacy_gate("slack")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, slack_conn.SlackClient.from_stored_token)
    channels = _wrap(spec, client.list_channels, types=types, limit=limit)
    return {"ok": True, "count": len(channels), "channels": channels}


@router.get("/slack/channels/{channel_id}/messages")
async def slack_messages(
    channel_id: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    spec = _get_spec("slack")
    _privacy_gate("slack")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, slack_conn.SlackClient.from_stored_token)
    msgs = _wrap(spec, client.recent_messages, channel_id, limit=limit)
    return {"ok": True, "channel_id": channel_id, "count": len(msgs), "messages": msgs}


@router.get("/slack/mentions")
async def slack_mentions(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """Wave 122 — wire the FE Dashboard SlackMentionsWidget endpoint.

    Frontend has been polling ``/api/connectors/slack/mentions`` since
    the dashboard widget shipped; the audit (Wave 122) caught that
    backend never registered the route. The Slack connector already
    exposes :meth:`SlackClient.mentions_for_user`, so this is a thin
    wrap; pre-existing 404 fallback in ``SlackMentionsWidget.tsx``
    keeps the UI safe even when the connector isn't configured.
    """
    spec = _get_spec("slack")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, slack_conn.SlackClient.from_stored_token)
    mentions = _wrap(spec, client.mentions_for_user, limit=limit)
    return {"ok": True, "count": len(mentions), "mentions": mentions}


# -- Gmail reads ---------------------------------------------------------


@router.get("/gmail/threads")
async def gmail_threads(
    query: str = Query(default="is:unread"),
    max: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    spec = _get_spec("gmail")
    _privacy_gate("gmail")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, gmail_conn.GmailClient.from_stored_token)
    threads = _wrap(spec, client.list_threads, query=query, max_results=max)
    return {"ok": True, "query": query, "count": len(threads), "threads": threads}


@router.get("/gmail/threads/{thread_id}")
async def gmail_read_thread(thread_id: str) -> dict[str, Any]:
    spec = _get_spec("gmail")
    _privacy_gate("gmail")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, gmail_conn.GmailClient.from_stored_token)
    thread = _wrap(spec, client.read_thread, thread_id)
    return {"ok": True, "thread_id": thread_id, "thread": thread}


# -- Calendar reads ------------------------------------------------------


@router.get("/calendar/today")
async def calendar_today(
    calendar_id: str = Query(default="primary"),
) -> dict[str, Any]:
    spec = _get_spec("calendar")
    _privacy_gate("calendar")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, calendar_conn.CalendarClient.from_stored_token)
    return _wrap(spec, client.today_summary, calendar_id=calendar_id)


@router.get("/calendar/upcoming")
async def calendar_upcoming(
    days: int = Query(default=7, ge=1, le=60),
    calendar_id: str = Query(default="primary"),
) -> dict[str, Any]:
    spec = _get_spec("calendar")
    _privacy_gate("calendar")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, calendar_conn.CalendarClient.from_stored_token)
    now = datetime.now(timezone.utc)
    events = _wrap(
        spec,
        client.list_events,
        now,
        now + timedelta(days=days),
        calendar_id=calendar_id,
    )
    return {
        "ok": True,
        "days": days,
        "calendar_id": calendar_id,
        "count": len(events),
        "events": events,
    }


# -- Telegram (Wave 108) -------------------------------------------------


@router.get("/telegram/bot-info")
async def telegram_bot_info() -> dict[str, Any]:
    """Returns the bot identity (getMe) when configured."""

    spec = _get_spec("telegram")
    if not spec.is_configured():
        raise _not_configured(spec)
    info = _wrap(spec, telegram_conn.get_bot_info)
    return {
        "ok": True,
        "bot_id": info.get("id"),
        "bot_username": info.get("username"),
        "bot_first_name": info.get("first_name"),
        "self_chat_id": telegram_conn.get_self_chat_id(),
    }


@router.post("/telegram/send-self")
async def telegram_send_self(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Body ``{text, parse_mode?}`` -- sends to operator's saved chat."""

    spec = _get_spec("telegram")
    if not spec.is_configured():
        raise _not_configured(spec)
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_text", "hint": "POST {text, parse_mode?}"},
        )
    parse_mode = payload.get("parse_mode") or "Markdown"
    client = _wrap(spec, telegram_conn.TelegramClient.from_stored_token)
    result = _wrap(spec, client.send_message_to_self, text, parse_mode=parse_mode)
    return {
        "ok": True,
        "message_id": result.get("message_id"),
        "chat_id": (result.get("chat") or {}).get("id") if isinstance(result.get("chat"), dict) else None,
    }


@router.post("/telegram/save-self")
async def telegram_save_self(
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Body ``{chat_id}`` -- stores the operator's chat ID for send-self."""

    spec = _get_spec("telegram")
    if not spec.is_configured():
        raise _not_configured(spec)
    raw = payload.get("chat_id")
    chat_id: int
    try:
        chat_id = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_chat_id", "hint": "POST {chat_id: <int>}"},
        )
    if chat_id == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_chat_id", "hint": "chat_id must be non-zero"},
        )
    try:
        return telegram_conn.save_self_chat_id(chat_id)
    except ConnectorNotConfigured:
        raise _not_configured(spec)


@router.get("/telegram/chats")
async def telegram_chats(
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """Recent chats via getUpdates."""

    spec = _get_spec("telegram")
    if not spec.is_configured():
        raise _not_configured(spec)
    client = _wrap(spec, telegram_conn.TelegramClient.from_stored_token)
    chats = _wrap(spec, client.list_recent_chats, limit=limit)
    return {"ok": True, "count": len(chats), "chats": chats}


__all__ = ["router"]
