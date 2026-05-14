"""TARS usage metering subsystem (W235).

Public surface for the consumption console + meeet.world billing
ingest. Hot-path callers should use :func:`record_usage` exclusively
— never poke the SQLite or receipt store directly.

Shape (see :class:`UsageEvent`):

    trace_id, ts_utc, provider, model, action, tokens_in,
    tokens_out, latency_ms, cost_usd, cost_meeet, outcome,
    tier, agent_id, domain_pack

Three sinks fire on every event:

1. ``~/.tars/usage.sqlite`` — fast-query mirror (``usage_events``
   table). Drives ``/api/usage/console`` panels.
2. Receipt ledger (kind=``usage``) — hash-chained tamper-evident
   trail for compliance + audit export.
3. POST to ``{MEEET_BASE_URL}/api/billing/usage_event`` (HMAC-signed)
   when ``MEEET_MODE=live`` AND the brother edge is reachable.
   Failures land in ``usage_retry_queue`` for a later manual sync.

Pricing + tier caps live inline in ``recorder.py`` to keep the
metering module self-contained — operators who need overrides
should patch the ``PRICING`` dict at startup or set
``TARS_PRICE_OVERRIDES_JSON``.
"""

from __future__ import annotations

from .recorder import (
    PRICING,
    TIER_CAPS,
    TOPUP_URL_DEFAULT,
    UsageEvent,
    aggregate_month,
    aggregate_today,
    cap_alert_level,
    cap_status,
    compute_cost_usd,
    current_balance_local,
    get_recent_events,
    healthz,
    is_request_allowed,
    maybe_fire_cap_notification,
    record_usage,
    reset_cap_notify_log,
    resolve_tier,
    retry_failed_sync,
    subscribe,
    unsubscribe,
)

__all__ = [
    "PRICING",
    "TIER_CAPS",
    "TOPUP_URL_DEFAULT",
    "UsageEvent",
    "aggregate_month",
    "aggregate_today",
    "cap_alert_level",
    "cap_status",
    "compute_cost_usd",
    "current_balance_local",
    "get_recent_events",
    "healthz",
    "is_request_allowed",
    "maybe_fire_cap_notification",
    "record_usage",
    "reset_cap_notify_log",
    "resolve_tier",
    "retry_failed_sync",
    "subscribe",
    "unsubscribe",
]
