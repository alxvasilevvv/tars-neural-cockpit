"""HTTP surface — entitlements (Phase M / P5).

Endpoints:

- ``GET  /api/entitlements``         → current tier + caps + 24h spend.
- ``POST /api/entitlements/upgrade`` → set tier (mocks the payment hop).
- ``POST /api/entitlements/byo``     → toggle the BYO-key path.
- ``POST /api/entitlements/can_run`` → ask the gate before issuing a
                                       cloud LLM call.

Every state-changing call emits a structured ``entitlements.*`` event
into the meeet store so the cockpit / audit page can render the
upgrade history.
"""

from __future__ import annotations

import os
import time
from typing import Any, Literal

from fastapi import APIRouter, Body, Header
from pydantic import BaseModel, Field

from backend.core.entitlements import (
    LIMITS,
    Tier,
    can_run,
    format_caps,
    get_store,
)
from backend.core.meeet import get_client, trace_scope
from web_extras.errors import TARSAPIError


router = APIRouter(prefix="/api/entitlements", tags=["entitlements"])


# Bug #3 fix from docs/SYSTEM_AUDIT_2026-05-02.md — the upgrade
# endpoint historically accepted any non-empty ``payment_token``.
# Until real Stripe / wallet integration lands, the endpoint is
# now ``opt-in`` via env so a misconfigured production deploy
# can't accidentally hand out paid tiers for free.
#
# Modes:
#   * ``off`` (default in production)  → 503 ``feature_disabled``
#   * ``mock`` (dev / staging only)    → accepts the legacy
#     ``payment_token`` mock and emits ``entitlements.upgraded.mock``
#   * ``stripe`` (when integration is live)
#                                      → real verification path
#                                        (TBD; rejects with 503 +
#                                        ``not_implemented`` until then)
_PAYMENT_MODE_ENV = "TARS_PAYMENT_MODE"


def _payment_mode() -> str:
    return (os.getenv(_PAYMENT_MODE_ENV) or "off").strip().lower()


class UpgradeRequest(BaseModel):
    tier: Literal["free", "pro", "business"] = Field(...)
    payment_token: str | None = Field(
        default=None,
        description=(
            "Mock payment hop — the real flow lands when the meeet "
            "wallet integration is live. Any non-empty value is accepted "
            "for now; ``free`` requires none."
        ),
    )


class BYORequest(BaseModel):
    enabled: bool


class CanRunRequest(BaseModel):
    kind: Literal["edge", "cloud", "fallback", "mixed"] = "cloud"
    model: str | None = None


@router.get("")
async def get_entitlements(
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    snap = get_store().snapshot()
    tier = Tier(snap["tier"])
    caps = format_caps(tier)

    # Live spend + cap remainder so the cockpit doesn't have to call
    # /api/usage and join itself.
    gate = await can_run(kind="cloud")

    return {
        "ok": True,
        "tier": tier.value,
        "byo_enabled": bool(snap.get("byo_enabled", False)),
        "upgraded_at": snap.get("upgraded_at"),
        "caps": caps,
        "live": {
            "spent_usd_24h": round(gate.spent_usd, 6),
            "cap_usd_daily": round(gate.cap_usd, 6),
            "remaining_usd": round(gate.remaining_usd, 6),
            "allowed_cloud": gate.allowed,
            "reason": gate.reason,
        },
    }


@router.post("/upgrade")
async def upgrade(
    body: UpgradeRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    target = Tier(body.tier)
    mode = _payment_mode()

    # Downgrade to FREE is always allowed (no payment hop needed).
    if target is Tier.FREE:
        previous = get_store().load()
        record = get_store().set_tier(target)
        client = get_client()
        with trace_scope(parent=x_meeet_trace_id) as trace_id:
            await client.emit(
                "entitlements.downgraded",
                {
                    "from": previous.value,
                    "to": target.value,
                    "at": record.get("upgraded_at", time.time()),
                },
            )
            return {
                "ok": True,
                "trace_id": trace_id,
                "tier": target.value,
                "previous": previous.value,
                "byo_enabled": bool(record.get("byo_enabled", False)),
                "caps": format_caps(target),
            }

    # Paid tier path. The pre-2026-05-02 audit gate accepted any
    # non-empty ``payment_token`` — see Bug #3. Now the env decides:
    if mode == "off":
        raise TARSAPIError(
            status_code=503,
            error_code="feature_disabled",
            message=(
                "paid tier upgrades are disabled in this deployment "
                f"(set {_PAYMENT_MODE_ENV}=mock for dev or wait for the "
                "Stripe / $MEEET wallet integration to land)"
            ),
            hint=(
                f"export {_PAYMENT_MODE_ENV}=mock for dev shells, or "
                "follow the upgrade flow on meeet.world once payments "
                "are wired"
            ),
            context={
                "payment_mode": mode,
                "tier_requested": target.value,
            },
        )

    if mode == "stripe":
        # Real integration not implemented yet; return 503 with a
        # clear "not_implemented" code so cockpit / mobile clients
        # can render a "coming soon" panel instead of pretending.
        raise TARSAPIError(
            status_code=503,
            error_code="not_implemented",
            message=(
                "Stripe payment verification is not implemented yet; "
                "fall back to TARS_PAYMENT_MODE=mock for dev or wait "
                "for the next release"
            ),
            hint="watch docs/AGENT_HANDOFF.md for the Stripe rollout",
            context={"payment_mode": mode},
        )

    # mode == "mock": accept any non-empty payment_token (legacy path).
    if not body.payment_token:
        raise TARSAPIError(
            status_code=402,
            error_code="payment_required",
            message="payment_token required for paid tiers",
            hint="pass {tier:'pro', payment_token:<...>} (mock mode accepts any non-empty value)",
        )
    previous = get_store().load()
    record = get_store().set_tier(target)
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        # Emit a *mock* event kind so the audit trail shows the
        # operator wasn't charged for real. When Stripe lands the
        # event becomes ``entitlements.upgraded`` with a charge id.
        await client.emit(
            "entitlements.upgraded.mock",
            {
                "from": previous.value,
                "to": target.value,
                "at": record.get("upgraded_at", time.time()),
                # We never log the payment token. Operators on a hostile
                # network would see it bounce through CloudFront — keep
                # it out of the audit trail.
                "payment_token_present": bool(body.payment_token),
                "payment_mode": mode,
            },
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "tier": target.value,
            "previous": previous.value,
            "byo_enabled": bool(record.get("byo_enabled", False)),
            "caps": format_caps(target),
            "payment_mode": mode,
        }


@router.post("/byo")
async def toggle_byo(
    body: BYORequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    record = get_store().set_byo(body.enabled)
    client = get_client()
    with trace_scope(parent=x_meeet_trace_id) as trace_id:
        await client.emit(
            "entitlements.byo_toggled",
            {
                "enabled": bool(record.get("byo_enabled", False)),
                "tier": record.get("tier", Tier.FREE.value),
            },
        )
        return {
            "ok": True,
            "trace_id": trace_id,
            "byo_enabled": bool(record.get("byo_enabled", False)),
        }


@router.post("/can_run")
async def post_can_run(
    body: CanRunRequest = Body(default_factory=CanRunRequest),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    gate = await can_run(kind=body.kind, model=body.model)
    if not gate.allowed:
        # We deliberately don't surface a 402 here — the cockpit may
        # be polling proactively to render BudgetWarning before any
        # call goes out. The HTTP edge that *executes* the cloud call
        # is responsible for raising 402 when it sees `allowed=False`.
        client = get_client()
        with trace_scope(parent=x_meeet_trace_id) as trace_id:
            await client.emit(
                "entitlements.cap_hit",
                {
                    "tier": gate.tier.value,
                    "kind": body.kind,
                    "spent_usd": round(gate.spent_usd, 6),
                    "cap_usd": round(gate.cap_usd, 6),
                },
            )
            return {
                "ok": True,
                "trace_id": trace_id,
                "allowed": False,
                "reason": gate.reason,
                "tier": gate.tier.value,
                "byo_enabled": gate.byo_enabled,
                "spent_usd": round(gate.spent_usd, 6),
                "cap_usd": round(gate.cap_usd, 6),
                "remaining_usd": 0.0,
            }
    return {
        "ok": True,
        "allowed": True,
        "tier": gate.tier.value,
        "byo_enabled": gate.byo_enabled,
        "spent_usd": round(gate.spent_usd, 6),
        "cap_usd": round(gate.cap_usd, 6),
        "remaining_usd": round(gate.remaining_usd, 6),
    }


@router.get("/tiers")
async def list_tiers() -> dict[str, Any]:
    """Static tier table — useful for keeping cockpit Pricing in sync."""

    return {
        "ok": True,
        "tiers": [format_caps(t) for t in LIMITS.keys()],
    }
