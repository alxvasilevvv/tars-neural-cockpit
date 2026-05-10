"""Built-in starter report templates (Wave 103).

Six templates ship with TARS out of the box. Each describes the
``kind`` (which skill renders it), an input schema (used by the FE
to auto-generate the form + by the renderer to validate inputs), and
a short description. Built-ins are seeded into the store on first
router hit; their ``slug`` is the stable handle (custom templates can
NOT shadow a builtin slug).

The schema dialect is intentionally small (no JSON-Schema dep): a
dict of ``field_name -> {type, label, required?, description?,
default?, items?}``. ``type`` is one of ``string``, ``number``,
``int``, ``boolean``, ``array``, ``object``. ``items`` is the inner
type for ``array`` or the nested schema for ``object`` (best-effort
on the FE side -- complex shapes degrade to JSON textarea).
"""

from __future__ import annotations

from typing import Any

from .models import KIND_DOCX, KIND_PDF, KIND_PPTX, KIND_XLSX
from .store import ReportStore, get_store


# ---------- the six built-in starter templates -----------------------------


BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    # 1. LP quarterly update -- 8-slide deck for fund LPs.
    {
        "name": "LP quarterly update",
        "slug": "lp_quarterly_update",
        "kind": KIND_PPTX,
        "description": (
            "8-slide deck: cover, executive summary, AUM update, top 3 wins "
            "(with portfolio-company logos), challenges, financial summary "
            "table, next-quarter focus, Q&A. Designed for quarterly LP "
            "communications from the GP."
        ),
        "template_path": "templates/reports/lp_quarterly_update.pptx",
        "schema": {
            "quarter": {
                "type": "string",
                "label": "Quarter",
                "required": True,
                "description": "e.g. Q1 2026",
            },
            "aum": {
                "type": "number",
                "label": "AUM (USD)",
                "required": True,
            },
            "aum_delta_pct": {
                "type": "number",
                "label": "AUM change (%)",
                "default": 0.0,
            },
            "wins": {
                "type": "array",
                "label": "Top 3 wins",
                "items": "string",
            },
            "challenges": {
                "type": "array",
                "label": "Challenges",
                "items": "string",
            },
            "financial_summary": {
                "type": "object",
                "label": "Financial summary",
                "description": "Free-form table data (rows/cols).",
            },
            "next_quarter": {
                "type": "string",
                "label": "Next-quarter focus",
            },
        },
    },
    # 2. Board meeting pack -- 10-page pdf bundle.
    {
        "name": "Board meeting pack",
        "slug": "board_meeting_pack",
        "kind": KIND_PDF,
        "description": (
            "10-page PDF: agenda, financial KPIs, OKR progress, hiring "
            "update, risk register. Pre-read pack for quarterly board "
            "meetings."
        ),
        "template_path": "templates/reports/board_meeting_pack.pdf",
        "schema": {
            "quarter": {
                "type": "string",
                "label": "Quarter",
                "required": True,
            },
            "kpis": {
                "type": "object",
                "label": "Financial KPIs",
                "description": "Free-form metric -> value map.",
            },
            "okrs": {
                "type": "array",
                "label": "OKR progress",
                "items": "object",
            },
            "hiring": {
                "type": "object",
                "label": "Hiring update",
            },
            "risks": {
                "type": "array",
                "label": "Risk register",
                "items": "object",
            },
        },
    },
    # 3. Monthly KPI dashboard -- 5-sheet xlsx workbook.
    {
        "name": "Monthly KPI dashboard",
        "slug": "monthly_kpi_dashboard",
        "kind": KIND_XLSX,
        "description": (
            "5-sheet workbook: revenue, retention, cash, hiring, "
            "milestones. Drop-in dashboard for monthly operating "
            "reviews."
        ),
        "template_path": "",
        "schema": {
            "month": {
                "type": "string",
                "label": "Month",
                "required": True,
                "description": "e.g. May 2026",
            },
            "revenue": {
                "type": "number",
                "label": "Revenue (USD)",
                "required": True,
            },
            "retention_pct": {
                "type": "number",
                "label": "Retention (%)",
            },
            "cash_runway_months": {
                "type": "number",
                "label": "Cash runway (months)",
            },
            "hires_this_month": {
                "type": "int",
                "label": "Hires this month",
            },
            "milestones_hit": {
                "type": "array",
                "label": "Milestones hit",
                "items": "string",
            },
        },
    },
    # 4. Portfolio audit pack -- VC fund use case.
    {
        "name": "Portfolio audit pack",
        "slug": "portfolio_audit_pack",
        "kind": KIND_PDF,
        "description": (
            "Fund use case: each portfolio company gets one page (logo, "
            "current valuation, last activity, KPIs, risk flags). One PDF "
            "per audit cycle."
        ),
        "template_path": "",
        "schema": {
            "portfolio": {
                "type": "array",
                "label": "Portfolio companies",
                "items": "object",
                "description": (
                    "Each entry: name, logo_url?, valuation, last_activity, "
                    "kpis{}, risk_flags[]"
                ),
                "required": True,
            },
        },
    },
    # 5. Deal screening memo -- VC founder review document.
    {
        "name": "Deal screening memo",
        "slug": "deal_screening_memo",
        "kind": KIND_DOCX,
        "description": (
            "VC founder review document. Sections: company snapshot, "
            "team, market, traction, recommendation, score breakdown."
        ),
        "template_path": "templates/reports/deal_screening_memo.docx",
        "schema": {
            "company": {
                "type": "string",
                "label": "Company",
                "required": True,
            },
            "team": {
                "type": "object",
                "label": "Team",
            },
            "market": {
                "type": "object",
                "label": "Market",
            },
            "traction": {
                "type": "object",
                "label": "Traction",
            },
            "recommendation": {
                "type": "string",
                "label": "Recommendation",
                "description": "pass / fast-no / dig-deeper / invest",
            },
            "score_breakdown": {
                "type": "object",
                "label": "Score breakdown",
            },
        },
    },
    # 6. Incident postmortem -- tech-org blameless writeup.
    {
        "name": "Incident postmortem",
        "slug": "incident_postmortem",
        "kind": KIND_DOCX,
        "description": (
            "Blameless tech postmortem. Sections: timeline, root cause, "
            "action items. For SEV-1/SEV-2 production incidents."
        ),
        "template_path": "templates/reports/incident_postmortem.docx",
        "schema": {
            "incident_id": {
                "type": "string",
                "label": "Incident ID",
                "required": True,
            },
            "timeline": {
                "type": "array",
                "label": "Timeline",
                "items": "object",
                "description": "Each entry: ts, actor, event",
            },
            "root_cause": {
                "type": "string",
                "label": "Root cause",
            },
            "actions": {
                "type": "array",
                "label": "Action items",
                "items": "object",
                "description": "Each entry: owner, due, description",
            },
        },
    },
]


def list_builtin_slugs() -> list[str]:
    return [t["slug"] for t in BUILTIN_TEMPLATES]


async def seed_builtin_templates(store: ReportStore | None = None) -> int:
    """Idempotently insert / refresh every built-in template.

    Returns the count seeded. Safe to call repeatedly -- the
    underlying ``upsert_template`` is keyed off the slug.
    """

    s = store or get_store()
    if not s.enabled:
        return 0
    count = 0
    for spec in BUILTIN_TEMPLATES:
        await s.upsert_template(
            name=spec["name"],
            slug=spec["slug"],
            kind=spec["kind"],
            schema=spec.get("schema", {}),
            template_path=spec.get("template_path", ""),
            description=spec.get("description", ""),
            is_builtin=True,
        )
        count += 1
    return count


__all__ = [
    "BUILTIN_TEMPLATES",
    "list_builtin_slugs",
    "seed_builtin_templates",
]
