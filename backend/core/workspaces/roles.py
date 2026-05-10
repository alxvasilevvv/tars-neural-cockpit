"""RBAC: roles + permission matrix for the Workspaces module (Wave 110).

The matrix below is the source-of-truth for what each role can do
inside a workspace. It mirrors the design in
``docs/contracts/WORKSPACES.md`` extended with the operator surfaces
that landed between W94 and W108.

Two helpers:

- :func:`can(role, permission)` — bool predicate, cheap dict lookup.
- :func:`roles_with(permission)` — list of roles that hold a permission.

Both are pure / sync / no I/O so they're safe to call from request
handlers, middleware, FE-facing JSON serialisers, or test fixtures.
"""

from __future__ import annotations

import enum


class Role(str, enum.Enum):
    """Workspace member roles, ordered by privilege (most -> least)."""

    OWNER = "owner"
    ADMIN = "admin"
    DESIGNER = "designer"
    ANALYST = "analyst"
    VIEWER = "viewer"


VALID_ROLES = {r.value for r in Role}


class Permission(str, enum.Enum):
    """Permissions checked across the TARS HTTP + agent surface."""

    WORKSPACE_DELETE = "workspace.delete"
    MEMBERS_INVITE = "members.invite"
    MEMBERS_REMOVE = "members.remove"
    AGENTS_CREATE = "agents.create"
    AGENTS_DELETE = "agents.delete"
    PLAYBOOKS_CREATE = "playbooks.create"
    PLAYBOOKS_RUN = "playbooks.run"
    WALLET_SIGN = "wallet.sign"
    OUTREACH_SEND = "outreach.send"
    RECEIPTS_VIEW = "receipts.view"
    RECEIPTS_EXPORT = "receipts.export"
    REPORTS_GENERATE = "reports.generate"
    COMPLIANCE_EXPORT = "compliance.export"


VALID_PERMISSIONS = {p.value for p in Permission}


# OWNER     - every permission, including workspace deletion + member kicks.
# ADMIN     - every permission EXCEPT workspace deletion (only owner can nuke
#             the tenant). Can invite + remove members.
# DESIGNER  - operational power user: builds playbooks, runs them, ships
#             outreach, generates reports. Cannot manage members or sign
#             wallet tx (those land at admin+ tier per current SOPs).
# ANALYST   - read + run + report. Can run existing playbooks but not create
#             them, and can generate reports but not export compliance bundles.
#             No outreach send (HIL gate is owner/admin/designer).
# VIEWER    - read-only. Can see receipts but cannot export anything.

MATRIX: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(
        {
            Permission.WORKSPACE_DELETE,
            Permission.MEMBERS_INVITE,
            Permission.MEMBERS_REMOVE,
            Permission.AGENTS_CREATE,
            Permission.AGENTS_DELETE,
            Permission.PLAYBOOKS_CREATE,
            Permission.PLAYBOOKS_RUN,
            Permission.WALLET_SIGN,
            Permission.OUTREACH_SEND,
            Permission.RECEIPTS_VIEW,
            Permission.RECEIPTS_EXPORT,
            Permission.REPORTS_GENERATE,
            Permission.COMPLIANCE_EXPORT,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.MEMBERS_INVITE,
            Permission.MEMBERS_REMOVE,
            Permission.AGENTS_CREATE,
            Permission.AGENTS_DELETE,
            Permission.PLAYBOOKS_CREATE,
            Permission.PLAYBOOKS_RUN,
            Permission.WALLET_SIGN,
            Permission.OUTREACH_SEND,
            Permission.RECEIPTS_VIEW,
            Permission.RECEIPTS_EXPORT,
            Permission.REPORTS_GENERATE,
            Permission.COMPLIANCE_EXPORT,
        }
    ),
    Role.DESIGNER: frozenset(
        {
            Permission.AGENTS_CREATE,
            Permission.PLAYBOOKS_CREATE,
            Permission.PLAYBOOKS_RUN,
            Permission.OUTREACH_SEND,
            Permission.RECEIPTS_VIEW,
            Permission.REPORTS_GENERATE,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.PLAYBOOKS_RUN,
            Permission.RECEIPTS_VIEW,
            Permission.REPORTS_GENERATE,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.RECEIPTS_VIEW,
        }
    ),
}


def _normalise_role(role):
    if isinstance(role, Role):
        return role
    try:
        return Role(str(role).strip().lower())
    except ValueError:
        return None


def _normalise_permission(perm):
    if isinstance(perm, Permission):
        return perm
    try:
        return Permission(str(perm).strip().lower())
    except ValueError:
        return None


def can(role, permission) -> bool:
    """Return True if ``role`` is allowed to perform ``permission``."""

    r = _normalise_role(role)
    p = _normalise_permission(permission)
    if r is None or p is None:
        return False
    return p in MATRIX.get(r, frozenset())


def roles_with(permission) -> list:
    """Return every :class:`Role` that has ``permission``, in declaration order."""

    p = _normalise_permission(permission)
    if p is None:
        return []
    return [r for r in Role if p in MATRIX.get(r, frozenset())]


def matrix_to_dict() -> dict:
    """Serialise the matrix for FE consumption (role -> sorted perm strings)."""

    return {
        role.value: sorted(p.value for p in MATRIX[role])
        for role in Role
    }


__all__ = [
    "MATRIX",
    "Permission",
    "Role",
    "VALID_PERMISSIONS",
    "VALID_ROLES",
    "can",
    "matrix_to_dict",
    "roles_with",
]
