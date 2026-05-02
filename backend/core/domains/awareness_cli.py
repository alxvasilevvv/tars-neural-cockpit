"""Command-line tool for inspecting domain pack awareness sources.

Usage::

    python -m backend.core.domains.awareness_cli list
    python -m backend.core.domains.awareness_cli list <slug>
    python -m backend.core.domains.awareness_cli snapshot <slug> <source_id>
    python -m backend.core.domains.awareness_cli snapshot-all <slug>

Operator parity with the planner CLI. Three jobs:

- **Operator scripting** — chain awareness snapshots into a cron
  job for cold-start morning briefs (e.g.
  ``traders.awareness.binance_ws.snapshot`` →
  ``traders.summarize_market`` from a single bash invocation).
- **Cold-start recovery** — when the HTTP layer is down, the CLI
  is the only path to inspect what awareness sources are
  configured / wired up.
- **Fleet rollouts** — shell out to TARS from a higher-level
  orchestrator without going through the FastAPI surface.

All subcommands print machine-friendly JSON to stdout (one
top-level object per call) so they pipe cleanly into ``jq``.
Pass ``--quiet`` to switch to compact (single-line) JSON.

Snapshots run inside a meeet ``trace_scope`` so the same
``awareness.snapshot.{requested,completed,failed}`` events the
HTTP route emits land in the local meeet buffer (the CLI is the
operator-facing equivalent of the cockpit's HTTP path).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import all_packs, get_pack
from backend.core.meeet import (
    get_client,
    thread_id_scope,
    trace_scope,
)


# ---------------------------------------------------------------------------
# JSON output helper
# ---------------------------------------------------------------------------


def _emit(args: argparse.Namespace, body: dict[str, Any]) -> int:
    """Print ``body`` as JSON; return the conventional exit code.

    Exit code mapping: 0 when ``body["ok"]`` is truthy, 1 otherwise.
    Tests rely on the exit code so non-zero shells out cleanly in
    cron / Make targets.
    """

    indent = None if getattr(args, "quiet", False) else 2
    print(json.dumps(body, indent=indent, sort_keys=False))
    return 0 if body.get("ok", False) else 1


def _err(reason: str, *, message: str | None = None, **extra: Any) -> dict[str, Any]:
    payload = {"ok": False, "reason": reason}
    if message:
        payload["message"] = message
    payload.update(extra)
    return payload


def _ms_since(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 3)


def _source_envelope(src: Any) -> dict[str, Any]:
    """Mirror the HTTP ``GET /api/domains/<slug>/awareness`` per-row shape."""

    return {
        "id": src.id,
        "name": src.name,
        "description": src.description,
        "kind": src.kind,
        "config": dict(src.config),
        "live": src.fetcher is not None,
    }


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


async def _cmd_list(args: argparse.Namespace) -> int:
    if args.slug:
        pack = get_pack(args.slug)
        if pack is None:
            return _emit(args, _err("domain_not_found", slug=args.slug))
        sources = list(pack.awareness())
        return _emit(
            args,
            {
                "ok": True,
                "slug": args.slug,
                "count": len(sources),
                "live_count": sum(1 for s in sources if s.fetcher is not None),
                "awareness": [_source_envelope(s) for s in sources],
            },
        )

    # No slug → catalogue every pack.
    packs_out: list[dict[str, Any]] = []
    for pack in all_packs():
        sources = list(pack.awareness())
        packs_out.append(
            {
                "slug": pack.manifest.slug,
                "name": pack.manifest.name,
                "count": len(sources),
                "live_count": sum(1 for s in sources if s.fetcher is not None),
                "awareness": [_source_envelope(s) for s in sources],
            },
        )
    return _emit(
        args,
        {
            "ok": True,
            "count": len(packs_out),
            "packs": packs_out,
        },
    )


async def _snapshot_one(
    pack: Any,
    src: Any,
    *,
    thread_id: str | None,
    parent_trace: str | None,
) -> dict[str, Any]:
    """Materialise one source inside a meeet trace scope.

    Mirrors the body of
    :func:`web_extras.routers.domains.awareness_snapshot` so the
    CLI shares the same emitted-event surface (cockpit dashboards
    that count ``awareness.snapshot.*`` events will see CLI
    invocations the same as HTTP ones).
    """

    if src.fetcher is None:
        return {
            "ok": False,
            "slug": pack.manifest.slug,
            "source_id": src.id,
            "kind": src.kind,
            "error": "fetcher_unavailable",
            "hint": (
                "this source is config-only (likely a webhook receiver); "
                "no live snapshot is implemented yet"
            ),
        }

    client = get_client()
    started_at = time.perf_counter()
    with thread_id_scope(thread_id), trace_scope(
        parent=parent_trace,
        route="cli",
    ) as trace_id:
        await client.emit(
            "awareness.snapshot.requested",
            {
                "slug": pack.manifest.slug,
                "source_id": src.id,
                "kind": src.kind,
            },
        )
        try:
            data = await src.fetcher(dict(src.config))
        except Exception as exc:
            await client.emit(
                "awareness.snapshot.failed",
                {
                    "slug": pack.manifest.slug,
                    "source_id": src.id,
                    "error": str(exc),
                    "took_ms": _ms_since(started_at),
                },
            )
            return {
                "ok": False,
                "slug": pack.manifest.slug,
                "source_id": src.id,
                "kind": src.kind,
                "trace_id": trace_id,
                "took_ms": _ms_since(started_at),
                "error": str(exc),
            }

        took_ms = _ms_since(started_at)
        await client.emit(
            "awareness.snapshot.completed",
            {
                "slug": pack.manifest.slug,
                "source_id": src.id,
                "took_ms": took_ms,
                "ok": (
                    bool(data.get("ok", True))
                    if isinstance(data, dict)
                    else True
                ),
            },
        )
        return {
            "ok": True,
            "slug": pack.manifest.slug,
            "source_id": src.id,
            "kind": src.kind,
            "trace_id": trace_id,
            "took_ms": took_ms,
            "data": data,
        }


async def _cmd_snapshot(args: argparse.Namespace) -> int:
    pack = get_pack(args.slug)
    if pack is None:
        return _emit(args, _err("domain_not_found", slug=args.slug))
    src = pack.find_awareness(args.source_id)
    if src is None:
        return _emit(
            args,
            _err(
                "awareness_not_found",
                slug=args.slug,
                source_id=args.source_id,
            ),
        )
    out = await _snapshot_one(
        pack,
        src,
        thread_id=args.thread_id,
        parent_trace=args.trace_id,
    )
    return _emit(args, out)


async def _cmd_snapshot_all(args: argparse.Namespace) -> int:
    """Materialise every source on a pack that has a fetcher.

    Skipped sources (no fetcher) appear in the ``skipped`` array
    rather than as failures so the operator can tell the
    "config-only" case apart from a real fetch error. Overall
    ``ok`` is ``true`` only when every fetched source returned
    ``ok=true``; skipped sources don't fail the envelope.
    """

    pack = get_pack(args.slug)
    if pack is None:
        return _emit(args, _err("domain_not_found", slug=args.slug))

    fetched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    overall_ok = True
    for src in pack.awareness():
        if src.fetcher is None:
            skipped.append(
                {
                    "source_id": src.id,
                    "kind": src.kind,
                    "reason": "fetcher_unavailable",
                },
            )
            continue
        result = await _snapshot_one(
            pack,
            src,
            thread_id=args.thread_id,
            parent_trace=args.trace_id,
        )
        fetched.append(result)
        if not result.get("ok", False):
            overall_ok = False

    return _emit(
        args,
        {
            "ok": overall_ok,
            "slug": args.slug,
            "fetched_count": len(fetched),
            "skipped_count": len(skipped),
            "fetched": fetched,
            "skipped": skipped,
        },
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.domains.awareness_cli",
        description=(
            "Inspect and materialise domain pack awareness sources "
            "from the shell."
        ),
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Print compact JSON (no indent). Defaults to indented.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser(
        "list", help="List awareness sources (all packs or one)."
    )
    p_list.add_argument(
        "slug",
        nargs="?",
        default=None,
        help="Optional pack slug. When omitted, lists every pack.",
    )

    p_snap = sub.add_parser(
        "snapshot",
        help="Materialise one awareness source by id.",
    )
    p_snap.add_argument("slug", help="Pack slug.")
    p_snap.add_argument("source_id", help="Awareness source id.")
    p_snap.add_argument(
        "--thread-id",
        default=None,
        help="Optional chat thread id to bind the trace to.",
    )
    p_snap.add_argument(
        "--trace-id",
        default=None,
        help=(
            "Optional parent trace id (continues an upstream trace "
            "from meeet.world or another TARS surface)."
        ),
    )

    p_snap_all = sub.add_parser(
        "snapshot-all",
        help="Materialise every fetcher-bearing source on one pack.",
    )
    p_snap_all.add_argument("slug", help="Pack slug.")
    p_snap_all.add_argument(
        "--thread-id",
        default=None,
        help="Optional chat thread id to bind the trace to.",
    )
    p_snap_all.add_argument(
        "--trace-id",
        default=None,
        help="Optional parent trace id.",
    )

    return p


_DISPATCH = {
    "list": _cmd_list,
    "snapshot": _cmd_snapshot,
    "snapshot-all": _cmd_snapshot_all,
}


async def _run(args: argparse.Namespace) -> int:
    handler = _DISPATCH.get(args.command)
    if handler is None:  # pragma: no cover - argparse guards this
        return _emit(args, _err("unknown_command", command=args.command))
    return await handler(args)


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
