"""Background dispatcher loop.

Runs every ``TARS_WEBHOOKS_DISPATCH_INTERVAL_S`` seconds (default 30,
``0`` disables) and fires deliveries that are ``pending`` or
``retry`` past their ``next_attempt_at``. Same safety contract as the
other lifespan loops in :mod:`web_extras.app`:

- Disabled when the env interval is 0 or
  ``TARS_WEBHOOKS_ENABLED`` is unset / falsy.
- Disabled when the webhooks store is disabled.
- Never propagates exceptions; per-tick failures are logged + the
  loop continues.
"""

from __future__ import annotations

import asyncio
import logging
import os

from .dispatcher import fire_delivery
from .store import WebhookStore, get_store

log = logging.getLogger("tars.webhooks.loop")


def _interval_s() -> float:
    raw = os.getenv("TARS_WEBHOOKS_DISPATCH_INTERVAL_S")
    if raw is None:
        return 30.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 30.0


def _is_enabled() -> bool:
    flag = (os.getenv("TARS_WEBHOOKS_ENABLED") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _batch_limit() -> int:
    raw = os.getenv("TARS_WEBHOOKS_DISPATCH_BATCH")
    if raw is None:
        return 50
    try:
        return max(1, min(int(raw), 500))
    except ValueError:
        return 50


async def webhooks_dispatcher_loop() -> None:
    """Lifespan task — opt-in via ``TARS_WEBHOOKS_ENABLED=1``."""

    if not _is_enabled():
        return
    interval = _interval_s()
    if interval <= 0:
        return
    store: WebhookStore = get_store()
    if not store.enabled:
        return
    limit = _batch_limit()
    log.info(
        "webhooks dispatcher loop active: interval_s=%.1f batch=%s db=%s",
        interval,
        limit,
        store.db_path,
    )
    while True:
        try:
            await asyncio.sleep(interval)
            due = await store.list_due_deliveries(limit=limit)
            if not due:
                continue
            for delivery in due:
                hook = await store.get_outgoing(delivery.webhook_id)
                if hook is None or not hook.active:
                    # Webhook was deleted / deactivated mid-flight; mark
                    # the delivery as failed so we stop trying.
                    from .models import DeliveryStatus

                    await store.patch_delivery(
                        delivery.id,
                        {
                            "status": DeliveryStatus.FAILED,
                            "last_error": "webhook_inactive",
                            "next_attempt_at": None,
                        },
                    )
                    continue
                try:
                    await fire_delivery(delivery, webhook=hook, store=store)
                except Exception as exc:  # never crash the loop
                    log.warning(
                        "webhooks loop fire failed: id=%s err=%s: %s",
                        delivery.id,
                        type(exc).__name__,
                        exc,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("webhooks loop tick failed: %s", exc)
