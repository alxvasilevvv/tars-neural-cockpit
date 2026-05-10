"""HTTP surface for the reports module (Wave 103).

Endpoints (operator-facing; loopback-only by deployment policy):

- ``GET    /api/reports/templates``                list templates (built-ins + custom)
- ``POST   /api/reports/templates``                create custom template
- ``GET    /api/reports/templates/{id}``           fetch one
- ``DELETE /api/reports/templates/{id}``           delete custom (built-ins protected)
- ``POST   /api/reports/templates/{id}/preview``   render preview HTML
- ``POST   /api/reports/run``                      kick off render -- returns run_id
- ``GET    /api/reports/runs``                     list with filters
- ``GET    /api/reports/runs/{id}``                single run with status
- ``GET    /api/reports/runs/{id}/download``       download bytes
- ``POST   /api/reports/runs/{id}/send``           outreach delivery (HIL gated)
- ``POST   /api/reports/schedule``                 register cron schedule (HIL gated)
- ``GET    /api/reports/providers``                list inputs providers

All ``send`` / ``schedule`` endpoints route through
``policy_gate.require_confirm`` so the HIL gate (Wave 76) kicks in
when ``TARS_REQUIRE_OPERATOR_CONFIRM=1``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from backend.core.reports import (
    REPORT_KINDS,
    REPORT_STATUSES,
    get_store,
)
from backend.core.reports.delivery import (
    download_url,
    file_exists,
    send_via_outreach,
    send_via_webhook,
)
from backend.core.reports.providers import list_providers
from backend.core.reports.renderer import (
    InputValidationError,
    render,
    render_preview_html,
)
from backend.core.reports.scheduling import create_scheduled_report
from backend.core.reports.templates_lib import seed_builtin_templates

from web_extras import policy_gate


router = APIRouter(prefix="/api/reports", tags=["reports"])


# ---------- helpers ---------------------------------------------------------


def _ensure_enabled() -> None:
    store = get_store()
    if not store.enabled:
        raise HTTPException(status_code=503, detail="reports_store_disabled")


_starter_seeded = False


async def _ensure_builtins() -> None:
    """Lazily seed the six built-in templates on first hit."""

    global _starter_seeded
    if _starter_seeded:
        return
    try:
        await seed_builtin_templates()
    except Exception:
        # Seeding is best-effort -- log and continue. Endpoints stay
        # functional even if a template upsert hiccups.
        pass
    _starter_seeded = True


# ---------- templates -------------------------------------------------------


@router.get("/templates")
async def get_templates(
    kind: str | None = Query(default=None),
) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_builtins()
    if kind and kind not in REPORT_KINDS:
        raise HTTPException(status_code=400, detail=f"bad_kind:{kind}")
    rows = await get_store().list_templates(kind=kind)
    return {
        "templates": [t.to_dict() for t in rows],
        "kinds": list(REPORT_KINDS),
    }


@router.post("/templates")
async def post_template(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_builtins()
    name = (payload.get("name") or "").strip()
    slug = (payload.get("slug") or "").strip()
    kind = (payload.get("kind") or "").strip()
    if not name or not slug or kind not in REPORT_KINDS:
        raise HTTPException(status_code=400, detail="bad_payload")
    existing = await get_store().get_template_by_slug(slug)
    if existing and existing.is_builtin:
        raise HTTPException(status_code=409, detail="builtin_slug_protected")
    tpl = await get_store().upsert_template(
        name=name,
        slug=slug,
        kind=kind,
        schema=payload.get("schema") or {},
        template_path=payload.get("template_path") or "",
        description=payload.get("description") or "",
        is_builtin=False,
    )
    return tpl.to_dict()


@router.get("/templates/{template_id}")
async def get_template(template_id: str) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_builtins()
    tpl = await get_store().get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template_not_found")
    return tpl.to_dict()


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> dict[str, Any]:
    _ensure_enabled()
    tpl = await get_store().get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template_not_found")
    if tpl.is_builtin:
        raise HTTPException(status_code=409, detail="builtin_protected")
    ok = await get_store().delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="template_not_found")
    return {"ok": True, "template_id": template_id}


@router.post("/templates/{template_id}/preview", response_class=HTMLResponse)
async def post_template_preview(
    template_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> HTMLResponse:
    _ensure_enabled()
    await _ensure_builtins()
    tpl = await get_store().get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template_not_found")
    inputs = payload.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=400, detail="inputs_must_be_object")
    html = render_preview_html(tpl, inputs)
    return HTMLResponse(content=html)


# ---------- runs ------------------------------------------------------------


@router.post("/run")
async def post_run(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_builtins()
    template_id = (payload.get("template_id") or "").strip()
    inputs = payload.get("inputs") or {}
    recipient_emails = payload.get("recipient_emails") or []
    if not template_id:
        raise HTTPException(status_code=400, detail="template_id_required")
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=400, detail="inputs_must_be_object")
    if not isinstance(recipient_emails, list):
        raise HTTPException(status_code=400, detail="recipient_emails_must_be_list")
    try:
        run = await render(
            template_id=template_id,
            inputs=inputs,
            recipient_emails=[str(e) for e in recipient_emails],
        )
    except InputValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return run.to_dict()


@router.get("/runs")
async def get_runs(
    template_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    since: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    _ensure_enabled()
    if status and status not in REPORT_STATUSES:
        raise HTTPException(status_code=400, detail=f"bad_status:{status}")
    rows = await get_store().list_runs(
        status=status,
        template_id=template_id,
        since_ts=since,
        limit=limit,
    )
    return {"runs": [r.to_dict() for r in rows]}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    _ensure_enabled()
    run = await get_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    out = run.to_dict()
    out["download_url"] = download_url(run.id) if run.status == "done" else None
    return out


@router.get("/runs/{run_id}/download")
async def get_run_download(run_id: str) -> FileResponse:
    _ensure_enabled()
    run = await get_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    if run.status != "done":
        raise HTTPException(status_code=409, detail=f"run_not_done:{run.status}")
    if not file_exists(run.output_path):
        raise HTTPException(status_code=410, detail="file_missing")
    media = {
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }.get(run.output_kind, "application/octet-stream")
    return FileResponse(
        path=run.output_path,
        media_type=media,
        filename=f"{run.template_id}-{run_id}.{run.output_kind}",
    )


@router.post("/runs/{run_id}/send")
async def post_run_send(
    run_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    _ensure_enabled()
    run = await get_store().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    recipients = payload.get("recipient_emails") or run.recipient_emails or []
    if not isinstance(recipients, list) or not recipients:
        raise HTTPException(status_code=400, detail="recipient_emails_required")
    channel = (payload.get("channel") or "outreach").strip()

    # HIL gate -- noop unless TARS_REQUIRE_OPERATOR_CONFIRM=1.
    await policy_gate.require_confirm(
        request,
        wallet_id="reports",
        action="reports.send",
        params={
            "run_id": run_id,
            "channel": channel,
            "recipient_count": len(recipients),
        },
    )

    if channel == "webhook":
        return await send_via_webhook(run_id)
    elif channel == "outreach":
        subject = (payload.get("subject_template") or "{template_name}")
        return await send_via_outreach(
            run_id,
            recipient_emails=[str(e) for e in recipients],
            subject_template=subject,
        )
    else:
        raise HTTPException(status_code=400, detail=f"bad_channel:{channel}")


# ---------- scheduling ------------------------------------------------------


@router.post("/schedule")
async def post_schedule(
    request: Request,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    _ensure_enabled()
    await _ensure_builtins()
    template_id = (payload.get("template_id") or "").strip()
    inputs_provider = (payload.get("inputs_provider") or "").strip()
    cron_expression = (payload.get("cron") or payload.get("cron_expression") or "").strip()
    timezone = (payload.get("timezone") or "UTC").strip()
    if not template_id or not inputs_provider or not cron_expression:
        raise HTTPException(status_code=400, detail="bad_payload")

    await policy_gate.require_confirm(
        request,
        wallet_id="reports",
        action="reports.schedule",
        params={
            "template_id": template_id,
            "inputs_provider": inputs_provider,
            "cron": cron_expression,
        },
    )

    result = await create_scheduled_report(
        template_id=template_id,
        inputs_provider=inputs_provider,
        cron_expression=cron_expression,
        timezone=timezone,
        enabled=bool(payload.get("enabled", True)),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "schedule_failed")
    return result


@router.get("/providers")
async def get_providers() -> dict[str, Any]:
    return {"providers": list_providers()}


__all__ = ["router"]
