"""Template execution + skill dispatch for the reports module (Wave 103).

Public surface: :func:`render` -- saves a ``ReportRun`` row in
``pending``, kicks off rendering on a background task, and returns
the run id immediately so the FE can poll for status. The actual
render hands off to a kind-specific backend (pptx / docx / xlsx /
pdf), each of which is best-effort: if no skill loader is wired into
the host process, we fall back to a deterministic plain-text
placeholder so the file is always produced and the lifecycle never
gets stuck in ``rendering``.

The ``invoke_skill`` hook is intentionally pluggable: callers can
mount a richer renderer (e.g. python-pptx, reportlab, openpyxl)
without touching this module. See ``docs/contracts/REPORTS.md`` for
the contract.

Records a Wave 95 receipt of type ``report.generated`` on success.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import traceback
from typing import Any, Awaitable, Callable, Optional

from .models import (
    KIND_DOCX,
    KIND_PDF,
    KIND_PPTX,
    KIND_XLSX,
    REPORT_KINDS,
    ReportRun,
    ReportTemplate,
    new_run_id,
)
from .store import ReportStore, get_store


log = logging.getLogger("tars.reports")


# Where rendered files live on disk.
DEFAULT_OUTPUT_DIR = "~/.tars/reports"


def _resolve_output_dir(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_REPORTS_OUTPUT_DIR") or DEFAULT_OUTPUT_DIR
    expanded = os.path.expanduser(raw)
    os.makedirs(expanded, exist_ok=True)
    return expanded


# ---------- pluggable skill hook -------------------------------------------


# Type for the renderer hook: takes (kind, template, inputs, output_path)
# and writes bytes to output_path. Returns the byte count written.
SkillHook = Callable[
    [str, ReportTemplate, dict[str, Any], str],
    Awaitable[int],
]


_skill_hook: SkillHook | None = None


def set_skill_hook(hook: SkillHook | None) -> None:
    """Mount a custom skill renderer (called by the host process).

    Pass ``None`` to clear -- subsequent renders fall back to the
    built-in plaintext writer.
    """

    global _skill_hook
    _skill_hook = hook


def get_skill_hook() -> SkillHook | None:
    return _skill_hook


# ---------- built-in fallback writers --------------------------------------


def _summarise_inputs(inputs: dict[str, Any]) -> str:
    """Pretty-print inputs for the fallback text body."""

    lines: list[str] = []
    for k in sorted(inputs.keys()):
        v = inputs[k]
        if isinstance(v, (list, tuple)):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _fallback_render(
    kind: str,
    template: ReportTemplate,
    inputs: dict[str, Any],
    output_path: str,
) -> int:
    """Deterministic fallback writer used when no skill is mounted.

    Produces a plain-text body wrapped with a kind-appropriate
    header. Real rendering is the host's job (python-pptx, reportlab,
    openpyxl, python-docx) -- this just guarantees the run completes.
    """

    body = (
        f"# {template.name}\n"
        f"slug: {template.slug}\n"
        f"kind: {kind}\n"
        f"generated_at: {time.time():.0f}\n\n"
        f"## inputs\n"
        f"{_summarise_inputs(inputs)}\n"
    )
    raw = body.encode("utf-8")
    with open(output_path, "wb") as fh:
        fh.write(raw)
    return len(raw)


# ---------- preview ---------------------------------------------------------


def render_preview_html(
    template: ReportTemplate,
    inputs: dict[str, Any],
) -> str:
    """Render a lightweight HTML preview for the FE iframe.

    No file I/O; safe to call synchronously. Used by the
    ``POST /api/reports/templates/{id}/preview`` endpoint.
    """

    parts: list[str] = []
    parts.append("<!doctype html><html><head><meta charset='utf-8'>")
    parts.append(
        "<style>"
        "body{font-family:-apple-system,system-ui,sans-serif;"
        "padding:24px;color:#111;background:#fafafa;}"
        "h1{font-size:20px;margin:0 0 4px 0;}"
        ".meta{color:#666;font-size:12px;margin-bottom:18px;}"
        "h2{font-size:14px;text-transform:uppercase;letter-spacing:1px;"
        "color:#333;border-bottom:1px solid #ddd;padding-bottom:4px;}"
        "dl{margin:0;}dt{font-weight:600;margin-top:8px;}dd{margin:0 0 6px 16px;color:#444;}"
        "ul{margin:4px 0 0 20px;color:#444;}"
        "</style></head><body>"
    )
    parts.append(f"<h1>{_escape(template.name)}</h1>")
    parts.append(
        f"<div class='meta'>{_escape(template.kind.upper())} · {_escape(template.slug)}</div>"
    )
    if template.description:
        parts.append(f"<p>{_escape(template.description)}</p>")
    parts.append("<h2>Inputs</h2><dl>")
    for k in sorted(inputs.keys()):
        v = inputs[k]
        parts.append(f"<dt>{_escape(k)}</dt>")
        if isinstance(v, (list, tuple)):
            parts.append("<dd><ul>")
            for item in v:
                parts.append(f"<li>{_escape(str(item))}</li>")
            parts.append("</ul></dd>")
        elif isinstance(v, dict):
            parts.append("<dd><ul>")
            for kk, vv in v.items():
                parts.append(f"<li><b>{_escape(str(kk))}</b>: {_escape(str(vv))}</li>")
            parts.append("</ul></dd>")
        else:
            parts.append(f"<dd>{_escape(str(v))}</dd>")
    parts.append("</dl></body></html>")
    return "".join(parts)


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------- input validation ------------------------------------------------


class InputValidationError(ValueError):
    """Raised when ``inputs`` doesn't satisfy the template schema."""


def validate_inputs(template: ReportTemplate, inputs: dict[str, Any]) -> None:
    """Cheap structural validation against the template's schema.

    Only checks ``required`` flags and gross type mismatches. Rich
    validation (regex, ranges, enums) is left to the renderer hook.
    """

    schema = template.schema or {}
    if not isinstance(inputs, dict):
        raise InputValidationError("inputs_must_be_object")
    for field, spec in schema.items():
        if not isinstance(spec, dict):
            continue
        required = bool(spec.get("required"))
        present = field in inputs and inputs[field] not in (None, "")
        if required and not present:
            raise InputValidationError(f"missing_required:{field}")
        if not present:
            continue
        expected = spec.get("type")
        v = inputs[field]
        if expected == "string" and not isinstance(v, str):
            raise InputValidationError(f"bad_type:{field}:expected_string")
        if expected in ("number", "int") and not isinstance(v, (int, float)):
            raise InputValidationError(f"bad_type:{field}:expected_number")
        if expected == "boolean" and not isinstance(v, bool):
            raise InputValidationError(f"bad_type:{field}:expected_boolean")
        if expected == "array" and not isinstance(v, (list, tuple)):
            raise InputValidationError(f"bad_type:{field}:expected_array")
        if expected == "object" and not isinstance(v, dict):
            raise InputValidationError(f"bad_type:{field}:expected_object")


# ---------- main render entry point ----------------------------------------


async def render(
    template_id: str,
    inputs: dict[str, Any],
    *,
    recipient_emails: list[str] | None = None,
    store: ReportStore | None = None,
    output_dir: str | None = None,
    background: bool = True,
) -> ReportRun:
    """Kick off a render. Returns the persisted ``ReportRun`` row.

    The actual rendering happens on a detached background task when
    ``background=True`` (default), so the HTTP layer returns the run
    id immediately. Tests pass ``background=False`` to await
    completion synchronously.
    """

    s = store or get_store()
    if not s.enabled:
        raise RuntimeError("reports_store_disabled")
    tpl = await s.get_template(template_id)
    if tpl is None:
        raise LookupError(f"template_not_found:{template_id}")
    if tpl.kind not in REPORT_KINDS:
        raise ValueError(f"bad_template_kind:{tpl.kind}")
    validate_inputs(tpl, inputs)

    out_dir = _resolve_output_dir(output_dir)
    run_id = new_run_id()
    out_ext = _ext_for_kind(tpl.kind)
    out_path = os.path.join(out_dir, f"{run_id}.{out_ext}")

    run = ReportRun(
        id=run_id,
        template_id=tpl.id,
        inputs=dict(inputs),
        output_path=out_path,
        output_kind=tpl.kind,
        status="pending",
        recipient_emails=list(recipient_emails or []),
    )
    await s.insert_run(run)

    if background:
        asyncio.create_task(_render_and_finalize(s, tpl, run))
    else:
        await _render_and_finalize(s, tpl, run)
    return run


def _ext_for_kind(kind: str) -> str:
    return {
        KIND_PPTX: "pptx",
        KIND_DOCX: "docx",
        KIND_XLSX: "xlsx",
        KIND_PDF: "pdf",
    }.get(kind, "bin")


async def _render_and_finalize(
    store: ReportStore,
    template: ReportTemplate,
    run: ReportRun,
) -> None:
    """Background task: invoke the skill hook, update the run row.

    Never raises. Failure is recorded on the row.
    """

    await store.update_run(run.id, status="rendering")
    try:
        hook = get_skill_hook()
        if hook is not None:
            byte_count = await hook(template.kind, template, run.inputs, run.output_path)
        else:
            byte_count = await asyncio.to_thread(
                _fallback_render,
                template.kind,
                template,
                run.inputs,
                run.output_path,
            )
        await store.update_run(
            run.id,
            status="done",
            generated_at=time.time(),
            bytes_size=int(byte_count),
        )
        await _record_receipt(run.id, template.slug, template.kind, run.output_path)
    except Exception as exc:  # pragma: no cover - safety net
        log.warning(
            "reports.render failed run=%s template=%s err=%s",
            run.id,
            template.slug,
            exc,
        )
        await store.update_run(
            run.id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


async def _record_receipt(
    run_id: str,
    template_slug: str,
    kind: str,
    output_path: str,
) -> None:
    """Best-effort Wave 95 receipt emission.

    Uses the dispatch helper so a disabled receipt store never breaks
    the render pipeline.
    """

    try:
        from backend.core.receipts.dispatch import record  # local import: optional dep
        await record(
            type="report.generated",
            actor="reports",
            resource=f"run:{run_id}",
            payload={
                "template_slug": template_slug,
                "kind": kind,
                "output_path": output_path,
            },
        )
    except Exception as exc:
        log.debug("reports.receipt skipped err=%s", exc)


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "InputValidationError",
    "SkillHook",
    "get_skill_hook",
    "render",
    "render_preview_html",
    "set_skill_hook",
    "validate_inputs",
]
