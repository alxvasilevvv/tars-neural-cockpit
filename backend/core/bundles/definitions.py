"""Built-in bundle definitions (Wave 107).

Seven verticals, each a one-click ready-to-demo pack:

1. ``vc_fund_bundle``       -- VC fund partner cockpit
2. ``hedge_fund_bundle``    -- quant cockpit (algotrade pack)
3. ``family_office_bundle`` -- family office statements + KYC
4. ``saas_bundle``          -- SaaS founder ops + churn + PRs
5. ``dao_bundle``           -- DAO treasury + proposals
6. ``research_lab_bundle``  -- small mixed pack for labs
7. ``other_bundle``         -- generic top-6 fallback

Definitions are pure data; installer/previewer consume them. To
add an eighth vertical: write the dict, append to
``BUILTIN_BUNDLES``, drop a card on the FE.
"""

from __future__ import annotations

from .models import Bundle


# ---------- VC fund --------------------------------------------------------


vc_fund_bundle = Bundle(
    id="vc_fund_bundle",
    slug="vc-fund",
    name="VC Fund template",
    description=(
        "Ready-to-demo cockpit for a VC partner. Wires the weekly LP "
        "report, deal screening, founder DD, portfolio monitoring and "
        "tax memo playbooks; schedules the LP report for Monday "
        "mornings; opens with the partner-friendly dashboard."
    ),
    org_type="vc_fund",
    components={
        "playbooks": [
            "fund/weekly_lp_report",
            "fund/deal_screening",
            "fund/founder_dd",
            "fund/portfolio_monitoring",
            "fund/tax_memo",
        ],
        "scheduled": [
            {
                "playbook_id": "fund/weekly_lp_report",
                "cron": "0 9 * * MON",
            },
            {
                "playbook_id": "fund/portfolio_monitoring",
                "cron": "0 7 * * *",
            },
        ],
        "dashboard_widgets": [
            "calendar-today",
            "gmail-unread",
            "recent-receipts",
            "active-cohorts",
            "hil-inbox",
        ],
        "report_templates": [
            "lp_quarterly_update",
            "portfolio_audit_pack",
            "deal_screening_memo",
        ],
        "outreach_templates": [
            "lp_update",
            "founder_dd",
            "intro",
            "follow_up",
            "welcome_lp",
        ],
        "connectors_hints": [
            {"id": "gmail", "priority": True},
            "calendar",
            "slack",
        ],
        "welcome_content": (
            "# Welcome, partner.\n\n"
            "Your VC fund cockpit is ready. We just installed:\n\n"
            "- 5 playbooks (LP report, deal screening, founder DD, "
            "portfolio monitoring, tax memo)\n"
            "- a Monday 09:00 LP-report schedule\n"
            "- a daily 07:00 portfolio-monitoring sweep\n"
            "- LP / founder / intro / follow-up / welcome outreach "
            "templates\n\n"
            "Connect Gmail first -- that's where every other playbook "
            "starts. Then run **Portfolio monitoring** (queued for you) "
            "and watch the receipts roll in."
        ),
        "first_run_playbook": "fund/portfolio_monitoring",
    },
)


# ---------- Hedge fund / quant ---------------------------------------------


hedge_fund_bundle = Bundle(
    id="hedge_fund_bundle",
    slug="hedge-fund",
    name="Hedge Fund / Quant template",
    description=(
        "Quant cockpit wired around the algotrade pack -- strategy IR, "
        "backtests, paper exec session, risk audit. Mean-reversion and "
        "momentum-breakout strategies installed; weekly risk audit "
        "scheduled for Monday mornings."
    ),
    org_type="hedge_fund",
    components={
        "playbooks": [
            "algotrade/mean_reversion_strategy",
            "algotrade/momentum_breakout_strategy",
            "algotrade/live_paper_session",
            "algotrade/backtest_to_live_pipeline",
            "algotrade/risk_audit_weekly",
        ],
        "scheduled": [
            {
                "playbook_id": "algotrade/risk_audit_weekly",
                "cron": "0 8 * * MON",
            },
        ],
        "dashboard_widgets": [
            "backtest-summary",
            "recent-receipts",
            "hil-inbox",
            "calendar-today",
        ],
        "report_templates": [
            "monthly_kpi_dashboard",
        ],
        "outreach_templates": [
            "lp_update",
        ],
        "connectors_hints": [
            "gmail",
            "slack",
        ],
        "welcome_content": (
            "# Quant cockpit ready.\n\n"
            "Strategy IR + backtest + paper exec wired. Mean-reversion "
            "and momentum-breakout strategies are pre-loaded -- kick off "
            "a small backtest first to see the receipt pipeline.\n\n"
            "Weekly risk audit runs Monday 08:00. Live paper session is "
            "manual-start (no cron) so you control when capital moves."
        ),
        "first_run_playbook": "algotrade/mean_reversion_strategy",
    },
)


# ---------- Family office --------------------------------------------------


family_office_bundle = Bundle(
    id="family_office_bundle",
    slug="family-office",
    name="Family Office template",
    description=(
        "Monthly statements + KYC refresh + compliance pack for "
        "multi-asset family offices. Statement runs the 1st of every "
        "month; KYC sweep every quarter."
    ),
    org_type="family_office",
    components={
        "playbooks": [
            "family-office/monthly_statement",
            "family-office/kyc_refresh",
            "family-office/compliance_pack",
        ],
        "scheduled": [
            {
                "playbook_id": "family-office/monthly_statement",
                "cron": "0 9 1 * *",
            },
            {
                "playbook_id": "family-office/kyc_refresh",
                "cron": "0 8 1 */3 *",
            },
        ],
        "dashboard_widgets": [
            "wallet-balance",
            "recent-receipts",
            "calendar-today",
        ],
        "report_templates": [
            "portfolio_audit_pack",
        ],
        "outreach_templates": [
            "welcome_lp",
        ],
        "connectors_hints": [
            "gmail",
            "calendar",
        ],
        "welcome_content": (
            "# Family office cockpit ready.\n\n"
            "Statements fire the 1st of every month at 09:00; KYC "
            "refresh sweeps run every three months. The compliance "
            "pack is on-demand -- run it before any audit window."
        ),
        "first_run_playbook": "family-office/monthly_statement",
    },
)


# ---------- SaaS founder ---------------------------------------------------


saas_bundle = Bundle(
    id="saas_bundle",
    slug="saas",
    name="SaaS Founder template",
    description=(
        "Morning ops brief, churn alert, outreach loop and PR review "
        "wired for an early-stage SaaS team. PR review polls every 15 "
        "minutes during the working week."
    ),
    org_type="saas",
    components={
        "playbooks": [
            "saas/morning_ops",
            "saas/churn_alert",
            "saas/outreach_loop",
            "saas/pr_review",
        ],
        "scheduled": [
            {
                "playbook_id": "saas/morning_ops",
                "cron": "30 8 * * 1-5",
            },
            {
                "playbook_id": "saas/churn_alert",
                "cron": "0 9 * * *",
            },
            {
                "playbook_id": "saas/pr_review",
                "cron": "*/15 * * * 1-5",
            },
        ],
        "dashboard_widgets": [
            "github-prs",
            "slack-mentions",
            "gmail-unread",
            "playbook-runs",
            "recent-receipts",
        ],
        "report_templates": [
            "monthly_kpi_dashboard",
            "board_meeting_pack",
        ],
        "outreach_templates": [
            "intro",
            "follow_up",
        ],
        "connectors_hints": [
            {"id": "github", "priority": True},
            "slack",
            "gmail",
        ],
        "welcome_content": (
            "# SaaS founder cockpit ready.\n\n"
            "Morning brief at 08:30 weekdays, churn alert daily 09:00, "
            "PR review every 15 minutes during work hours. Connect "
            "GitHub first so the PR sweep has something to read."
        ),
        "first_run_playbook": "saas/morning_ops",
    },
)


# ---------- DAO ------------------------------------------------------------


dao_bundle = Bundle(
    id="dao_bundle",
    slug="dao",
    name="DAO Ops template",
    description=(
        "Treasury diff (daily), proposal summarisation and contributor "
        "recognition for a DAO. Discord support is on the roadmap; "
        "Slack works today."
    ),
    org_type="dao",
    components={
        "playbooks": [
            "dao/treasury_diff",
            "dao/proposal_summarize",
            "dao/contributor_recognition",
        ],
        "scheduled": [
            {
                "playbook_id": "dao/treasury_diff",
                "cron": "0 8 * * *",
            },
        ],
        "dashboard_widgets": [
            "wallet-balance",
            "recent-receipts",
            "active-cohorts",
        ],
        "report_templates": [
            "monthly_kpi_dashboard",
        ],
        "outreach_templates": [
            "intro",
        ],
        "connectors_hints": [
            "slack",
        ],
        "welcome_content": (
            "# DAO ops cockpit ready.\n\n"
            "Daily treasury diff at 08:00. Proposal summary and "
            "contributor recognition are on-demand. Discord support "
            "ships in a follow-up wave -- Slack handles announcements "
            "today."
        ),
        "first_run_playbook": "dao/treasury_diff",
    },
)


# ---------- Research lab ---------------------------------------------------


research_lab_bundle = Bundle(
    id="research_lab_bundle",
    slug="research-lab",
    name="Research Lab template",
    description=(
        "Smaller mixed pack for academic / industrial labs -- ops brief "
        "from the SaaS pack plus founder DD from the fund pack."
    ),
    org_type="research_lab",
    components={
        "playbooks": [
            "saas/morning_ops",
            "fund/founder_dd",
        ],
        "scheduled": [
            {
                "playbook_id": "saas/morning_ops",
                "cron": "0 9 * * 1-5",
            },
        ],
        "dashboard_widgets": [
            "github-prs",
            "calendar-today",
            "recent-receipts",
        ],
        "report_templates": [
            "monthly_kpi_dashboard",
        ],
        "outreach_templates": [
            "intro",
            "follow_up",
        ],
        "connectors_hints": [
            {"id": "github", "priority": True},
            "calendar",
        ],
        "welcome_content": (
            "# Research lab cockpit ready.\n\n"
            "Lightweight pack: morning brief at 09:00 weekdays plus "
            "founder DD on demand for collaborator screening."
        ),
        "first_run_playbook": "saas/morning_ops",
    },
)


# ---------- Other / fallback -----------------------------------------------


other_bundle = Bundle(
    id="other_bundle",
    slug="other",
    name="General template",
    description=(
        "Generic top-6 pack for orgs that don't match a specific "
        "vertical. Picks one playbook from each major workshop pack so "
        "you can explore before committing."
    ),
    org_type="other",
    components={
        "playbooks": [
            "saas/morning_ops",
            "fund/founder_dd",
            "dao/treasury_diff",
            "family-office/monthly_statement",
            "fund/deal_screening",
            "fund/weekly_lp_report",
        ],
        "scheduled": [],
        "dashboard_widgets": [
            "calendar-today",
            "gmail-unread",
            "recent-receipts",
            "playbook-runs",
        ],
        "report_templates": [
            "monthly_kpi_dashboard",
        ],
        "outreach_templates": [
            "intro",
            "follow_up",
        ],
        "connectors_hints": [
            "gmail",
            "calendar",
        ],
        "welcome_content": (
            "# Generic cockpit ready.\n\n"
            "We installed one playbook from each major vertical so you "
            "can explore. Once you've picked a direction, install the "
            "matching specialised bundle from /bundles."
        ),
        "first_run_playbook": "saas/morning_ops",
    },
)


# ---------- Registry -------------------------------------------------------


BUILTIN_BUNDLES: tuple[Bundle, ...] = (
    vc_fund_bundle,
    hedge_fund_bundle,
    family_office_bundle,
    saas_bundle,
    dao_bundle,
    research_lab_bundle,
    other_bundle,
)


def list_bundles() -> list[Bundle]:
    """Return the built-in bundles as a fresh list."""

    return list(BUILTIN_BUNDLES)


def bundle_by_id(bundle_id: str) -> Bundle | None:
    """Look up a bundle by its ``id`` (e.g. ``vc_fund_bundle``)."""

    norm = (bundle_id or "").strip().lower()
    for b in BUILTIN_BUNDLES:
        if b.id == norm or b.slug == norm:
            return b
    return None


def bundle_for_org_type(org_type: str | None) -> Bundle:
    """Return the recommended bundle for an org type.

    Falls back to ``other_bundle`` for unknown / empty inputs.
    """

    norm = (org_type or "").strip().lower()
    for b in BUILTIN_BUNDLES:
        if b.org_type == norm:
            return b
    return other_bundle


__all__ = [
    "BUILTIN_BUNDLES",
    "bundle_by_id",
    "bundle_for_org_type",
    "dao_bundle",
    "family_office_bundle",
    "hedge_fund_bundle",
    "list_bundles",
    "other_bundle",
    "research_lab_bundle",
    "saas_bundle",
    "vc_fund_bundle",
]
