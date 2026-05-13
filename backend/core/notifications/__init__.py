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
    is_supported,
    recent_messages,
    send_imessage,
)
from .telegram import (
    fanout_doctor_change,
    is_configured as telegram_is_configured,
    send_telegram,
)


__all__ = [
    "CONTRACT_VERSION",
    "IMessageError",
    "Message",
    "fanout_doctor_change",
    "is_supported",
    "recent_messages",
    "send_imessage",
    "send_telegram",
    "telegram_is_configured",
]
