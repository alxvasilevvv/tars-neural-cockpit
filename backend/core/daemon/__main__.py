"""``python -m backend.core.daemon`` — run the headless background loop.

Subcommands:

  (none)             — run the daemon loop (this is what launchd
                       calls).
  --install          — write the launchd plist and bootstrap the
                       LaunchAgent.
  --uninstall        — bootout + remove the plist.
  --status           — print plist + heartbeat status, exit 0.
  --render-plist     — print the plist XML to stdout, no side effects.
  --heartbeat        — pretty-print the most recent heartbeat JSON.

Exit codes:
  0  — success / heartbeat-only shutdown
  1  — install / bootstrap failed
  2  — bad CLI args
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .launchd import (
    PlistConfig,
    install_plist,
    plist_status,
    render_plist,
    uninstall_plist,
)
from .runner import read_heartbeat, run_daemon


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.daemon",
        description="TARS background daemon (Wave 152).",
    )
    p.add_argument(
        "--install",
        action="store_true",
        help="Install the launchd plist and bootstrap the LaunchAgent.",
    )
    p.add_argument(
        "--uninstall",
        action="store_true",
        help="Bootout the agent and remove the plist.",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Print the agent + heartbeat status and exit.",
    )
    p.add_argument(
        "--render-plist",
        action="store_true",
        help="Print the plist XML to stdout (no side effects).",
    )
    p.add_argument(
        "--heartbeat",
        action="store_true",
        help="Print the latest heartbeat JSON and exit.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="With --install, write the plist but skip launchctl bootstrap.",
    )
    return p


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _setup_logging()

    # --render-plist
    if args.render_plist:
        sys.stdout.write(render_plist(PlistConfig()))
        return 0

    # --status
    if args.status:
        hb = read_heartbeat()
        out = {
            "plist": plist_status(),
            "heartbeat": hb,
        }
        _print_json(out)
        return 0

    # --heartbeat
    if args.heartbeat:
        hb = read_heartbeat()
        if hb is None:
            sys.stderr.write("No heartbeat file found.\n")
            return 1
        _print_json(hb)
        return 0

    # --install
    if args.install:
        result = install_plist(dry_run=args.dry_run)
        _print_json(result)
        return 0 if result.get("ok") else 1

    # --uninstall
    if args.uninstall:
        result = uninstall_plist()
        _print_json(result)
        return 0 if result.get("ok") else 1

    # Default — run the loop (launchd path).
    try:
        return asyncio.run(run_daemon())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
