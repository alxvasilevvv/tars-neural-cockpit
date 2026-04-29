"""Entrepreneur pack actions — Phase M / P6.

Re-exports the MLM action handlers under the renamed ids:

  downline_snapshot → network_snapshot
  score_recruit     → lead_score
  generate_post     → generate_content
  add_member        → add_lead
  retention_alert   → retention_alert      (kept)
  log_activity      → log_activity         (kept)

We deliberately *reuse* the handler functions instead of forking them:
the underlying SQLite store + CSV fallback are unchanged, only the
action namespace and the brand voice differ.
"""

from __future__ import annotations

from ...base import ActionSpec
from ..mlm.actions import (
    add_member,
    downline_snapshot,
    generate_post,
    log_activity,
    retention_alert,
    score_recruit,
)


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="network_snapshot",
        name="Network snapshot",
        description="Snapshot of your network depth, activity and tiers from the local store.",
        handler=downline_snapshot,
        schema={
            "type": "object",
            "properties": {
                "depth": {"type": "integer", "minimum": 1, "maximum": 32},
                "active_window_days": {
                    "type": "integer", "minimum": 1, "maximum": 365,
                },
                "path": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="lead_score",
        name="Lead score",
        description="Score the fit of a candidate by public profile signals.",
        handler=score_recruit,
        schema={
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
        },
    ),
    ActionSpec(
        id="generate_content",
        name="Generate content",
        description="Draft a channel-appropriate piece of content (post / dm / story / thread).",
        handler=generate_post,
        schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["ig", "tg", "wa"]},
                "format": {
                    "type": "string",
                    "enum": ["story", "post", "reel", "dm"],
                },
                "topic": {"type": "string"},
            },
            "required": ["channel"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="retention_alert",
        name="Retention alert",
        description="Find network members going quiet beyond the threshold and explain why.",
        handler=retention_alert,
        schema={
            "type": "object",
            "properties": {
                "threshold_days": {"type": "integer", "minimum": 1, "maximum": 365},
                "path": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="add_lead",
        name="Add network lead",
        description=(
            "Insert a new network lead into the local SQLite store. "
            "The sponsor (if any) must already exist."
        ),
        handler=add_member,
        schema={
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "sponsor": {"type": "string"},
                "rank": {
                    "type": "string",
                    "enum": ["starter", "bronze", "silver", "gold", "platinum"],
                },
                "joined_at": {"type": "string", "format": "date"},
                "volume_usd": {"type": "number", "minimum": 0},
                "notes": {"type": "string"},
                "on_conflict": {
                    "type": "string",
                    "enum": ["update", "skip"],
                },
            },
            "required": ["handle"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="log_activity",
        name="Log activity",
        description="Stamp a member's last_active_at and add to volume.",
        handler=log_activity,
        schema={
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "ts": {"type": "string"},
                "volume_delta": {"type": "number"},
            },
            "required": ["handle"],
        },
        destructive=True,
    ),
)
