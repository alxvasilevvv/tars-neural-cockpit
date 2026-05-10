"""TARS outreach module (Wave 98).

Email drafting + send pipeline for B2B operators (LP updates, founder
DD reach-outs, intros, follow-ups, welcome touches). Drafts are
generated in the operator's voice via the AI Clone style profile
(:mod:`backend.core.clone.style`) and gated behind explicit
human-in-the-loop approval before they hit Gmail.

Persistence: SQLite at ``~/.tars/outreach.sqlite`` (override with
``TARS_OUTREACH_DB_PATH``; ``TARS_OUTREACH_STORE=disabled`` short-
circuits the entire module).

Public surface:

- :mod:`.models`     dataclasses (`OutreachTemplate`, `OutreachDraft`,
  `OutreachCampaign`).
- :mod:`.store`      SQLite-backed CRUD + queries.
- :mod:`.templates`  five built-in starter templates (lp_update,
  founder_dd, intro, follow_up, welcome_lp).
- :mod:`.drafter`    :func:`generate_draft` -- pulls AI Clone profile
  + calls council LLM. Cost-tracked through the entitlements gate.
- :mod:`.sender`     Gmail-based send (uses Wave 91 Gmail connector
  token). Records receipts via Wave 95 receipts module.
- :mod:`.campaigns`  bulk draft + bulk approve + paced send.
- :mod:`.safety`     recipient validation, placeholder detection,
  daily-cap enforcement, unsubscribe footer.

Contract version: 1.0 (see ``docs/contracts/OUTREACH.md``).
"""

from __future__ import annotations

from .models import (
    CAMPAIGN_STATUSES,
    CONTRACT_VERSION,
    DRAFT_STATUSES,
    OutreachCampaign,
    OutreachDraft,
    OutreachTemplate,
    USE_CASES,
    new_campaign_id,
    new_draft_id,
    new_template_id,
)
from .store import OutreachStore, get_store, reset_store

__all__ = [
    "CAMPAIGN_STATUSES",
    "CONTRACT_VERSION",
    "DRAFT_STATUSES",
    "OutreachCampaign",
    "OutreachDraft",
    "OutreachTemplate",
    "OutreachStore",
    "USE_CASES",
    "get_store",
    "new_campaign_id",
    "new_draft_id",
    "new_template_id",
    "reset_store",
]
