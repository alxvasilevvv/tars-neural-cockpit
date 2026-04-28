"""MLM pack awareness sources.

The downline DB is the only one with a live local fetcher right now —
it reuses the same CSV the action handlers read. Webhook receivers
(Telegram / WhatsApp) and Instagram Graph stay config-only until the
secrets vault lands.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import AwarenessSource
from .actions import downline_snapshot


async def _fetch_downline_db(args: Mapping[str, Any]) -> Mapping[str, Any]:
    # The source's ``config["path"]`` points at the future SQLite location
    # (``~/.tars/downline.sqlite``). The CSV fallback at
    # ``data/mlm_network.csv`` is what we actually read today, so we
    # drop the SQLite path before delegating to the action handler.
    forwarded = {k: v for k, v in args.items() if k != "path"}
    snap = await downline_snapshot(forwarded)
    if not snap.get("ok"):
        return snap
    snap = dict(snap)
    snap["source"] = "csv-local"
    snap["hint"] = "downline.sqlite not yet wired; CSV fallback in use"
    return snap


SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="downline_db",
        name="Downline database",
        description="Local sqlite of network members, ranks, activity (CSV fallback).",
        kind="local",
        config={"path": "~/.tars/downline.sqlite"},
        fetcher=_fetch_downline_db,
    ),
    AwarenessSource(
        id="telegram_bot",
        name="Telegram inbound",
        description="Webhook from a TG bot for incoming messages.",
        kind="webhook",
        config={"path": "/api/domains/mlm/webhooks/telegram"},
    ),
    AwarenessSource(
        id="instagram_graph",
        name="Instagram Graph",
        description="Insights, comments, and DMs via Graph API.",
        kind="poll",
        config={"interval_s": 600, "scopes": ["insights", "messaging"]},
    ),
    AwarenessSource(
        id="whatsapp_business",
        name="WhatsApp Business",
        description="WhatsApp Business API for transactional messages.",
        kind="webhook",
        config={"path": "/api/domains/mlm/webhooks/whatsapp"},
    ),
)
