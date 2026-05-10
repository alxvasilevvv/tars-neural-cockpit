"""Dataclasses + ID helpers for the reports module (Wave 103).

Two records:

- :class:`ReportTemplate` -- reusable description of a report
  (kind + JSON input schema + path to the template file used by the
  rendering skill). Built-ins live in :mod:`.templates_lib`; custom
  templates are inserted via the router.
- :class:`ReportRun` -- one execution. Lifecycle:
  ``pending -> rendering -> done`` (terminal), or
  ``pending|rendering -> failed`` on error. Stores the rendered file
  path + opt-in recipient list for outreach delivery.

Status vocabularies are kept as module-level constants so the store
+ renderer + router agree on the lexicon.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# Rendering-kind enum -- picks which skill produces the artefact.
KIND_PPTX = "pptx"
KIND_DOCX = "docx"
KIND_XLSX = "xlsx"
KIND_PDF = "pdf"
REPORT_KINDS: tuple[str, ...] = (KIND_PPTX, KIND_DOCX, KIND_XLSX, KIND_PDF)


# Run status lifecycle.
REPORT_STATUSES: tuple[str, ...] = ("pending", "rendering", "done", "failed")


# ---------- ID helpers ------------------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_template_id() -> str:
    return _short_id("rtpl")


def new_run_id() -> str:
    return _short_id("rrun")


# ---------- ReportTemplate --------------------------------------------------


@dataclass
class ReportTemplate:
    """Reusable description of a report.

    ``schema`` is a JSON-Schema-ish dict describing the inputs the
    template expects. The router uses it to auto-generate the input
    form on the FE; the renderer uses it to validate inputs before
    invoking the skill. ``template_path`` is the path to a starter
    file checked into the repo (for skills that use a base template
    file) -- may be empty when the skill renders from scratch.
    """

    id: str
    name: str
    slug: str
    kind: str  # one of REPORT_KINDS
    schema: dict[str, Any] = field(default_factory=dict)
    template_path: str = ""
    description: str = ""
    is_builtin: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "kind": self.kind,
            "schema": dict(self.schema),
            "template_path": self.template_path,
            "description": self.description,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at,
        }


# ---------- ReportRun -------------------------------------------------------


@dataclass
class ReportRun:
    """One report execution -- pending, rendering, done, or failed."""

    id: str
    template_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output_path: str = ""
    output_kind: str = ""
    status: str = "pending"  # one of REPORT_STATUSES
    recipient_emails: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    generated_at: float | None = None
    error: str | None = None
    bytes_size: int | None = None

    def to_dict(self, *, redact_inputs: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "inputs": {} if redact_inputs else dict(self.inputs),
            "output_path": self.output_path,
            "output_kind": self.output_kind,
            "status": self.status,
            "recipient_emails": list(self.recipient_emails),
            "created_at": self.created_at,
            "generated_at": self.generated_at,
            "error": self.error,
            "bytes_size": self.bytes_size,
        }


__all__ = [
    "CONTRACT_VERSION",
    "KIND_DOCX",
    "KIND_PDF",
    "KIND_PPTX",
    "KIND_XLSX",
    "REPORT_KINDS",
    "REPORT_STATUSES",
    "ReportRun",
    "ReportTemplate",
    "new_run_id",
    "new_template_id",
]
