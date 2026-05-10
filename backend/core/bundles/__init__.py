"""TARS vertical bundle generator (Wave 107).

A *bundle* is a one-click "ready to demo" pack for a specific
org-type vertical. Installing a bundle wires together everything
that vertical needs to look and feel finished out of the box:

- a curated set of playbooks (from the W80/W81 workshop pack and
  the W106 marketplace);
- scheduled jobs for the playbooks that should run on a cadence
  (via the Wave 97 scheduler);
- a default dashboard layout (Wave 96 widgets);
- a list of report templates to enable (Wave 103);
- starter outreach templates (Wave 98);
- connector hints (gmail / slack / github / calendar) so the
  onboarding wizard nudges the operator to authorise the right
  ones first;
- welcome-content markdown shown immediately after install;
- an optional ``first_run_playbook`` queued to fire right after
  install so the operator sees output within ~30 seconds.

The bundle definitions are pure data (see :mod:`.definitions`) so
they're trivially auditable and unit-testable. The installer is
idempotent -- re-installing the same bundle re-uses existing
schedules / templates / receipts and is a no-op for already-present
items. Uninstall walks the install report and removes the bits
that were created by *this* bundle install (it doesn't blow away
hand-edited schedules).

Public surface:

- :mod:`.models`       -- :class:`Bundle`, :class:`InstallReport`
  dataclasses + ID helpers + valid org-type vocab.
- :mod:`.definitions`  -- seven built-in bundles + lookup helpers.
- :mod:`.installer`    -- async ``install_bundle`` /
  ``uninstall_bundle`` / ``list_installed`` / ``installed_for_org``.
- :mod:`.previewer`    -- dry-run ``preview_bundle`` returning the
  same shape as a real install report so the FE confirm dialog
  can render the diff before the operator commits.

Contract version: 1.0 (see ``docs/contracts/BUNDLES.md``).
"""

from __future__ import annotations

from .definitions import (
    BUILTIN_BUNDLES,
    bundle_by_id,
    bundle_for_org_type,
    list_bundles,
)
from .models import (
    CONTRACT_VERSION,
    ORG_TYPES,
    Bundle,
    InstallReport,
    new_install_id,
)

__all__ = [
    "BUILTIN_BUNDLES",
    "Bundle",
    "CONTRACT_VERSION",
    "InstallReport",
    "ORG_TYPES",
    "bundle_by_id",
    "bundle_for_org_type",
    "list_bundles",
    "new_install_id",
]
