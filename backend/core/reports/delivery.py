"""Auto-send pipeline for rendered reports (Wave 103).

Three delivery channels:

1. ``send_via_outreach`` -- attaches the rendered file to a fresh
   :mod:`backend.core.outreach` draft and routes it through the
   normal HIL gate. Most LP-update use cases hit this path.
2. ``send_via_webhook`` -- POSTs ``{run_id, template_slug, output_url,
   recipient_emails}`` to a Wave 90 outgoing-webhook endpoint. Useful
   when a downstream system (Notion / DocSend / Slack) ingests the
   PDF.
3. ``download_url`` -- builds the local download URL the FE renders
   in the runs table.

Every helper is best-effort: on missing dependencies or disabled
modules we surface a clear error string instead of raising. The
router decides whether to bubble up or swallow.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from .store import ReportStore, get_store


log = logging.getLogger("tars.reports.delivery")


def download_url(run_id: str) -> str:
    """Stable local download URL for a rendered run."""

    return f"/api/reports/runs/{run_id}/download"


# ---------- outreach send --------------------------------------------------


async def send_via_outreach(
    run_id: str,
    recipient_emails: list[str],
    *,
    subject_template: str = "{template_name}",
    body_template: str = (
        "Hi,\n\nPlease find the attached {template_name} ({kind}).\n\n"
        "Best,\nTARS"
    ),
    store: ReportStore | None = None,
) -> dict[str, Any]:
    """Attach the rendered report to a fresh outreach draft per recipient.

    Returns a small ``{ok, drafts_created, error?}`` summary. Routes
    through the standard outreach drafter so the HIL gate +
    deliverability checks all kick in.
    """

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "error": "reports_store_disabled"}
    run = await s.get_run(run_id)
    if run is None:
        return {"ok": False, "error": "run_not_found"}
    if run.status != "done":
        return {"ok": False, "error": f"run_not_done:{run.status}"}
    template = await s.get_template(run.template_id)
    template_name = template.name if template else run.template_id

    try:
        from backend.core.outreach import (  # local import: optional dep
            OutreachDraft,
            get_store as get_outreach_store,
            new_draft_id,
        )
    except Exception as exc:
        return {"ok": False, "error": f"outreach_unavailable:{exc}"}

    o_store = get_outreach_store()
    if not o_store.enabled:
        return {"ok": False, "error": "outreach_store_disabled"}

    subject = subject_template.format(
        template_name=template_name,
        kind=run.output_kind,
        run_id=run_id,
    )
    body = body_template.format(
        template_name=template_name,
        kind=run.output_kind,
        run_id=run_id,
    )

    drafts_created = 0
    for email in recipient_emails:
        if not email or "@" not in email:
            continue
        draft = OutreachDraft(
            id=new_draft_id(),
            template_id=f"report:{run.template_id}",
            recipient={"email": email},
            context={
                "report_run_id": run_id,
                "report_output_path": run.output_path,
                "report_kind": run.output_kind,
            },
            subject=subject,
            body=body,
            status="draft",
        )
        try:
            await o_store.insert_draft(draft)
            drafts_created += 1
        except Exception as exc:
            log.warning("reports.delivery.outreach_insert_failed email=%s err=%s", email, exc)

    if drafts_created:
        await s.update_run(run_id, recipient_emails=list(recipient_emails))
    return {"ok": drafts_created > 0, "drafts_created": drafts_created}


# ---------- webhook send ----------------------------------------------------


async def send_via_webhook(
    run_id: str,
    *,
    store: ReportStore | None = None,
) -> dict[str, Any]:
    """POST the run metadata to every outgoing Wave 90 webhook.

    The payload includes the local ``download_url`` -- consumers that
    need the bytes follow up with a GET. We intentionally don't ship
    the bytes inline (could be 50MB+).
    """

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "error": "reports_store_disabled"}
    run = await s.get_run(run_id)
    if run is None:
        return {"ok": False, "error": "run_not_found"}

    payload = {
        "type": "report.generated",
        "run_id": run.id,
        "template_id": run.template_id,
        "kind": run.output_kind,
        "status": run.status,
        "download_url": download_url(run.id),
        "recipient_emails": list(run.recipient_emails),
        "ts": time.time(),
    }

    try:
        from backend.core.webhooks import dispatch_outgoing  # local import: optional dep
    except Exception:
        try:
            from backend.core.webhooks.outgoing import dispatch as dispatch_outgoing  # type: ignore
        except Exception as exc:
            return {"ok": False, "error": f"webhooks_unavailable:{exc}"}

    try:
        result = await dispatch_outgoing("report.generated", payload)
        return {"ok": True, "delivered": result}
    except Exception as exc:
        log.warning("reports.delivery.webhook_failed run=%s err=%s", run_id, exc)
        return {"ok": False, "error": f"webhook_dispatch_failed:{exc}"}


# ---------- file probing ----------------------------------------------------


def file_exists(run_path: str) -> bool:
    return bool(run_path) and os.path.isfile(run_path)


__all__ = [
    "download_url",
    "file_exists",
    "send_via_outreach",
    "send_via_webhook",
]
