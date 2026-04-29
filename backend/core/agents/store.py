"""SQLite-backed durable store for agents + tasks.

Same WAL + ``asyncio.to_thread`` discipline as
:mod:`backend.core.chat.store` and :mod:`backend.core.meeet.store`.

Disable with ``TARS_AGENTS_STORE=disabled``; override path with
``TARS_AGENTS_DB_PATH``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from typing import Any, Mapping

from .models import (
    Agent,
    AgentStatus,
    Task,
    TaskStatus,
    is_valid_agent_transition,
    is_valid_task_transition,
    new_agent_id,
    new_task_id,
)

DEFAULT_DB_PATH = "~/.tars/agents.sqlite"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pack_slug TEXT NOT NULL,
    description TEXT NOT NULL,
    system_prompt TEXT,
    wallet_address TEXT,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    trace_id TEXT,
    policy_token TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (agent_id) REFERENCES agents (id)
);

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents (status);
CREATE INDEX IF NOT EXISTS idx_agents_pack ON agents (pack_slug);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks (agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
"""


def _resolve_db_path(override: str | None = None) -> str:
    raw = override or os.getenv("TARS_AGENTS_DB_PATH") or DEFAULT_DB_PATH
    return os.path.expanduser(raw)


def _is_disabled() -> bool:
    flag = (os.getenv("TARS_AGENTS_STORE") or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class AgentStore:
    """Durable agent + task store."""

    def __init__(
        self,
        db_path: str | None = None,
        *,
        enabled: bool | None = None,
    ) -> None:
        self.db_path = (
            _resolve_db_path(db_path) if db_path is None else os.path.expanduser(db_path)
        )
        self.enabled = (not _is_disabled()) if enabled is None else enabled
        if self.enabled:
            self._ensure_schema()

    # -- helpers ----------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # -- agents ----------------------------------------------------------

    def _row_to_agent(self, row: sqlite3.Row) -> Agent:
        return Agent(
            id=row["id"],
            name=row["name"],
            pack_slug=row["pack_slug"],
            description=row["description"],
            system_prompt=row["system_prompt"],
            wallet_address=row["wallet_address"],
            status=AgentStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
        )

    def _create_agent_sync(
        self,
        *,
        name: str,
        pack_slug: str,
        description: str,
        system_prompt: str | None,
        wallet_address: str | None,
        metadata: Mapping[str, Any] | None,
    ) -> Agent:
        agent = Agent(
            id=new_agent_id(),
            name=name.strip(),
            pack_slug=pack_slug.strip(),
            description=description.strip(),
            system_prompt=system_prompt,
            wallet_address=wallet_address.lower() if wallet_address else None,
            metadata_json=json.dumps(dict(metadata or {})),
        )
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO agents (
                    id, name, pack_slug, description, system_prompt,
                    wallet_address, status, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent.id,
                    agent.name,
                    agent.pack_slug,
                    agent.description,
                    agent.system_prompt,
                    agent.wallet_address,
                    agent.status.value,
                    agent.created_at,
                    agent.updated_at,
                    agent.metadata_json,
                ),
            )
        finally:
            conn.close()
        return agent

    async def create_agent(
        self,
        *,
        name: str,
        pack_slug: str,
        description: str = "",
        system_prompt: str | None = None,
        wallet_address: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Agent:
        if not name.strip():
            raise ValueError("agent name must be non-empty")
        if not pack_slug.strip():
            raise ValueError("pack_slug must be non-empty")
        return await asyncio.to_thread(
            self._create_agent_sync,
            name=name,
            pack_slug=pack_slug,
            description=description,
            system_prompt=system_prompt,
            wallet_address=wallet_address,
            metadata=metadata,
        )

    def _list_agents_sync(self, *, include_archived: bool) -> list[Agent]:
        conn = self._connect()
        try:
            if include_archived:
                rows = conn.execute(
                    "SELECT * FROM agents ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agents WHERE status != ? ORDER BY created_at DESC",
                    (AgentStatus.ARCHIVED.value,),
                ).fetchall()
            return [self._row_to_agent(r) for r in rows]
        finally:
            conn.close()

    async def list_agents(self, *, include_archived: bool = False) -> list[Agent]:
        return await asyncio.to_thread(
            self._list_agents_sync, include_archived=include_archived
        )

    def _get_agent_sync(self, agent_id: str) -> Agent | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()
            return self._row_to_agent(row) if row else None
        finally:
            conn.close()

    async def get_agent(self, agent_id: str) -> Agent | None:
        return await asyncio.to_thread(self._get_agent_sync, agent_id)

    def _patch_agent_sync(
        self, agent_id: str, updates: Mapping[str, Any]
    ) -> Agent | None:
        existing = self._get_agent_sync(agent_id)
        if existing is None:
            return None
        cols: list[str] = []
        params: list[Any] = []
        new_status = existing.status
        for k, v in updates.items():
            if k == "status":
                try:
                    candidate = AgentStatus(v) if isinstance(v, str) else v
                except ValueError as e:
                    raise ValueError(f"invalid status: {v}") from e
                if candidate != existing.status and not is_valid_agent_transition(
                    existing.status, candidate
                ):
                    raise ValueError(
                        f"invalid agent status transition: {existing.status.value} → {candidate.value}"
                    )
                cols.append("status=?")
                params.append(candidate.value)
                new_status = candidate
            elif k == "wallet_address":
                cols.append("wallet_address=?")
                params.append(v.lower() if isinstance(v, str) else v)
            elif k in {"name", "description", "system_prompt"}:
                cols.append(f"{k}=?")
                params.append(v)
            elif k == "metadata":
                cols.append("metadata_json=?")
                params.append(json.dumps(dict(v or {})))
        if not cols:
            return existing
        import time as _t

        cols.append("updated_at=?")
        params.append(_t.time())
        params.append(agent_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE agents SET {', '.join(cols)} WHERE id = ?",
                params,
            )
        finally:
            conn.close()
        return self._get_agent_sync(agent_id)

    async def patch_agent(
        self, agent_id: str, updates: Mapping[str, Any]
    ) -> Agent | None:
        return await asyncio.to_thread(self._patch_agent_sync, agent_id, dict(updates))

    # -- tasks -----------------------------------------------------------

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            agent_id=row["agent_id"],
            prompt=row["prompt"],
            status=TaskStatus(row["status"]),
            result_json=row["result_json"],
            error=row["error"],
            trace_id=row["trace_id"],
            policy_token=row["policy_token"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            metadata_json=row["metadata_json"],
        )

    def _create_task_sync(
        self,
        *,
        agent_id: str,
        prompt: str,
        metadata: Mapping[str, Any] | None,
    ) -> Task:
        if self._get_agent_sync(agent_id) is None:
            raise LookupError(f"agent_not_found: {agent_id}")
        task = Task(
            id=new_task_id(),
            agent_id=agent_id,
            prompt=prompt.strip(),
            metadata_json=json.dumps(dict(metadata or {})),
        )
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, agent_id, prompt, status, result_json, error,
                    trace_id, policy_token, created_at, updated_at,
                    completed_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.agent_id,
                    task.prompt,
                    task.status.value,
                    task.result_json,
                    task.error,
                    task.trace_id,
                    task.policy_token,
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                    task.metadata_json,
                ),
            )
        finally:
            conn.close()
        return task

    async def create_task(
        self,
        *,
        agent_id: str,
        prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> Task:
        if not prompt.strip():
            raise ValueError("task prompt must be non-empty")
        return await asyncio.to_thread(
            self._create_task_sync,
            agent_id=agent_id,
            prompt=prompt,
            metadata=metadata,
        )

    def _list_tasks_sync(
        self,
        *,
        agent_id: str | None,
        status: TaskStatus | None,
        limit: int,
    ) -> list[Task]:
        conn = self._connect()
        try:
            sql = "SELECT * FROM tasks"
            params: list[Any] = []
            wheres: list[str] = []
            if agent_id is not None:
                wheres.append("agent_id = ?")
                params.append(agent_id)
            if status is not None:
                wheres.append("status = ?")
                params.append(status.value)
            if wheres:
                sql += " WHERE " + " AND ".join(wheres)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_task(r) for r in rows]
        finally:
            conn.close()

    async def list_tasks(
        self,
        *,
        agent_id: str | None = None,
        status: TaskStatus | None = None,
        limit: int = 100,
    ) -> list[Task]:
        return await asyncio.to_thread(
            self._list_tasks_sync,
            agent_id=agent_id,
            status=status,
            limit=limit,
        )

    def _get_task_sync(self, task_id: str) -> Task | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return self._row_to_task(row) if row else None
        finally:
            conn.close()

    async def get_task(self, task_id: str) -> Task | None:
        return await asyncio.to_thread(self._get_task_sync, task_id)

    def _patch_task_sync(
        self, task_id: str, updates: Mapping[str, Any]
    ) -> Task | None:
        existing = self._get_task_sync(task_id)
        if existing is None:
            return None
        cols: list[str] = []
        params: list[Any] = []
        new_status = existing.status
        for k, v in updates.items():
            if k == "status":
                try:
                    candidate = TaskStatus(v) if isinstance(v, str) else v
                except ValueError as e:
                    raise ValueError(f"invalid status: {v}") from e
                if candidate != existing.status and not is_valid_task_transition(
                    existing.status, candidate
                ):
                    raise ValueError(
                        f"invalid task status transition: {existing.status.value} → {candidate.value}"
                    )
                cols.append("status=?")
                params.append(candidate.value)
                new_status = candidate
                if candidate in {
                    TaskStatus.DONE,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                }:
                    cols.append("completed_at=?")
                    import time as _t

                    params.append(_t.time())
            elif k == "result":
                cols.append("result_json=?")
                params.append(json.dumps(v))
            elif k in {"error", "trace_id", "policy_token"}:
                cols.append(f"{k}=?")
                params.append(v)
            elif k == "metadata":
                cols.append("metadata_json=?")
                params.append(json.dumps(dict(v or {})))
        if not cols:
            return existing
        import time as _t

        cols.append("updated_at=?")
        params.append(_t.time())
        params.append(task_id)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE tasks SET {', '.join(cols)} WHERE id = ?",
                params,
            )
        finally:
            conn.close()
        return self._get_task_sync(task_id)

    async def patch_task(
        self, task_id: str, updates: Mapping[str, Any]
    ) -> Task | None:
        return await asyncio.to_thread(self._patch_task_sync, task_id, dict(updates))


_SINGLETON: AgentStore | None = None


def get_agent_store() -> AgentStore:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = AgentStore()
    return _SINGLETON


def reset_singleton_for_tests() -> None:
    global _SINGLETON
    _SINGLETON = None
