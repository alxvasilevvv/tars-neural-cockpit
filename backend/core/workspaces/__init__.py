"""TARS multi-tenant Workspaces module (Wave 110 — additive MVP).

Schema-only foundation that lays the groundwork for v9.3 to flip the
switch on data fencing. In v9.1.0 the module ships:

- :mod:`.models`     — :class:`Workspace`, :class:`Membership`,
  :class:`Invite` dataclasses (URL-safe random invite tokens).
- :mod:`.store`      — SQLite-backed CRUD + invite flow at
  ``~/.tars/workspaces.sqlite`` (override with
  ``TARS_WORKSPACES_DB_PATH``).
- :mod:`.roles`      — RBAC :class:`Role` enum + :class:`Permission`
  enum + permission matrix + ``can()`` / ``roles_with()`` helpers.
- :mod:`.middleware` — workspace context extractor (records the
  requested workspace in request scope but does NOT enforce fencing
  on existing endpoints — that's deferred to v9.3).

A "personal" workspace auto-creates on first store call so existing
single-tenant code implicitly "lives in" it without any migration.

Disable the module with ``TARS_WORKSPACES_STORE=disabled``.

Contract version: 1.0 (see ``docs/contracts/WORKSPACES.md``).
"""

from __future__ import annotations

from .middleware import (
    PERSONAL_WORKSPACE_ID,
    WORKSPACE_HEADER,
    WORKSPACE_QUERY_PARAM,
    extract_workspace_id,
    record_requested_workspace,
)
from .models import (
    CONTRACT_VERSION,
    Invite,
    Membership,
    Workspace,
    new_invite_id,
    new_invite_token,
    new_membership_id,
    new_workspace_id,
)
from .roles import MATRIX, Permission, Role, can, roles_with
from .store import WorkspacesStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "Invite",
    "MATRIX",
    "Membership",
    "PERSONAL_WORKSPACE_ID",
    "Permission",
    "Role",
    "WORKSPACE_HEADER",
    "WORKSPACE_QUERY_PARAM",
    "Workspace",
    "WorkspacesStore",
    "can",
    "extract_workspace_id",
    "get_store",
    "new_invite_id",
    "new_invite_token",
    "new_membership_id",
    "new_workspace_id",
    "record_requested_workspace",
    "reset_store",
    "roles_with",
]
