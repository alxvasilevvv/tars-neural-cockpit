"""On-prem deployment package — W263.

Drop-in replacements for the meeet.world-coupled paths when TARS runs
in self-hosted mode for enterprise / fund / air-gapped deployments.

Modules:
    local_auth         — replaces backend/core/meeet auth handshake.
                          Local JWT + optional SAML/OIDC bridge.
    pg_migrations      — Postgres schema parity with the ~21 SQLite
                          stores; Alembic migrations run on boot.
    meeet_mock_server  — optional in-cluster stand-in for the brother's
                          cloud endpoints; only used when
                          ONPREM_MOCK_MEEET=1 or compose --profile mock-meeet.

Activation:
    The runtime check is `os.getenv("MEEET_MODE") == "onprem"`. When that
    is the case, the auth_meeet router (and metering / billing siblings)
    consult these modules instead of dialling out to meeet.world.

See docs/ONPREM_DEPLOYMENT_GUIDE.md for the operator-facing playbook.
"""

from __future__ import annotations

import os

__all__ = ["is_onprem", "ONPREM_MODE_VALUE"]

ONPREM_MODE_VALUE = "onprem"


def is_onprem() -> bool:
    """True when MEEET_MODE=onprem (case-insensitive)."""
    return (os.environ.get("MEEET_MODE", "") or "").strip().lower() == ONPREM_MODE_VALUE
