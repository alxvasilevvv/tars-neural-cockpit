"""Session metadata store.

A *session* groups every intent / order / fill / verdict for a
single (strategy_fingerprint, mode, started_at) tuple. The
cockpit and the audit exporter both key off ``session_id``.

Backed by a JSONL file so multi-process readers (FastAPI worker
+ background runner + CLI tail) all see the same view.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERRORED = "errored"
    COMPLETED = "completed"


@dataclass
class Session:
    session_id: str
    mode: str  # "paper" | "live"
    strategy_fingerprint: str
    instrument: str
    adapter: str
    sandbox_id: str | None = None
    started_at: float = field(default_factory=lambda: time.time())
    closed_at: float | None = None
    status: SessionStatus = SessionStatus.PENDING
    notes: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "strategy_fingerprint": self.strategy_fingerprint,
            "instrument": self.instrument,
            "adapter": self.adapter,
            "sandbox_id": self.sandbox_id,
            "started_at": float(self.started_at),
            "closed_at": (
                None if self.closed_at is None else float(self.closed_at)
            ),
            "status": self.status.value,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            session_id=str(data["session_id"]),
            mode=str(data.get("mode", "paper")),
            strategy_fingerprint=str(data.get("strategy_fingerprint", "")),
            instrument=str(data.get("instrument", "")),
            adapter=str(data.get("adapter", "")),
            sandbox_id=data.get("sandbox_id"),
            started_at=float(data.get("started_at", time.time())),
            closed_at=(
                None
                if data.get("closed_at") is None
                else float(data["closed_at"])
            ),
            status=SessionStatus(str(data.get("status", "pending"))),
            notes=str(data.get("notes", "")),
            metadata=dict(data.get("metadata", {})),
        )


class SessionStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                self._load(path)

    def create(
        self,
        *,
        mode: str,
        strategy_fingerprint: str,
        instrument: str,
        adapter: str,
        sandbox_id: str | None = None,
        notes: str = "",
        metadata: dict | None = None,
    ) -> Session:
        with self._lock:
            session = Session(
                session_id=f"sess_{uuid.uuid4().hex[:14]}",
                mode=mode,
                strategy_fingerprint=strategy_fingerprint,
                instrument=instrument,
                adapter=adapter,
                sandbox_id=sandbox_id,
                notes=notes,
                metadata=dict(metadata or {}),
                status=SessionStatus.PENDING,
            )
            self._sessions[session.session_id] = session
            self._persist()
            return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def all(self) -> list[Session]:
        return list(self._sessions.values())

    def filter(
        self,
        *,
        mode: str | None = None,
        sandbox_id: str | None = None,
        status: SessionStatus | None = None,
    ) -> list[Session]:
        out: list[Session] = []
        for s in self._sessions.values():
            if mode is not None and s.mode != mode:
                continue
            if sandbox_id is not None and s.sandbox_id != sandbox_id:
                continue
            if status is not None and s.status is not status:
                continue
            out.append(s)
        return out

    def update_status(
        self, session_id: str, status: SessionStatus, *, notes: str | None = None
    ) -> Session | None:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return None
            s.status = status
            if notes is not None:
                s.notes = notes
            if status in (
                SessionStatus.STOPPED,
                SessionStatus.ERRORED,
                SessionStatus.COMPLETED,
            ):
                s.closed_at = time.time()
            self._persist()
            return s

    # -------------------------------------------------------- io

    def _persist(self) -> None:
        if self._path is None:
            return
        lines = [
            json.dumps(s.to_dict(), ensure_ascii=False)
            for s in self._sessions.values()
        ]
        self._path.write_text("\n".join(lines) + ("\n" if lines else ""))

    def _load(self, path: Path) -> None:
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                s = Session.from_dict(data)
                self._sessions[s.session_id] = s
        except OSError:
            return

    def __iter__(self) -> Iterable[Session]:
        return iter(list(self._sessions.values()))

    def __len__(self) -> int:
        return len(self._sessions)
