"""HTTP-edge cap enforcement for cloud-LLM-touching endpoints.

Bug #2 fix from ``docs/SYSTEM_AUDIT_2026-05-02.md``.
The system audit found that ``backend.core.entitlements.can_run``
exists and the gate is correct, but **0 of 4 cloud paths invoke
it before issuing the call**. A FREE-tier operator could
``POST /api/planner/{id}/run`` and burn the pooled cloud budget
to zero. This module is the seam that closes that gap at the HTTP
edge — orchestrators stay route-agnostic, the router decides
"is this a cloud-touching call?" and gates accordingly.

Public surface:

- :func:`require_cloud_budget` — async helper. Awaits the gate
  and raises :class:`TARSAPIError` with HTTP 402 (+
  ``error_code="payment_required"``) when the cap is hit. Emits
  ``entitlements.cap_hit`` to the meeet store inside the active
  trace so the cockpit / audit page surfaces the block.
- :func:`is_cap_enforcement_enabled` — env-driven kill switch
  (``TARS_CAP_ENFORCEMENT=off`` disables enforcement entirely
  for tests / dev). Defaults ``on`` everywhere.
- :class:`CapHit` — exposed for tests that want to assert the
  exception payload shape.

Why HTTP-edge and not orchestrator-edge:

- One choke point per cloud-touching route is much easier to
  reason about than threading a gate through every voice / LLM
  adapter. Each affected router gets one ``await
  require_cloud_budget(...)`` line right after request validation.
- The orchestrator is allowed to mix edge + cloud calls inside
  one turn; the HTTP layer enforces per-request, not per-call.
  When a tier upgrade is needed mid-stream the next request
  re-evaluates.
- This mirrors what pairing / recovery already do with
  ``RateLimiter`` (Bug #4 follows the same pattern).

Why not just block from inside ``can_run`` itself:

- ``can_run`` returns a structured ``CanRunResult`` so
  cockpit-side BudgetWarning components can poll without
  triggering 402s. This module is the *enforcement* sibling that
  lives at the HTTP edge.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from backend.core.entitlements import can_run as _can_run
from backend.core.meeet import current_trace, get_client
from web_extras.errors import TARSAPIError


# Public alias so callers don't have to import from a deep package.
RouteKind = Literal["edge", "cloud", "fallback", "mixed"]


@dataclass(frozen=True)
class CapHit:
    """Snapshot of the offending budget state when 402 is raised.

    Attached to :class:`TARSAPIError.context`` so the cockpit can
    render a structured "cap hit" panel instead of a raw error
    message.
    """

    tier: str
    kind: str
    spent_usd: float
    cap_usd: float
    reason: str | None
    byo_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": self.tier,
            "kind": self.kind,
            "spent_usd": round(self.spent_usd, 6),
            "cap_usd": round(self.cap_usd, 6),
            "reason": self.reason,
            "byo_enabled": self.byo_enabled,
        }


def is_cap_enforcement_enabled() -> bool:
    """Env kill-switch. Defaults to enabled.

    Set ``TARS_CAP_ENFORCEMENT=off`` (or ``0`` / ``false``) to
    bypass enforcement entirely — useful for ``pytest`` runs
    that don't want to seed an entitlements DB and for dev shells
    where the operator is on FREE but wants to exercise the
    cloud path.
    """

    raw = (os.getenv("TARS_CAP_ENFORCEMENT") or "").strip().lower()
    if raw in {"off", "0", "false", "no", "disabled"}:
        return False
    return True


async def require_cloud_budget(
    *,
    kind: RouteKind = "cloud",
    model: str | None = None,
    surface: str,
) -> None:
    """Block when the cap is exhausted; emit ``entitlements.cap_hit``.

    Parameters
    ----------
    kind:
        Route kind to gate. ``"edge"`` is always allowed.
        ``"cloud"`` / ``"fallback"`` / ``"mixed"`` follow the
        cloud cap.
    model:
        Optional model hint (passed straight through to
        ``can_run``; reserved for future per-model gating).
    surface:
        Short label of the calling endpoint (e.g.
        ``"voice.speak"`` / ``"council.deliberate"``). Surfaces
        in the meeet event payload so the cockpit can attribute
        the block to a specific endpoint.

    Raises
    ------
    TARSAPIError
        HTTP 402 with ``error_code="payment_required"`` when the
        cap is hit. Otherwise returns ``None`` and the caller
        proceeds.
    """

    if not is_cap_enforcement_enabled():
        return

    if kind == "edge":
        # Edge calls don't touch the cloud cap; nothing to gate.
        return

    gate = await _can_run(kind=kind, model=model)
    if gate.allowed:
        return

    cap_hit = CapHit(
        tier=gate.tier.value,
        kind=kind,
        spent_usd=gate.spent_usd,
        cap_usd=gate.cap_usd,
        reason=gate.reason,
        byo_enabled=gate.byo_enabled,
    )

    # Emit a structured cap_hit event so the cockpit timeline /
    # audit page renders the block. We don't want to crash on a
    # meeet outage — wrap the emit so the 402 still flies even
    # when the durable buffer is unhappy.
    try:
        await get_client().emit(
            "entitlements.cap_hit",
            {
                **cap_hit.to_dict(),
                "surface": surface,
                "trace_id": current_trace(),
            },
        )
    except Exception:
        # Intentionally swallow — the operator-facing 402 is the
        # point. Loss-of-event is recoverable through replay.
        pass

    raise TARSAPIError(
        status_code=402,
        error_code="payment_required",
        message=(
            f"daily cloud budget exhausted for tier {gate.tier.value}: "
            f"spent ${gate.spent_usd:.4f} of ${gate.cap_usd:.4f}; "
            f"upgrade or enable BYO to continue"
        ),
        hint=(
            "POST /api/entitlements/upgrade {tier:'pro'|'business', payment_token:<...>} "
            "or POST /api/entitlements/byo {enabled:true}"
        ),
        context=cap_hit.to_dict() | {"surface": surface},
    )


__all__ = [
    "CapHit",
    "RouteKind",
    "is_cap_enforcement_enabled",
    "require_cloud_budget",
]
