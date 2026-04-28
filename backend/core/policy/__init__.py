"""TARS policy engine — modes and a destructive-action gate.

Three modes (env ``TARS_POLICY_MODE``, per-request header
``x-tars-policy-mode``):

- ``autopilot``  — actions run immediately. Use for trusted automation.
- ``confirm``    — destructive actions stage a confirmation token; the
                   operator hits ``POST /api/policy/confirm/{token}``
                   to execute. Default.
- ``dry_run``    — actions return a preview without executing. Useful
                   in testing and demos.

Read-only actions (``destructive=False`` on :class:`ActionSpec`) bypass
the gate entirely. Every gate decision emits ``policy.allowed`` or
``policy.blocked`` events through the meeet bridge.
"""

from .gate import (
    GateDecision,
    PolicyGate,
    PolicyMode,
    get_gate,
    resolve_mode,
)
from .store import PolicyStore, PendingConfirmation, get_policy_store, reset_policy_store

__all__ = [
    "GateDecision",
    "PendingConfirmation",
    "PolicyGate",
    "PolicyMode",
    "PolicyStore",
    "get_gate",
    "get_policy_store",
    "reset_policy_store",
    "resolve_mode",
]
