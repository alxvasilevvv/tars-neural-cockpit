"""Wallet audit log helpers (Phase O4).

By default, ``wallet.*_signed`` Meeet events carry the *metadata* of
a signed transaction (tx_signature / hash / body_hash) but **not** the
raw broadcastable bytes (raw_b64 / boc / raw_hex). This is a
privacy-by-default stance: raw bytes contain the full destination /
amount / nonce, and writing them to the local meeet store means
they're re-readable forever.

Operators who want a full audit trail (compliance, paranoia, forensic
replay) can opt in via ``TARS_AUDIT_RAW_TX=1``. When enabled:

- :func:`enrich_signed_event` returns a payload dict that includes
  the raw fields.
- :func:`prune_signed_events` removes entries older than
  ``TARS_AUDIT_RETENTION_DAYS`` (default 30) from the meeet store.
  Operators can wire this into a cron / launchd job.

Raw audit is independent of policy_gate (O2) and structured errors
(O1) — purely additive. When the flag is off everything behaves
identically to the pre-O4 world.
"""

from __future__ import annotations

import os
import time
from typing import Any, Mapping


def is_enabled() -> bool:
    return os.getenv("TARS_AUDIT_RAW_TX", "0") in ("1", "true", "yes")


def retention_seconds() -> int:
    """Audit log retention window in seconds. Default: 30 days."""
    raw = os.getenv("TARS_AUDIT_RETENTION_DAYS", "30")
    try:
        days = max(1, int(raw))
    except ValueError:
        days = 30
    return days * 24 * 60 * 60


def enrich_signed_event(
    *,
    base: Mapping[str, Any],
    signed: Mapping[str, Any],
    raw_keys: tuple[str, ...] = ("raw_b64", "raw_b58", "raw_hex", "boc", "body_hash"),
) -> dict[str, Any]:
    """Return a copy of ``base`` with raw signed fields attached
    iff the audit flag is on.

    ``signed`` is the dict returned by ``sign_*_transfer`` /
    ``sign_*_tx``. ``raw_keys`` whitelists which fields to copy
    over — defaults cover Solana, EVM, and TON.

    TODO(v9.3): the wallet router callers should ALSO fire a
    receipt via :func:`backend.core.receipts.record`. As of Wave 95
    the receipt-ledger is the canonical signed audit trail —
    ``enrich_signed_event`` keeps emitting raw-tx metadata to the
    meeet store for backward-compat with O4 audit mode, and will be
    deprecated in v9.3 once every wallet caller writes through the
    receipt ledger directly.
    """

    out: dict[str, Any] = dict(base)
    out["audit_raw_attached"] = is_enabled()
    if is_enabled():
        for k in raw_keys:
            v = signed.get(k)
            if v is not None:
                out[k] = v
    return out


async def prune_signed_events(
    *,
    now_seconds: float | None = None,
) -> int:
    """Drop ``wallet.*_signed`` events older than the retention window.

    Returns the number of rows pruned. Cheap (~1ms even on a fat store)
    because the meeet table is indexed on ``timestamp``.

    Safe to call when audit is OFF — still removes any historical
    rows that were emitted while it was on.
    """

    from backend.core.meeet import get_store

    store = get_store()
    if store is None:
        return 0
    cutoff = (now_seconds if now_seconds is not None else time.time()) - retention_seconds()
    return await store.prune_kind_before(
        kind_prefix="wallet.",
        kind_suffix="_signed",
        before_unix=cutoff,
    )
