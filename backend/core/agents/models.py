"""Data classes for the multi-agent surface (Phase M)."""

from __future__ import annotations

import enum
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


def _now() -> float:
    return time.time()


def new_agent_id() -> str:
    return "agent_" + secrets.token_hex(8)


def new_task_id() -> str:
    return "task_" + secrets.token_hex(8)


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Agent:
    """A user-created agent.

    `pack_slug` selects the domain pack persona (system prompt + actions)
    the council orchestrator runs the agent inside. `system_prompt`
    overrides the pack's default when set.

    `wallet_address` (optional, lower-case hex) binds an EVM wallet to
    the agent so wallet domain actions can hard-pin the address rather
    than letting the model pick. The wallet itself lives in the
    secrets vault — the model only ever sees the address.
    """

    id: str
    name: str
    pack_slug: str
    description: str
    system_prompt: Optional[str] = None
    wallet_address: Optional[str] = None
    status: AgentStatus = AgentStatus.ACTIVE
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    metadata_json: str = "{}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pack_slug": self.pack_slug,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "wallet_address": self.wallet_address,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class Task:
    """A single task assigned to an agent."""

    id: str
    agent_id: str
    prompt: str
    status: TaskStatus = TaskStatus.PENDING
    result_json: Optional[str] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None
    policy_token: Optional[str] = None
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    completed_at: Optional[float] = None
    metadata_json: str = "{}"

    def to_dict(self) -> dict[str, Any]:
        import json

        result: Any = None
        if self.result_json:
            try:
                result = json.loads(self.result_json)
            except json.JSONDecodeError:
                result = self.result_json
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "prompt": self.prompt,
            "status": self.status.value,
            "result": result,
            "error": self.error,
            "trace_id": self.trace_id,
            "policy_token": self.policy_token,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


VALID_AGENT_TRANSITIONS: Mapping[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.ACTIVE: frozenset({AgentStatus.PAUSED, AgentStatus.ARCHIVED}),
    AgentStatus.PAUSED: frozenset({AgentStatus.ACTIVE, AgentStatus.ARCHIVED}),
    AgentStatus.ARCHIVED: frozenset(),
}

VALID_TASK_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset(
        {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED}
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.DONE,
            TaskStatus.FAILED,
            TaskStatus.AWAITING_CONFIRMATION,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.AWAITING_CONFIRMATION: frozenset(
        {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.DONE}
    ),
    TaskStatus.DONE: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.PENDING}),
    TaskStatus.CANCELLED: frozenset(),
}


def is_valid_agent_transition(src: AgentStatus, dst: AgentStatus) -> bool:
    return dst in VALID_AGENT_TRANSITIONS.get(src, frozenset())


def is_valid_task_transition(src: TaskStatus, dst: TaskStatus) -> bool:
    return dst in VALID_TASK_TRANSITIONS.get(src, frozenset())
