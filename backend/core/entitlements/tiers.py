"""Tier enum + limit table.

The numbers below are the launch defaults (Phase M, 2026-04-29). They
are intentionally conservative; bumping them is an additive contract
change that doesn't require a major version bump.

Free
----
- 0 cloud-LLM calls/day (BYO key path is unlimited).
- Unlimited on-device LLM calls.
- All 4 domain packs available.
- No cloud sync.
- No T2T (agent-to-agent commerce).
- No council voting.

Pro · $19/mo (or 200 $MEEET/mo)
-------------------------------
- $10/mo cloud-LLM budget metered against ``usage.tokens.cost_usd``.
- BYO key path is also $9/mo (cheaper since no cloud usage).
- Cloud sync across paired devices.
- 50 T2T deals / month.
- 100 council votes / day.

Business · $79/seat/mo
----------------------
- $40 cloud budget per seat (pooled across the team).
- Unlimited T2T + council votes.
- Audit, SSO, RBAC, private marketplace.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Tier(str, Enum):
    """Canonical entitlement tier."""

    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


# Sentinel — int.MAX is fine for daily caps (we only compare).
UnlimitedDaily = 1_000_000_000


# A `RouteKind` is the same name the meeet usage ledger uses for the
# cost rollup. We deliberately mirror that vocabulary so cap-checking
# is one query, not a translation step.
RouteKind = Literal["edge", "cloud", "fallback", "mixed"]


@dataclass(frozen=True)
class TierLimits:
    """Caps applied per tier.

    All caps are *daily*. The meeet usage ledger rolls cost up by route;
    the entitlements checker compares the rolling 24-h cloud spend
    against ``daily_cloud_budget_usd`` and blocks new cloud calls when
    the cap is hit.
    """

    tier: Tier
    daily_cloud_budget_usd: float
    daily_council_votes: int
    monthly_t2t_deals: int
    cloud_sync: bool
    audit_log: bool
    rbac: bool

    def is_unlimited_council(self) -> bool:
        return self.daily_council_votes >= UnlimitedDaily

    def is_unlimited_t2t(self) -> bool:
        return self.monthly_t2t_deals >= UnlimitedDaily


LIMITS: dict[Tier, TierLimits] = {
    Tier.FREE: TierLimits(
        tier=Tier.FREE,
        daily_cloud_budget_usd=0.00,
        daily_council_votes=0,
        monthly_t2t_deals=0,
        cloud_sync=False,
        audit_log=False,
        rbac=False,
    ),
    Tier.PRO: TierLimits(
        tier=Tier.PRO,
        daily_cloud_budget_usd=10.00 / 30.0,  # $10/mo amortised
        daily_council_votes=100,
        monthly_t2t_deals=50,
        cloud_sync=True,
        audit_log=False,
        rbac=False,
    ),
    Tier.BUSINESS: TierLimits(
        tier=Tier.BUSINESS,
        daily_cloud_budget_usd=40.00 / 30.0,  # $40/seat/mo amortised
        daily_council_votes=UnlimitedDaily,
        monthly_t2t_deals=UnlimitedDaily,
        cloud_sync=True,
        audit_log=True,
        rbac=True,
    ),
}


def format_caps(tier: Tier) -> dict[str, object]:
    """Return a cockpit-friendly dict of the tier's caps + features."""

    lim = LIMITS[tier]
    return {
        "tier": tier.value,
        "daily_cloud_budget_usd": round(lim.daily_cloud_budget_usd, 4),
        "daily_council_votes": (
            None if lim.is_unlimited_council() else lim.daily_council_votes
        ),
        "monthly_t2t_deals": (
            None if lim.is_unlimited_t2t() else lim.monthly_t2t_deals
        ),
        "cloud_sync": lim.cloud_sync,
        "audit_log": lim.audit_log,
        "rbac": lim.rbac,
    }
