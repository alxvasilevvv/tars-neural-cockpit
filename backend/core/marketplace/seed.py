"""Bundled seed listings for the marketplace (Wave 106).

12 starter entries across the canonical B2B verticals + a handful
of community-tagged ones. Used as a fallback when the public
GitHub registry URL is unreachable (offline dev / first run / CI),
and as the canonical seed shipped with the install zip.

Listings are JSON-serialisable dicts that match
``Listing.from_dict``. Stable IDs (``mlst_seed_*``) keep the
fixtures referentially stable across calls so the FE can pin
favourites by ID without worrying about reseeding shuffling them.

Rebadged content sources (kept honest -- the README in each
``playbooks/_workshop/<vertical>/`` folder lists the original
recipe set):

- ``fund``         -> Fund Operator Pack
- ``saas``         -> SaaS Founder Pack
- ``dao``          -> DAO Operator Pack
- ``family-office``-> Family Office Pack
- ``algotrade``    -> Algotrade Pack (Cursor's recipes)
- ``quant``        -> Quant Research Pack

Plus three report templates and one community-contributed example
to demonstrate the surface beyond first-party packs.
"""

from __future__ import annotations

from typing import Any


# Frozen seed timestamp -- 2026-05-10 00:00 UTC. Stable across
# reseeds so the FE caching key based on (id, updated_at) is
# deterministic in CI.
_T0 = 1746835200.0


SEED_LISTINGS: list[dict[str, Any]] = [
    {
        "id": "mlst_seed_fund_pack",
        "kind": "playbook",
        "name": "Fund Operator Pack",
        "slug": "fund-operator-pack",
        "description": (
            "5 recipes for venture / PE fund managers: weekly LP "
            "report, deal screening triage, founder DD checklist, "
            "portfolio monitoring + tax memo drafting."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "1.0.0",
        "tags": ["fund", "lp", "deal", "due-diligence", "portfolio"],
        "category": "fund",
        "install_payload": {
            "format": "playbook_bundle",
            "source_dir": "playbooks/_workshop/fund",
        },
        "preview_url": "/workshop/materials#fund",
        "ratings": {"count": 47, "avg": 4.7},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_algotrade_pack",
        "kind": "playbook",
        "name": "Algotrade Pack",
        "slug": "algotrade-pack",
        "description": (
            "Cursor-authored recipes for systematic traders: mean-"
            "reversion + momentum-breakout strategy templates, "
            "backtest -> paper -> live promotion pipeline, weekly "
            "risk audit and a live paper-trading session runner."
        ),
        "author": {"handle": "cursor-algotrade", "url": "https://github.com"},
        "version": "1.1.0",
        "tags": ["algotrade", "backtest", "risk", "live-trading"],
        "category": "algotrade",
        "install_payload": {
            "format": "playbook_bundle",
            "source_dir": "playbooks/_workshop/algotrade",
        },
        "preview_url": "/workshop/materials#algotrade",
        "ratings": {"count": 38, "avg": 4.8},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_dao_pack",
        "kind": "playbook",
        "name": "DAO Operator Pack",
        "slug": "dao-operator-pack",
        "description": (
            "3 recipes for DAO operators: proposal summarisation, "
            "treasury delta diff and contributor recognition (with "
            "a leaderboard receipt that anchors weekly)."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "1.0.0",
        "tags": ["dao", "treasury", "governance", "contributors"],
        "category": "dao",
        "install_payload": {
            "format": "playbook_bundle",
            "source_dir": "playbooks/_workshop/dao",
        },
        "preview_url": "/workshop/materials#dao",
        "ratings": {"count": 19, "avg": 4.4},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_saas_pack",
        "kind": "playbook",
        "name": "SaaS Founder Pack",
        "slug": "saas-founder-pack",
        "description": (
            "Recipes for SaaS founders: weekly KPI snapshot, "
            "churn-risk triage, customer-call summary -> CRM and "
            "Slack-to-Linear ticket drafting."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "1.0.0",
        "tags": ["saas", "kpi", "crm", "churn", "founder"],
        "category": "saas",
        "install_payload": {
            "format": "playbook_bundle",
            "source_dir": "playbooks/_workshop/saas",
        },
        "preview_url": "/workshop/materials#saas",
        "ratings": {"count": 28, "avg": 4.5},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_family_office_pack",
        "kind": "playbook",
        "name": "Family Office Pack",
        "slug": "family-office-pack",
        "description": (
            "Single-family-office recipes: monthly NAV report, "
            "private-investment cap-call drafting and tax-loss "
            "harvest scanner."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "0.9.0",
        "tags": ["family-office", "nav", "tax", "private-investments"],
        "category": "family-office",
        "install_payload": {
            "format": "playbook_bundle",
            "source_dir": "playbooks/_workshop/family-office",
        },
        "preview_url": "/workshop/materials#family-office",
        "ratings": {"count": 12, "avg": 4.6},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_quant_pack",
        "kind": "playbook",
        "name": "Quant Research Pack",
        "slug": "quant-research-pack",
        "description": (
            "Quant-research recipes: factor exploration scaffolds, "
            "rolling-window backtester template and a regime-"
            "detection notebook."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "0.8.0",
        "tags": ["quant", "research", "factor", "regime"],
        "category": "quant",
        "install_payload": {
            "format": "playbook_bundle",
            "source_dir": "playbooks/_workshop/quant",
        },
        "preview_url": "/workshop/materials#quant",
        "ratings": {"count": 9, "avg": 4.3},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    # ---------- report templates -------------------------------------------
    {
        "id": "mlst_seed_lp_quarterly_pptx",
        "kind": "report_template",
        "name": "LP Quarterly PPTX",
        "slug": "lp-quarterly-pptx",
        "description": (
            "12-slide LP quarterly update template with NAV, top "
            "5 deals, marks summary and a forward calendar. Plays "
            "with the Reports module (Wave 103)."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "1.0.0",
        "tags": ["report", "lp", "pptx", "fund"],
        "category": "fund",
        "install_payload": {
            "format": "report_template",
            "kind": "pptx",
            "slug": "lp-quarterly",
        },
        "preview_url": "/reports?tab=templates",
        "ratings": {"count": 22, "avg": 4.6},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_board_pack_pdf",
        "kind": "report_template",
        "name": "Board Pack PDF",
        "slug": "board-pack-pdf",
        "description": (
            "End-to-end board pack PDF: KPI dashboard, financial "
            "summary, P&L delta, OKR tracker and a forward asks "
            "page. Generates from structured inputs."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "1.0.0",
        "tags": ["report", "board", "pdf", "saas"],
        "category": "saas",
        "install_payload": {
            "format": "report_template",
            "kind": "pdf",
            "slug": "board-pack",
        },
        "preview_url": "/reports?tab=templates",
        "ratings": {"count": 17, "avg": 4.7},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_kpi_dashboard_xlsx",
        "kind": "report_template",
        "name": "KPI Dashboard XLSX",
        "slug": "kpi-dashboard-xlsx",
        "description": (
            "Monthly KPI dashboard for SaaS / fund operators: "
            "ARR, MRR, churn, gross margin, runway, NPS. Editable "
            "downstream in Excel / Numbers / Sheets."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "1.0.0",
        "tags": ["report", "kpi", "xlsx", "saas", "fund"],
        "category": "saas",
        "install_payload": {
            "format": "report_template",
            "kind": "xlsx",
            "slug": "kpi-dashboard",
        },
        "preview_url": "/reports?tab=templates",
        "ratings": {"count": 14, "avg": 4.5},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    # ---------- standalone skills ------------------------------------------
    {
        "id": "mlst_seed_skill_pdf_redact",
        "kind": "skill",
        "name": "PDF Redactor",
        "slug": "pdf-redactor",
        "description": (
            "Standalone skill: takes a PDF + a redaction policy "
            "(emails, SSNs, custom regex) and returns a redacted "
            "copy with an audit log of redactions applied."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "0.7.0",
        "tags": ["skill", "pdf", "redact", "compliance"],
        "category": "compliance",
        "install_payload": {
            "format": "skill_module",
            "module": "pdf_redactor",
        },
        "preview_url": "/files",
        "ratings": {"count": 31, "avg": 4.8},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    {
        "id": "mlst_seed_skill_calendar_brief",
        "kind": "skill",
        "name": "Calendar Brief",
        "slug": "calendar-brief",
        "description": (
            "Standalone skill: pulls today's calendar via the "
            "real .ics reader (Iter A) and drafts a 1-paragraph "
            "brief per meeting + a one-line agenda for the day."
        ),
        "author": {"handle": "tars-core", "url": "https://tars.meeet.world"},
        "version": "0.9.0",
        "tags": ["skill", "calendar", "briefing"],
        "category": "general",
        "install_payload": {
            "format": "skill_module",
            "module": "calendar_brief",
        },
        "preview_url": "/dashboard",
        "ratings": {"count": 25, "avg": 4.4},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
    # ---------- one community-contributed listing --------------------------
    {
        "id": "mlst_seed_community_ma_regime",
        "kind": "playbook",
        "name": "MA Crossover with Regime Filter",
        "slug": "ma-crossover-regime-filter",
        "description": (
            "Community-contributed: classic moving-average "
            "crossover signal with a Hidden-Markov regime filter "
            "to suppress whipsaw in choppy markets. Includes a "
            "backtest harness + paper-trading wrapper."
        ),
        "author": {"handle": "@quantgrim", "url": "https://github.com/quantgrim"},
        "version": "0.4.2",
        "tags": ["algotrade", "moving-average", "regime", "community"],
        "category": "algotrade",
        "install_payload": {
            "format": "playbook_inline",
            "recipe": {
                "name": "MA Crossover with Regime Filter",
                "steps": [
                    "fetch_ohlcv",
                    "compute_ma(fast=20, slow=50)",
                    "fit_regime_hmm(states=2)",
                    "generate_signal_when_regime_in([0])",
                    "backtest(slippage_bps=2)",
                ],
            },
        },
        "preview_url": "",
        "ratings": {"count": 8, "avg": 4.1},
        "price": "free",
        "license": "MIT",
        "created_at": _T0,
        "updated_at": _T0,
    },
]


def seed_listings() -> list[dict[str, Any]]:
    """Return the bundled seed list (a deep-ish copy on each call).

    The registry merges the seed in when the upstream URL is
    unreachable; tests use this to assert the fallback path.
    """

    return [dict(item) for item in SEED_LISTINGS]


def seed_count() -> int:
    """Number of bundled seed listings (used by /api/marketplace/registry/refresh)."""

    return len(SEED_LISTINGS)
