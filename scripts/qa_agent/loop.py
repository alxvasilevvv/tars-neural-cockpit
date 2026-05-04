"""
qa_agent.loop — autonomous QA loop wrapped around qa_agent.runner.

Runs the full probe suite on a configurable interval, persists each
run's JSON report under ``.qa-runs/`` (override with ``QA_RUN_DIR``),
and emits a per-run summary line so cron / launchd / systemd journals
can surface the result without parsing the JSON.

Stdlib-only, designed to run from:

  - macOS local:        ``python -m scripts.qa_agent.loop --interval 300``
  - GH Actions:         single shot via ``--once``
  - launchd / systemd:  long-running with ``--interval N``

Exit codes:
  0   loop ran cleanly (or ``--once`` and all critical probes passed)
  1   ``--once`` and at least one critical probe failed
  130 SIGINT (Ctrl-C) — clean shutdown of a running loop
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .env_resolve import resolved_ingest_api_key
from .probes import Context, Probe
from .runner import render_json, render_text, run_all


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _write_run(report_dir: Path, probes: list[Probe], ctx: Context) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"qa-run-{_ts()}.json"
    payload = json.loads(render_json(probes, ctx))
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Also keep a stable "latest" pointer so external dashboards can poll.
    latest = report_dir / "latest.json"
    latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _summary_line(probes: Iterable[Probe], ctx: Context, run_path: Path) -> str:
    counts: Counter[str] = Counter(p.status for p in probes)
    return (
        f"[qa_loop] {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"target={ctx.tars_base} "
        f"pass={counts['pass']} fail={counts['fail']} warn={counts['warn']} "
        f"skip={counts['skip']} "
        f"out={run_path}"
    )


def _emit_meeet_event(probes: list[Probe], ctx: Context) -> None:
    """Best-effort heartbeat: emit a `qa_agent.run.completed` event via the
    meeet client when MEEET_INGEST_URL is set. Never raises."""

    try:
        # Local import to keep the loop usable from a fresh checkout
        # (the meeet bridge is part of the backend; tools shouldn't crash
        # if it's missing).
        from backend.core.meeet import get_client, trace_scope
    except Exception:
        return

    counts: Counter[str] = Counter(p.status for p in probes)
    payload = {
        "agent": "tars-qa-agent",
        "agent_version": "1.0.0",
        "target": ctx.tars_base,
        "summary": {
            "pass": counts["pass"],
            "fail": counts["fail"],
            "warn": counts["warn"],
            "skip": counts["skip"],
            "total": len(probes),
        },
        "fails": [p.name for p in probes if p.status == "fail"],
    }

    client = get_client()
    if not getattr(client.config, "enabled", False):
        return

    import asyncio

    async def _go() -> None:
        with trace_scope():
            await client.emit("qa_agent.run.completed", payload)

    try:
        asyncio.run(_go())
    except RuntimeError:
        # Already inside a running loop (e.g. nested); skip silently.
        pass
    except Exception:
        # Heartbeat must never crash the loop.
        pass


_STOP = False


def _install_sigint_handler() -> None:
    def _handler(_signum, _frame):  # type: ignore[no-untyped-def]
        global _STOP
        _STOP = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qa_agent.loop",
        description="Autonomous QA loop for TARS — runs probes on an interval.",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("TARS_BASE", "https://tars.meeet.world"),
        help="Base URL for TARS subdomain (default: env TARS_BASE or prod)",
    )
    parser.add_argument(
        "--core-bridge",
        default=os.environ.get(
            "CORE_BRIDGE_URL",
            "https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge",
        ),
        help="core-bridge endpoint URL",
    )
    parser.add_argument(
        "--tars-supabase",
        default=os.environ.get(
            "TARS_SUPABASE_URL", "https://hhpaukjobskcwkxbgecl.supabase.co"
        ),
        help="TARS Supabase project URL",
    )
    parser.add_argument(
        "--bridge-secret",
        default=os.environ.get("BRIDGE_SHARED_SECRET", "") or None,
        help="Shared secret for authenticated core-bridge probes",
    )
    parser.add_argument(
        "--core-supabase",
        default=os.environ.get(
            "CORE_SUPABASE_URL", "https://zujrmifaabkletgnpoyw.supabase.co"
        ),
        help="Core (meeet.world) Supabase project URL — used for tars-ingest heartbeat",
    )
    parser.add_argument(
        "--ingest-api-key",
        default=None,
        help="Bearer / x-api-key for tars-ingest (default: TARS_INGEST_API_KEY or MEEET_API_KEY)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("QA_LOOP_INTERVAL_S", "300")),
        help="Seconds between runs (default: 300; 0 = no sleep, run continuously)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single iteration and exit (alias for --interval 0 --max-runs 1)",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=int(os.environ.get("QA_LOOP_MAX_RUNS", "0")),
        help="Stop after N runs (0 = run forever)",
    )
    parser.add_argument(
        "--report-dir",
        default=os.environ.get("QA_RUN_DIR", ".qa-runs"),
        help="Where to write per-run JSON reports (default: .qa-runs/)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-run text reports; still writes JSON + summary line",
    )
    args = parser.parse_args(argv)
    ingest_key = resolved_ingest_api_key(args.ingest_api_key)

    ctx = Context(
        tars_base=args.target.rstrip("/"),
        core_bridge_url=args.core_bridge.rstrip("/"),
        tars_supabase_url=args.tars_supabase.rstrip("/"),
        core_supabase_url=args.core_supabase.rstrip("/"),
        tars_ingest_api_key=ingest_key,
        bridge_shared_secret=args.bridge_secret,
    )

    _install_sigint_handler()
    report_dir = Path(args.report_dir).expanduser()

    runs = 0
    last_exit = 0
    while True:
        probes = run_all(ctx)
        run_path = _write_run(report_dir, probes, ctx)

        if not args.quiet:
            print(render_text(probes, ctx, sys.stdout.isatty()), flush=True)
        print(_summary_line(probes, ctx, run_path), flush=True)

        _emit_meeet_event(probes, ctx)

        fails = sum(1 for p in probes if p.status == "fail")
        last_exit = 0 if fails == 0 else 1
        runs += 1

        if args.once or (args.max_runs > 0 and runs >= args.max_runs):
            return last_exit
        if _STOP:
            return 130

        # Reset transient context flags before next iteration so probes can
        # recover from a previous DNS hiccup.
        ctx.skip_subdomain = False
        ctx.skip_authenticated = False

        if args.interval <= 0:
            continue
        # Sleep in 1s slices so SIGINT/SIGTERM lands fast.
        slept = 0.0
        while slept < args.interval and not _STOP:
            time.sleep(min(1.0, args.interval - slept))
            slept += 1.0
        if _STOP:
            return 130


if __name__ == "__main__":
    sys.exit(main())
