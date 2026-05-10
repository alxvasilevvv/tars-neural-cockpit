"""Dataclasses + ID helpers for the bundles module (Wave 107).

A :class:`Bundle` is a frozen-ish data record bundling a vertical
into one install unit. The ``components`` dict carries the actual
payload -- see ``docs/contracts/BUNDLES.md`` for the schema.

An :class:`InstallReport` is what the installer + previewer return:
counts of each component type plus the list of items that *would
be* / *were* installed. The dry-run path (previewer) and the wet
path (installer) share the same shape so the FE renders both with
one component.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# Org-type vocabulary. Must match the value the W99 onboarding
# wizard records on the org record. Bundles outside this set
# fall back to ``other_bundle``.
ORG_TYPES: tuple[str, ...] = (
    "vc_fund",
    "hedge_fund",
    "family_office",
    "saas",
    "dao",
    "research_lab",
    "other",
)


# ---------- ID helpers ------------------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_install_id() -> str:
    return _short_id("bins")


# ---------- Bundle ----------------------------------------------------------


@dataclass
class Bundle:
    """A single vertical bundle.

    ``components`` keys (all optional, missing == empty list / no-op):

    - ``playbooks``           list[str]              ids like ``fund/weekly_lp_report``
    - ``scheduled``           list[dict]             ``{playbook_id, cron, args?}``
    - ``dashboard_widgets``   list[str]              widget ids in display order
    - ``report_templates``    list[str]              report-template slugs to enable
    - ``outreach_templates``  list[str]              outreach-template slugs to seed
    - ``connectors_hints``    list[str|dict]         ``"gmail"`` or ``{"id":"gmail","priority":True}``
    - ``welcome_content``     str                    markdown shown post-install
    - ``first_run_playbook``  str | None             id of one playbook to queue
    """

    id: str
    slug: str
    name: str
    description: str
    org_type: str
    version: str = "1.0.0"
    components: dict[str, Any] = field(default_factory=dict)

    # ---- accessors --------------------------------------------------------

    def playbooks(self) -> list[str]:
        return list(self.components.get("playbooks") or [])

    def scheduled(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for entry in self.components.get("scheduled") or []:
            if not isinstance(entry, dict):
                continue
            pid = str(entry.get("playbook_id") or "").strip()
            cron = str(entry.get("cron") or "").strip()
            if not pid or not cron:
                continue
            out.append(
                {
                    "playbook_id": pid,
                    "cron": cron,
                    "args": dict(entry.get("args") or {}),
                }
            )
        return out

    def dashboard_widgets(self) -> list[str]:
        return [str(x) for x in (self.components.get("dashboard_widgets") or [])]

    def report_templates(self) -> list[str]:
        return [str(x) for x in (self.components.get("report_templates") or [])]

    def outreach_templates(self) -> list[str]:
        return [str(x) for x in (self.components.get("outreach_templates") or [])]

    def connectors_hints(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for h in self.components.get("connectors_hints") or []:
            if isinstance(h, str):
                out.append({"id": h, "priority": False})
            elif isinstance(h, dict):
                hid = str(h.get("id") or "").strip()
                if hid:
                    out.append(
                        {
                            "id": hid,
                            "priority": bool(h.get("priority", False)),
                        }
                    )
        return out

    def welcome_content(self) -> str:
        return str(self.components.get("welcome_content") or "")

    def first_run_playbook(self) -> str | None:
        v = self.components.get("first_run_playbook")
        return str(v) if v else None

    # ---- serde ------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "org_type": self.org_type,
            "version": self.version,
            "components": {
                "playbooks": self.playbooks(),
                "scheduled": self.scheduled(),
                "dashboard_widgets": self.dashboard_widgets(),
                "report_templates": self.report_templates(),
                "outreach_templates": self.outreach_templates(),
                "connectors_hints": self.connectors_hints(),
                "welcome_content": self.welcome_content(),
                "first_run_playbook": self.first_run_playbook(),
            },
        }

    def counts(self) -> dict[str, int]:
        """Cheap summary used by the preview-modal header."""

        return {
            "playbooks": len(self.playbooks()),
            "scheduled": len(self.scheduled()),
            "dashboard_widgets": len(self.dashboard_widgets()),
            "report_templates": len(self.report_templates()),
            "outreach_templates": len(self.outreach_templates()),
            "connectors_hints": len(self.connectors_hints()),
            "first_run": 1 if self.first_run_playbook() else 0,
        }


# ---------- InstallReport ---------------------------------------------------


@dataclass
class InstallReport:
    """Result of a bundle install (or preview).

    ``dry_run=True`` means nothing was persisted -- the installer
    walks the bundle and reports what *would* be created.
    """

    install_id: str
    bundle_id: str
    org_id: str
    dry_run: bool = False
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    welcome_content: str = ""
    first_run_id: str | None = None
    items: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {
            "playbooks": [],
            "scheduled": [],
            "dashboard_widgets": [],
            "report_templates": [],
            "outreach_templates": [],
            "connectors_hints": [],
        }
    )
    warnings: list[str] = field(default_factory=list)

    def add(self, key: str, item: dict[str, Any]) -> None:
        self.items.setdefault(key, []).append(item)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.items.items()}

    def total(self) -> int:
        return sum(self.counts().values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "install_id": self.install_id,
            "bundle_id": self.bundle_id,
            "org_id": self.org_id,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "welcome_content": self.welcome_content,
            "first_run_id": self.first_run_id,
            "items": {k: list(v) for k, v in self.items.items()},
            "counts": self.counts(),
            "total": self.total(),
            "warnings": list(self.warnings),
        }


__all__ = [
    "Bundle",
    "CONTRACT_VERSION",
    "InstallReport",
    "ORG_TYPES",
    "new_install_id",
]
