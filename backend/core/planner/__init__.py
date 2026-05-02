"""TARS planner — turns operator goals into structured multi-step plans.

A :class:`Plan` is a typed dataclass that mirrors the
:class:`backend.core.playbooks.Playbook` shape (steps with ids,
actions, args, ``store_as``, ``when`` clauses) so a plan can be fed
directly to :class:`backend.core.playbooks.PlaybookRunner` once
approved by the operator. Plans live in their own SQLite store
(``~/.tars/planner.sqlite``) so a partially-approved plan survives
process restarts and the cockpit can render an "approval inbox" of
pending plans alongside policy confirmations.

This module ships:

- ``Plan`` / ``PlanStep`` / ``PlanStatus`` types.
- ``PlannerStore`` (SQLite) with CRUD + status transitions.
- ``synthesize_plan(...)`` — deterministic mapper from a free-form
  operator goal onto either an existing registered playbook or a
  single-action fallback. Cloud LLM planning is reserved for a
  follow-up PR.
- ``PlanRunner`` / ``run_plan`` — drives an approved Plan through
  the policy gate and emits ``plan.run.started`` /
  ``plan.step.{requested,allowed,completed}`` / ``plan.completed``
  / ``plan.aborted`` events keyed by ``plan_id``.
- ``PlanRunRegistry`` — tracks in-flight runs so the HTTP layer
  can request a cooperative abort.
"""

from .history import (
    PlanRun,
    RunStep,
    reconstruct_runs,
    reconstruct_runs_async,
)
from .runner import (
    PlanRunError,
    PlanRunner,
    PlanRunRegistry,
    get_run_registry,
    reset_run_registry,
    run_plan,
)
from .store import PlannerStore, get_planner_store, reset_planner_store
from .synthesizer import (
    PlannerError,
    PlannerSynthesisRequest,
    synthesize_plan,
)
from .types import Plan, PlanStatus, PlanStep

__all__ = [
    "Plan",
    "PlanRun",
    "PlanRunError",
    "PlanRunRegistry",
    "PlanRunner",
    "PlanStatus",
    "PlanStep",
    "PlannerError",
    "PlannerStore",
    "PlannerSynthesisRequest",
    "RunStep",
    "get_planner_store",
    "get_run_registry",
    "reconstruct_runs",
    "reconstruct_runs_async",
    "reset_planner_store",
    "reset_run_registry",
    "run_plan",
    "synthesize_plan",
]
