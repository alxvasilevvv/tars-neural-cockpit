"""Cost ledger for council voices and adapters.

The ledger doesn't keep its own database — it derives rollups from the
meeet event store (`backend/core/meeet/store.py`) which already
persists every ``usage.tokens`` and ``sampler.decision`` event with
``trace_id``, ``session_id``, and ``route`` tags.

This keeps the source of truth single (meeet), which means cost data
survives replay-from-cold-start and is filterable by the same
session/route dimensions as the rest of observability.

Pricing is approximate and configurable via :class:`PriceTable`. We
ship reasonable defaults for the LLM voices that ship today; missing
models report ``cost_usd=None`` and the UI shows "n/a" rather than a
fabricated number.
"""

from .ledger import (
    PriceEntry,
    PriceTable,
    UsageLedger,
    UsageLine,
    UsageRollup,
    default_price_table,
    get_ledger,
    reset_ledger,
)

__all__ = [
    "PriceEntry",
    "PriceTable",
    "UsageLedger",
    "UsageLine",
    "UsageRollup",
    "default_price_table",
    "get_ledger",
    "reset_ledger",
]
