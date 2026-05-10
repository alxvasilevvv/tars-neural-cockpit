"""Dataclasses + ID helpers for the outreach module (Wave 98).

Three core records:

- :class:`OutreachTemplate` -- reusable prompt + variable schema for a
  recurring email type (LP update, founder DD, intro, follow-up,
  welcome, or a custom operator-defined template).
- :class:`OutreachDraft` -- a generated email tied to a single
  recipient. Lifecycle: ``draft -> approved -> sent`` (terminal) or
  ``draft -> failed`` on a send error.
- :class:`OutreachCampaign` -- a batch send (one template, N
  recipients) the operator orchestrates as a unit. Tracks generated /
  approved / sent counters so the FE can render progress bars.

Status vocabularies are kept as module-level constants so the store +
router + safety layer all agree on the lexicon.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# Template use-case enum -- lets the FE bucket built-ins from custom.
USE_CASES: tuple[str, ...] = (
    "lp_update",
    "founder_dd",
    "intro",
    "follow_up",
    "welcome_lp",
    "custom",
)


# Draft status lifecycle. ``sent`` is terminal; ``failed`` is recoverable
# (operator can edit + retry which flips it back to ``draft``).
DRAFT_STATUSES: tuple[str, ...] = ("draft", "approved", "sent", "failed")


# Campaign status. ``planning`` = drafts not all generated yet;
# ``sending`` = approve-all + send loop in progress; ``done`` = every
# draft is in a terminal state (sent or failed); ``aborted`` = operator
# bailed mid-flight.
CAMPAIGN_STATUSES: tuple[str, ...] = ("planning", "sending", "done", "aborted")


# ---------- ID helpers ------------------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_template_id() -> str:
    return _short_id("tpl")


def new_draft_id() -> str:
    return _short_id("drf")


def new_campaign_id() -> str:
    return _short_id("cmp")


# ---------- OutreachTemplate ------------------------------------------------


@dataclass
class OutreachTemplate:
    """Reusable prompt + variable schema for an outreach email."""

    id: str
    name: str
    slug: str
    use_case: str  # one of USE_CASES
    system_prompt: str
    variables: list[str] = field(default_factory=list)
    default_subject_template: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "use_case": self.use_case,
            "system_prompt": self.system_prompt,
            "variables": list(self.variables),
            "default_subject_template": self.default_subject_template,
            "created_at": self.created_at,
        }


# ---------- OutreachDraft ---------------------------------------------------


@dataclass
class OutreachDraft:
    """One outreach email (draft, approved, sent, or failed)."""

    id: str
    template_id: str
    recipient: dict[str, Any]  # {email, name, company?}
    context: dict[str, Any] = field(default_factory=dict)
    subject: str = ""
    body: str = ""
    status: str = "draft"  # one of DRAFT_STATUSES
    created_at: float = field(default_factory=time.time)
    sent_at: float | None = None
    gmail_message_id: str | None = None
    error: str | None = None
    campaign_id: str | None = None

    def to_dict(self, *, redact_body: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "recipient": dict(self.recipient),
            "context": dict(self.context),
            "subject": self.subject,
            "body": "" if redact_body else self.body,
            "status": self.status,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "gmail_message_id": self.gmail_message_id,
            "error": self.error,
            "campaign_id": self.campaign_id,
        }


# ---------- OutreachCampaign ------------------------------------------------


@dataclass
class OutreachCampaign:
    """A batch outreach run (one template, N recipients)."""

    id: str
    name: str
    template_id: str
    recipients: list[dict[str, Any]] = field(default_factory=list)
    schedule_at: float | None = None
    status: str = "planning"  # one of CAMPAIGN_STATUSES
    drafts_generated: int = 0
    drafts_approved: int = 0
    drafts_sent: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "template_id": self.template_id,
            "recipients": [dict(r) for r in self.recipients],
            "schedule_at": self.schedule_at,
            "status": self.status,
            "drafts_generated": self.drafts_generated,
            "drafts_approved": self.drafts_approved,
            "drafts_sent": self.drafts_sent,
            "created_at": self.created_at,
        }


__all__ = [
    "CAMPAIGN_STATUSES",
    "CONTRACT_VERSION",
    "DRAFT_STATUSES",
    "OutreachCampaign",
    "OutreachDraft",
    "OutreachTemplate",
    "USE_CASES",
    "new_campaign_id",
    "new_draft_id",
    "new_template_id",
]
