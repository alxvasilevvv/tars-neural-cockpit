"""Composer dataclasses — :mod:`backend.core.composer.types`.

These are the wire shapes shared between the planner, executor,
storage layer, the HTTP router, and the frontend panel. They are
plain dataclasses (no Pydantic dependency) so that the module stays
import-cheap and the SQLite layer can serialise them directly to
JSON. The ``to_dict`` / ``from_dict`` helpers preserve None for
optional fields so a round-trip through SQLite is lossless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class SafetyError(RuntimeError):
    """Raised by the planner when an op violates the safety limits.

    The HTTP router maps this to a 400 with the ``reason`` payload so
    the cockpit can show a non-scary message ("refused: would touch
    .env"). Never surfaces as a 500.
    """

    def __init__(self, reason: str, *, op_index: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.op_index = op_index


# ---------------------------------------------------------------------------
# EditOp
# ---------------------------------------------------------------------------


_VALID_OPS = {"create", "modify", "delete", "rename"}


@dataclass
class EditOp:
    """A single file-level mutation in a composer plan.

    ``op`` is one of ``create`` / ``modify`` / ``delete`` / ``rename``.
    Semantics:

    - ``create``  — ``path`` must not exist; writes ``new_content``.
    - ``modify``  — ``path`` must exist; replaces with ``new_content``.
    - ``delete``  — ``path`` must exist; removes the file.
    - ``rename``  — ``path`` is the source, ``new_path`` is the target;
      ``new_content`` optional (if present, the file is re-written at
      the new path).

    ``old_content`` is captured at plan time so the unified diff can
    be rendered without re-reading the disk and so we have a stable
    snapshot for the receipt payload.

    ``diff_unified`` is the cached unified-diff string for the
    frontend. Computed by the planner; the executor never recomputes
    it.
    """

    op: str
    path: str
    new_path: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    diff_unified: str | None = None

    def __post_init__(self) -> None:
        if self.op not in _VALID_OPS:
            raise ValueError(
                f"unknown op {self.op!r} (expected one of {sorted(_VALID_OPS)})"
            )
        if self.op == "rename" and not self.new_path:
            raise ValueError("rename op requires new_path")
        if self.op in ("create", "modify") and self.new_content is None:
            # Treat missing content as empty string rather than
            # blowing up — the planner stub paths sometimes emit
            # placeholder ops.
            self.new_content = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "path": self.path,
            "new_path": self.new_path,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "diff_unified": self.diff_unified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditOp":
        return cls(
            op=str(data.get("op") or ""),
            path=str(data.get("path") or ""),
            new_path=data.get("new_path"),
            old_content=data.get("old_content"),
            new_content=data.get("new_content"),
            diff_unified=data.get("diff_unified"),
        )

    def size_bytes(self) -> int:
        """Conservative byte estimate of the op's contribution to the
        diff budget. Used by the planner to enforce ``MAX_DIFF_BYTES``.
        """

        n = 0
        for s in (self.old_content, self.new_content, self.diff_unified):
            if s:
                n += len(s.encode("utf-8", errors="replace"))
        return n


# ---------------------------------------------------------------------------
# ComposerPlan
# ---------------------------------------------------------------------------


_VALID_STATES = {"draft", "approved", "applied", "rejected", "rolled_back"}


@dataclass
class ComposerPlan:
    """A bundled multi-file edit awaiting operator approval."""

    plan_id: str
    transcript: str
    intent_summary: str
    ops: list[EditOp] = field(default_factory=list)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    state: str = "draft"
    project_root: str | None = None
    model: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.state not in _VALID_STATES:
            raise ValueError(
                f"unknown state {self.state!r} "
                f"(expected one of {sorted(_VALID_STATES)})"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "transcript": self.transcript,
            "intent_summary": self.intent_summary,
            "ops": [o.to_dict() for o in self.ops],
            "estimated_tokens": int(self.estimated_tokens),
            "estimated_cost_usd": float(self.estimated_cost_usd),
            "created_at": self.created_at.isoformat(),
            "state": self.state,
            "project_root": self.project_root,
            "model": self.model,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComposerPlan":
        raw_ts = data.get("created_at")
        if isinstance(raw_ts, str):
            try:
                created = datetime.fromisoformat(raw_ts)
            except ValueError:
                created = datetime.now(timezone.utc)
        elif isinstance(raw_ts, (int, float)):
            created = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
        else:
            created = datetime.now(timezone.utc)
        return cls(
            plan_id=str(data.get("plan_id") or ""),
            transcript=str(data.get("transcript") or ""),
            intent_summary=str(data.get("intent_summary") or ""),
            ops=[EditOp.from_dict(o) for o in (data.get("ops") or [])],
            estimated_tokens=int(data.get("estimated_tokens") or 0),
            estimated_cost_usd=float(data.get("estimated_cost_usd") or 0.0),
            created_at=created,
            state=str(data.get("state") or "draft"),
            project_root=data.get("project_root"),
            model=data.get("model"),
            error=data.get("error"),
        )


# ---------------------------------------------------------------------------
# ApplyResult
# ---------------------------------------------------------------------------


@dataclass
class ApplyResult:
    """Outcome of :func:`composer.executor.apply_plan`."""

    plan_id: str
    ok: bool
    applied_ops: list[int] = field(default_factory=list)
    failed_index: int | None = None
    error: str | None = None
    backup_dir: str | None = None
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "ok": bool(self.ok),
            "applied_ops": list(self.applied_ops),
            "failed_index": self.failed_index,
            "error": self.error,
            "backup_dir": self.backup_dir,
            "receipts": list(self.receipts),
        }
