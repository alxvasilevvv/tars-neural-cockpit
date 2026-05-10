"""``tars`` CLI top-level entry point.

Stdlib-only — no ``click``, no ``typer``, no ``rich``. argparse
+ a tiny in-house Markdown renderer (``backend.cli.output``)
keep the cold-start under 100ms and the dependency tree empty.

Why a CLI when the cockpit / HTTP layer already exposes every
verb? Three reasons:

1. **Workshop power-users live in terminals.** Quants prefer
   `tars algotrade backtest --recipe ma_cross --binance
   BTCUSDT:1h:500` over a UI form.
2. **CI / cron need a stable command surface** — playbook
   schedulers, smoke tests, and post-workshop debrief mailers
   all want a single binary.
3. **MCP is next** (Wave M3/M4) — the CLI is the natural
   testing harness for the MCP client/server exchange.

Exit codes:
- ``0`` — success (action handler returned ``ok=True``)
- ``1`` — handler returned ``ok=False``
- ``2`` — argparse / usage error
- ``3`` — uncaught exception (always pretty-prints stderr)
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from typing import Any

from .commands import algotrade, lab, playbooks, version
from .output import render


PROG = "tars"
CLI_VERSION = version.CLI_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "TARS command-line interface — strategy IR, paper +"
            " live executors, workshop lab roster + leaderboard,"
            " playbook runner. All verbs route to the same"
            " action handlers the cockpit and external MCP"
            " clients drive, so the audit log stays unified."
        ),
        epilog=(
            "Output mode: --json forces machine-readable JSON;"
            " --human forces the pretty Markdown / table layout"
            " (default when stdout is a TTY)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {CLI_VERSION}",
    )
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "--json",
        dest="output_mode",
        action="store_const",
        const="json",
        help="Force JSON output (default for non-TTY stdout).",
    )
    grp.add_argument(
        "--human",
        dest="output_mode",
        action="store_const",
        const="human",
        help="Force Markdown / table output (default on a TTY).",
    )
    parser.set_defaults(output_mode=None)

    subparsers = parser.add_subparsers(
        dest="command", metavar="<command>"
    )
    algotrade.add_parser(subparsers)
    lab.add_parser(subparsers)
    playbooks.add_parser(subparsers)
    version.add_parser(subparsers)

    return parser


def _resolve_output_mode(args: argparse.Namespace) -> str:
    if args.output_mode:
        return args.output_mode
    return "human" if sys.stdout.isatty() else "json"


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    cmd = args.command
    if cmd == "algotrade":
        return algotrade.handle(args)
    if cmd == "lab":
        return lab.handle(args)
    if cmd == "playbooks":
        return playbooks.handle(args)
    if cmd == "version":
        return version.handle(args)
    return {
        "ok": False,
        "error": "missing_command",
        "detail": "Try `tars --help` for available commands.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        return 2

    output_mode = _resolve_output_mode(args)

    try:
        result = _dispatch(args)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted.\n")
        return 130
    except Exception as exc:  # noqa: BLE001 — top-level catch
        if os.environ.get("TARS_CLI_TRACEBACK"):
            traceback.print_exc(file=sys.stderr)
        sys.stderr.write(f"unhandled error: {type(exc).__name__}: {exc}\n")
        return 3

    print(render(result, mode=output_mode))
    if isinstance(result, dict) and result.get("ok") is False:
        return 1
    return 0
