"""Notification bridges — iMessage, Telegram, Email (Wave 160).

The W148 reality audit flagged ``backend/core/notifications/`` as
honesty drift: task #66 was marked complete but no code existed.
Wave 160 closes that gap with a real iMessage bridge.

v0.1 scope:
  - macOS iMessage send via AppleScript (``osascript``)
  - macOS iMessage inbox read via ``~/Library/Messages/chat.db``
    (SQLite, read-only)
  - Telegram + Email stubs left for v9.1.2 and v9.2

Honest framing:
  - **macOS only.** iMessage is an Apple product; no Linux/Windows
    equivalent. The module returns clear "not supported on platform"
    errors elsewhere.
  - **Read requires Full Disk Access.** macOS sandboxes
    ``~/Library/Messages/chat.db`` — the operator must grant the
    Terminal (or whatever process runs TARS) FDA in System
    Settings. We surface a helpful error if the file isn't
    readable.
  - **Send requires Messages.app to be running** and the
    destination handle to already exist in Contacts (Apple-side
    behaviour).
  - **No auto-reply.** The bridge offers send + read primitives;
    operators must explicitly wire an automation if they want
    auto-respond behaviour. (Per the safety rules: messaging
    on-behalf-of requires explicit per-message approval.)
"""

from __future__ import annotations

from .imessage import (
    CONTRACT_VERSION,
    IMessageError,
    Message,
    fanout_doctor_change as imessage_fanout_doctor_change,
    is_supported,
    recent_messages,
    send_imessage,
)
from .telegram import (
    fanout_doctor_change as telegram_fanout_doctor_change,
    is_configured as telegram_is_configured,
    send_telegram,
)
from .email import (
    fanout_doctor_change as email_fanout_doctor_change,
    is_configured as email_is_configured,
    send_email,
)

# Keep `fanout_doctor_change` as the Telegram default for callers
# that didn't specify a channel (back-compat with W161).
from .telegram import fanout_doctor_change


def fanout_all(
    change: dict,
    *,
    channels: list[str] | None = None,
) -> list[dict]:
    """Wave 162 — dispatch a single doctor change across N channels.

    ``channels`` is a list of channel slugs. If omitted, reads
    ``TARS_DAEMON_FANOUT_CHANNELS`` env (comma-separated). Returns
    a list of per-channel result dicts in input order.

    Recognised channels: ``telegram``, ``imessage``.
    Unknown channels are skipped with a ``unknown_channel`` result.
    """

    import os

    if channels is None:
        raw = (os.getenv("TARS_DAEMON_FANOUT_CHANNELS") or "").strip()
        channels = [c.strip().lower() for c in raw.split(",") if c.strip()]

    results: list[dict] = []
    for ch in channels:
        if ch == "telegram":
            results.append({"channel": "telegram", **telegram_fanout_doctor_change(change)})
        elif ch == "imessage":
            results.append({"channel": "imessage", **imessage_fanout_doctor_change(change)})
        elif ch == "email":
            results.append({"channel": "email", **email_fanout_doctor_change(change)})
        else:
            results.append({"channel": ch, "ok": False, "error": "unknown_channel"})
    return results


__all__ = [
    "CONTRACT_VERSION",
    "IMessageError",
    "Message",
    "email_fanout_doctor_change",
    "email_is_configured",
    "fanout_all",
    "fanout_doctor_change",
    "imessage_fanout_doctor_change",
    "is_supported",
    "recent_messages",
    "send_email",
    "send_imessage",
    "send_telegram",
    "telegram_fanout_doctor_change",
    "telegram_is_configured",
]
