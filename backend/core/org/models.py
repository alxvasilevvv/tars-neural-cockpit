"""Dataclasses + ID helpers for the org onboarding store (Wave 99).

Two records:

- :class:`Org` — the single-tenant org the operator is configuring
  via ``/onboard/org``. Most fields come straight from Step 1 of the
  wizard (name / type / size / timezone / primary use case). A
  ``metadata`` dict carries forward whatever Step 2 / Step 3 / Step 4
  recorded (connector statuses, invite count, picked playbook slugs)
  so the cockpit can render a live progress badge without re-querying
  every subsystem.

- :class:`Invite` — a single Step 3 invite intent. ``status`` stays
  ``pending`` until v9.3 multi-tenant workspaces ship and the email
  send job actually fires; the wizard surfaces this with a ROADMAP
  badge so the operator knows it's recorded but not active.

Helpers:

- :func:`new_org_id` / :func:`new_invite_id` — short prefixed UUIDs
  matching the ``coh_`` / ``att_`` style used elsewhere.
- :func:`normalize_role` — coerce arbitrary input to one of the four
  roles the wizard offers (defaults to ``viewer``).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# Org-type taxonomy — keep in sync with the dropdown in
# ``OrgOnboarding.tsx`` (Step 1) and the role→playbook mapping in
# ``orgOnboarding.ts`` (Step 4).
ORG_TYPES: tuple[str, ...] = (
    "vc_fund",
    "hedge_fund",
    "family_office",
    "saas_company",
    "dao",
    "research_lab",
    "other",
)


# Four invite roles. Mirrors the v9.3 multi-tenant RBAC plan; today
# these are recorded as intent only and the cockpit ignores them.
INVITE_ROLES: tuple[str, ...] = ("admin", "designer", "analyst", "viewer")


# Lifecycle: ``pending`` → ``sent`` (when the v9.3 cron fires) →
# ``accepted`` (when the invitee clicks the magic link). Today
# everything stays ``pending`` — that's the contract the FE renders.
INVITE_STATUSES: tuple[str, ...] = ("pending", "sent", "accepted")


# ---------- ID helpers ------------------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_org_id() -> str:
    return _short_id("org")


def new_invite_id() -> str:
    return _short_id("inv")


# ---------- Org -------------------------------------------------------------


@dataclass
class Org:
    """The single org the operator is configuring."""

    id: str
    name: str
    type: str = "other"
    size: str = ""
    timezone: str = "UTC"
    primary_use_case: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------- Invite ----------------------------------------------------------


@dataclass
class Invite:
    """One Step 3 invite intent — recorded, not yet emailed."""

    id: str
    org_id: str
    email: str
    role: str = "viewer"
    invited_at: float = field(default_factory=time.time)
    status: str = "pending"


# ---------- Helpers ---------------------------------------------------------


def normalize_role(role: str | None) -> str:
    """Coerce arbitrary input to a known role, defaulting to viewer."""

    if not role:
        return "viewer"
    role_l = str(role).strip().lower()
    if role_l in INVITE_ROLES:
        return role_l
    return "viewer"


def normalize_org_type(otype: str | None) -> str:
    """Coerce arbitrary input to a known org type, defaulting to other."""

    if not otype:
        return "other"
    t = str(otype).strip().lower().replace("-", "_").replace(" ", "_")
    if t in ORG_TYPES:
        return t
    # Friendly aliases matching the FE dropdown labels.
    aliases = {
        "vc": "vc_fund",
        "fund": "vc_fund",
        "hedge": "hedge_fund",
        "family": "family_office",
        "saas": "saas_company",
        "company": "saas_company",
        "lab": "research_lab",
        "research": "research_lab",
    }
    return aliases.get(t, "other")
