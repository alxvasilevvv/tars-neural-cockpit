from __future__ import annotations

from ...base import AwarenessSource

SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="downline_db",
        name="Downline database",
        description="Local sqlite of network members, ranks, activity.",
        kind="local",
        config={"path": "~/.tars/downline.sqlite"},
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
