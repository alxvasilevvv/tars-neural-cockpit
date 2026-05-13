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

from fastapi import APIRouter, HTTPException

from backend.core.doctor import REGISTRY, run_all, run_check


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
