"""TARS webhooks subsystem (Wave 90).

Provides outgoing dispatch + incoming inbox for B2B integrations
(Slack, Stripe, GitHub Actions, Zapier, n8n, custom). The whole
module is opt-in: it persists to its own SQLite DB at
``~/.tars/webhooks.sqlite`` (override via ``TARS_WEBHOOKS_DB_PATH``)
and the background dispatcher loop only runs when
``TARS_WEBHOOKS_ENABLED=1``.

Public surface:

- :mod:`.models`     — dataclasses + event envelope helpers.
- :mod:`.signing`    — HMAC-SHA256 sign / verify (replay window).
- :mod:`.store`      — SQLite-backed CRUD + delivery state machine.
- :mod:`.dispatcher` — outgoing fire (single delivery + retry).
- :mod:`.dispatcher_loop` — periodic scan-and-fire for retries.
- :mod:`.inbox`      — incoming token validation + playbook dispatch.
- :func:`emit`       — convenience helper called by event sources;
  swallows every exception so it never breaks the caller.

Contract version: 1.0 (see ``docs/contracts/WEBHOOKS.md``).
"""

from __future__ import annotations

from .models import (
    CONTRACT_VERSION,
    Delivery,
    DeliveryStatus,
    IncomingWebhook,
    OutgoingWebhook,
    build_envelope,
    new_delivery_id,
    new_event_id,
    new_incoming_id,
    new_outgoing_id,
    new_token,
)
from .signing import sign_payload, verify_payload
from .store import WebhookStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "Delivery",
    "DeliveryStatus",
    "IncomingWebhook",
    "OutgoingWebhook",
    "WebhookStore",
    "build_envelope",
    "emit",
    "get_store",
    "new_delivery_id",
    "new_event_id",
    "new_incoming_id",
    "new_outgoing_id",
    "new_token",
    "reset_store",
    "sign_payload",
    "verify_payload",
]


async def emit(event_type: str, payload: dict) -> dict:
    """Fire-and-forget webhook emit hook.

    Designed for hot paths (runner, policy gate, wallet, agents store).
    NEVER raises — any failure is swallowed and logged at debug level
    so the calling code keeps running.

    Returns ``{ok, count}`` where ``count`` is the number of outgoing
    webhooks queued for delivery (zero when the module is disabled
    or no webhooks match the event filter).
    """

    try:
        from .dispatcher import dispatch  # local import keeps cold-start light

        store = get_store()
        if not store.enabled:
            return {"ok": True, "count": 0, "reason": "disabled"}
        return await dispatch(event_type, payload, store=store)
    except Exception as exc:  # pragma: no cover — never break callers
        import logging

        logging.getLogger("tars.webhooks").debug(
            "webhooks.emit swallowed: %s: %s", type(exc).__name__, exc
        )
        return {"ok": False, "count": 0, "error": str(exc)}
