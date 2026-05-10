"""``tars playbooks ...`` subcommands."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "playbooks",
        help="Discover + run playbooks (recursive loader from W4-PR1).",
    )
    sub = p.add_subparsers(dest="playbooks_cmd", metavar="<verb>")

    sub.add_parser("list", help="List discovered playbooks.")

    sh = sub.add_parser("show", help="Show one playbook's full definition.")
    sh.add_argument("playbook_id")

    rn = sub.add_parser("run", help="Execute a playbook by id.")
    rn.add_argument("playbook_id")
    rn.add_argument(
        "--mode",
        choices=["dry_run", "confirm", "auto"],
        default="confirm",
        help=(
            "Policy mode for the run. `dry_run` plans without "
            "executing destructive verbs; `confirm` (default) gates "
            "destructive verbs through the operator; `auto` runs "
            "everything (use only in trusted automation)."
        ),
    )
    rn.add_argument(
        "--context",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Inline context overrides for the playbook's `${context.*}` "
            "placeholders. Repeat for multiple keys."
        ),
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    cmd = args.playbooks_cmd
    if cmd is None:
        return {
            "ok": False,
            "error": "missing_subcommand",
            "detail": "Try `tars playbooks --help` for the verb list.",
        }
    if cmd == "list":
        return _do_list()
    if cmd == "show":
        return _do_show(args)
    if cmd == "run":
        return _do_run(args)
    return {"ok": False, "error": "unknown_subcommand", "detail": cmd}


def _do_list() -> dict[str, Any]:
    from backend.core.playbooks.loader import discover

    playbooks = discover()
    rows = []
    for p in sorted(playbooks.values(), key=lambda x: x.id):
        rows.append(
            {
                "id": p.id,
                "name": p.name,
                "pack": p.pack,
                "tags": list(p.tags),
            }
        )
    return {"ok": True, "playbooks": rows, "count": len(rows)}


def _do_show(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.playbooks.loader import discover

    playbooks = discover()
    pb = playbooks.get(args.playbook_id)
    if pb is None:
        return {
            "ok": False,
            "error": "playbook_not_found",
            "detail": args.playbook_id,
        }
    return {"ok": True, "playbook": pb.to_dict()}


def _do_run(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.playbooks.loader import discover
    from backend.core.playbooks.runner import PlaybookRunner

    try:
        from backend.core.playbooks.policy import PolicyMode
    except ImportError:
        # Older scaffolds before the policy module landed —
        # CLI degrades gracefully.
        PolicyMode = None  # type: ignore

    playbooks = discover()
    pb = playbooks.get(args.playbook_id)
    if pb is None:
        return {
            "ok": False,
            "error": "playbook_not_found",
            "detail": args.playbook_id,
        }

    context: dict[str, Any] = {}
    for kv in args.context or []:
        if "=" not in kv:
            return {
                "ok": False,
                "error": "invalid_context",
                "detail": f"`{kv}` must be KEY=VALUE",
            }
        k, v = kv.split("=", 1)
        context[k] = v

    runner = PlaybookRunner()
    if PolicyMode is None:
        result = asyncio.run(runner.run(pb, context=context))
    else:
        mode = PolicyMode(args.mode)
        result = asyncio.run(runner.run(pb, context=context, mode=mode))
    return result if isinstance(result, dict) else {"ok": True, "result": result}
