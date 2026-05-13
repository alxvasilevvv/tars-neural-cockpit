"""HTTP surface for ``tars-doctor`` (Wave 155).

Endpoints:

- ``GET /api/doctor`` — run every registered check and return the
  array of results.
- ``GET /api/doctor/{slug}`` — run a single check by slug.
- ``GET /api/doctor/registry`` — list available check slugs +
  labels without running them.

Same shape as the CLI's ``--json`` output, so any consumer (cockpit
panel, W117 synthetic monitor, brother's status dashboard) can
parse it the same way.

The endpoint is read-only — no body, no side-effects on the
subsystems being checked. Each check has its own short timeout
(default 5s) so a slow subsystem can never stall the response
indefinitely; the whole-run wall-time is bounded by sum-of-checks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
# W201: HTMLResponse no longer imported — UI moved to Tauri .app

from backend.core.doctor import (
    FIX_REGISTRY,
    REGISTRY,
    run_all,
    run_all_fixes,
    run_check,
    run_fix,
)


router = APIRouter(prefix="/api/doctor", tags=["doctor"])


@router.get("")
async def doctor_all() -> dict[str, Any]:
    """Run every registered check and return all results.

    Response shape::

      {
        "ok": True,
        "summary": {"ok": 4, "warn": 2, "fail": 0, "skip": 1},
        "results": [<CheckResult.to_dict()>, ...]
      }

    The top-level ``ok`` mirrors the CLI's exit code logic — false
    iff any check has ``status == "fail"``.
    """

    results = run_all()
    summary = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return {
        "ok": summary["fail"] == 0,
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }


@router.get("/registry")
async def doctor_registry() -> dict[str, Any]:
    """List available check slugs + labels without running them."""

    entries: list[dict[str, str]] = []
    for slug, fn in REGISTRY:
        doc = (fn.__doc__ or "").strip().splitlines()
        entries.append(
            {
                "slug": slug,
                "label": (doc[0] if doc else slug),
            }
        )
    return {"ok": True, "checks": entries, "count": len(entries)}


# W201: HTML cockpit routes /page and /cockpit removed per user pivot —
# UI now lives ONLY in TARS.app (Tauri desktop), bundled at
# desktop/src-tauri/web/index.html. Backend exposes JSON endpoints only.


@router.get("/{slug}")
async def doctor_one(slug: str) -> dict[str, Any]:
    """Run a single check by slug."""

    known = {s for s, _ in REGISTRY}
    if slug not in known:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_check",
                "slug": slug,
                "known": sorted(known),
            },
        )
    result = run_check(slug)
    return {"ok": result.status != "fail", "result": result.to_dict()}


# ─── Auto-remediation surface (Wave 167) ────────────────────────────


@router.post("/fix")
async def doctor_fix_all() -> dict[str, Any]:
    """Apply every registered fixer.

    Response::

      {
        "ok": True,
        "summary": {"applied": 1, "skipped": 2, "failed": 0},
        "results": [<FixResult.to_dict()>, ...]
      }

    ``ok`` is false iff any fixer failed (applied=False AND
    skipped=False). Skip-only fixers (daemon, scheduler) don't
    demote ok.
    """

    results = run_all_fixes()
    summary = {"applied": 0, "skipped": 0, "failed": 0}
    for r in results:
        if r.applied:
            summary["applied"] += 1
        elif r.skipped:
            summary["skipped"] += 1
        else:
            summary["failed"] += 1
    return {
        "ok": summary["failed"] == 0,
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }


@router.post("/fix/{slug}")
async def doctor_fix_one(slug: str) -> dict[str, Any]:
    """Apply a single fixer by slug. 404 when slug isn't known.

    Returns ``{ok, result: <FixResult.to_dict()>}``. ``ok`` is
    false iff the fixer ran but failed (applied=False AND
    skipped=False).
    """

    known = {s for s, _ in REGISTRY}
    if slug not in known:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_check",
                "slug": slug,
                "known": sorted(known),
                "fixable": sorted(FIX_REGISTRY.keys()),
            },
        )
    result = run_fix(slug)
    failed = (not result.applied) and (not result.skipped)
    return {"ok": not failed, "result": result.to_dict()}


# ─── Notification test surface (Wave 168) ───────────────────────────


@router.post("/test/notify")
async def doctor_test_notify(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Fire a synthetic doctor.status_changed alert through fanout_all.

    Body shape (all optional):
      {
        "channels": ["telegram", "imessage", "email"]  # default: env
        "slug": "test",
        "from": "ok",
        "to": "warn",
        "summary": "test alert from /api/doctor/test/notify"
      }

    Returns ``{ok, results: [...]}`` mirroring the fanout_all
    contract. ``ok`` is true iff every channel reports ``ok=True``.

    Use this to verify TARS_DAEMON_FANOUT_CHANNELS + per-channel
    config is wired correctly without waiting for a real drift.
    """

    body = payload or {}
    channels = body.get("channels")  # None → fanout_all reads env
    change = {
        "slug": str(body.get("slug") or "test"),
        "from": str(body.get("from") or "ok"),
        "to": str(body.get("to") or "warn"),
        "summary": str(
            body.get("summary")
            or "test alert from /api/doctor/test/notify"
        ),
    }

    try:
        from backend.core.notifications import fanout_all
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "notifications_import_failed", "detail": str(exc)},
        )

    results = fanout_all(change, channels=channels)
    if not results:
        return {
            "ok": False,
            "results": [],
            "error": "no_channels_configured",
            "hint": (
                "Pass {channels:[...]} in the body OR set "
                "TARS_DAEMON_FANOUT_CHANNELS env"
            ),
        }
    all_ok = all(r.get("ok") for r in results)
    return {"ok": all_ok, "results": results, "change": change}

