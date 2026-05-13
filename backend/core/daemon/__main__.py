"""``python -m backend.core.daemon`` — run the headless background loop.

Subcommands auto-detect platform: macOS uses launchd, Linux uses
systemd. Pass ``--platform launchd|systemd`` to override.

  (none)             — run the daemon loop (this is what launchd /
                       systemd calls).
  --install          — write the platform-native service definition
                       and start it.
  --uninstall        — stop + remove the platform-native service.
  --status           — print service + heartbeat status, exit 0.
  --render-plist     — print the launchd plist XML to stdout.
  --render-unit      — print the systemd .service body to stdout.
  --render           — render whichever fits the platform.
  --heartbeat        — pretty-print the most recent heartbeat JSON.

Exit codes:
  0  — success / heartbeat-only shutdown
  1  — install / bootstrap failed / unsupported platform
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
from .systemd import (
    UnitConfig,
    install_unit,
    render_unit,
    uninstall_unit,
    unit_status,
)
from .windows import (
    WindowsTaskConfig,
    install_task,
    render_task_xml,
    task_status,
    uninstall_task,
)


def _detect_platform() -> str:
    """Return ``launchd`` on macOS, ``systemd`` on Linux, ``schtasks`` on Windows, else ``unsupported``."""

    if sys.platform == "darwin":
        return "launchd"
    if sys.platform.startswith("linux"):
        return "systemd"
    if sys.platform.startswith("win"):
        return "schtasks"
    return "unsupported"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.daemon",
        description="TARS background daemon (Wave 152 + Linux parity Wave 153).",
    )
    p.add_argument(
        "--install",
        action="store_true",
        help="Install the platform-native service (launchd plist on macOS, systemd user-unit on Linux).",
    )
    p.add_argument(
        "--uninstall",
        action="store_true",
        help="Stop + remove the platform-native service.",
    )
    p.add_argument(
        "--status",
        action="store_true",
        help="Print the service + heartbeat status and exit.",
    )
    p.add_argument(
        "--render-plist",
        action="store_true",
        help="Print the launchd plist XML to stdout (no side effects).",
    )
    p.add_argument(
        "--render-unit",
        action="store_true",
        help="Print the systemd .service body to stdout (no side effects).",
    )
    p.add_argument(
        "--render",
        action="store_true",
        help="Render whichever native service definition fits the current platform.",
    )
    p.add_argument(
        "--heartbeat",
        action="store_true",
        help="Print the latest heartbeat JSON and exit.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="With --install, write the file but skip the launchctl/systemctl bootstrap.",
    )
    p.add_argument(
        "--render-task",
        action="store_true",
        help="Print the Windows Task Scheduler XML to stdout (no side effects).",
    )
    p.add_argument(
        "--platform",
        choices=["launchd", "systemd", "schtasks", "auto"],
        default="auto",
        help="Override platform detection (default: auto).",
    )
    return p


def _print_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, indent=2, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _setup_logging()

    target_platform = args.platform if args.platform != "auto" else _detect_platform()

    # --render-plist (explicit launchd render)
    if args.render_plist:
        sys.stdout.write(render_plist(PlistConfig()))
        return 0

    # --render-unit (explicit systemd render)
    if args.render_unit:
        sys.stdout.write(render_unit(UnitConfig()))
        return 0

    # --render-task (explicit Windows task render)
    if args.render_task:
        sys.stdout.write(render_task_xml(WindowsTaskConfig()))
        return 0

    # --render (platform-auto)
    if args.render:
        if target_platform == "launchd":
            sys.stdout.write(render_plist(PlistConfig()))
            return 0
        if target_platform == "systemd":
            sys.stdout.write(render_unit(UnitConfig()))
            return 0
        if target_platform == "schtasks":
            sys.stdout.write(render_task_xml(WindowsTaskConfig()))
            return 0
        sys.stderr.write(
            f"Unsupported platform '{sys.platform}'. Pass --render-plist / --render-unit / --render-task explicitly.\n"
        )
        return 1

    # --status (platform-aware)
    if args.status:
        hb = read_heartbeat()
        if target_platform == "launchd":
            out = {"platform": "launchd", "service": plist_status(), "heartbeat": hb}
        elif target_platform == "systemd":
            out = {"platform": "systemd", "service": unit_status(), "heartbeat": hb}
        elif target_platform == "schtasks":
            out = {"platform": "schtasks", "service": task_status(), "heartbeat": hb}
        else:
            out = {"platform": "unsupported", "heartbeat": hb}
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

    # --install (platform-aware)
    if args.install:
        if target_platform == "launchd":
            result = install_plist(dry_run=args.dry_run)
        elif target_platform == "systemd":
            result = install_unit(dry_run=args.dry_run)
        elif target_platform == "schtasks":
            result = install_task(dry_run=args.dry_run)
        else:
            sys.stderr.write(
                f"Install not supported on platform '{sys.platform}'. "
                "Use --platform launchd|systemd|schtasks to force.\n"
            )
            return 1
        _print_json(result)
        return 0 if result.get("ok") else 1

    # --uninstall (platform-aware)
    if args.uninstall:
        if target_platform == "launchd":
            result = uninstall_plist()
        elif target_platform == "systemd":
            result = uninstall_unit()
        elif target_platform == "schtasks":
            result = uninstall_task()
        else:
            sys.stderr.write(
                f"Uninstall not supported on platform '{sys.platform}'.\n"
            )
            return 1
        _print_json(result)
        return 0 if result.get("ok") else 1

    # Default — run the loop (launchd/systemd both call this path).
    try:
        return asyncio.run(run_daemon())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
