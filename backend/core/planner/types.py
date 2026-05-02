"""Planner data classes.

Mirrors the playbook shape so a generated Plan can flow straight into
``PlaybookRunner`` once approved. The status enum is an additive field
that the runner (follow-up PR) drives forward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class PlanStatus(str, Enum):
    """Status transitions a Plan goes through during its lifetime.

    - ``proposed``  — synthesized but not yet acknowledged by the
      operator. Default status on insert.
    - ``approved``  — operator hit "run". The runner picks this up.
    - ``running``   — runner has started executing steps. Set by the
      runner only.
    - ``completed`` — every step finished successfully (or the
      runner reached its ``stop`` boundary cleanly).
    - ``aborted``   — operator cancelled OR a step failed with
      ``on_error=stop``.
    - ``rejected``  — operator rejected the plan before any step ran.
    """

    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    REJECTED = "rejected"

    @classmethod
    def terminal(cls) -> tuple["PlanStatus", ...]:
        """Statuses that cannot transition any further."""

        return (cls.COMPLETED, cls.ABORTED, cls.REJECTED)

    def is_terminal(self) -> bool:
        return self in self.terminal()


@dataclass(frozen=True)
class PlanStep:
    """One step in a plan.

    Mirrors :class:`backend.core.playbooks.PlaybookStep` 1:1 so the
    generated plan can be fed straight into ``PlaybookRunner``. Adds
    a ``rationale`` field so the cockpit can render *why* the planner
    proposed each step alongside the action call.
    """

    id: str
    action: str  # "<slug>.<action_id>" OR "<slug>.awareness.<src_id>.snapshot"
    args: Mapping[str, Any] = field(default_factory=dict)
    store_as: Optional[str] = None
    when: Optional[str] = None
    on_error: str = "stop"
    parallel: bool = False
    rationale: str = ""
    destructive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "args": dict(self.args),
            "store_as": self.store_as,
            "when": self.when,
            "on_error": self.on_error,
            "parallel": self.parallel,
            "rationale": self.rationale,
            "destructive": self.destructive,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PlanStep":
        return cls(
            id=str(raw.get("id") or ""),
            action=str(raw.get("action") or ""),
            args=dict(raw.get("args") or {}),
            store_as=(
                str(raw["store_as"]) if raw.get("store_as") is not None else None
            ),
            when=(str(raw["when"]) if raw.get("when") is not None else None),
            on_error=str(raw.get("on_error") or "stop"),
            parallel=bool(raw.get("parallel", False)),
            rationale=str(raw.get("rationale") or ""),
            destructive=bool(raw.get("destructive", False)),
        )


@dataclass(frozen=True)
class Plan:
    """A planner-synthesized multi-step plan.

    ``id`` is a stable ``pln_<token>`` string assigned by the store on
    insert. ``goal`` is the free-form operator request, ``model`` is
    the synthesizer label (``heuristic-v1`` for v1; cloud-LLM voices
    will land later). ``rationale`` is a short text block explaining
    the planner's overall approach.

    ``estimated_cost_usd`` is a forward-looking guess derived from the
    underlying actions' price hints (``None`` when unknown). The
    runner stamps the *actual* total on the meeet ``plan.completed``
    event in a follow-up PR.

    ``thread_id`` lets the cockpit's per-thread audit lane join plans
    to the chat that triggered them.

    ``trace_id`` carries the trace context that birthed the plan so
    every plan-related event downstream can be correlated.
    """

    id: str
    goal: str
    steps: tuple[PlanStep, ...]
    status: PlanStatus = PlanStatus.PROPOSED
    rationale: str = ""
    model: str = "heuristic-v1"
    pack_slug: Optional[str] = None
    playbook_id: Optional[str] = None
    thread_id: Optional[str] = None
    trace_id: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "rationale": self.rationale,
            "model": self.model,
            "pack_slug": self.pack_slug,
            "playbook_id": self.playbook_id,
            "thread_id": self.thread_id,
            "trace_id": self.trace_id,
            "estimated_cost_usd": self.estimated_cost_usd,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "steps": [s.to_dict() for s in self.steps],
            "step_count": len(self.steps),
            "destructive_step_count": sum(1 for s in self.steps if s.destructive),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Plan":
        steps_raw = raw.get("steps") or ()
        return cls(
            id=str(raw.get("id") or ""),
            goal=str(raw.get("goal") or ""),
            steps=tuple(PlanStep.from_dict(s) for s in steps_raw),
            status=PlanStatus(str(raw.get("status") or PlanStatus.PROPOSED.value)),
            rationale=str(raw.get("rationale") or ""),
            model=str(raw.get("model") or "heuristic-v1"),
            pack_slug=(
                str(raw["pack_slug"]) if raw.get("pack_slug") is not None else None
            ),
            playbook_id=(
                str(raw["playbook_id"])
                if raw.get("playbook_id") is not None
                else None
            ),
            thread_id=(
                str(raw["thread_id"]) if raw.get("thread_id") is not None else None
            ),
            trace_id=(
                str(raw["trace_id"]) if raw.get("trace_id") is not None else None
            ),
            estimated_cost_usd=(
                float(raw["estimated_cost_usd"])
                if raw.get("estimated_cost_usd") is not None
                else None
            ),
            created_at=float(raw.get("created_at") or 0.0),
            updated_at=float(raw.get("updated_at") or 0.0),
            error=(str(raw["error"]) if raw.get("error") is not None else None),
        )
