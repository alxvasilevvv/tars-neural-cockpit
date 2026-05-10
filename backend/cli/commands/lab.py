"""``tars lab ...`` subcommands — workshop facilitator surface."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "lab",
        help="Workshop lab roster + leaderboard + debrief.",
    )
    sub = p.add_subparsers(dest="lab_cmd", metavar="<verb>")

    cw = sub.add_parser("create-workshop", help="Create a workshop bucket.")
    cw.add_argument("--name", required=True)
    cw.add_argument("--facilitator", default="")
    cw.add_argument("--notes", default="")
    cw.add_argument(
        "--workshop-id",
        help="Optional explicit workshop_id. Auto-minted if omitted.",
    )

    lw = sub.add_parser("list-workshops", help="List workshops.")
    lw.add_argument("--status", choices=["open", "paused", "closed"])

    sw = sub.add_parser(
        "set-workshop-status", help="Pause / close / re-open a workshop."
    )
    sw.add_argument("--workshop-id", required=True)
    sw.add_argument(
        "--status", required=True, choices=["open", "paused", "closed"]
    )

    en = sub.add_parser("enroll", help="Enroll an attendee.")
    en.add_argument("--workshop-id", required=True)
    en.add_argument("--name", required=True, help="Display name.")
    en.add_argument("--attendee-id", help="Optional explicit attendee_id.")

    la = sub.add_parser("list-attendees", help="List attendees in a workshop.")
    la.add_argument("--workshop-id", required=True)

    lb = sub.add_parser("leaderboard", help="Compute & print the leaderboard.")
    lb.add_argument("--workshop-id", required=True)

    sn = sub.add_parser("snapshot", help="Per-attendee handout.")
    sn.add_argument("--attendee-id", required=True)

    db = sub.add_parser(
        "debrief",
        help="Render the W4-PR3 markdown debrief bundle for the workshop.",
    )
    db.add_argument("--workshop-id", required=True)
    db.add_argument(
        "--no-session-reports",
        action="store_true",
        help="Headlines-only mode — leaderboard + per-attendee summaries only.",
    )
    db.add_argument(
        "--output",
        type=Path,
        help="Write the markdown bundle to this path instead of stdout.",
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    cmd = args.lab_cmd
    if cmd is None:
        return {
            "ok": False,
            "error": "missing_subcommand",
            "detail": "Try `tars lab --help` for the verb list.",
        }

    handlers = {
        "create-workshop": _do_create,
        "list-workshops": _do_list_workshops,
        "set-workshop-status": _do_set_status,
        "enroll": _do_enroll,
        "list-attendees": _do_list_attendees,
        "leaderboard": _do_leaderboard,
        "snapshot": _do_snapshot,
        "debrief": _do_debrief,
    }
    fn = handlers.get(cmd)
    if fn is None:
        return {"ok": False, "error": "unknown_subcommand", "detail": cmd}
    return fn(args)


def _run(coro):
    return asyncio.run(coro)


def _do_create(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_create_workshop_action,
    )

    payload: dict[str, Any] = {
        "name": args.name,
        "facilitator": args.facilitator,
        "notes": args.notes,
    }
    if args.workshop_id:
        payload["workshop_id"] = args.workshop_id
    return _run(lab_create_workshop_action(payload))


def _do_list_workshops(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_list_workshops_action,
    )

    payload: dict[str, Any] = {}
    if args.status:
        payload["status"] = args.status
    return _run(lab_list_workshops_action(payload))


def _do_set_status(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_set_workshop_status_action,
    )

    return _run(
        lab_set_workshop_status_action(
            {"workshop_id": args.workshop_id, "status": args.status}
        )
    )


def _do_enroll(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_enroll_attendee_action,
    )

    payload: dict[str, Any] = {
        "workshop_id": args.workshop_id,
        "display_name": args.name,
    }
    if args.attendee_id:
        payload["attendee_id"] = args.attendee_id
    return _run(lab_enroll_attendee_action(payload))


def _do_list_attendees(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_list_attendees_action,
    )

    return _run(lab_list_attendees_action({"workshop_id": args.workshop_id}))


def _do_leaderboard(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_leaderboard_action,
    )

    return _run(lab_leaderboard_action({"workshop_id": args.workshop_id}))


def _do_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_attendee_snapshot_action,
    )

    return _run(
        lab_attendee_snapshot_action({"attendee_id": args.attendee_id})
    )


def _do_debrief(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.lab_actions import (
        lab_workshop_debrief_action,
    )

    payload: dict[str, Any] = {"workshop_id": args.workshop_id}
    if args.no_session_reports:
        payload["include_session_reports"] = False
    result = _run(lab_workshop_debrief_action(payload))
    if (
        args.output
        and isinstance(result, dict)
        and result.get("ok") is True
    ):
        markdown = (
            result.get("debrief", {}).get("markdown", "")
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
        # Replace the noisy debrief payload with a small confirmation
        # so stdout doesn't dump the entire bundle on top of the file.
        return {
            "ok": True,
            "wrote": str(args.output),
            "bytes": len(markdown.encode("utf-8")),
            "workshop_id": args.workshop_id,
        }
    return result
