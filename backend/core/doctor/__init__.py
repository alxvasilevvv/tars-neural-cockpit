"""``tars-doctor`` — unified health check across every TARS subsystem.

After Waves 150 (MCP), 151 (Clone v0.2), 152 (Background daemon
macOS), and 153 (daemon Linux parity), the operator has a lot of
moving parts. A single ``tars-doctor`` invocation surfaces the
health of:

  - Background daemon heartbeat + service status
  - MCP server tool registry (tool count + version)
  - AI Clone store + sync interval
  - Scheduler store + enabled flag
  - Webhooks store + dispatcher queue
  - Cowork sessions store
  - Receipts ledger store
  - Vault directory + key presence

The contract is intentionally simple:

  - Each check returns ``CheckResult`` with ``status`` ∈
    ``ok | warn | fail | skip``.
  - The doctor never tries to *fix* — it diagnoses, then prints a
    one-line suggestion when something is off (e.g. "run
    ``tars-daemon install``" when no heartbeat is found).
  - Network is never touched; checks are local-only. The web app
    has its own ``/health`` endpoint for the live cockpit badge.

The CLI:

  python -m backend.core.doctor          # human-readable table
  python -m backend.core.doctor --json   # machine-readable JSON
  python -m backend.core.doctor --quiet  # only print problems
"""

from __future__ import annotations

from .checks import (
    CheckResult,
    CheckStatus,
    REGISTRY,
    run_check,
    run_all,
)


__all__ = [
    "CheckResult",
    "CheckStatus",
    "REGISTRY",
    "run_check",
    "run_all",
]
