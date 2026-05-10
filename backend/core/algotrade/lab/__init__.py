"""Workshop lab mode (W4-PR2).

Multi-attendee sandbox layer that sits on top of the W2 + W3
execution stack. Each attendee gets a stable ``sandbox_id`` —
the same ``sandbox_id`` field that already lived on
:class:`backend.core.algotrade.exec.sessions.Session`. The lab
roster groups attendees into a *workshop*; the leaderboard
fans the W3-PR1 :class:`SessionMetrics` across every session
the attendee owns and ranks them by net realised PnL.

No new persistence layer for sessions — the lab module just
adds a ``$TARS_HOME/algotrade/lab/<workshop_id>/roster.json``
file per workshop. Rebuilds are idempotent: the leaderboard
recomputes from disk every call (sessions, audit logs,
positions). This keeps the lab transparent for cresco-style
workshops where the facilitator wants a *deterministic*
leaderboard at any point.
"""

from .debrief import (
    AttendeeDebrief,
    WorkshopDebrief,
    render_workshop_debrief,
)
from .lab import (
    Attendee,
    LabStore,
    Leaderboard,
    LeaderboardEntry,
    Workshop,
    WorkshopStatus,
    compute_leaderboard,
    get_lab_store,
    reset_lab_store,
)

__all__ = [
    "Attendee",
    "AttendeeDebrief",
    "LabStore",
    "Leaderboard",
    "LeaderboardEntry",
    "Workshop",
    "WorkshopDebrief",
    "WorkshopStatus",
    "compute_leaderboard",
    "get_lab_store",
    "render_workshop_debrief",
    "reset_lab_store",
]
