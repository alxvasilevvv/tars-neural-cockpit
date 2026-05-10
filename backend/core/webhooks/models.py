"""Dataclasses + ID helpers for the webhooks module.

Three core records:

- :class:`OutgoingWebhook` — operator-registered URL the dispatcher
  POSTs signed events to.
- :class:`IncomingWebhook` — token-protected entry point external
  systems call into to trigger a playbook.
- :class:`Delivery` — one outgoing dispatch attempt; the retry loop
  walks rows that are ``pending`` or ``retry`` past their
  ``next_attempt_at``.

Plus :func:`build_envelope`, the shared event JSON shape:

    {"id": "...", "type": "playbook.started", "occurred_at": 1.7e9, "data": {...}}

External consumers should treat unknown ``type`` values as no-ops
and use ``id`` as the idempotency key.
"""

from __future__ import annotations

import enum
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# ---------- ID + token helpers -----------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_outgoing_id() -> str:
    return _short_id("ohk")


def new_incoming_id() -> str:
    return _short_id("ihk")


def new_delivery_id() -> str:
    return _short_id("del")


def new_event_id() -> str:
    return _short_id("evt")


def new_token(nbytes: int = 32) -> str:
    """URL-safe random token used for incoming webhook auth."""

    return secrets.token_urlsafe(nbytes)


# ---------- Envelope ---------------------------------------------------------


def build_envelope(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Standard outgoing event envelope.

    Stable shape — third-party integrations rely on these field
    names. Any additions go inside ``data``, never at the top level.
    """

    return {
        "id": new_event_id(),
        "type": event_type,
        "occurred_at": time.time(),
        "data": dict(data),
    }


# ---------- Outgoing ---------------------------------------------------------


@dataclass
class OutgoingWebhook:
    """Operator-registered destination for outgoing events."""

    id: str
    name: str
    url: str
    secret: bytes
    event_filter: list[str]  # glob patterns, e.g. ["playbook.*", "hil.requested"]
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def matches(self, event_type: str) -> bool:
        if not self.active:
            return False
        if not self.event_filter:
            return True  # explicit empty filter == subscribe to everything
        from fnmatch import fnmatchcase

        for pattern in self.event_filter:
            if fnmatchcase(event_type, pattern):
                return True
        return False


# ---------- Incoming ---------------------------------------------------------


@dataclass
class IncomingWebhook:
    """Token-protected inbound entry point."""

    id: str
    name: str
    token: str  # URL-safe random; carried in the path
    trigger_playbook_id: str | None = None
    allowed_event_schemas: list[dict[str, Any]] = field(default_factory=list)
    active: bool = True
    created_at: float = field(default_factory=time.time)


# ---------- Delivery ---------------------------------------------------------


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


# Retry schedule (seconds after the *previous* attempt). Index = attempt
# number minus one. Length defines max attempts.
RETRY_BACKOFF_S: tuple[int, ...] = (30, 120, 600, 3600)
MAX_ATTEMPTS = len(RETRY_BACKOFF_S)


def next_attempt_delay(attempts: int) -> int | None:
    """Seconds to wait before attempt ``attempts + 1``.

    Returns ``None`` once the retry budget is exhausted (caller should
    mark the delivery ``failed``).
    """

    if attempts < 1:
        return RETRY_BACKOFF_S[0]
    if attempts >= MAX_ATTEMPTS:
        return None
    return RETRY_BACKOFF_S[attempts]


@dataclass
class Delivery:
    """One outgoing dispatch attempt."""

    id: str
    webhook_id: str
    event_id: str
    event_type: str
    payload_json: str  # serialised envelope (stable across retries)
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    last_attempt_at: float | None = None
    next_attempt_at: float | None = None
    last_error: str | None = None
    last_status_code: int | None = None
    signature_used: str | None = None
    created_at: float = field(default_factory=time.time)
