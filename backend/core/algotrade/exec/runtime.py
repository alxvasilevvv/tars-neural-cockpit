"""Process-scoped runtime for paper / live execution.

Glues the dataclass-only :mod:`base` types to a single shared
state machine so HTTP, CLI, and council can address the same
session by id.

Backed entirely by the filesystem so a worker restart can pick up
where it left off:

- ``$TARS_HOME/algotrade/sessions.jsonl`` — :class:`SessionStore`
- ``$TARS_HOME/algotrade/positions/<session_id>.json`` — per-session book
- ``$TARS_HOME/algotrade/audit/<session_id>.jsonl`` — per-session ledger
- ``$TARS_HOME/algotrade/policies/<session_id>.json`` — risk policy

Live (Binance) adapters are added in W2-PR2; the runtime wires
``adapter="paper"`` today and treats anything else as not-yet-
implemented (returns a structured error).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .base import OrderIntent, Side, OrderType
from .paper import PaperAdapter, PaperConfig
from .positions import PositionStore
from .risk import RiskGate, RiskPolicy
from .router import AuditLog, OrderRouter
from .sessions import Session, SessionStatus, SessionStore


def _root() -> Path:
    raw = (
        os.environ.get("TARS_ALGOTRADE_HOME")
        or os.environ.get("TARS_HOME")
        or str(Path.home() / ".tars")
    )
    root = Path(raw).expanduser() / "algotrade"
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass
class _Wiring:
    session: Session
    adapter: PaperAdapter
    router: OrderRouter
    audit: AuditLog
    positions: PositionStore
    gate: RiskGate
    policy_path: Path


class ExecRuntime:
    """Singleton (per process) that owns the session graph."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions = SessionStore(_root() / "sessions.jsonl")
        self._wirings: dict[str, _Wiring] = {}

    # ------------------------------------------------- introspection

    @property
    def root(self) -> Path:
        return _root()

    def session_store(self) -> SessionStore:
        return self._sessions

    def get(self, session_id: str) -> _Wiring | None:
        with self._lock:
            wiring = self._wirings.get(session_id)
            if wiring is not None:
                return wiring
            session = self._sessions.get(session_id)
            if session is None:
                return None
            wiring = self._rehydrate(session)
            self._wirings[session_id] = wiring
            return wiring

    def list_sessions(self, **filters: Any) -> list[Session]:
        return self._sessions.filter(**filters)

    # ------------------------------------------------- lifecycle

    def start_paper_session(
        self,
        *,
        strategy_fingerprint: str,
        instrument: str,
        sandbox_id: str | None = None,
        notes: str = "",
        metadata: Mapping[str, Any] | None = None,
        config: Mapping[str, Any] | None = None,
        policy: Mapping[str, Any] | None = None,
    ) -> _Wiring:
        with self._lock:
            session = self._sessions.create(
                mode="paper",
                strategy_fingerprint=str(strategy_fingerprint),
                instrument=str(instrument),
                adapter="paper",
                sandbox_id=sandbox_id,
                notes=notes,
                metadata=dict(metadata or {}),
            )
            wiring = self._wire_paper(session, config or {}, policy)
            self._sessions.update_status(session.session_id, SessionStatus.RUNNING)
            wiring.session.status = SessionStatus.RUNNING
            self._wirings[session.session_id] = wiring
            return wiring

    def stop_session(self, session_id: str, *, reason: str = "stopped by operator") -> Session | None:
        with self._lock:
            session = self._sessions.update_status(
                session_id, SessionStatus.STOPPED, notes=reason
            )
            if session is None:
                return None
            wiring = self._wirings.get(session_id)
            if wiring is not None:
                wiring.session = session
            return session

    # ------------------------------------------------- risk

    def get_policy(self, session_id: str) -> RiskPolicy | None:
        wiring = self.get(session_id)
        return None if wiring is None else wiring.gate.policy

    def set_policy(self, session_id: str, policy: RiskPolicy) -> RiskPolicy | None:
        wiring = self.get(session_id)
        if wiring is None:
            return None
        wiring.gate.set_policy(policy)
        wiring.policy_path.write_text(json.dumps(policy.to_dict(), indent=2))
        return policy

    # ------------------------------------------------- internals

    def _wire_paper(
        self,
        session: Session,
        config: Mapping[str, Any],
        policy: Mapping[str, Any] | None,
    ) -> _Wiring:
        positions_path = self.root / "positions" / f"{session.session_id}.json"
        audit_path = self.root / "audit" / f"{session.session_id}.jsonl"
        policy_path = self.root / "policies" / f"{session.session_id}.json"
        for p in (positions_path.parent, audit_path.parent, policy_path.parent):
            p.mkdir(parents=True, exist_ok=True)

        positions = PositionStore(path=positions_path)
        audit = AuditLog(audit_path)
        risk_policy = RiskPolicy.from_dict(dict(policy)) if policy else RiskPolicy()
        policy_path.write_text(json.dumps(risk_policy.to_dict(), indent=2))

        gate = RiskGate(policy=risk_policy, positions=positions)
        adapter = PaperAdapter(
            PaperConfig(
                commission_bps=float(config.get("commission_bps", 1.0)),
                slippage_bps=float(config.get("slippage_bps", 2.0)),
                starting_cash=float(config.get("starting_cash", 100_000.0)),
                name="paper",
            )
        )
        router = OrderRouter(
            adapter=adapter,
            gate=gate,
            positions=positions,
            audit=audit,
            session_id=session.session_id,
        )
        return _Wiring(
            session=session,
            adapter=adapter,
            router=router,
            audit=audit,
            positions=positions,
            gate=gate,
            policy_path=policy_path,
        )

    def _rehydrate(self, session: Session) -> _Wiring:
        # Best-effort rehydration: read policy from disk if present.
        policy_path = self.root / "policies" / f"{session.session_id}.json"
        policy_dict = None
        if policy_path.exists():
            try:
                policy_dict = json.loads(policy_path.read_text())
            except json.JSONDecodeError:
                policy_dict = None
        return self._wire_paper(session, {}, policy_dict)


_RUNTIME_LOCK = threading.Lock()
_RUNTIME: ExecRuntime | None = None


def get_runtime() -> ExecRuntime:
    """Return the shared per-process runtime (lazy-init)."""

    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = ExecRuntime()
        return _RUNTIME


def reset_runtime() -> None:
    """Test-only — wipe the in-memory runtime so each test gets a
    clean process. Does not delete on-disk state."""

    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = None
