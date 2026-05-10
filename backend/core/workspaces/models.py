"""Dataclasses for the Workspaces module (Wave 110).

Three immutable records — :class:`Workspace`, :class:`Membership`,
:class:`Invite` — plus id + token mint helpers.

Contract version is bumped here when the schema changes; the FE/SDK
read it through ``GET /api/workspaces`` to detect drift.
"""

from __future__ import annotations

import enum
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


CONTRACT_VERSION = "1.0"


class Plan(str, enum.Enum):
    """Workspace billing plan."""

    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


VALID_PLANS = {p.value for p in Plan}


class MembershipStatus(str, enum.Enum):
    """Lifecycle of a membership row."""

    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


VALID_MEMBERSHIP_STATUSES = {s.value for s in MembershipStatus}


class InviteStatus(str, enum.Enum):
    """Lifecycle of an invite row."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


VALID_INVITE_STATUSES = {s.value for s in InviteStatus}


def _now() -> float:
    return time.time()


def new_workspace_id() -> str:
    return "ws_" + secrets.token_hex(8)


def new_membership_id() -> str:
    return "mem_" + secrets.token_hex(8)


def new_invite_id() -> str:
    return "inv_" + secrets.token_hex(8)


def new_invite_token() -> str:
    """URL-safe random 32-byte invite token.

    The token IS the auth — anyone with the link can accept the invite,
    so we use ``secrets.token_urlsafe(32)`` (256 bits of entropy).
    """

    return secrets.token_urlsafe(32)


def _norm_settings(settings: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if not settings:
        return {}
    if not isinstance(settings, Mapping):
        return {}
    return dict(settings)


@dataclass(frozen=True)
class Workspace:
    """A multi-tenant workspace. Owned by a user, billed under a plan."""

    id: str
    slug: str
    name: str
    owner_user_id: str
    plan: str = Plan.FREE.value
    created_at: float = field(default_factory=_now)
    archived_at: Optional[float] = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.archived_at is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "owner_user_id": self.owner_user_id,
            "plan": self.plan,
            "created_at": self.created_at,
            "archived_at": self.archived_at,
            "settings": dict(self.settings),
            "is_active": self.is_active,
        }


@dataclass(frozen=True)
class Membership:
    """A user's membership in a workspace."""

    id: str
    workspace_id: str
    user_id: str
    email: str
    role: str
    invited_by: Optional[str] = None
    display_name: Optional[str] = None
    joined_at: Optional[float] = None
    invited_at: float = field(default_factory=_now)
    status: str = MembershipStatus.ACTIVE.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "invited_by": self.invited_by,
            "joined_at": self.joined_at,
            "invited_at": self.invited_at,
            "status": self.status,
        }


@dataclass(frozen=True)
class Invite:
    """A pending invite to a workspace."""

    id: str
    workspace_id: str
    email: str
    role: str
    token: str
    invited_by: str
    invited_at: float = field(default_factory=_now)
    expires_at: float = field(default_factory=lambda: _now() + 7 * 24 * 3600)
    accepted_at: Optional[float] = None
    status: str = InviteStatus.PENDING.value

    @property
    def is_expired(self) -> bool:
        return (
            self.status == InviteStatus.PENDING.value
            and _now() > self.expires_at
        )

    def to_dict(self, *, include_token: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "email": self.email,
            "role": self.role,
            "invited_by": self.invited_by,
            "invited_at": self.invited_at,
            "expires_at": self.expires_at,
            "accepted_at": self.accepted_at,
            "status": self.status,
            "is_expired": self.is_expired,
        }
        if include_token:
            out["token"] = self.token
        return out


__all__ = [
    "CONTRACT_VERSION",
    "Invite",
    "InviteStatus",
    "Membership",
    "MembershipStatus",
    "Plan",
    "VALID_INVITE_STATUSES",
    "VALID_MEMBERSHIP_STATUSES",
    "VALID_PLANS",
    "Workspace",
    "new_invite_id",
    "new_invite_token",
    "new_membership_id",
    "new_workspace_id",
]
