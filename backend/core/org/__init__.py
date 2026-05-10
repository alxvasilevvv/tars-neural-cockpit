"""TARS organization onboarding subsystem (Wave 99).

Persists the minimum state needed by ``/onboard/org`` — the wizard a
new fund / company runs once when they install TARS to seed their
org-level config:

- :mod:`.models` — :class:`Org` (name / type / size / timezone /
  primary use case) + :class:`Invite` (email + role + status).
- :mod:`.store` — SQLite-backed CRUD at ``~/.tars/org.sqlite``
  (override with ``TARS_ORG_DB_PATH``; disable with
  ``TARS_ORG_STORE=disabled``).

The wizard itself lives in
``experiments/neural-showcase-v3/src/pages/OrgOnboarding.tsx``; the
backend stores the answers so re-installs / multi-device pickups skip
the steps they already finished.

Multi-tenant workspaces ship in v9.3 — until then the invites table
just records intent. The router still surfaces them so the cockpit
can show "3 teammates queued for v9.3 workspaces" without lying about
what's already wired.

Contract version: 1.0.
"""

from __future__ import annotations

from .models import (
    CONTRACT_VERSION,
    INVITE_ROLES,
    INVITE_STATUSES,
    ORG_TYPES,
    Invite,
    Org,
    new_invite_id,
    new_org_id,
    normalize_role,
)
from .store import OrgStore, get_store, reset_store

__all__ = [
    "CONTRACT_VERSION",
    "INVITE_ROLES",
    "INVITE_STATUSES",
    "Invite",
    "Org",
    "ORG_TYPES",
    "OrgStore",
    "get_store",
    "new_invite_id",
    "new_org_id",
    "normalize_role",
    "reset_store",
]
