"""Algotrade workshop lab actions (W4-PR2).

HTTP-exposed verbs for the workshop lab: create / list / pause /
close workshops, enroll attendees, render the leaderboard, and
fetch an attendee's full snapshot (sessions + rank).

The lab roster is a thin file-backed layer on top of W2's
``sandbox_id`` field — every attendee gets a deterministic
``sandbox_id`` of the form ``lab:<workshop_id>:<attendee_id>``
so existing actions (`start_paper_session`,
`start_live_session`, `submit_intent`, `list_sessions`, …) can
filter by sandbox without any new sub-API. This makes the lab
mode opt-in: a workshop attendee uses normal algotrade verbs
with the sandbox_id the lab assigns them.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from ...base import ActionSpec
from backend.core.algotrade.exec import get_runtime
from backend.core.algotrade.exec.sessions import SessionStatus
from backend.core.algotrade.lab import (
    Attendee,
    Workshop,
    WorkshopStatus,
    compute_leaderboard,
    get_lab_store,
    render_workshop_debrief,
)


def _err(error: str, **detail: Any) -> dict[str, Any]:
    return {"ok": False, "error": error, **detail}


def _ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


# ----------------------------------------------------- handlers


async def lab_create_workshop_action(args: Mapping[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    if not name:
        return _err("missing_name", detail="workshop must have a `name`")

    facilitator = str(args.get("facilitator") or "").strip()
    notes = str(args.get("notes") or "")
    metadata = args.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return _err("invalid_metadata", detail="`metadata` must be an object")
    workshop_id = args.get("workshop_id")
    if workshop_id is not None:
        workshop_id = str(workshop_id).strip()
        if not workshop_id:
            workshop_id = None

    store = get_lab_store()
    try:
        workshop = store.create_workshop(
            name=name,
            facilitator=facilitator,
            notes=notes,
            metadata=dict(metadata),
            workshop_id=workshop_id,
        )
    except ValueError as exc:
        return _err("workshop_exists", detail=str(exc))
    return _ok(workshop=workshop.to_dict())


async def lab_list_workshops_action(args: Mapping[str, Any]) -> dict[str, Any]:
    raw_status = args.get("status")
    status: WorkshopStatus | None = None
    if raw_status is not None:
        try:
            status = WorkshopStatus(str(raw_status))
        except ValueError:
            return _err(
                "invalid_status",
                detail=(
                    "`status` must be one of: "
                    + ", ".join(s.value for s in WorkshopStatus)
                ),
            )
    workshops = get_lab_store().list_workshops(status=status)
    return _ok(workshops=[w.to_dict() for w in workshops], total=len(workshops))


async def lab_set_workshop_status_action(
    args: Mapping[str, Any],
) -> dict[str, Any]:
    workshop_id = str(args.get("workshop_id") or "")
    if not workshop_id:
        return _err("missing_workshop_id")
    raw_status = args.get("status")
    if not raw_status:
        return _err("missing_status")
    try:
        status = WorkshopStatus(str(raw_status))
    except ValueError:
        return _err(
            "invalid_status",
            detail=(
                "`status` must be one of: "
                + ", ".join(s.value for s in WorkshopStatus)
            ),
        )
    workshop = get_lab_store().set_workshop_status(workshop_id, status)
    if workshop is None:
        return _err("workshop_not_found", workshop_id=workshop_id)
    return _ok(workshop=workshop.to_dict())


async def lab_enroll_attendee_action(
    args: Mapping[str, Any],
) -> dict[str, Any]:
    workshop_id = str(args.get("workshop_id") or "")
    display_name = str(args.get("display_name") or "").strip()
    if not workshop_id:
        return _err("missing_workshop_id")
    if not display_name:
        return _err(
            "missing_display_name",
            detail="attendee must have a `display_name`",
        )
    attendee_id = args.get("attendee_id")
    if attendee_id is not None:
        attendee_id = str(attendee_id).strip()
        if not attendee_id:
            attendee_id = None
    metadata = args.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return _err("invalid_metadata", detail="`metadata` must be an object")

    store = get_lab_store()
    try:
        attendee = store.enroll(
            workshop_id=workshop_id,
            display_name=display_name,
            attendee_id=attendee_id,
            metadata=dict(metadata),
        )
    except KeyError:
        return _err("workshop_not_found", workshop_id=workshop_id)
    except PermissionError as exc:
        return _err("workshop_closed", detail=str(exc))
    except ValueError as exc:
        return _err("attendee_exists", detail=str(exc))
    return _ok(
        attendee=attendee.to_dict(),
        usage_hint=(
            "Pass `sandbox_id`='" + attendee.sandbox_id + "' to "
            "`start_paper_session` / `start_live_session` so the "
            "session is automatically scoped to this attendee. "
            "The leaderboard fans across every session that "
            "carries this sandbox_id."
        ),
    )


async def lab_list_attendees_action(
    args: Mapping[str, Any],
) -> dict[str, Any]:
    workshop_id = str(args.get("workshop_id") or "")
    if not workshop_id:
        return _err("missing_workshop_id")
    store = get_lab_store()
    if store.get_workshop(workshop_id) is None:
        return _err("workshop_not_found", workshop_id=workshop_id)
    attendees = store.list_attendees(workshop_id)
    return _ok(
        workshop_id=workshop_id,
        attendees=[a.to_dict() for a in attendees],
        total=len(attendees),
    )


async def lab_leaderboard_action(args: Mapping[str, Any]) -> dict[str, Any]:
    workshop_id = str(args.get("workshop_id") or "")
    if not workshop_id:
        return _err("missing_workshop_id")
    try:
        leaderboard = compute_leaderboard(workshop_id)
    except KeyError:
        return _err("workshop_not_found", workshop_id=workshop_id)
    return _ok(leaderboard=leaderboard.to_dict())


async def lab_workshop_debrief_action(
    args: Mapping[str, Any],
) -> dict[str, Any]:
    workshop_id = str(args.get("workshop_id") or "")
    if not workshop_id:
        return _err("missing_workshop_id")
    include_session_reports = bool(
        args.get("include_session_reports", True)
    )
    try:
        debrief = render_workshop_debrief(
            workshop_id,
            include_session_reports=include_session_reports,
        )
    except KeyError:
        return _err("workshop_not_found", workshop_id=workshop_id)
    return _ok(debrief=debrief.to_dict())


async def lab_attendee_snapshot_action(
    args: Mapping[str, Any],
) -> dict[str, Any]:
    attendee_id = str(args.get("attendee_id") or "")
    if not attendee_id:
        return _err("missing_attendee_id")
    store = get_lab_store()
    attendee = store.get_attendee(attendee_id)
    if attendee is None:
        return _err("attendee_not_found", attendee_id=attendee_id)

    runtime = get_runtime()
    sessions = runtime.list_sessions(sandbox_id=attendee.sandbox_id)
    sessions_payload = [s.to_dict() for s in sessions]

    leaderboard = compute_leaderboard(attendee.workshop_id)
    rank_entry = next(
        (e for e in leaderboard.entries if e.attendee_id == attendee_id),
        None,
    )

    return _ok(
        attendee=attendee.to_dict(),
        workshop=(
            store.get_workshop(attendee.workshop_id).to_dict()
            if store.get_workshop(attendee.workshop_id)
            else None
        ),
        sessions=sessions_payload,
        sessions_total=len(sessions_payload),
        sessions_running=sum(
            1
            for s in sessions
            if s.status is SessionStatus.RUNNING
        ),
        rank=(rank_entry.to_dict() if rank_entry else None),
        leaderboard_size=len(leaderboard.entries),
    )


# ----------------------------------------------------- specs


_WORKSHOP_STATUS_VALUES = [s.value for s in WorkshopStatus]


LAB_ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="lab_create_workshop",
        name="Create workshop (lab)",
        description=(
            "Create a workshop bucket. The workshop_id is "
            "auto-minted from the slugified name + epoch + a "
            "short uuid suffix. Roster + attendee mints are "
            "persisted at $TARS_HOME/algotrade/lab/<workshop_id>/"
            "roster.json so a facilitator can `cat` the file "
            "mid-workshop to audit who's enrolled."
        ),
        handler=lab_create_workshop_action,
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "facilitator": {"type": "string"},
                "notes": {"type": "string"},
                "metadata": {"type": "object"},
                "workshop_id": {"type": "string"},
            },
            "required": ["name"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="lab_list_workshops",
        name="List workshops",
        description=(
            "List every workshop the lab knows about (newest "
            "first). Optional `status` filter: open | paused | "
            "closed."
        ),
        handler=lab_list_workshops_action,
        schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": _WORKSHOP_STATUS_VALUES},
            },
        },
    ),
    ActionSpec(
        id="lab_set_workshop_status",
        name="Set workshop status",
        description=(
            "Pause a workshop for a handout review or close it "
            "to freeze the leaderboard. Closing sets `closed_at` "
            "and prevents new enrollments."
        ),
        handler=lab_set_workshop_status_action,
        schema={
            "type": "object",
            "properties": {
                "workshop_id": {"type": "string"},
                "status": {"type": "string", "enum": _WORKSHOP_STATUS_VALUES},
            },
            "required": ["workshop_id", "status"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="lab_enroll_attendee",
        name="Enroll attendee",
        description=(
            "Add an attendee to a workshop. The lab mints a "
            "deterministic `sandbox_id` of the form "
            "`lab:<workshop_id>:<attendee_id>` — pass it to "
            "`start_paper_session` / `start_live_session` so "
            "every downstream session, audit log, position book "
            "and council review is scoped to this attendee. "
            "Closed workshops reject new enrollments."
        ),
        handler=lab_enroll_attendee_action,
        schema={
            "type": "object",
            "properties": {
                "workshop_id": {"type": "string"},
                "display_name": {"type": "string"},
                "attendee_id": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["workshop_id", "display_name"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="lab_list_attendees",
        name="List attendees",
        description=(
            "Return every attendee enrolled in a workshop, in "
            "join order. The cockpit lab UI uses this to render "
            "the roster panel."
        ),
        handler=lab_list_attendees_action,
        schema={
            "type": "object",
            "properties": {
                "workshop_id": {"type": "string"},
            },
            "required": ["workshop_id"],
        },
    ),
    ActionSpec(
        id="lab_leaderboard",
        name="Workshop leaderboard",
        description=(
            "Replay every attendee's audit log via the W3-PR1 "
            "session metrics aggregator and rank by net edge: "
            "score = realized_pnl - fees_total - slippage_cost. "
            "Tie-breakers: higher acceptance_rate, more fills, "
            "earlier joined_at. Always recomputed from disk so "
            "the ranking is reproducible after a worker restart "
            "and matches the audit log byte-for-byte. Pure "
            "stdlib, no caching."
        ),
        handler=lab_leaderboard_action,
        schema={
            "type": "object",
            "properties": {
                "workshop_id": {"type": "string"},
            },
            "required": ["workshop_id"],
        },
    ),
    ActionSpec(
        id="lab_workshop_debrief",
        name="Workshop debrief (markdown bundle)",
        description=(
            "One-shot Markdown bundle for the entire workshop: "
            "header + leaderboard table + per-attendee sections "
            "(rank, council consensus, every session's W3-PR2 "
            "Markdown report). Pure stdlib, deterministic — same "
            "audit logs always produce the same bundle. Set "
            "`include_session_reports=false` to render the "
            "headline-only debrief (leaderboard + attendee "
            "summaries) the cockpit's lab summary panel uses. "
            "The full bundle is what facilitators email out at "
            "the end of the workshop."
        ),
        handler=lab_workshop_debrief_action,
        schema={
            "type": "object",
            "properties": {
                "workshop_id": {"type": "string"},
                "include_session_reports": {"type": "boolean"},
            },
            "required": ["workshop_id"],
        },
    ),
    ActionSpec(
        id="lab_attendee_snapshot",
        name="Attendee snapshot",
        description=(
            "Full per-attendee handout: attendee + workshop "
            "rows, every session the attendee owns, and the "
            "attendee's current leaderboard rank. Used by the "
            "cockpit attendee detail panel and the post-workshop "
            "debrief export."
        ),
        handler=lab_attendee_snapshot_action,
        schema={
            "type": "object",
            "properties": {
                "attendee_id": {"type": "string"},
            },
            "required": ["attendee_id"],
        },
    ),
)
