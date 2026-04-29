"""Wallet awareness sources.

Two stream sources sit here as placeholders so the cockpit's
awareness ticker has wallet-shaped frames; both are config-only —
real fetchers live behind their respective chain RPCs.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import AwarenessSource


async def _fetch_wallet_summary(args: Mapping[str, Any]) -> Mapping[str, Any]:
    from backend.core.wallet import get_wallet_service

    svc = get_wallet_service()
    items = await svc.list_wallets()
    return {
        "ok": True,
        "count": len(items),
        "addresses_by_chain": {
            chain: [w.address for w in items if w.chain.value == chain]
            for chain in {w.chain.value for w in items}
        },
    }


SOURCES = (
    AwarenessSource(
        id="wallet.summary",
        name="Wallet summary",
        description="Local roster of wallets (no balances; no secrets).",
        kind="local",
        fetcher=_fetch_wallet_summary,
    ),
)
