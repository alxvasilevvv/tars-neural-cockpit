"""W253 — voice-driven Composer for TARS.

Cursor's Composer lets the user describe multi-file edits in natural
language and review the proposed diff before applying. TARS adds the
voice surface as the primary input: the operator says "rename
Customer to Account across the project, add a migration for the
rename, update tests" and the planner returns a structured
``ComposerPlan`` with a list of file ops + cached unified diffs.

This package is intentionally framework-free:

- :mod:`composer.types` — dataclasses (``EditOp``, ``ComposerPlan``,
  ``ApplyResult``).
- :mod:`composer.planner` — turns a transcript into a plan by
  combining project structure, rules, and recently-changed files
  into a prompt for the active LLM. Falls back to a deterministic
  stub when no LLM key is configured (so unit tests and offline
  mode still work).
- :mod:`composer.executor` — atomic apply (staging dir → swap with
  per-file backups) and rollback. Emits one receipt per op via the
  W67 receipt-ledger.
- :mod:`composer.storage` — ``~/.tars/composer.sqlite`` persistence
  for plans + applied ops with state transitions.

Safety limits enforced in :mod:`composer.planner`:

- max 50 ops per plan
- max 5 MB total diff size
- forbidden paths: ``.env``, ``*.pem``, ``*.key``, ``.git/`` unless
  the transcript contains the explicit ``--allow-secrets`` token.
"""

from __future__ import annotations

from .types import EditOp, ComposerPlan, ApplyResult, SafetyError
from .planner import (
    plan_from_transcript,
    FORBIDDEN_PATTERNS,
    MAX_OPS,
    MAX_DIFF_BYTES,
)
from .executor import apply_plan, rollback
from .storage import ComposerStore, get_store, reset_store

__all__ = [
    "EditOp",
    "ComposerPlan",
    "ApplyResult",
    "SafetyError",
    "plan_from_transcript",
    "apply_plan",
    "rollback",
    "ComposerStore",
    "get_store",
    "reset_store",
    "FORBIDDEN_PATTERNS",
    "MAX_OPS",
    "MAX_DIFF_BYTES",
]
