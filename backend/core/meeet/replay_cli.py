"""Command-line replay tool for the meeet durable buffer.

Usage::

    python -m backend.core.meeet.replay_cli --limit 200
    python -m backend.core.meeet.replay_cli --stats
    python -m backend.core.meeet.replay_cli --export /tmp/events.jsonl
    # Per-run dump (one plan execution → one JSONL):
    python -m backend.core.meeet.replay_cli \\
        --export /tmp/run.jsonl --trace-id trc_abc123
    # Force-repush every event for one trace, regardless of ``pushed``:
    python -m backend.core.meeet.replay_cli --repush-trace trc_abc123

Reads the same env vars the host uses (``MEEET_INGEST_URL``,
``MEEET_API_KEY``, ``MEEET_STORE_PATH``). Safe to run while the host
process is up — sqlite WAL handles concurrent readers.

The CLI is the cold-start recovery story: if the host is down or the
ingest contract changes shape, an operator can dump the local buffer,
patch it, and re-push from this tool. Per-run scoping (``--trace-id``)
lets fleet ops audit / backfill a single plan execution without
shoveling the entire buffer; the ``planner-replay-run`` Make target
wraps it so cron jobs can name the file by ``<plan_id>``.
``--repush-trace`` is the follow-up that actually re-emits the
matching rows upstream (regardless of whether they were already
``pushed=1``), so an operator can recover from a meeet ingest
contract-bump without hand-editing SQLite.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from .client import MeeetClient
from .config import load_config
from .store import MeeetStore


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.meeet.replay_cli",
        description="Inspect or flush the local meeet event buffer.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max events processed in one go (default 200).",
    )
    p.add_argument(
        "--stats",
        action="store_true",
        help="Print store stats and bridge config; do not push.",
    )
    p.add_argument(
        "--export",
        type=str,
        default=None,
        help="Dump newest-first events to JSONL at the given path; do not push.",
    )
    p.add_argument(
        "--since",
        type=float,
        default=None,
        help="Filter events to ts >= since (unix seconds). Used by --export.",
    )
    p.add_argument(
        "--kind",
        type=str,
        default=None,
        help="Filter events to this kind. Used by --export.",
    )
    p.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Filter events to this session id. Used by --export.",
    )
    p.add_argument(
        "--trace-id",
        type=str,
        default=None,
        help=(
            "Filter events to this trace id (a single plan run, a "
            "single SSE subscription, etc.). Used by --export. "
            "Combine with the Make target ``planner-replay-run "
            "ARGS=\"<plan_id> <run_trace>\"`` to dump exactly one "
            "run's events for backfill / audit."
        ),
    )
    p.add_argument(
        "--repush-trace",
        type=str,
        default=None,
        help=(
            "Force-push every event for one trace upstream, "
            "regardless of the ``pushed`` flag. Use after a meeet "
            "ingest outage / contract bump when you need to "
            "re-emit one run's events for billing backfill or "
            "audit. Mutually exclusive with --export and --stats. "
            "Returns the standard {pushed, failed, remaining} "
            "envelope plus a ``trace_id`` echo. Wired into the "
            "Make target ``planner-repush-run ARGS=\"<run_trace>\"``."
        ),
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Print machine-friendly JSON only (no progress lines).",
    )
    return p


async def _run(args: argparse.Namespace) -> int:
    config = load_config()
    store = MeeetStore()
    client = MeeetClient(config=config, store=store)

    if args.stats:
        out = await client.health()
        print(json.dumps(out, indent=2 if not args.quiet else None))
        return 0

    if args.repush_trace:
        # Subcommand precedence: stats > repush > export > replay.
        # We already short-circuited stats above; repush comes
        # before export so an operator passing both flags by
        # mistake gets the more meaningful action (pushing).
        out = await client.repush_trace(
            args.repush_trace, limit=max(1, int(args.limit))
        )
        print(json.dumps(out, indent=2 if not args.quiet else None))
        return 0 if out.get("failed", 0) == 0 else 1

    if args.export:
        events = await store.list_events(
            limit=max(1, int(args.limit)),
            since=args.since,
            kind=args.kind,
            session_id=args.session_id,
            trace_id=args.trace_id,
        )
        with open(args.export, "w", encoding="utf-8") as fh:
            for ev in reversed(events):  # oldest first
                body: dict[str, Any] = {
                    "ts": ev.ts,
                    "trace_id": ev.trace_id,
                    "session_id": ev.session_id,
                    "route": ev.route,
                    "kind": ev.kind,
                    "source": ev.source,
                    "contract_version": ev.contract_version,
                    "payload": ev.payload,
                    "pushed": ev.pushed,
                    "pushed_at": ev.pushed_at,
                    "last_error": ev.last_error,
                }
                fh.write(json.dumps(body, separators=(",", ":")) + "\n")
        if not args.quiet:
            print(
                f"exported {len(events)} events to {args.export}",
                file=sys.stderr,
            )
        return 0

    out = await client.replay_unpushed(limit=max(1, int(args.limit)))
    print(json.dumps(out, indent=2 if not args.quiet else None))
    return 0 if out.get("failed", 0) == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
