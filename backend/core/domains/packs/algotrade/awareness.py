"""Algotrade awareness — registry + live sessions inventory.

W1b shipped one **local** awareness source (no network): an
inventory snapshot of the strategy registry that the cockpit
polls to render the strategy gallery.

W2-PR1 adds a second source: a live session snapshot
(open positions, last audit events, realised + unrealised PnL)
the cockpit polls to render the live PnL strip and the audit
viewer rail.

W2-PR2 will add a ``binance_kline_stream`` poll source for live
market data; W3 will add a ``session_pnl_stream`` SSE source.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import AwarenessSource


async def _registry_snapshot(_args: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact inventory: {slug, latest_version, fingerprint,
    instrument, tags, author, created_at}."""

    from backend.core.algotrade import get_registry

    reg = get_registry()
    out: list[dict[str, Any]] = []
    for slug in reg.list_slugs():
        latest = reg.latest(slug)
        if latest is None:
            continue
        s = latest.strategy
        out.append(
            {
                "slug": slug,
                "name": s.name,
                "latest_version": int(latest.version),
                "fingerprint": latest.fingerprint,
                "instrument": s.instrument,
                "timeframe": s.timeframe.value,
                "side": s.side.value,
                "tags": list(s.tags),
                "author": latest.author,
                "created_at": float(latest.created_at),
            }
        )
    return {
        "ok": True,
        "kind": "registry_snapshot",
        "count": len(out),
        "strategies": out,
    }


async def _live_sessions(args: Mapping[str, Any]) -> dict[str, Any]:
    """Compact snapshot of every live session: id, mode, status,
    open positions, realised + unrealised PnL totals, audit-tail
    head/tail timestamps. The cockpit polls this to render the
    sessions strip without spamming ``get_session`` per row."""

    from backend.core.algotrade.exec import get_runtime

    runtime = get_runtime()
    rows: list[dict[str, Any]] = []
    sandbox_id = args.get("sandbox_id")
    sessions = runtime.list_sessions(
        sandbox_id=str(sandbox_id) if sandbox_id else None,
    )
    for s in sessions:
        wiring = runtime.get(s.session_id)
        if wiring is None:
            continue
        positions = wiring.positions.all()
        open_orders = wiring.adapter.open_orders()
        rows.append(
            {
                "session_id": s.session_id,
                "mode": s.mode,
                "status": s.status.value,
                "strategy_fingerprint": s.strategy_fingerprint,
                "instrument": s.instrument,
                "adapter": s.adapter,
                "sandbox_id": s.sandbox_id,
                "started_at": s.started_at,
                "closed_at": s.closed_at,
                "positions_open": sum(1 for p in positions if not p.is_flat()),
                "open_orders": len(open_orders),
                "realized_pnl": wiring.positions.total_realized(),
                "unrealized_pnl": wiring.positions.total_unrealized(),
                "kill_switch": wiring.gate.policy.kill_switch,
            }
        )
    return {
        "ok": True,
        "kind": "live_sessions",
        "count": len(rows),
        "sessions": rows,
    }


SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="strategy_registry",
        name="Strategy registry",
        description=(
            "Inventory of locally stored strategies (slug, latest "
            "version, fingerprint, instrument, tags). Snapshot only — "
            "use the registry actions to mutate."
        ),
        kind="local",
        config={"backend": "filesystem", "root": "$TARS_HOME/algotrade/strategies/"},
        fetcher=_registry_snapshot,
    ),
    AwarenessSource(
        id="live_sessions",
        name="Live trading sessions",
        description=(
            "Compact snapshot of every paper / live session: status, "
            "open position count, realised + unrealised PnL totals, "
            "kill-switch state. Optional `sandbox_id` filter for "
            "workshop multi-tenancy."
        ),
        kind="local",
        config={"backend": "filesystem", "root": "$TARS_HOME/algotrade/sessions.jsonl"},
        fetcher=_live_sessions,
    ),
)
