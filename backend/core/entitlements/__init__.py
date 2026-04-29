"""Tier-based entitlements + cap enforcement (Phase M / P5).

The *desktop, local-first* edition is unlimited under MIT — entitlements
only gate **cloud** LLM calls + sync features. Free tier ships with
zero cloud budget; Pro/Business unlock pooled cloud budgets billed in
USD or $MEEET.

Public surface:

    from backend.core.entitlements import (
        Tier, TierLimits, LIMITS,
        load_tier, set_tier, can_run,
        format_caps, RouteKind,
    )

The store lives at ``$TARS_ENTITLEMENTS_PATH`` (default
``~/.tars/entitlements.json``). It is a tiny single-tenant JSON file —
the desktop is single-user by design.
"""

from .tiers import (
    LIMITS,
    RouteKind,
    Tier,
    TierLimits,
    UnlimitedDaily,
    format_caps,
)
from .checker import CanRunResult, can_run
from .store import load_tier, set_tier, EntitlementsStore, get_store

__all__ = [
    "Tier",
    "TierLimits",
    "LIMITS",
    "RouteKind",
    "UnlimitedDaily",
    "format_caps",
    "CanRunResult",
    "can_run",
    "load_tier",
    "set_tier",
    "EntitlementsStore",
    "get_store",
]
