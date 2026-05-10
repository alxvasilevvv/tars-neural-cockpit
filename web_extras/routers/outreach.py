"""HTTP surface for the outreach module (Wave 98).

Endpoints (operator-facing; loopback-only by deployment policy):

- ``GET    /api/outreach/templates``                 list templates
- ``POST   /api/outreach/templates``                 create custom template
- ``PATCH  /api/outreach/templates/{id}``            edit prompt / vars
- ``POST   /api/outreach/drafts``                    generate one draft
- ``GET    /api/outreach/drafts?status=...``         list drafts
- ``GET    /api/outreach/drafts/{id}``               fetch one
- ``PATCH  /api/outreach/drafts/{id}``               edit subject/body
                                                     or change status
- ``DELETE /api/outreach/drafts/{id}``               discard
- ``POST   /api/outreach/drafts/{id}/send``          fire (HIL gated)
- ``GET    /api/outreach/drafts/{id}/preview``       render w/ context
- ``POST   /api/outreach/campaigns``                 create + bulk draft
- ``GET    /api/outreach/campaigns``                 list
- ``GET    /api/outreach/campaigns/{id}``            detail
- ``POST   /api/outreach/campaigns/{id}/generate``   re-run drafting
- ``POST   /api/outreach/campaigns/{id}/approve-all``
- ``POST   /api/outreach/campaigns/{id}/send``       paced bulk send

The send endpoints call :func:`policy_gate.require_confirm` so the
HIL token gate (Wave 76) gets enforced when
``TARS_REQUIRE_OPERATOR_CONFIRM`` is on.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

from backend.core.outreach import (
    DRAFT_STATUSES,
    USE_CASES,
    get_store,
    new_draft_id,
    OutreachDraft,
)
from backend.core.outreach.campaigns import (
    abort_campaign,
    approve_all_in_campaign,
    create_campaign,
    send_campaign,
)
from backend.core.outreach.drafter import generate_draft
from backend.core.outreach.safety import check_send_eligibility
from backend.core.outreach.sender import send_draft
from backend.core.outreach.templates import seed_starter_templates

from web_extras import policy_gate


router = APIRouter(prefix="/api/outreach", tags=["outreach"])


# ---------- helpers ---------------------------------------------------------


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="outreach_store_disabled")


_starter_seeded = False


async def _ensure_starters() -> None:
    """Lazily seed the five built-in templates on first hit."""

    global _starter_seeded
    if _starter_seeded:
        return
    try:
        await seed_starter_templates()
    except Exception:
        # Seeding is best-effort -- log and continue. The /templates
        # list will simply be empty, which the FE can handle.
        pass
    _starter_seeded = True


def _draft_dict(draft: OutreachDraft) -> dict[str, Any]:
    return draft.to_dict()


# ---------- templates -------------------------------------------------------


@router.get("/templates")
async def list_templates() -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_starters()
    store = get_store()
    templates = await store.list_templates()
    return {
        "ok": True,
        "templates": [t.to_dict() for t in templates],
        "use_cases": list(USE_CASES),
        "count": len(templates),
    }


@router.post("/templates")
async def create_template(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_starters()
    name = (payload.get("name") or "").strip()
    slug = (payload.get("slug") or "").strip().lower()
    use_case = (payload.get("use_case") or "custom").strip()
    system_prompt = payload.get("system_prompt") or ""
    if not name or not slug or not system_prompt:
        raise HTTPException(
            status_code=400, detail="name, slug, system_prompt are required"
        )
    if use_case not in USE_CASES:
        raise HTTPException(status_code=400, detail=f"use_case must be in {USE_CASES}")
    variables = payload.get("variables") or []
    if not isinstance(variables, list):
        raise HTTPException(status_code=400, detail="variables must be a list")
    default_subject = payload.get("default_subject_template") or ""
    store = get_store()
    template = await store.upsert_template(
        name=name,
        slug=slug,
        use_case=use_case,
        system_prompt=system_prompt,
        variables=[str(v) for v in variables],
        default_subject_template=str(default_subject),
    )
    return {"ok": True, "template": template.to_dict()}


@router.patch("/templates/{template_id}")
async def patch_template(
    template_id: str, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    template = await store.update_template(
        template_id,
        name=payload.get("name"),
        system_prompt=payload.get("system_prompt"),
        variables=payload.get("variables"),
        default_subject_template=payload.get("default_subject_template"),
    )
    if not template:
        raise HTTPException(status_code=404, detail="template_not_found")
    return {"ok": True, "template": template.to_dict()}


# ---------- drafts ----------------------------------------------------------


@router.post("/drafts")
async def post_draft(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_starters()
    template_id = payload.get("template_id")
    recipient = payload.get("recipient") or {}
    context = payload.get("context") or {}
    if not template_id or not isinstance(recipient, dict):
        raise HTTPException(
            status_code=400, detail="template_id + recipient(dict) are required"
        )
    if not recipient.get("email"):
        raise HTTPException(status_code=400, detail="recipient.email is required")
    result = await generate_draft(
        template_id=template_id, recipient=recipient, context=context
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/drafts")
async def list_drafts(
    status: str | None = Query(default=None),
    since_ts: float | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    _ensure_enabled()
    if status and status not in DRAFT_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be in {DRAFT_STATUSES}"
        )
    store = get_store()
    drafts = await store.list_drafts(
        status=status, since_ts=since_ts, limit=limit
    )
    return {
        "ok": True,
        "drafts": [_draft_dict(d) for d in drafts],
        "count": len(drafts),
    }


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str) -> dict[str, Any]:
    _ensure_enabled()
    draft = await get_store().get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="draft_not_found")
    return {"ok": True, "draft": _draft_dict(draft)}


@router.patch("/drafts/{draft_id}")
async def patch_draft(
    draft_id: str, payload: dict[str, Any] = Body(...)
) -> dict[str, Any]:
    _ensure_enabled()
    new_status = payload.get("status")
    if new_status and new_status not in DRAFT_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be in {DRAFT_STATUSES}"
        )
    if new_status == "sent":
        # Status -> 'sent' must go through the send endpoint so the
        # safety + HIL chain runs and the gmail_message_id gets set.
        raise HTTPException(
            status_code=400,
            detail="use POST /drafts/{id}/send to mark as sent",
        )
    store = get_store()
    draft = await store.update_draft(
        draft_id,
        subject=payload.get("subject"),
        body=payload.get("body"),
        status=new_status,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="draft_not_found")
    return {"ok": True, "draft": _draft_dict(draft)}


@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str) -> dict[str, Any]:
    _ensure_enabled()
    ok = await get_store().delete_draft(draft_id)
    if not ok:
        raise HTTPException(status_code=404, detail="draft_not_found")
    return {"ok": True, "draft_id": draft_id}


@router.post("/drafts/{draft_id}/send")
async def post_draft_send(draft_id: str, request: Request) -> dict[str, Any]:
    _ensure_enabled()
    draft = await get_store().get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="draft_not_found")
    # HIL gate -- noop unless TARS_REQUIRE_OPERATOR_CONFIRM=1.
    await policy_gate.require_confirm(
        request,
        wallet_id="outreach",
        action="outreach.send",
        params={
            "draft_id": draft.id,
            "recipient_email": (draft.recipient or {}).get("email"),
            "subject": draft.subject,
        },
    )
    safety = await check_send_eligibility(draft)
    if not safety.ok:
        raise HTTPException(
            status_code=412,
            detail={"reason": safety.reason, "detail": safety.detail},
        )
    result = await send_draft(draft_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result)
    return result


@router.get("/drafts/{draft_id}/preview")
async def get_draft_preview(draft_id: str) -> dict[str, Any]:
    _ensure_enabled()
    draft = await get_store().get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="draft_not_found")
    safety = await check_send_eligibility(draft)
    return {
        "ok": True,
        "draft": _draft_dict(draft),
        "safety": {
            "ok": safety.ok,
            "reason": safety.reason,
            "detail": safety.detail,
        },
    }


# ---------- campaigns -------------------------------------------------------


@router.post("/campaigns")
async def post_campaign(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_starters()
    name = (payload.get("name") or "").strip()
    template_id = payload.get("template_id")
    recipients = payload.get("recipients") or []
    if not name or not template_id:
        raise HTTPException(
            status_code=400, detail="name + template_id are required"
        )
    if not isinstance(recipients, list) or not recipients:
        raise HTTPException(
            status_code=400, detail="recipients must be a non-empty list"
        )
    schedule_at = payload.get("schedule_at")
    result = await create_campaign(
        name=name,
        template_id=template_id,
        recipients=recipients,
        schedule_at=schedule_at,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/campaigns")
async def list_campaigns() -> dict[str, Any]:
    _ensure_enabled()
    campaigns = await get_store().list_campaigns()
    return {
        "ok": True,
        "campaigns": [c.to_dict() for c in campaigns],
        "count": len(campaigns),
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    campaign = await store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    drafts = await store.list_drafts(campaign_id=campaign_id, limit=1000)
    return {
        "ok": True,
        "campaign": campaign.to_dict(),
        "drafts": [_draft_dict(d) for d in drafts],
    }


@router.post("/campaigns/{campaign_id}/generate")
async def post_campaign_generate(
    campaign_id: str, payload: dict[str, Any] = Body(default={})
) -> dict[str, Any]:
    """Re-run drafting for a campaign whose generation didn't finish.

    No-ops for recipients who already have a draft on the campaign.
    """

    _ensure_enabled()
    store = get_store()
    campaign = await store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    existing = await store.list_drafts(campaign_id=campaign_id, limit=1000)
    seen_emails = {(d.recipient or {}).get("email") for d in existing}
    pending = [
        r for r in campaign.recipients
        if (r.get("email") not in seen_emails)
    ]
    generated = 0
    outcomes: list[dict[str, Any]] = []
    for r in pending:
        result = await generate_draft(
            template_id=campaign.template_id,
            recipient=r,
            context=dict(r.get("context") or {}),
            campaign_id=campaign.id,
        )
        outcomes.append({"recipient": r, "result": result})
        if result.get("ok"):
            generated += 1
    if generated:
        await store.update_campaign_counters(
            campaign_id, generated_delta=generated
        )
    return {
        "ok": True,
        "generated": generated,
        "skipped": len(existing),
        "outcomes": outcomes,
    }


@router.post("/campaigns/{campaign_id}/approve-all")
async def post_campaign_approve_all(
    campaign_id: str, payload: dict[str, Any] = Body(default={})
) -> dict[str, Any]:
    _ensure_enabled()
    except_ids = payload.get("except_ids") or []
    if not isinstance(except_ids, list):
        raise HTTPException(status_code=400, detail="except_ids must be a list")
    return await approve_all_in_campaign(
        campaign_id, except_ids=[str(x) for x in except_ids]
    )


@router.post("/campaigns/{campaign_id}/send")
async def post_campaign_send(
    campaign_id: str, request: Request
) -> dict[str, Any]:
    _ensure_enabled()
    store = get_store()
    campaign = await store.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    await policy_gate.require_confirm(
        request,
        wallet_id="outreach",
        action="outreach.send_campaign",
        params={"campaign_id": campaign_id, "name": campaign.name},
    )
    return await send_campaign(campaign_id)


@router.post("/campaigns/{campaign_id}/abort")
async def post_campaign_abort(campaign_id: str) -> dict[str, Any]:
    _ensure_enabled()
    return await abort_campaign(campaign_id)


__all__ = ["router"]
