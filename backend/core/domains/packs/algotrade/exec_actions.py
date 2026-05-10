"""Algotrade execution actions — paper trading verbs (W2-PR1).

This is the HTTP surface that turns the in-process exec runtime
into something cockpit / CLI / external MCP clients can drive.

W2-PR1 ships:

- ``start_paper_session`` — spin up a paper session bound to a
  registered strategy + risk policy.
- ``stop_session`` — close a session (no more intents accepted).
- ``list_sessions`` — paginated session list with filters.
- ``get_session`` — full snapshot: session, policy, open positions,
  open orders, audit tail.
- ``submit_intent`` — operator-issued intent (gates → audits → fills).
- ``cancel_order`` — cancel an open limit / pending order.
- ``feed_bar`` — advance the session's clock by one OHLCV bar.
  In production this is driven by the live data poller, but we
  expose it as an action so backtests-as-paper-replay work in
  workshops and CI.
- ``get_policy`` / ``set_policy`` — read & mutate the risk gate.
- ``audit_tail`` — read the last N events for the audit viewer.

W2-PR2 adds: live Binance adapter behind a vault key.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from ...base import ActionSpec
from backend.core.algotrade import (
    Strategy,
    StrategyError,
    get_registry,
)
from backend.core.algotrade.exec import (
    OrderIntent,
    OrderType,
    RiskPolicy,
    Side,
    get_runtime,
)


def _err(error: str, **detail: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error": error}
    payload.update(detail)
    return payload


def _ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


def _resolve_strategy(args: Mapping[str, Any]) -> tuple[Strategy | None, dict[str, Any] | None]:
    fp = args.get("fingerprint")
    if not fp:
        return None, _err(
            "missing_fingerprint",
            detail="paper sessions require a registered strategy fingerprint",
        )
    row = get_registry().get(str(fp))
    if row is None:
        return None, _err("strategy_not_found", fingerprint=fp)
    return row.strategy, None


# --------------------------------------------------------- session lifecycle


async def start_paper_session_action(args: Mapping[str, Any]) -> dict[str, Any]:
    strategy, err = _resolve_strategy(args)
    if err is not None:
        return err
    assert strategy is not None

    instrument = args.get("instrument") or strategy.instrument
    config = args.get("config") or {}
    if not isinstance(config, Mapping):
        return _err("invalid_config", detail="`config` must be an object")
    policy_raw = args.get("policy") or {}
    if policy_raw and not isinstance(policy_raw, Mapping):
        return _err("invalid_policy", detail="`policy` must be an object")
    metadata = args.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return _err("invalid_metadata", detail="`metadata` must be an object")

    runtime = get_runtime()
    wiring = runtime.start_paper_session(
        strategy_fingerprint=args["fingerprint"],
        instrument=str(instrument),
        sandbox_id=(str(args["sandbox_id"]) if args.get("sandbox_id") else None),
        notes=str(args.get("notes") or ""),
        metadata=dict(metadata),
        config=dict(config),
        policy=dict(policy_raw) if policy_raw else None,
    )
    return _ok(
        session=wiring.session.to_dict(),
        policy=wiring.gate.policy.to_dict(),
    )


async def stop_session_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return _err("missing_session_id")
    runtime = get_runtime()
    session = runtime.stop_session(str(sid), reason=str(args.get("reason") or "stopped"))
    if session is None:
        return _err("session_not_found", session_id=sid)
    return _ok(session=session.to_dict())


async def list_sessions_action(args: Mapping[str, Any]) -> dict[str, Any]:
    runtime = get_runtime()
    sessions = runtime.list_sessions(
        mode=str(args["mode"]) if args.get("mode") else None,
        sandbox_id=(str(args["sandbox_id"]) if args.get("sandbox_id") else None),
    )
    return _ok(
        count=len(sessions),
        sessions=[s.to_dict() for s in sessions],
    )


async def get_session_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return _err("missing_session_id")
    runtime = get_runtime()
    wiring = runtime.get(str(sid))
    if wiring is None:
        return _err("session_not_found", session_id=sid)

    audit_tail = int(args.get("audit_tail") or 50)
    return _ok(
        session=wiring.session.to_dict(),
        policy=wiring.gate.policy.to_dict(),
        positions=[p.to_dict() for p in wiring.positions.all()],
        open_orders=[o.to_dict() for o in wiring.adapter.open_orders()],
        all_orders_count=len(wiring.adapter.all_orders()),
        audit_tail=[e.to_dict() for e in wiring.audit.tail(audit_tail)],
        realized_pnl=wiring.positions.total_realized(),
        unrealized_pnl=wiring.positions.total_unrealized(),
    )


# --------------------------------------------------------- intents / orders


async def submit_intent_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return _err("missing_session_id")
    runtime = get_runtime()
    wiring = runtime.get(str(sid))
    if wiring is None:
        return _err("session_not_found", session_id=sid)

    side_raw = args.get("side")
    if side_raw not in ("buy", "sell"):
        return _err("invalid_side", detail="side must be 'buy' or 'sell'")
    type_raw = args.get("type", "market")
    if type_raw not in ("market", "limit"):
        return _err("invalid_type", detail="type must be 'market' or 'limit'")

    qty = args.get("qty")
    try:
        qty = float(qty)
    except (TypeError, ValueError):
        return _err("invalid_qty", detail="qty must be a positive number")
    if qty <= 0:
        return _err("invalid_qty", detail="qty must be > 0")

    price = args.get("price")
    if type_raw == "limit" and price is None:
        return _err("missing_price", detail="limit orders require price")
    if price is not None:
        try:
            price = float(price)
        except (TypeError, ValueError):
            return _err("invalid_price", detail="price must be a number")

    instrument = str(args.get("instrument") or wiring.session.instrument)

    intent = OrderIntent.make(
        strategy_fingerprint=wiring.session.strategy_fingerprint,
        instrument=instrument,
        side=Side(side_raw),
        qty=qty,
        type=OrderType(type_raw),
        price=price,
        sandbox_id=wiring.session.sandbox_id,
        metadata=args.get("metadata") if isinstance(args.get("metadata"), Mapping) else None,
    )
    verdict, order = await wiring.router.submit(intent)
    return _ok(
        verdict=verdict.to_dict(),
        intent=intent.to_dict(),
        order=None if order is None else order.to_dict(),
    )


async def cancel_order_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    oid = args.get("order_id")
    if not sid or not oid:
        return _err("missing_args", detail="`session_id` and `order_id` required")
    runtime = get_runtime()
    wiring = runtime.get(str(sid))
    if wiring is None:
        return _err("session_not_found", session_id=sid)
    try:
        order = await wiring.router.cancel(str(oid))
    except KeyError:
        return _err("order_not_found", order_id=oid)
    return _ok(order=order.to_dict())


async def feed_bar_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    bar = args.get("bar")
    if not sid:
        return _err("missing_session_id")
    if not isinstance(bar, Mapping):
        return _err("invalid_bar", detail="`bar` must be an object")
    runtime = get_runtime()
    wiring = runtime.get(str(sid))
    if wiring is None:
        return _err("session_not_found", session_id=sid)

    instrument = str(bar.get("instrument") or wiring.session.instrument)
    fills = await wiring.adapter.on_bar(dict(bar), instrument=instrument)
    if "close" in bar:
        try:
            wiring.gate.update_mark(instrument, float(bar["close"]))
            wiring.positions.mark(instrument, float(bar["close"]))
        except (TypeError, ValueError):
            pass

    return _ok(
        session_id=sid,
        instrument=instrument,
        fills=[f.to_dict() for f in fills],
        positions=[p.to_dict() for p in wiring.positions.all()],
        unrealized_pnl=wiring.positions.total_unrealized(),
        realized_pnl=wiring.positions.total_realized(),
    )


# --------------------------------------------------------- policy


async def get_policy_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return _err("missing_session_id")
    runtime = get_runtime()
    policy = runtime.get_policy(str(sid))
    if policy is None:
        return _err("session_not_found", session_id=sid)
    return _ok(session_id=sid, policy=policy.to_dict())


async def set_policy_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    raw = args.get("policy")
    if not sid:
        return _err("missing_session_id")
    if not isinstance(raw, Mapping):
        return _err("invalid_policy", detail="`policy` must be an object")
    runtime = get_runtime()
    new_policy = RiskPolicy.from_dict(dict(raw))
    applied = runtime.set_policy(str(sid), new_policy)
    if applied is None:
        return _err("session_not_found", session_id=sid)
    return _ok(session_id=sid, policy=applied.to_dict())


# --------------------------------------------------------- audit


async def audit_tail_action(args: Mapping[str, Any]) -> dict[str, Any]:
    sid = args.get("session_id")
    if not sid:
        return _err("missing_session_id")
    runtime = get_runtime()
    wiring = runtime.get(str(sid))
    if wiring is None:
        return _err("session_not_found", session_id=sid)
    n = int(args.get("limit") or 100)
    events = wiring.audit.tail(n)
    return _ok(
        session_id=sid,
        count=len(events),
        events=[e.to_dict() for e in events],
    )


# --------------------------------------------------------- specs


_POLICY_SCHEMA = {
    "type": "object",
    "properties": {
        "max_position_notional": {"type": "number"},
        "max_order_qty": {"type": "number"},
        "max_open_positions": {"type": "integer"},
        "max_daily_loss": {"type": "number"},
        "allow_short": {"type": "boolean"},
        "allowed_instruments": {"type": "array", "items": {"type": "string"}},
        "kill_switch": {"type": "boolean"},
        "notes": {"type": "string"},
    },
}

_BAR_SCHEMA = {
    "type": "object",
    "properties": {
        "ts": {"type": "number"},
        "open": {"type": "number"},
        "high": {"type": "number"},
        "low": {"type": "number"},
        "close": {"type": "number"},
        "volume": {"type": "number"},
        "instrument": {"type": "string"},
    },
    "required": ["ts", "open", "high", "low", "close"],
}


EXEC_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="start_paper_session",
        name="Start paper session",
        description=(
            "Spin up a paper-trading session bound to a registered "
            "strategy fingerprint. Optional `policy` configures the "
            "risk gate and `config` tunes commission / slippage."
        ),
        handler=start_paper_session_action,
        schema={
            "type": "object",
            "properties": {
                "fingerprint": {"type": "string"},
                "instrument": {"type": "string"},
                "sandbox_id": {"type": "string"},
                "notes": {"type": "string"},
                "metadata": {"type": "object"},
                "config": {
                    "type": "object",
                    "properties": {
                        "commission_bps": {"type": "number"},
                        "slippage_bps": {"type": "number"},
                        "starting_cash": {"type": "number"},
                    },
                },
                "policy": _POLICY_SCHEMA,
            },
            "required": ["fingerprint"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="stop_session",
        name="Stop session",
        description="Close an open session — no more intents accepted.",
        handler=stop_session_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["session_id"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="list_sessions",
        name="List sessions",
        description="Inventory of sessions, optionally filtered by mode + sandbox.",
        handler=list_sessions_action,
        schema={
            "type": "object",
            "properties": {
                "mode": {"type": "string"},
                "sandbox_id": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="get_session",
        name="Get session snapshot",
        description=(
            "Full session snapshot for the cockpit: session, policy, "
            "open positions, open orders, recent audit events, "
            "realised + unrealised PnL totals."
        ),
        handler=get_session_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "audit_tail": {"type": "integer"},
            },
            "required": ["session_id"],
        },
    ),
    ActionSpec(
        id="submit_intent",
        name="Submit intent",
        description=(
            "Submit an order intent into the session's risk gate → "
            "adapter → audit pipeline. Idempotent on the server-"
            "generated intent_id (callers do not provide one)."
        ),
        handler=submit_intent_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "qty": {"type": "number"},
                "type": {"type": "string", "enum": ["market", "limit"]},
                "price": {"type": "number"},
                "instrument": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["session_id", "side", "qty"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="cancel_order",
        name="Cancel order",
        description="Cancel an open order belonging to the session.",
        handler=cancel_order_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "order_id": {"type": "string"},
            },
            "required": ["session_id", "order_id"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="feed_bar",
        name="Feed bar",
        description=(
            "Advance the session's paper clock by one OHLCV bar. "
            "Drives limit-order fills, marks open positions, and "
            "updates risk-gate marks. In production the live data "
            "poller calls this; in workshops attendees can replay "
            "saved data deterministically."
        ),
        handler=feed_bar_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "bar": _BAR_SCHEMA,
            },
            "required": ["session_id", "bar"],
        },
    ),
    ActionSpec(
        id="get_policy",
        name="Get risk policy",
        description="Read the active risk policy for a session.",
        handler=get_policy_action,
        schema={
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    ),
    ActionSpec(
        id="set_policy",
        name="Set risk policy",
        description=(
            "Replace the session's risk policy. Use to tighten / "
            "loosen pre-trade caps, flip the kill-switch, or scope "
            "the instrument allowlist."
        ),
        handler=set_policy_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "policy": _POLICY_SCHEMA,
            },
            "required": ["session_id", "policy"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="audit_tail",
        name="Audit tail",
        description="Last N audit events for a session.",
        handler=audit_tail_action,
        schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["session_id"],
        },
    ),
)
