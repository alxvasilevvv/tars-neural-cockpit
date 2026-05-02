"""TARS planner — turns operator goals into structured multi-step plans.

A :class:`Plan` is a typed dataclass that mirrors the
:class:`backend.core.playbooks.Playbook` shape (steps with ids,
actions, args, ``store_as``, ``when`` clauses) so a plan can be fed
directly to :class:`backend.core.playbooks.PlaybookRunner` once
approved by the operator. Plans live in their own SQLite store
(``~/.tars/planner.sqlite``) so a partially-approved plan survives
process restarts and the cockpit can render an "approval inbox" of
pending plans alongside policy confirmations.

This v1 ships the **synthesis + persistence** legs:

- ``Plan`` / ``PlanStep`` / ``PlanStatus`` types.
- ``PlannerStore`` (SQLite) with CRUD + status transitions.
- ``Planner.synthesize(goal, *, available_playbooks, …)`` — a
  deterministic mapper from a free-form operator goal onto either an
  existing registered playbook or a single-action fallback. Cloud LLM
  planning is reserved for a follow-up PR.

The runner / event-emitting ``PlannerLoop`` lands in a follow-up PR.
"""

from .store import PlannerStore, get_planner_store, reset_planner_store
from .synthesizer import (
    PlannerError,
    PlannerSynthesisRequest,
    synthesize_plan,
)
from .types import Plan, PlanStatus, PlanStep

__all__ = [
    "Plan",
    "PlanStatus",
    "PlanStep",
    "PlannerError",
    "PlannerStore",
    "PlannerSynthesisRequest",
    "get_planner_store",
    "reset_planner_store",
    "synthesize_plan",
]
