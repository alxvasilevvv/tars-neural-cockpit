"""Algotrade awareness — the registry inventory.

W1b ships one **local** awareness source (no network): an
inventory snapshot of the strategy registry that the cockpit
polls to render the strategy gallery.

W2 will add a ``binance_kline_stream`` poll source for live data,
W3 will add a ``session_pnl_stream`` SSE source.
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
)
