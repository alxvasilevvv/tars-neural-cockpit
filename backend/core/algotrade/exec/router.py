"""OrderRouter — gate → adapter → audit pipeline.

Workshop-grade architecture: every order in the system flows
through exactly one router instance per session, so we have one
authoritative ledger to show attendees ("here's the intent the
strategy emitted; here's the gate's verdict; here's the adapter's
order envelope; here are the fills"). The router is also where
the cockpit subscribes for live updates (callbacks fan out to a
SSE / websocket layer in :mod:`web_extras.routers.algotrade`).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Awaitable, Callable

from .base import (
    AuditEvent,
    ExecAdapter,
    Fill,
    Order,
    OrderIntent,
    OrderStatus,
)
from .positions import PositionStore
from .risk import GateVerdict, RiskGate

ListenerFn = Callable[[AuditEvent], Awaitable[None]]


class AuditLog:
    """Append-only JSONL audit log scoped to a session."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not path.exists():
            path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: AuditEvent) -> None:
        with self._lock, self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False))
            fh.write("\n")

    def read_all(self) -> list[AuditEvent]:
        out: list[AuditEvent] = []
        if not self._path.exists():
            return out
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out.append(
                    AuditEvent(
                        ts=float(payload.get("ts", 0.0)),
                        kind=str(payload.get("kind", "")),
                        intent_id=payload.get("intent_id"),
                        order_id=payload.get("order_id"),
                        payload=dict(payload.get("payload", {})),
                    )
                )
        return out

    def tail(self, n: int = 100) -> list[AuditEvent]:
        events = self.read_all()
        return events[-n:]


class OrderRouter:
    """Funnels intents through the gate, into the adapter, and
    into the audit log + position store. Maintains an LRU of
    intent → order ids for idempotency."""

    def __init__(
        self,
        *,
        adapter: ExecAdapter,
        gate: RiskGate,
        positions: PositionStore,
        audit: AuditLog,
        session_id: str,
        idempotency_capacity: int = 4096,
    ) -> None:
        self.adapter = adapter
        self.gate = gate
        self.positions = positions
        self.audit = audit
        self.session_id = session_id
        self._intent_index: "OrderedDict[str, str]" = OrderedDict()
        self._intent_capacity = max(64, int(idempotency_capacity))
        self._listeners: list[ListenerFn] = []
        self._lock = asyncio.Lock()
        adapter.on_fill(self._handle_fill)

    # ------------------------------------------------------ public API

    def subscribe(self, listener: ListenerFn) -> Callable[[], None]:
        self._listeners.append(listener)

        def _unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return _unsubscribe

    async def submit(self, intent: OrderIntent) -> tuple[GateVerdict, Order | None]:
        async with self._lock:
            existing = self._intent_index.get(intent.intent_id)
            if existing is not None:
                cached = await self.adapter.status(existing)
                verdict = GateVerdict(
                    accepted=True,
                    reason="idempotent replay",
                    policy_snapshot=self.gate.policy.to_dict(),
                )
                await self._record(
                    "intent",
                    intent_id=intent.intent_id,
                    order_id=existing,
                    payload=intent.to_dict() | {"replay": True},
                )
                return verdict, cached

            await self._record(
                "intent",
                intent_id=intent.intent_id,
                order_id=None,
                payload=intent.to_dict(),
            )
            verdict = self.gate.evaluate(intent)
            await self._record(
                "verdict",
                intent_id=intent.intent_id,
                order_id=None,
                payload=verdict.to_dict(),
            )
            if not verdict.accepted:
                return verdict, None

            order = await self.adapter.submit(intent)
            self._intent_index[intent.intent_id] = order.order_id
            self._intent_index.move_to_end(intent.intent_id)
            while len(self._intent_index) > self._intent_capacity:
                self._intent_index.popitem(last=False)

            await self._record(
                "order",
                intent_id=intent.intent_id,
                order_id=order.order_id,
                payload=order.to_dict(),
            )
            for fill in order.fills:
                await self._handle_fill(order, fill)
            if order.status is OrderStatus.REJECTED:
                await self._record(
                    "reject",
                    intent_id=intent.intent_id,
                    order_id=order.order_id,
                    payload={"reason": order.rejection_reason or "rejected"},
                )
            return verdict, order

    async def cancel(self, order_id: str) -> Order:
        order = await self.adapter.cancel(order_id)
        await self._record(
            "cancel",
            intent_id=order.intent_id,
            order_id=order.order_id,
            payload=order.to_dict(),
        )
        return order

    async def status(self, order_id: str) -> Order | None:
        return await self.adapter.status(order_id)

    # ------------------------------------------------------ internal

    async def _handle_fill(self, order: Order, fill: Fill) -> None:
        position = self.positions.apply_fill(order, fill)
        await self._record(
            "fill",
            intent_id=order.intent_id,
            order_id=order.order_id,
            payload={
                "fill": fill.to_dict(),
                "order_status": order.status.value,
                "position": position.to_dict(),
            },
        )

    async def _record(
        self,
        kind: str,
        *,
        intent_id: str | None,
        order_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        event = AuditEvent(
            ts=time.time(),
            kind=kind,
            intent_id=intent_id,
            order_id=order_id,
            payload=payload | {"session_id": self.session_id},
        )
        self.audit.append(event)
        for listener in list(self._listeners):
            try:
                await listener(event)
            except Exception:
                pass
