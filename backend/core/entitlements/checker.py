"""Cap-checking against the meeet usage ledger.

Public function:

    can_run(*, kind, model=None, since_ts=None) -> CanRunResult

Returns a structured ``CanRunResult`` instead of raising — the agent
runner / orchestrator inspects it and either proceeds, switches the
voice to the BYO key path, or surfaces a 402 at the HTTP edge.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from backend.core.usage.ledger import UsageLedger

from .store import get_store
from .tiers import LIMITS, Tier


@dataclass(frozen=True)
class CanRunResult:
    allowed: bool
    tier: Tier
    reason: str | None
    spent_usd: float
    cap_usd: float
    remaining_usd: float
    byo_enabled: bool


def _seconds_in_24h() -> float:
    return 24 * 60 * 60.0


async def can_run(
    *,
    kind: Literal["edge", "cloud", "fallback", "mixed"] = "cloud",
    model: str | None = None,
    since_ts: float | None = None,
    ledger: UsageLedger | None = None,
) -> CanRunResult:
    """Return whether the operator may make another ``kind`` LLM call.

    - ``kind == "edge"`` always allowed (on-device is unlimited under MIT).
    - ``kind == "cloud"`` checks the rolling 24-h cloud-LLM spend
      against the tier's ``daily_cloud_budget_usd``.
    - ``kind == "fallback"`` / ``"mixed"`` follow the same gate as cloud.
    - When the operator toggled BYO on, cloud calls are *also* allowed
      (the cost lands on their key, not on TARS' pooled budget).

    ``model`` is reserved for future per-model gating.
    """

    snapshot = get_store().snapshot()
    try:
        tier = Tier(snapshot.get("tier", Tier.FREE.value))
    except ValueError:
        tier = Tier.FREE
    byo = bool(snapshot.get("byo_enabled", False))
    limits = LIMITS[tier]

    if kind == "edge":
        return CanRunResult(
            allowed=True,
            tier=tier,
            reason=None,
            spent_usd=0.0,
            cap_usd=0.0,
            remaining_usd=0.0,
            byo_enabled=byo,
        )

    spent = await _spend_24h(ledger, since_ts=since_ts, kind=kind)

    if byo:
        # BYO: cap doesn't apply, but we still track spend for visibility.
        return CanRunResult(
            allowed=True,
            tier=tier,
            reason=None,
            spent_usd=spent,
            cap_usd=limits.daily_cloud_budget_usd,
            remaining_usd=limits.daily_cloud_budget_usd,
            byo_enabled=True,
        )

    cap = limits.daily_cloud_budget_usd
    remaining = max(0.0, cap - spent)

    if remaining <= 0:
        return CanRunResult(
            allowed=False,
            tier=tier,
            reason="cap_hit",
            spent_usd=spent,
            cap_usd=cap,
            remaining_usd=0.0,
            byo_enabled=False,
        )
    return CanRunResult(
        allowed=True,
        tier=tier,
        reason=None,
        spent_usd=spent,
        cap_usd=cap,
        remaining_usd=remaining,
        byo_enabled=False,
    )


async def _spend_24h(
    ledger: UsageLedger | None,
    *,
    since_ts: float | None,
    kind: str,
) -> float:
    """Sum cost_usd over the last 24 h for the given route kind."""

    led = ledger or UsageLedger()
    cutoff = since_ts if since_ts is not None else time.time() - _seconds_in_24h()
    rollup = await led.rollup(since=cutoff)
    by_route = rollup.by_route or {}
    bucket = by_route.get(kind) or by_route.get("cloud") or {}
    raw = bucket.get("cost_usd", 0.0) if isinstance(bucket, dict) else 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0
