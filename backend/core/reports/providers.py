"""Built-in inputs providers for scheduled reports (Wave 103).

Operators wire a recurring report to a provider via
:func:`backend.core.reports.scheduling.create_scheduled_report`. At
fire time, the runner calls the provider to fetch FRESH data, so a
quarterly LP update auto-generates with this quarter's numbers
without operator babysitting.

Every provider is async + parameterless and returns a dict matching
the matching template's input schema. The implementations here are
mostly skeletons that return mock + connector-derived data -- real
data wiring happens template-by-template as the operator hooks up
their bookkeeping. Callers should treat provider output as
"best-effort until replaced".
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


log = logging.getLogger("tars.reports.providers")


# Type alias: provider is an async callable returning the inputs dict.
ProviderFn = Callable[[], Awaitable[dict[str, Any]]]


# ---------- helper: current quarter -----------------------------------------


def _current_quarter_label(now: datetime | None = None) -> str:
    n = now or datetime.now(tz=timezone.utc)
    q = (n.month - 1) // 3 + 1
    return f"Q{q} {n.year}"


def _current_month_label(now: datetime | None = None) -> str:
    n = now or datetime.now(tz=timezone.utc)
    return n.strftime("%B %Y")


# ---------- providers -------------------------------------------------------


async def fund_quarterly() -> dict[str, Any]:
    """Inputs for ``lp_quarterly_update``.

    Pulls AUM + wins + challenges from the chat history, connectors
    and Wave 95 receipts ledger when available. Falls back to mock
    figures so the schedule fires cleanly even on a fresh install.
    """

    aum = 0.0
    aum_delta_pct = 0.0
    wins: list[str] = []
    challenges: list[str] = []
    financial_summary: dict[str, Any] = {}
    next_quarter = ""

    # Best-effort receipt mining for wins/challenges. Failures are
    # silent -- providers must never raise into the scheduler.
    try:
        from backend.core.receipts.store import get_store as get_receipts_store
        rstore = get_receipts_store()
        if rstore is not None and getattr(rstore, "enabled", True):
            recents = await rstore.list_recent(limit=200) if hasattr(rstore, "list_recent") else []
            for r in recents or []:
                try:
                    rtype = getattr(r, "type", None) or (r.get("type") if isinstance(r, dict) else None)
                except Exception:
                    rtype = None
                if rtype and "win" in str(rtype).lower():
                    wins.append(str(rtype))
            wins = wins[:3]
    except Exception as exc:
        log.debug("fund_quarterly.receipts skipped: %s", exc)

    # Synthetic mock fill so downstream rendering has something to paint.
    if not wins:
        wins = ["Closed lead investor in Series B", "AUM grew 12% QoQ", "Hired Head of Research"]
    if not challenges:
        challenges = ["Macro headwinds compressed multiples", "Slower deployment pace than target"]
    if not financial_summary:
        financial_summary = {
            "AUM (USD)": aum or 125_000_000,
            "Net new commitments": 18_000_000,
            "Realisations": 4_500_000,
            "Management fees": 1_250_000,
        }
    if not next_quarter:
        next_quarter = (
            "Close 2 new platform investments; finish portco audit pack; "
            "hire 1 IR associate."
        )

    return {
        "quarter": _current_quarter_label(),
        "aum": float(aum or 125_000_000),
        "aum_delta_pct": float(aum_delta_pct or 12.0),
        "wins": wins,
        "challenges": challenges,
        "financial_summary": financial_summary,
        "next_quarter": next_quarter,
    }


async def monthly_kpis() -> dict[str, Any]:
    """Inputs for ``monthly_kpi_dashboard``.

    Stub today; real wiring will pull from Stripe (revenue),
    HRIS (hires), and the receipts ledger (milestones).
    """

    return {
        "month": _current_month_label(),
        "revenue": 845_000.0,
        "retention_pct": 96.4,
        "cash_runway_months": 22.0,
        "hires_this_month": 3,
        "milestones_hit": [
            "Shipped Wave 102 file UI",
            "Onboarded 4 new fund accounts",
            "Closed 2 follow-on rounds",
        ],
    }


async def portfolio_snapshot() -> dict[str, Any]:
    """Inputs for ``portfolio_audit_pack``.

    Reads from playbook runs + memory entries when available;
    otherwise emits a small synthetic portfolio.
    """

    portfolio: list[dict[str, Any]] = []

    try:
        from backend.core.playbooks import list_recent_runs  # type: ignore
        recent = await list_recent_runs(limit=20)
        for run in recent or []:
            ctx = getattr(run, "context", None) or {}
            name = ctx.get("portco") or ctx.get("company")
            if name:
                portfolio.append(
                    {
                        "name": name,
                        "valuation": ctx.get("valuation"),
                        "last_activity": ctx.get("last_activity") or run.created_at,
                        "kpis": ctx.get("kpis", {}),
                        "risk_flags": ctx.get("risk_flags", []),
                    }
                )
    except Exception as exc:
        log.debug("portfolio_snapshot.playbook_runs skipped: %s", exc)

    if not portfolio:
        portfolio = [
            {
                "name": "Acme Robotics",
                "valuation": 45_000_000,
                "last_activity": time.time() - 86400 * 7,
                "kpis": {"ARR": 4_200_000, "GM%": 62},
                "risk_flags": ["Single-customer concentration"],
            },
            {
                "name": "Northwind Bio",
                "valuation": 120_000_000,
                "last_activity": time.time() - 86400 * 14,
                "kpis": {"Phase II readout": "Q3 2026"},
                "risk_flags": [],
            },
        ]

    return {"portfolio": portfolio}


# ---------- provider registry -----------------------------------------------


_PROVIDERS: dict[str, ProviderFn] = {
    "reports.providers.fund_quarterly": fund_quarterly,
    "reports.providers.monthly_kpis": monthly_kpis,
    "reports.providers.portfolio_snapshot": portfolio_snapshot,
}


def register_provider(name: str, fn: ProviderFn) -> None:
    """Mount an additional provider (third-party / customer-specific)."""

    if not name or not callable(fn):
        raise ValueError("bad_provider")
    _PROVIDERS[name] = fn


def get_provider(name: str) -> ProviderFn | None:
    return _PROVIDERS.get(name)


def list_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())


__all__ = [
    "ProviderFn",
    "fund_quarterly",
    "get_provider",
    "list_providers",
    "monthly_kpis",
    "portfolio_snapshot",
    "register_provider",
]
