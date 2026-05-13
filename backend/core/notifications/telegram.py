"""Telegram bridge — cross-platform notification sibling (Wave 161).

Sister to ``imessage.py``: same shape (one ``send_*`` primitive,
result-dict contract, never raises). The W108 Telegram connector
already manages bot tokens; this module just provides a small
sync wrapper for use by playbooks / the doctor fan-out path.

Why a separate module?
  - The connector is OAuth + bot-info + long-poll machinery —
    too heavy for a single ``send_message`` call.
  - We want a lazy, stdlib-only path that doesn't import the
    full ``backend.core.connectors`` package when the operator
    just wants to fire a notification.

Honest framing:
  - **Token required.** ``TELEGRAM_BOT_TOKEN`` env must be set
    (or pass ``token=`` explicitly). Without it, ``send_telegram``
    returns ``token_missing``.
  - **chat_id required.** The bot can only DM users who've
    already messaged it once. v0.1 leaves chat discovery to the
    operator (the W108 connector's ``/api/connectors/telegram``
    endpoint provides it).
  - **No webhook listener here.** Inbound Telegram lands via the
    W108 connector, not this module.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


log = logging.getLogger("tars.notifications.telegram")


CONTRACT_VERSION = "0.1.0"
_API_BASE = "https://api.telegram.org"
_DEFAULT_TIMEOUT_S = 15.0


def _resolve_token(token: str | None) -> str | None:
    if token:
        return token.strip() or None
    raw = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    return raw or None


def is_configured() -> bool:
    """True iff a bot token is available."""

    return _resolve_token(None) is not None


def _post(
    method: str,
    *,
    token: str,
    payload: dict[str, Any],
    timeout_s: float,
) -> dict[str, Any]:
    """Single Bot-API POST. Returns the JSON dict or raises URLError."""

    url = f"{_API_BASE}/bot{token}/{method}"
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "accept": "application/json",
            "user-agent": "tars-notifications/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    parsed = json.loads(raw.decode("utf-8") or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("telegram response was not a JSON object")
    return parsed


def send_telegram(
    chat_id: int | str,
    text: str,
    *,
    token: str | None = None,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = False,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Send a Telegram message.

    Returns ``{ok, chat_id, message_id?, text_len?, error?, detail?}``.
    Never raises.

    ``parse_mode`` ∈ ``None`` | ``"Markdown"`` | ``"MarkdownV2"`` | ``"HTML"``.
    """

    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "text_required"}
    if len(text) > 4096:
        # Telegram's hard limit per message.
        return {"ok": False, "error": "text_too_long", "limit": 4096}

    tok = _resolve_token(token)
    if not tok:
        return {
            "ok": False,
            "error": "token_missing",
            "hint": "set TELEGRAM_BOT_TOKEN env or pass token= explicitly",
        }

    if chat_id is None or chat_id == "":
        return {"ok": False, "error": "chat_id_required"}

    payload: dict[str, Any] = {
        "chat_id": str(chat_id),
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if disable_web_page_preview:
        payload["disable_web_page_preview"] = "true"

    try:
        body = _post("sendMessage", token=tok, payload=payload, timeout_s=timeout_s)
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8") if exc.fp else ""
        except Exception:  # noqa: BLE001
            err_body = ""
        return {
            "ok": False,
            "error": "http_error",
            "status": exc.code,
            "detail": err_body[:300],
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "error": "transport_error",
            "detail": str(exc),
        }
    except (UnicodeDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "error": "bad_response",
            "detail": str(exc),
        }

    if not body.get("ok"):
        return {
            "ok": False,
            "error": "telegram_api_error",
            "detail": body.get("description") or "unknown",
            "code": body.get("error_code"),
        }

    result = body.get("result") or {}
    return {
        "ok": True,
        "chat_id": chat_id,
        "message_id": result.get("message_id"),
        "text_len": len(text),
    }


# ─── doctor fan-out helper ────────────────────────────────────────


def fanout_doctor_change(
    change: dict[str, Any],
    *,
    chat_id: int | str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """One-line helper to fan out a single doctor.status_changed entry.

    Caller (typically the daemon's doctor_watch or a playbook step)
    can map a `change` dict from the W157 webhook payload directly
    to a Telegram alert. Returns the same shape as send_telegram.
    """

    chat_id = chat_id if chat_id is not None else os.getenv("TARS_DOCTOR_ALERT_CHAT_ID")
    if chat_id is None or chat_id == "":
        return {"ok": False, "error": "chat_id_required",
                "hint": "set TARS_DOCTOR_ALERT_CHAT_ID env"}

    slug = change.get("slug", "?")
    frm = change.get("from", "?")
    to = change.get("to", "?")
    summary = (change.get("summary") or "").strip()
    emoji = {"ok": "✅", "warn": "⚠️", "fail": "❌", "skip": "·"}.get(to, "•")
    text = f"{emoji} TARS · {slug}: {frm} → {to}"
    if summary:
        text += f"\n{summary}"
    return send_telegram(chat_id, text, token=token)
