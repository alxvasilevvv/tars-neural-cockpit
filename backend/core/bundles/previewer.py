"""Dry-run previewer for bundle installs (Wave 107).

Produces the same shape as a real install but does NOT touch the
scheduler / outreach store / install DB / receipts. Used by the
``POST /api/bundles/{id}/preview`` endpoint so the FE can render
a confirm dialog with exactly what's about to happen.
"""

from __future__ import annotations

import time
from typing import Any

from .definitions import bundle_by_id
from .installer import _try_get_playbook
from .models import (
    Bundle,
    InstallReport,
    new_install_id,
)


def _walk_dry(bundle: Bundle, org_id: str) -> InstallReport:
    report = InstallReport(
        install_id=new_install_id(),
        bundle_id=bundle.id,
        org_id=org_id,
        dry_run=True,
        welcome_content=bundle.welcome_content(),
    )

    for pb_id in bundle.playbooks():
        pb = _try_get_playbook(pb_id)
        entry = {"id": pb_id, "available": pb is not None}
        if pb is None:
            report.warn(f"playbook_missing:{pb_id}")
        report.add("playbooks", entry)

    for sched in bundle.scheduled():
        report.add(
            "scheduled",
            {
                "playbook_id": sched["playbook_id"],
                "cron": sched["cron"],
                "would_create": True,
            },
        )

    for w in bundle.dashboard_widgets():
        report.add("dashboard_widgets", {"id": w})

    for slug in bundle.report_templates():
        report.add("report_templates", {"slug": slug})

    for slug in bundle.outreach_templates():
        report.add(
            "outreach_templates",
            {"slug": slug, "would_seed": True},
        )

    for hint in bundle.connectors_hints():
        report.add("connectors_hints", hint)

    report.first_run_id = bundle.first_run_playbook()
    report.finished_at = time.time()
    return report


def preview_bundle(
    bundle_id: str, org_id: str | None = None
) -> dict[str, Any]:
    """Return a dry-run report for the bundle.

    Includes a ``bundle`` payload alongside the report so the FE
    has everything to render in one round-trip.
    """

    bundle = bundle_by_id(bundle_id)
    if bundle is None:
        return {
            "ok": False,
            "error": "bundle_not_found",
            "bundle_id": bundle_id,
        }
    org = (org_id or "").strip() or "default"
    report = _walk_dry(bundle, org)
    return {
        "ok": True,
        "bundle": bundle.to_dict(),
        "preview": report.to_dict(),
        "summary": {
            "counts": report.counts(),
            "warnings": list(report.warnings),
            "first_run_playbook": report.first_run_id,
        },
    }


__all__ = ["preview_bundle"]
