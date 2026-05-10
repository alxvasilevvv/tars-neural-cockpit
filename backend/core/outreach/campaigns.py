"""Bulk-draft + bulk-approve + paced-send orchestration (Wave 98).

Wraps :func:`backend.core.outreach.drafter.generate_draft` and
:func:`backend.core.outreach.sender.send_draft` with:

- :func:`create_campaign(name, template_id, recipients)` -- inserts a
  campaign row, drafts one email per recipient (rate-limited via
  ``asyncio.sleep`` between calls so we don't hammer the LLM).
- :func:`approve_all_in_campaign(campaign_id, except_ids?)` -- flips
  every ``draft`` row in the campaign to ``approved`` (skipping any
  ID in ``except_ids``).
- :func:`send_campaign(campaign_id)` -- iterates approved drafts and
  fires them one-by-one with a 5 s delay between sends. Updates
  campaign counters as it goes.

These functions are best-effort: a single draft / send failure
flips just that draft to ``failed`` and the loop continues. The
return value carries the per-draft outcomes so the FE can render
partial success.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Iterable

from .drafter import generate_draft
from .models import OutreachCampaign, new_campaign_id
from .sender import send_draft
from .store import OutreachStore, get_store


log = logging.getLogger("tars.outreach.campaigns")


def _draft_interval_s() -> float:
    raw = (os.getenv("TARS_OUTREACH_DRAFT_INTERVAL_S") or "0.4").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.4


def _send_interval_s() -> float:
    """Inter-send delay -- guards against Gmail per-user rate limits.

    Gmail allows ~250 quota units / sec; a Send is 100 units. 5 s is
    generous for the desktop single-operator case.
    """

    raw = (os.getenv("TARS_OUTREACH_SEND_INTERVAL_S") or "5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 5.0


async def create_campaign(
    *,
    name: str,
    template_id: str,
    recipients: list[dict[str, Any]],
    schedule_at: float | None = None,
    context_factory=None,
    store: OutreachStore | None = None,
) -> dict[str, Any]:
    """Insert a campaign + generate one draft per recipient.

    ``context_factory`` is an optional callable that takes a recipient
    dict and returns the per-recipient ``context`` dict. If omitted,
    each draft is generated with ``recipient.get('context', {})``.
    """

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "reason": "store_disabled"}

    template = await s.get_template(template_id)
    if not template:
        return {"ok": False, "reason": "template_not_found"}
    if not isinstance(recipients, list) or not recipients:
        return {"ok": False, "reason": "no_recipients"}

    campaign = OutreachCampaign(
        id=new_campaign_id(),
        name=name,
        template_id=template_id,
        recipients=list(recipients),
        schedule_at=schedule_at,
        status="planning",
    )
    await s.insert_campaign(campaign)

    interval = _draft_interval_s()
    outcomes: list[dict[str, Any]] = []
    generated = 0
    for idx, recipient in enumerate(recipients):
        ctx = (
            context_factory(recipient)
            if callable(context_factory)
            else dict(recipient.get("context") or {})
        )
        result = await generate_draft(
            template_id=template_id,
            recipient=recipient,
            context=ctx,
            campaign_id=campaign.id,
            store=s,
        )
        outcomes.append({"recipient": recipient, "result": result})
        if result.get("ok"):
            generated += 1
        if idx + 1 < len(recipients):
            await asyncio.sleep(interval)

    await s.update_campaign_counters(
        campaign.id,
        generated_delta=generated,
    )

    refreshed = await s.get_campaign(campaign.id)
    return {
        "ok": True,
        "campaign": (refreshed or campaign).to_dict(),
        "outcomes": outcomes,
        "generated": generated,
        "total": len(recipients),
    }


async def approve_all_in_campaign(
    campaign_id: str,
    *,
    except_ids: Iterable[str] | None = None,
    store: OutreachStore | None = None,
) -> dict[str, Any]:
    """Flip every ``draft`` row in the campaign to ``approved``."""

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "reason": "store_disabled"}

    skips = set(except_ids or [])
    drafts = await s.list_drafts(
        campaign_id=campaign_id, status="draft", limit=1000
    )
    approved_count = 0
    skipped_ids: list[str] = []
    for draft in drafts:
        if draft.id in skips:
            skipped_ids.append(draft.id)
            continue
        updated = await s.update_draft(draft.id, status="approved")
        if updated and updated.status == "approved":
            approved_count += 1

    if approved_count:
        await s.update_campaign_counters(
            campaign_id, approved_delta=approved_count
        )

    return {
        "ok": True,
        "approved": approved_count,
        "skipped": skipped_ids,
        "total_pending": len(drafts),
    }


async def send_campaign(
    campaign_id: str,
    *,
    store: OutreachStore | None = None,
) -> dict[str, Any]:
    """Fire every ``approved`` draft in the campaign with paced delay."""

    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "reason": "store_disabled"}

    await s.update_campaign_counters(campaign_id, status="sending")

    approved = await s.list_drafts(
        campaign_id=campaign_id, status="approved", limit=1000
    )
    interval = _send_interval_s()
    outcomes: list[dict[str, Any]] = []
    sent_count = 0
    failed_count = 0
    for idx, draft in enumerate(approved):
        result = await send_draft(draft.id, store=s)
        outcomes.append({"draft_id": draft.id, "result": result})
        if result.get("ok"):
            sent_count += 1
        else:
            failed_count += 1
        if idx + 1 < len(approved):
            await asyncio.sleep(interval)

    if sent_count:
        await s.update_campaign_counters(campaign_id, sent_delta=sent_count)

    remaining_approved = await s.list_drafts(
        campaign_id=campaign_id, status="approved", limit=1
    )
    final_status = "done" if not remaining_approved else "sending"
    await s.update_campaign_counters(campaign_id, status=final_status)

    return {
        "ok": True,
        "sent": sent_count,
        "failed": failed_count,
        "outcomes": outcomes,
        "campaign_status": final_status,
    }


async def abort_campaign(
    campaign_id: str, *, store: OutreachStore | None = None
) -> dict[str, Any]:
    s = store or get_store()
    if not s.enabled:
        return {"ok": False, "reason": "store_disabled"}
    await s.update_campaign_counters(campaign_id, status="aborted")
    return {"ok": True, "campaign_id": campaign_id, "status": "aborted"}


__all__ = [
    "abort_campaign",
    "approve_all_in_campaign",
    "create_campaign",
    "send_campaign",
]
