"""Workshop lab — roster + leaderboard.

Three concerns, all stdlib:

1. **Workshop / Attendee dataclasses** + a file-backed
   :class:`LabStore` keyed at
   ``$TARS_HOME/algotrade/lab/<workshop_id>/roster.json``.
2. **`sandbox_id` minting** for new attendees so every
   downstream call (`start_paper_session`, `start_live_session`,
   `submit_intent`, …) carries the same scope tag.
3. **Leaderboard computation** that fans across every session
   in the workshop, replays each session's audit log via the
   W3-PR1 :func:`compute_session_metrics`, and ranks attendees
   by net realised PnL with deterministic tie-breakers.

The leaderboard is **always recomputed** from disk — no cached
totals — so a facilitator who pauses the workshop, restarts the
process, and re-opens the lab UI sees a stable ranking that
matches the audit log byte-for-byte. The same property makes
the leaderboard reproducible for post-workshop replay /
council-style debriefs.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from backend.core.algotrade.exec.analytics import compute_session_metrics
from backend.core.algotrade.exec.router import AuditLog
from backend.core.algotrade.exec.runtime import get_runtime
from backend.core.algotrade.exec.sessions import Session, SessionStatus


# ---------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------


def _root() -> Path:
    raw = (
        os.environ.get("TARS_ALGOTRADE_HOME")
        or os.environ.get("TARS_HOME")
        or str(Path.home() / ".tars")
    )
    root = Path(raw).expanduser() / "algotrade" / "lab"
    root.mkdir(parents=True, exist_ok=True)
    return root


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s or "x"


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------


class WorkshopStatus(str, Enum):
    OPEN = "open"  # accepting new attendees + sessions
    PAUSED = "paused"  # frozen for handout review
    CLOSED = "closed"  # archived; leaderboard read-only


@dataclass
class Attendee:
    attendee_id: str
    display_name: str
    sandbox_id: str
    workshop_id: str
    joined_at: float = field(default_factory=lambda: time.time())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attendee_id": self.attendee_id,
            "display_name": self.display_name,
            "sandbox_id": self.sandbox_id,
            "workshop_id": self.workshop_id,
            "joined_at": float(self.joined_at),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Attendee":
        return cls(
            attendee_id=str(raw["attendee_id"]),
            display_name=str(raw.get("display_name") or raw["attendee_id"]),
            sandbox_id=str(raw["sandbox_id"]),
            workshop_id=str(raw["workshop_id"]),
            joined_at=float(raw.get("joined_at") or time.time()),
            metadata=dict(raw.get("metadata") or {}),
        )


@dataclass
class Workshop:
    workshop_id: str
    name: str
    facilitator: str = ""
    started_at: float = field(default_factory=lambda: time.time())
    closed_at: float | None = None
    status: WorkshopStatus = WorkshopStatus.OPEN
    notes: str = ""
    attendee_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workshop_id": self.workshop_id,
            "name": self.name,
            "facilitator": self.facilitator,
            "started_at": float(self.started_at),
            "closed_at": (
                None if self.closed_at is None else float(self.closed_at)
            ),
            "status": self.status.value,
            "notes": self.notes,
            "attendee_ids": list(self.attendee_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Workshop":
        return cls(
            workshop_id=str(raw["workshop_id"]),
            name=str(raw.get("name") or raw["workshop_id"]),
            facilitator=str(raw.get("facilitator") or ""),
            started_at=float(raw.get("started_at") or time.time()),
            closed_at=(
                None
                if raw.get("closed_at") is None
                else float(raw["closed_at"])
            ),
            status=WorkshopStatus(str(raw.get("status") or "open")),
            notes=str(raw.get("notes") or ""),
            attendee_ids=[str(a) for a in (raw.get("attendee_ids") or [])],
            metadata=dict(raw.get("metadata") or {}),
        )


# ---------------------------------------------------------------------
# Roster store
# ---------------------------------------------------------------------


class LabStore:
    """One JSON document per workshop. Cheap, transparent,
    auditable — a facilitator can ``cat`` the file mid-workshop
    to check who's in the lab."""

    def __init__(self, root: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._root = root or _root()
        self._workshops: dict[str, Workshop] = {}
        self._attendees: dict[str, Attendee] = {}
        self._load_all()

    # ------------------------------------------------- workshops

    def create_workshop(
        self,
        *,
        name: str,
        facilitator: str = "",
        notes: str = "",
        metadata: Mapping[str, Any] | None = None,
        workshop_id: str | None = None,
    ) -> Workshop:
        with self._lock:
            wid = workshop_id or self._mint_workshop_id(name)
            if wid in self._workshops:
                raise ValueError(f"workshop already exists: {wid}")
            ws = Workshop(
                workshop_id=wid,
                name=name,
                facilitator=facilitator,
                notes=notes,
                metadata=dict(metadata or {}),
            )
            self._workshops[wid] = ws
            self._persist(wid)
            return ws

    def list_workshops(
        self, *, status: WorkshopStatus | None = None
    ) -> list[Workshop]:
        with self._lock:
            out = list(self._workshops.values())
        if status is not None:
            out = [w for w in out if w.status is status]
        return sorted(out, key=lambda w: w.started_at, reverse=True)

    def get_workshop(self, workshop_id: str) -> Workshop | None:
        return self._workshops.get(workshop_id)

    def set_workshop_status(
        self, workshop_id: str, status: WorkshopStatus
    ) -> Workshop | None:
        with self._lock:
            ws = self._workshops.get(workshop_id)
            if ws is None:
                return None
            ws.status = status
            if status is WorkshopStatus.CLOSED:
                ws.closed_at = time.time()
            self._persist(workshop_id)
            return ws

    # ------------------------------------------------- attendees

    def enroll(
        self,
        *,
        workshop_id: str,
        display_name: str,
        attendee_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Attendee:
        with self._lock:
            ws = self._workshops.get(workshop_id)
            if ws is None:
                raise KeyError(f"workshop not found: {workshop_id}")
            if ws.status is WorkshopStatus.CLOSED:
                raise PermissionError(
                    f"workshop is closed: {workshop_id} — "
                    "re-open it before enrolling new attendees"
                )

            aid = attendee_id or self._mint_attendee_id(workshop_id, display_name)
            if aid in self._attendees:
                raise ValueError(f"attendee already exists: {aid}")
            sandbox_id = f"lab:{workshop_id}:{aid}"
            attendee = Attendee(
                attendee_id=aid,
                display_name=display_name,
                sandbox_id=sandbox_id,
                workshop_id=workshop_id,
                metadata=dict(metadata or {}),
            )
            self._attendees[aid] = attendee
            ws.attendee_ids.append(aid)
            self._persist(workshop_id)
            return attendee

    def get_attendee(self, attendee_id: str) -> Attendee | None:
        return self._attendees.get(attendee_id)

    def list_attendees(self, workshop_id: str) -> list[Attendee]:
        return [
            self._attendees[a]
            for a in self._workshops[workshop_id].attendee_ids
            if a in self._attendees
        ] if workshop_id in self._workshops else []

    # ------------------------------------------------- io

    def _workshop_path(self, workshop_id: str) -> Path:
        path = self._root / workshop_id
        path.mkdir(parents=True, exist_ok=True)
        return path / "roster.json"

    def _persist(self, workshop_id: str) -> None:
        ws = self._workshops.get(workshop_id)
        if ws is None:
            return
        attendees = [
            self._attendees[a].to_dict()
            for a in ws.attendee_ids
            if a in self._attendees
        ]
        payload = {
            "workshop": ws.to_dict(),
            "attendees": attendees,
        }
        self._workshop_path(workshop_id).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False)
        )

    def _load_all(self) -> None:
        if not self._root.exists():
            return
        for workshop_dir in sorted(self._root.iterdir()):
            roster = workshop_dir / "roster.json"
            if not roster.exists():
                continue
            try:
                payload = json.loads(roster.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            ws = Workshop.from_dict(payload.get("workshop") or {})
            self._workshops[ws.workshop_id] = ws
            for raw in payload.get("attendees") or []:
                att = Attendee.from_dict(raw)
                self._attendees[att.attendee_id] = att

    # ------------------------------------------------- minting

    def _mint_workshop_id(self, name: str) -> str:
        slug = _slugify(name)[:20]
        ts = int(time.time())
        return f"ws_{slug}_{ts}_{uuid.uuid4().hex[:6]}"

    def _mint_attendee_id(self, workshop_id: str, display_name: str) -> str:
        slug = _slugify(display_name)[:20]
        return f"att_{slug}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class LeaderboardEntry:
    rank: int
    attendee_id: str
    display_name: str
    sandbox_id: str
    sessions_total: int
    sessions_running: int
    realized_pnl: float
    unrealized_pnl: float
    fees_total: float
    slippage_cost: float
    intents_total: int
    intents_accepted: int
    fills_total: int
    score: float
    """``realized_pnl - fees_total - slippage_cost`` — the net
    edge after costs. Same units as the underlying instrument
    quote currency."""
    acceptance_rate: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in (
            "realized_pnl",
            "unrealized_pnl",
            "fees_total",
            "slippage_cost",
            "score",
            "acceptance_rate",
        ):
            d[key] = float(d[key])
        return d


@dataclass(frozen=True)
class Leaderboard:
    workshop_id: str
    workshop_name: str
    workshop_status: str
    computed_at: float
    entries: tuple[LeaderboardEntry, ...]
    attendees_total: int
    attendees_with_sessions: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "workshop_id": self.workshop_id,
            "workshop_name": self.workshop_name,
            "workshop_status": self.workshop_status,
            "computed_at": float(self.computed_at),
            "attendees_total": int(self.attendees_total),
            "attendees_with_sessions": int(self.attendees_with_sessions),
            "entries": [e.to_dict() for e in self.entries],
        }


def _audit_path_for(session_id: str) -> Path:
    return get_runtime().root / "audit" / f"{session_id}.jsonl"


def _aggregate_attendee_metrics(
    attendee: Attendee, sessions: Iterable[Session]
) -> tuple[dict[str, float], int, int, int]:
    """Sum the W3-PR1 SessionMetrics across all of the
    attendee's sessions. Returns a totals dict + counters."""

    totals = {
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "fees_total": 0.0,
        "slippage_cost": 0.0,
    }
    intents_total = 0
    intents_accepted = 0
    fills_total = 0

    for session in sessions:
        path = _audit_path_for(session.session_id)
        if not path.exists():
            continue
        events = AuditLog(path).read_all()
        if not events:
            continue
        metrics = compute_session_metrics(events)
        totals["realized_pnl"] += float(metrics.realized_pnl)
        totals["unrealized_pnl"] += float(metrics.unrealized_pnl)
        totals["fees_total"] += float(metrics.fees_total)
        totals["slippage_cost"] += float(metrics.total_slippage_cost)
        intents_total += int(metrics.intents_total)
        intents_accepted += int(metrics.intents_accepted)
        fills_total += int(metrics.fills_total)

    return totals, intents_total, intents_accepted, fills_total


def compute_leaderboard(
    workshop_id: str,
    *,
    store: LabStore | None = None,
) -> Leaderboard:
    """Replay every session that belongs to every attendee in
    ``workshop_id`` and rank by net edge after costs.

    Tie-breakers (in order):
      1. Higher acceptance rate
         (well-formed intents > spam-rejected intents).
      2. More fills (more activity = more learning).
      3. Earlier ``Attendee.joined_at`` (stable, deterministic).
    """

    store = store or get_lab_store()
    workshop = store.get_workshop(workshop_id)
    if workshop is None:
        raise KeyError(f"workshop not found: {workshop_id}")

    attendees = store.list_attendees(workshop_id)
    runtime = get_runtime()

    raw_entries: list[tuple[Attendee, dict[str, float], int, int, int, int, int]] = []
    attendees_with_sessions = 0
    for attendee in attendees:
        sessions = runtime.list_sessions(sandbox_id=attendee.sandbox_id)
        running = sum(
            1
            for s in sessions
            if s.status is SessionStatus.RUNNING
        )
        if sessions:
            attendees_with_sessions += 1
        totals, intents_total, intents_accepted, fills_total = (
            _aggregate_attendee_metrics(attendee, sessions)
        )
        raw_entries.append(
            (
                attendee,
                totals,
                intents_total,
                intents_accepted,
                fills_total,
                len(sessions),
                running,
            )
        )

    def _score(totals: dict[str, float]) -> float:
        return (
            totals["realized_pnl"]
            - totals["fees_total"]
            - totals["slippage_cost"]
        )

    def _key(item):
        attendee, totals, it, ia, fills, _n, _r = item
        accept_rate = (ia / it) if it > 0 else 0.0
        # Sort DESCENDING by score, then accept_rate, then fills,
        # then ASCENDING by joined_at (earlier = better).
        return (
            -_score(totals),
            -accept_rate,
            -fills,
            attendee.joined_at,
        )

    raw_entries.sort(key=_key)

    entries: list[LeaderboardEntry] = []
    for rank, item in enumerate(raw_entries, start=1):
        attendee, totals, it, ia, fills, n_sessions, n_running = item
        score = _score(totals)
        accept_rate = (ia / it) if it > 0 else 0.0
        entries.append(
            LeaderboardEntry(
                rank=rank,
                attendee_id=attendee.attendee_id,
                display_name=attendee.display_name,
                sandbox_id=attendee.sandbox_id,
                sessions_total=n_sessions,
                sessions_running=n_running,
                realized_pnl=totals["realized_pnl"],
                unrealized_pnl=totals["unrealized_pnl"],
                fees_total=totals["fees_total"],
                slippage_cost=totals["slippage_cost"],
                intents_total=it,
                intents_accepted=ia,
                fills_total=fills,
                score=score,
                acceptance_rate=accept_rate,
            )
        )

    return Leaderboard(
        workshop_id=workshop.workshop_id,
        workshop_name=workshop.name,
        workshop_status=workshop.status.value,
        computed_at=time.time(),
        entries=tuple(entries),
        attendees_total=len(attendees),
        attendees_with_sessions=attendees_with_sessions,
    )


# ---------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------


_STORE_LOCK = threading.Lock()
_STORE: LabStore | None = None


def get_lab_store() -> LabStore:
    global _STORE
    if _STORE is not None:
        return _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = LabStore()
        return _STORE


def reset_lab_store() -> None:
    """Test-only — wipe the in-memory cache."""

    global _STORE
    with _STORE_LOCK:
        _STORE = None
