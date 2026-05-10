"""Dataclasses + ID helpers for the cohort tracking module (Wave 94).

Three core records:

- :class:`Cohort` — a workshop session (group of attendees) the
  facilitator is running. Owns a slug used in URLs.
- :class:`Attendee` — one participant. Has a join token (32 B URL-safe
  random) the attendee uses to claim their slot.
- :class:`AttendeeAction` — a single observed action. Mirrors the
  webhook envelope shape so events flow naturally between subsystems.

Phases follow the workshop lifecycle:
``intake → design → test → deploy → done``.

The ``done`` phase is terminal; once an attendee reaches it they are
counted in stats but no longer raise idle alerts.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# Workshop phases — order matters; used for phase-advance inference.
PHASES: tuple[str, ...] = ("intake", "design", "test", "deploy", "done")


# ---------- ID + token helpers ----------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_cohort_id() -> str:
    return _short_id("coh")


def new_attendee_id() -> str:
    return _short_id("att")


def new_action_id() -> str:
    return _short_id("act")


def new_token(nbytes: int = 32) -> str:
    """URL-safe random token used for attendee self-join.

    32 bytes = 256 bits of entropy, enough for single-tenant local
    deployments. v9.3 multi-tenant will move to per-cohort HMAC.
    """

    return secrets.token_urlsafe(nbytes)


# ---------- Cohort ----------------------------------------------------------


@dataclass
class Cohort:
    """A workshop cohort (group of attendees)."""

    id: str
    name: str
    slug: str
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    facilitator_user_id: str | None = None
    max_attendees: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.ended_at is None


# ---------- Attendee --------------------------------------------------------


@dataclass
class Attendee:
    """One workshop participant."""

    id: str
    cohort_id: str
    display_name: str
    email: str | None = None
    token: str = field(default_factory=new_token)
    joined_at: float = field(default_factory=time.time)
    current_phase: str = "intake"
    last_activity_at: float = field(default_factory=time.time)
    playbook_runs: int = 0
    errors: int = 0
    flagged: bool = False
    flag_reason: str | None = None


# ---------- AttendeeAction --------------------------------------------------


# Canonical action types. The router accepts any string but these are
# the well-known ones the dashboard knows how to render.
ACTION_TYPES: tuple[str, ...] = (
    "join",
    "playbook_start",
    "playbook_finish",
    "hil_gate",
    "error",
    "phase_advance",
    "broadcast_ack",
    "broadcast",
)


@dataclass
class AttendeeAction:
    """One observed action — mirrors webhook event envelope shape."""

    id: str
    attendee_id: str
    type: str
    occurred_at: float = field(default_factory=time.time)
    payload: dict[str, Any] = field(default_factory=dict)


# ---------- Helpers ---------------------------------------------------------


def normalize_phase(phase: str | None) -> str:
    """Coerce arbitrary input to a known phase, defaulting to intake."""

    if not phase:
        return "intake"
    phase_l = str(phase).strip().lower()
    if phase_l in PHASES:
        return phase_l
    return "intake"


def next_phase(current: str) -> str | None:
    """Return the next phase after `current`, or None if already done."""

    cur = normalize_phase(current)
    try:
        idx = PHASES.index(cur)
    except ValueError:
        return PHASES[0]
    if idx >= len(PHASES) - 1:
        return None
    return PHASES[idx + 1]
