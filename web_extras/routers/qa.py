"""HTTP surface over QA suite findings.

Reads a structured ``qa-report/1.0.0`` JSON file produced by either:

- the TARS Layer-1 Python qa_agent (``python -m scripts.qa_agent --json``), or
- the meeet core qa-suite Playwright runner
  (``qa-suite/.reports/findings.json``).

Endpoints:

- ``GET /api/qa/health`` — high-level digest: trace_id, base_url,
  started/finished timestamps, summary counters, and the list of
  failing probes only.
- ``GET /api/qa/report`` — full JSON report (paginated when too large).
- ``POST /api/qa/report`` — ingest a fresh report (CI uploads here so
  a single ``/health`` call shows the latest result; auth via
  ``QA_INGEST_TOKEN`` env when set).

Configuration:

- ``QA_REPORT_PATH`` — absolute path to the report JSON.
  Defaults to ``./qa-suite/.reports/findings.json`` relative to the
  process cwd, falling back to ``~/.tars/qa-report.json`` when the
  workspace path doesn't exist.
- ``QA_INGEST_TOKEN`` — when set, ``POST /api/qa/report`` requires
  ``Authorization: Bearer <token>``.

The router is intentionally stdlib-only (no extra deps) and survives
when no report file is present (returns ``status="absent"``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from backend.core.meeet import current_trace, trace_scope, get_client

router = APIRouter(prefix="/api/qa", tags=["qa"])


_DEFAULT_REPORT_PATHS = (
    "./qa-suite/.reports/findings.json",
    "~/.tars/qa-report.json",
)


def _resolve_report_path() -> Path | None:
    """Return the first existing path from env or the defaults."""
    candidates: list[str] = []
    env_path = os.environ.get("QA_REPORT_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.extend(_DEFAULT_REPORT_PATHS)
    for raw in candidates:
        p = Path(os.path.expanduser(raw))
        if p.is_file():
            return p
    # Fall back to the env path even if it doesn't exist — useful for
    # POST /api/qa/report which creates it.
    if env_path:
        return Path(os.path.expanduser(env_path))
    return Path(os.path.expanduser(_DEFAULT_REPORT_PATHS[0]))


def _load_report() -> dict[str, Any] | None:
    p = _resolve_report_path()
    if not p or not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summary_from(report: dict[str, Any]) -> dict[str, int]:
    """Compute a {pass, warn, fail, skip} summary from probes."""
    summary = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for probe in report.get("probes", []) or []:
        s = probe.get("status")
        if s in summary:
            summary[s] += 1
    return summary


def _ingest_token_check(authorization: str | None) -> None:
    expected = os.environ.get("QA_INGEST_TOKEN")
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[len("Bearer "):].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="invalid token")


@router.get("/health")
async def qa_health() -> dict[str, Any]:
    """Compact digest. Always 200; signals absence via ``status``."""
    with trace_scope() as trace_id:
        report = _load_report()
        if report is None:
            await _emit("qa.health.absent", {"path": str(_resolve_report_path())})
            return {
                "ok": True,
                "status": "absent",
                "trace_id": trace_id,
                "report_path": str(_resolve_report_path()),
                "summary": {"pass": 0, "warn": 0, "fail": 0, "skip": 0},
                "failing_probes": [],
            }

        summary = report.get("summary") or _summary_from(report)
        failing = [
            {
                "name": p.get("name"),
                "category": p.get("category"),
                "details": p.get("details"),
                "ts": p.get("ts"),
            }
            for p in (report.get("probes") or [])
            if p.get("status") == "fail"
        ]
        status = "fail" if summary.get("fail", 0) > 0 else "warn" if summary.get("warn", 0) > 0 else "pass"
        await _emit(
            "qa.health.read",
            {"status": status, "fail_count": summary.get("fail", 0), "report_trace": report.get("trace_id")},
        )
        return {
            "ok": True,
            "status": status,
            "trace_id": trace_id,
            "report_trace": report.get("trace_id"),
            "version": report.get("version"),
            "base_url": report.get("base_url"),
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "summary": summary,
            "failing_probes": failing,
        }


@router.get("/report")
async def qa_report(limit: int = 250, offset: int = 0) -> dict[str, Any]:
    """Full report, with `probes` list paginated."""
    report = _load_report()
    if report is None:
        return {"ok": True, "status": "absent", "probes": []}
    probes = report.get("probes") or []
    page = probes[offset : offset + limit]
    return {
        "ok": True,
        "status": "present",
        "version": report.get("version"),
        "base_url": report.get("base_url"),
        "trace_id": report.get("trace_id"),
        "started_at": report.get("started_at"),
        "finished_at": report.get("finished_at"),
        "summary": report.get("summary") or _summary_from(report),
        "total_probes": len(probes),
        "page": {"limit": limit, "offset": offset, "count": len(page)},
        "probes": page,
    }


@router.post("/report")
async def qa_report_post(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Accept a fresh report (CI pushes here)."""
    _ingest_token_check(authorization)
    body_raw = await request.body()
    try:
        body = json.loads(body_raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid json: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="report body must be a JSON object")
    if body.get("version", "").startswith("qa-report/") is False:
        raise HTTPException(
            status_code=400,
            detail="report.version must start with 'qa-report/' (e.g. 'qa-report/1.0.0')",
        )

    p = _resolve_report_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body, indent=2), encoding="utf-8")

    summary = body.get("summary") or _summary_from(body)
    await _emit(
        "qa.report.ingested",
        {
            "trace_id": body.get("trace_id"),
            "fail_count": summary.get("fail", 0),
            "probe_count": len(body.get("probes") or []),
            "path": str(p),
        },
    )
    return {
        "ok": True,
        "stored_at": str(p),
        "trace_id": current_trace(),
        "report_trace": body.get("trace_id"),
        "summary": summary,
    }


async def _emit(kind: str, payload: dict[str, Any]) -> None:
    """Best-effort meeet event emit; never raises."""
    try:
        await get_client().emit(kind, payload)
    except Exception:  # pragma: no cover - bridge optional
        pass
