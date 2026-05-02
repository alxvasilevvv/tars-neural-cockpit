"""Command-line tool for inspecting and executing TARS playbooks.

Usage::

    python -m backend.core.playbooks.cli list
    python -m backend.core.playbooks.cli show <id>
    python -m backend.core.playbooks.cli run <id>
        [--mode confirm|autopilot|dry_run]
        [--context '<json>'] [--context-file <path>]
        [--thread-id <id>] [--trace-id <id>]
    python -m backend.core.playbooks.cli validate <id>
    python -m backend.core.playbooks.cli validate-all
    python -m backend.core.playbooks.cli reload

Operator parity with the planner / awareness CLIs. Three jobs:

- **Cron-driven brief execution** — the canonical
  ``traders.morning_check`` playbook can now be wired into a
  bare ``cron`` job (no FastAPI process required) and the
  emitted ``playbook.*`` events still land in the local meeet
  buffer the cockpit reads from.
- **Authoring loop** — ``validate`` / ``validate-all`` give a
  fast feedback signal when hand-editing
  ``playbooks/<pack>/<name>.json`` files; the strict validator
  surfaces every issue in one pass instead of bouncing on
  each ``run`` attempt.
- **Cold-start recovery** — when the FastAPI app is wedged,
  the CLI is the only path to materialise a multi-step action
  chain.

All subcommands print machine-friendly JSON to stdout (one
top-level object per call) so they pipe cleanly into ``jq``.
``--quiet`` switches to compact (single-line) JSON. Exit code
mirrors the body's ``ok`` field (``0`` on truthy, ``1`` else)
so cron scripts running ``set -e`` halt on the first failure.

Trace propagation: ``run`` enters a ``trace_scope(parent=...)``
identical to the HTTP route in
``web_extras/routers/playbooks.py``, so cockpit-side trace
search threads CLI invocations through the same UI as HTTP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.meeet import thread_id_scope, trace_scope
from backend.core.playbooks import (
    get_playbook,
    list_playbooks,
    reset_loader_cache,
    run_playbook,
    validate_payload,
)
from backend.core.policy import resolve_mode


# ---------------------------------------------------------------------------
# JSON output helper
# ---------------------------------------------------------------------------


def _emit(args: argparse.Namespace, body: dict[str, Any]) -> int:
    """Print ``body`` as JSON; return the conventional exit code.

    Exit code mapping: ``0`` when ``body["ok"]`` is truthy, ``1``
    otherwise. Cron scripts running ``set -e`` rely on this so a
    typo halts the pipeline instead of silently succeeding.
    """

    indent = None if getattr(args, "quiet", False) else 2
    print(json.dumps(body, indent=indent, sort_keys=False, default=str))
    return 0 if body.get("ok", False) else 1


def _err(reason: str, *, message: str | None = None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "reason": reason}
    if message:
        payload["message"] = message
    payload.update(extra)
    return payload


def _ms_since(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 3)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


async def _cmd_list(args: argparse.Namespace) -> int:
    items = list(list_playbooks(refresh=getattr(args, "refresh", False)))
    rows = [pb.to_dict() for pb in items]
    if args.pack:
        rows = [r for r in rows if (r.get("pack") or "") == args.pack]
    return _emit(
        args,
        {
            "ok": True,
            "count": len(rows),
            "playbooks": rows,
        },
    )


async def _cmd_show(args: argparse.Namespace) -> int:
    pb = get_playbook(args.playbook_id, refresh=getattr(args, "refresh", False))
    if pb is None:
        return _emit(args, _err("playbook_not_found", playbook_id=args.playbook_id))
    return _emit(args, {"ok": True, "playbook": pb.to_dict()})


def _resolve_context(args: argparse.Namespace) -> tuple[dict[str, Any] | None, str | None]:
    """Parse the ``--context`` / ``--context-file`` flags.

    Returns ``(context_dict, error_reason)``. On any parse problem
    returns ``(None, "<reason>")`` so the caller can short-circuit
    with a clean error envelope.

    Precedence (when both are supplied): ``--context-file`` wins so
    a cron job baking a sidecar JSON file can be overridden ad-hoc
    on the CLI without retyping the long string. We surface a
    warning in the error envelope when both are set so the operator
    isn't silently surprised.
    """

    raw: str | None = None
    if args.context_file:
        try:
            raw = open(args.context_file, "r", encoding="utf-8").read()
        except OSError as exc:
            return None, f"context_file_unreadable: {exc}"
    elif args.context:
        raw = args.context

    if raw is None:
        return {}, None

    try:
        ctx = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"context_not_json: {exc}"

    if not isinstance(ctx, dict):
        return None, "context_must_be_object"

    return ctx, None


async def _cmd_run(args: argparse.Namespace) -> int:
    pb = get_playbook(args.playbook_id)
    if pb is None:
        return _emit(args, _err("playbook_not_found", playbook_id=args.playbook_id))

    context, ctx_err = _resolve_context(args)
    if ctx_err is not None:
        return _emit(args, _err("invalid_context", message=ctx_err))

    mode = resolve_mode(header=None, request_arg=args.mode)

    started_at = time.perf_counter()
    with thread_id_scope(args.thread_id), trace_scope(
        parent=args.trace_id,
        route="cli",
    ) as trace_id:
        try:
            result = await run_playbook(pb, context=context, mode=mode)
        except Exception as exc:
            return _emit(
                args,
                _err(
                    "playbook_run_failed",
                    message=str(exc),
                    playbook_id=args.playbook_id,
                    trace_id=trace_id,
                    took_ms=_ms_since(started_at),
                ),
            )

    took_ms = _ms_since(started_at)
    # `run_playbook` already returns its own `ok` / `trace_id` /
    # `mode` envelope; layer on the CLI-specific timing field
    # without overriding the runner's authoritative `trace_id`.
    out = dict(result)
    out.setdefault("trace_id", trace_id)
    out.setdefault("playbook_id", args.playbook_id)
    out["took_ms"] = took_ms
    return _emit(args, out)


async def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate a single playbook from disk by id.

    Mirrors the HTTP ``POST /api/playbooks/_validate`` flow with
    the ``{"id": ...}`` body — re-reads the playbook to dodge
    stale-cache surprises (operator just edited the file).
    """

    pb = get_playbook(args.playbook_id, refresh=True)
    if pb is None:
        return _emit(args, _err("playbook_not_found", playbook_id=args.playbook_id))
    result = validate_payload(pb.to_dict())
    return _emit(
        args,
        {
            **result.to_dict(),
            "id": pb.id,
            "playbook_id": pb.id,
        },
    )


async def _cmd_validate_all(args: argparse.Namespace) -> int:
    """Strict-validate every playbook on disk.

    Same shape as ``GET /api/playbooks/_validate_all`` so the CLI
    output is drop-in for cockpit dashboards / CI pipes. Designed
    to be wired into the control-tower gate as
    ``make playbooks-validate-all``.
    """

    items = list(list_playbooks(refresh=True))
    rows: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0
    for pb in items:
        result = validate_payload(pb.to_dict())
        rows.append({"id": pb.id, **result.to_dict()})
        error_count += len(result.errors)
        warning_count += len(result.warnings)
    return _emit(
        args,
        {
            "ok": all(r["ok"] for r in rows),
            "playbook_count": len(rows),
            "error_count": error_count,
            "warning_count": warning_count,
            "playbooks": rows,
        },
    )


async def _cmd_reload(args: argparse.Namespace) -> int:
    reset_loader_cache()
    items = list(list_playbooks(refresh=True))
    return _emit(
        args,
        {
            "ok": True,
            "count": len(items),
            "ids": [pb.id for pb in items],
        },
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.playbooks.cli",
        description=(
            "Inspect, validate and execute TARS playbooks from the shell. "
            "Mirrors the FastAPI surface in web_extras/routers/playbooks.py."
        ),
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Print compact JSON (no indent). Defaults to indented.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List playbooks (optionally filtered by pack).")
    p_list.add_argument(
        "--pack",
        default=None,
        help="Filter to one pack folder (e.g. 'traders').",
    )
    p_list.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-scan of the playbooks directory before listing.",
    )

    p_show = sub.add_parser("show", help="Show one playbook's full definition.")
    p_show.add_argument("playbook_id", help="Playbook id, e.g. 'traders.morning_check'.")
    p_show.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-scan before lookup (catches just-edited files).",
    )

    p_run = sub.add_parser(
        "run",
        help=(
            "Execute a playbook. Wraps backend.core.playbooks.run_playbook "
            "with the same trace + policy semantics as the HTTP route."
        ),
    )
    p_run.add_argument("playbook_id", help="Playbook id to execute.")
    p_run.add_argument(
        "--mode",
        default=None,
        help=(
            "Policy mode: confirm | autopilot | dry_run. Defaults to the "
            "TARS_POLICY_MODE env var if set, else 'confirm'."
        ),
    )
    p_run.add_argument(
        "--context",
        default=None,
        help=(
            "JSON object string passed as initial context, e.g. "
            "--context '{\"basket\":[\"BTC\",\"ETH\"]}'."
        ),
    )
    p_run.add_argument(
        "--context-file",
        default=None,
        help=(
            "Path to a JSON file containing the initial context. Wins "
            "over --context if both are supplied."
        ),
    )
    p_run.add_argument(
        "--thread-id",
        default=None,
        help="Optional chat thread id to bind the trace to.",
    )
    p_run.add_argument(
        "--trace-id",
        default=None,
        help=(
            "Optional parent trace id (continues an upstream trace from "
            "meeet.world or another TARS surface)."
        ),
    )

    p_validate = sub.add_parser(
        "validate",
        help="Strict-validate one playbook by id (re-reads disk).",
    )
    p_validate.add_argument("playbook_id", help="Playbook id to validate.")

    sub.add_parser(
        "validate-all",
        help="Strict-validate every playbook on disk (CI gate).",
    )

    sub.add_parser(
        "reload",
        help="Reset the loader cache and re-scan the playbooks directory.",
    )

    return p


_DISPATCH = {
    "list": _cmd_list,
    "show": _cmd_show,
    "run": _cmd_run,
    "validate": _cmd_validate,
    "validate-all": _cmd_validate_all,
    "reload": _cmd_reload,
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
