from __future__ import annotations

from ...base import AwarenessSource

SOURCES: tuple[AwarenessSource, ...] = (
    AwarenessSource(
        id="gmail",
        name="Gmail",
        description="Inbox of the operator account (read-only).",
        kind="poll",
        config={"interval_s": 60, "scope": "read", "label": "INBOX"},
    ),
    AwarenessSource(
        id="gcalendar",
        name="Google Calendar",
        description="Primary calendar with event metadata.",
        kind="poll",
        config={"interval_s": 120, "calendar": "primary"},
    ),
    AwarenessSource(
        id="hubspot",
        name="HubSpot CRM",
        description="Deals, contacts and pipelines.",
        kind="poll",
        config={"interval_s": 300, "objects": ["deals", "contacts", "companies"]},
    ),
    AwarenessSource(
        id="gsheets_kpi",
        name="KPI sheet",
        description="A Google Sheet treated as a KPI data source.",
        kind="poll",
        config={"interval_s": 600, "sheet_id": ""},
    ),
)
