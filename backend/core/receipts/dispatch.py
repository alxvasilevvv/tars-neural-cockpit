"""Best-effort, never-throws receipt-record helper (Wave 95).

Other modules (playbook runner, policy gate, wallet router, ...)
fire receipts without coupling to the store: a single
``await record(...)`` call. Any failure (store disabled, SQLite hit,
filesystem error, anything else) is swallowed and logged at DEBUG.

This is the sole hook other modules should use for receipt emission.
Do NOT bypass it — coupling new code to ``ReceiptStore.append``
directly will break callers that disable the module via
``TARS_RECEIPT_STORE=disabled``.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import Receipt
from .store import get_store

log = logging.getLogger("tars.receipts")


async def record(
    type: str,
    actor: str,
    resource: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Receipt | None:
    """Append a receipt and return it; ``None`` on any failure or
    when the store is disabled. Never raises.
    """

    store = get_store()
    if store is None:
        return None
    try:
        return await store.append(
            type=type,
            actor=actor,
            resource=resource,
            payload=dict(payload or {}),
        )
    except Exception as exc:
        log.debug("receipts.dispatch.record failed: %s", exc)
        return None
