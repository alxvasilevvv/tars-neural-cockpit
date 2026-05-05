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
from backend.core.meeet_billing.client import (
    fetch_operator_snapshot,
    is_remote_billing_configured,
)
from web_extras.errors import TARSAPIError


router = APIRouter(prefix="/api/entitlements", tags=["entitlements"])


# Bug #3 fix from docs/SYSTEM_AUDIT_2026-05-02.md — the upgrade
# endpoint historically accepted any non-empty ``payment_token``.
# Until on-chain (SOL / $MEEET) verification lands, the endpoint is
# ``opt-in`` via env so a misconfigured production deploy cannot
# accidentally hand out paid tiers for free.
#
# Modes:
#   * ``off`` (default in production)  → 503 ``feature_disabled``
#   * ``mock`` (dev / staging only)    → accepts the legacy
#     ``payment_token`` mock and emits ``entitlements.upgraded.mock``
#   * ``onchain`` / ``tokens``         → reserved for Solana + $MEEET
#     settlement (503 ``not_implemented`` until wired)
#   * ``stripe``                         → **deprecated alias** for the
#     same stub as ``onchain`` (legacy env only; card rails are not used)
_PAYMENT_MODE_ENV = "TARS_PAYMENT_MODE"


def _payment_mode() -> str:
    return (os.getenv(_PAYMENT_MODE_ENV) or "off").strip().lower()


def _is_onchain_payment_mode(mode: str) -> bool:
    """Paid tier via Solana / $MEEET (and legacy ``stripe`` env alias)."""

    return mode in {"onchain", "tokens", "stripe"}


class UpgradeRequest(BaseModel):
    tier: Literal["free", "pro", "business"] = Field(...)
    payment_token: str | None = Field(
        default=None,
        description=(
            "Mock payment hop in ``mock`` mode — real settlement is "
            "on-chain (SOL / $MEEET). Any non-empty value is accepted in "
            "mock mode; ``free`` requires none."
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
    gate = await can_run(kind="cloud")

    billing_block: dict[str, Any] = {"authority": "local", "source": "local"}
    if is_remote_billing_configured():
        remote = await fetch_operator_snapshot()
        billing_block = {
            "authority": "meeet.world",
            "source": "remote",
            "remote_ok": bool(remote and remote.get("ok") is True),
        }
        if remote and remote.get("ok") is True:
            try:
                tier = Tier(str(remote.get("tier", Tier.FREE.value)))
            except ValueError:
                tier = Tier.FREE
            caps = format_caps(tier)
            live = remote.get("live") or {}
            return {
                "ok": True,
                "tier": tier.value,
                "byo_enabled": bool(remote.get("byo_enabled", False)),
                "upgraded_at": snap.get("upgraded_at"),
                "caps": caps,
                "live": {
                    "spent_usd_24h": round(float(live.get("spent_usd_24h", 0) or 0), 6),
                    "cap_usd_daily": round(float(live.get("cap_usd_daily", 0) or 0), 6),
                    "remaining_usd": round(float(live.get("remaining_usd", 0) or 0), 6),
                    "allowed_cloud": bool(live.get("allowed_cloud", False)),
                    "reason": live.get("reason"),
                },
                "billing": {
                    **billing_block,
                    "account_url": remote.get("account_url"),
                    "checkout": remote.get("checkout") or {},
                },
            }
        billing_block["remote_error"] = (remote or {}).get("error", "unavailable")

    tier = Tier(snap["tier"])
    caps = format_caps(tier)
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
        "billing": billing_block,
    }


@router.post("/upgrade")
async def upgrade(
    body: UpgradeRequest = Body(...),
    x_meeet_trace_id: str | None = Header(default=None),
) -> dict[str, Any]:
    target = Tier(body.tier)
    mode = _payment_mode()

    if is_remote_billing_configured() and target is not Tier.FREE:
        remote = await fetch_operator_snapshot(bypass_cache=True)
        if not remote or remote.get("ok") is not True:
            raise TARSAPIError(
                status_code=503,
                error_code="billing_unreachable",
                message="meeet.world billing is unreachable; paid upgrades require the billing plane",
                hint="retry shortly or check MEEET_BILLING_BASE_URL / network",
                context={"tier_requested": target.value},
            )
        checkout_map = remote.get("checkout") or {}
        redirect = checkout_map.get(target.value) or remote.get("account_url")
        if not redirect:
            raise TARSAPIError(
                status_code=503,
                error_code="not_implemented",
                message="meeet.world billing snapshot is missing checkout URLs for this tier",
                context={"tier_requested": target.value},
            )
        return {
            "ok": True,
            "delegated": True,
            "tier_requested": target.value,
            "redirect": redirect,
            "message": "Complete SOL / $MEEET payment on meeet.world; this host picks up tier from the billing snapshot.",
            "billing": {"authority": "meeet.world", "source": "remote"},
        }

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
                "SOL / $MEEET on-chain upgrade flow to land)"
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

    if _is_onchain_payment_mode(mode):
        # On-chain (SOL / $MEEET) settlement not implemented yet; return 503
        # with a clear "not_implemented" code so cockpit / mobile clients
        # can render a "coming soon" panel instead of pretending.
        raise TARSAPIError(
            status_code=503,
            error_code="not_implemented",
            message=(
                "On-chain payment verification (SOL / $MEEET) is not "
                "implemented yet; fall back to TARS_PAYMENT_MODE=mock "
                "for dev or wait for the next release"
            ),
            hint="watch docs/AGENT_HANDOFF.md for the Solana / $MEEET rollout",
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
        # operator wasn't charged for real. When on-chain settlement lands
        # the event becomes ``entitlements.upgraded`` with a tx id.
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
    if is_remote_billing_configured():
        raise TARSAPIError(
            status_code=503,
            error_code="feature_disabled",
            message="BYO is managed on meeet.world when TARS_BILLING_SOURCE=remote",
            hint="https://meeet.world/account",
        )
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
                "remaining_usd": round(gate.remaining_usd, 6),
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
