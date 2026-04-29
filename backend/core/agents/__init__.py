"""Phase M — multi-agent surface for TARS.

A *user* of TARS can spin up many *agents*. Each agent is a thin
configuration object: an identity, a domain-pack persona, an optional
system prompt override, and an inbox of tasks the operator (or another
agent) hands it. Tasks run through the existing council orchestrator
+ policy gate, so destructive work stays gated by the same guardrails
as direct domain-pack invocations.

Stdlib + `pynacl` only — no extra deps. Persistence lives in SQLite
next to the chat / pairing stores.
"""

from .models import Agent, AgentStatus, Task, TaskStatus
from .store import AgentStore, get_agent_store, reset_singleton_for_tests

__all__ = [
    "Agent",
    "AgentStatus",
    "AgentStore",
    "Task",
    "TaskStatus",
    "get_agent_store",
    "reset_singleton_for_tests",
]
