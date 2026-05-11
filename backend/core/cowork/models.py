"""Dataclasses + ID helpers for the cowork module (Wave 129).

Five core records:

- :class:`Session` — a shared agent session. Owns a slug used in
  URLs (`/cowork/<slug>`), tracks owner and creation time, has a
  lifecycle: `live → paused → ended`.
- :class:`Member` — one human participant. Holds a join token (32 B
  URL-safe random) the member uses to claim their slot; the token
  doubles as the WebSocket auth credential.
- :class:`Cursor` — last-known cursor position of one member over a
  shared workspace file. Path is opaque to cowork — the client side
  decides what "file" means (a markdown buffer, a code file, a row
  in a table). Coords are `line` + `col`; `selection` is optional.
- :class:`Handoff` — pending ownership transfer. One-time token,
  short TTL (default 15 min), single-use semantics enforced by the
  store.
- ``SessionStatus`` / ``MemberRole`` — small enums.

The model layer is pure: no I/O, no SQL. ``store.py`` is the only
file that touches SQLite.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


CONTRACT_VERSION = "1.0"


# ---------- Enums -----------------------------------------------------------


class SessionStatus(str, Enum):
    """Lifecycle of a cowork session."""

    LIVE = "live"
    PAUSED = "paused"
    ENDED = "ended"


class MemberRole(str, Enum):
    """Per-member capability tier.

    - ``owner``   — created the session, full controls (handoff, end).
    - ``editor``  — can publish cursor + send chat + view agent frames.
    - ``viewer``  — read-only: agent frames + presence + cursors.
    """

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


# ---------- ID + token helpers ----------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_session_id() -> str:
    return _short_id("cw")


def new_member_id() -> str:
    return _short_id("cm")


def new_cursor_id() -> str:
    return _short_id("cu")


def new_handoff_id() -> str:
    return _short_id("ho")


def new_token(nbytes: int = 32) -> str:
    """URL-safe random token used for member join + handoff accept.

    32 bytes = 256 bits of entropy. v9.3 multi-tenant will move to
    per-workspace HMAC, but for single-tenant local TARS the raw
    token is fine.
    """

    return secrets.token_urlsafe(nbytes)


# ---------- Session ---------------------------------------------------------


@dataclass
class Session:
    """A shared cowork session."""

    id: str
    name: str
    slug: str
    owner_user_id: str
    status: SessionStatus = SessionStatus.LIVE
    created_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    workspace_id: str | None = None  # W110 workspace fence (v9.3)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == SessionStatus.LIVE


# ---------- Member ----------------------------------------------------------


@dataclass
class Member:
    """One human in a cowork session."""

    id: str
    session_id: str
    display_name: str
    user_id: str | None = None  # nullable for ad-hoc anonymous join
    email: str | None = None
    role: MemberRole = MemberRole.EDITOR
    token: str = field(default_factory=new_token)
    joined_at: float = field(default_factory=time.time)
    color: str | None = None  # hex like "#6366F1" — for presence dot
    last_seen_at: float = field(default_factory=time.time)


# Palette used to assign a unique colour per member. Cycles when more
# than 8 members join (rare in practice — 2-5 is the realistic upper
# bound for a single cowork session).
MEMBER_COLOR_PALETTE: tuple[str, ...] = (
    "#6366F1",  # indigo
    "#8B5CF6",  # violet
    "#06B6D4",  # cyan
    "#34D399",  # success-green
    "#F59E0B",  # warning-amber
    "#EC4899",  # pink
    "#10B981",  # emerald
    "#F472B6",  # rose
)


def assign_color(seat_index: int) -> str:
    """Map a 0-based member ordinal to a stable palette colour."""

    return MEMBER_COLOR_PALETTE[seat_index % len(MEMBER_COLOR_PALETTE)]


# ---------- Cursor ----------------------------------------------------------


@dataclass
class Cursor:
    """Last-known cursor position for one member over one shared path."""

    id: str
    session_id: str
    member_id: str
    path: str  # opaque to cowork; client-defined ("notes.md", "plan.tsx:42", …)
    line: int = 0
    col: int = 0
    selection: dict[str, Any] | None = None  # {"end_line": int, "end_col": int}
    updated_at: float = field(default_factory=time.time)


# ---------- Handoff ---------------------------------------------------------


# Default handoff TTL. Long enough for a recipient to context-switch
# and confirm, short enough that a leaked token expires quickly.
DEFAULT_HANDOFF_TTL_S: int = 15 * 60  # 15 minutes


@dataclass
class Handoff:
    """A pending ownership transfer."""

    id: str
    session_id: str
    from_user_id: str
    to_email: str | None  # nullable for "open handoff" — anyone with token
    token: str = field(default_factory=new_token)
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(
        default_factory=lambda: time.time() + DEFAULT_HANDOFF_TTL_S
    )
    accepted_at: float | None = None
    accepted_by_user_id: str | None = None
    revoked_at: float | None = None

    @property
    def is_pending(self) -> bool:
        if self.accepted_at is not None or self.revoked_at is not None:
            return False
        return time.time() < self.expires_at

    @property
    def is_expired(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and time.time() >= self.expires_at
        )


# ---------- Helpers ---------------------------------------------------------


def normalize_role(role: str | MemberRole | None) -> MemberRole:
    """Coerce arbitrary input to a valid role, defaulting to viewer.

    Viewer (most restrictive) is the safe default — a malformed join
    request shouldn't grant write access.
    """

    if isinstance(role, MemberRole):
        return role
    if not role:
        return MemberRole.VIEWER
    try:
        return MemberRole(str(role).strip().lower())
    except ValueError:
        return MemberRole.VIEWER


def slugify(name: str) -> str:
    """Turn an arbitrary session name into a URL slug.

    Deterministic + URL-safe: lowercase, ASCII letters/digits/dash
    only, max 48 chars, suffixed with a 6-char random nonce to keep
    collisions rare in single-tenant land.
    """

    base = "".join(
        ch.lower() if ch.isalnum() else "-"
        for ch in (name or "").strip()
    )
    # Collapse repeats + strip leading/trailing dashes.
    while "--" in base:
        base = base.replace("--", "-")
    base = base.strip("-")[:48] or "session"
    suffix = secrets.token_hex(3)
    return f"{base}-{suffix}"
