"""Command-line tool for the planner.

Usage::

    python -m backend.core.planner.cli list [--status proposed] [--limit 20]
    python -m backend.core.planner.cli show <plan_id>
    python -m backend.core.planner.cli runs <plan_id>
    python -m backend.core.planner.cli stats
    python -m backend.core.planner.cli synthesize <goal> [--pinned-pack <slug>] [--thread-id <id>]
    python -m backend.core.planner.cli approve <plan_id>
    python -m backend.core.planner.cli reject  <plan_id>
    python -m backend.core.planner.cli run     <plan_id> [--mode autopilot|confirm|dry_run]
    python -m backend.core.planner.cli abort   <plan_id>
    python -m backend.core.planner.cli clone   <plan_id> [--thread-id <id>] [--goal <override>] [--approve] [--run [--mode autopilot|confirm|dry_run]]
    python -m backend.core.planner.cli delete  <plan_id> [--yes]

Reads the same env vars the host uses (``TARS_PLANNER_DB_PATH``,
``MEEET_STORE_PATH``, ``TARS_POLICY_MODE``, ``MEEET_INGEST_URL``)
and shares the SQLite WAL DBs with the running host process —
safe to run while the cockpit / API is up.

Why a CLI? Three jobs:

- **Operator scripting**: chain ``synthesize`` + ``approve`` +
  ``run`` in a one-shot bash invocation for cron jobs.
- **Cold-start recovery**: when the HTTP layer is down, the CLI
  is the only path to inspect / reset planner state.
- **Fleet rollouts**: shell out to TARS from a higher-level
  orchestrator without going through the FastAPI surface.

All subcommands print machine-friendly JSON to stdout (one
top-level object per call) so they pipe cleanly into ``jq``.
Pass ``--quiet`` to suppress the trailing human progress line on
stderr (default is to print it for interactive use).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import all_packs
from backend.core.meeet import thread_id_scope, trace_scope
from backend.core.playbooks import list_playbooks
from backend.core.policy import PolicyMode, resolve_mode

from .history import reconstruct_runs_async
from .runner import PlanRunError, PlanRunner, get_run_registry
from .store import get_planner_store
from .synthesizer import (
    PlannerError,
    PlannerSynthesisRequest,
    synthesize_plan,
)
from .types import Plan, PlanStatus


_SNAPSHOT_KEYWORDS = ("snapshot", "summarize", "list", "brief", "status")


def _is_snapshot_action(action_id: str, destructive: bool) -> bool:
    if destructive:
        return False
    aid = (action_id or "").lower()
    return any(kw in aid for kw in _SNAPSHOT_KEYWORDS)


def _enumerate_actions() -> tuple[tuple[str, str, bool, bool], ...]:
    out: list[tuple[str, str, bool, bool]] = []
    for pack in all_packs():
        slug = pack.manifest.slug
        for spec in pack.actions():
            out.append(
                (
                    slug,
                    spec.id,
                    bool(getattr(spec, "destructive", False)),
                    _is_snapshot_action(
                        spec.id, bool(getattr(spec, "destructive", False))
                    ),
                )
            )
    return tuple(out)


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


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


async def _cmd_list(args: argparse.Namespace) -> int:
    status_enum: PlanStatus | None = None
    if args.status:
        try:
            status_enum = PlanStatus(args.status.lower())
        except ValueError:
            return _emit(
                args,
                _err(
                    "unknown_status",
                    message=f"unknown status {args.status!r}",
                    allowed=[s.value for s in PlanStatus],
                ),
            )
    plans = await get_planner_store().list(
        status=status_enum,
        thread_id=args.thread_id,
        limit=args.limit,
    )
    return _emit(
        args,
        {
            "ok": True,
            "count": len(plans),
            "plans": [p.to_dict() for p in plans],
        },
    )


async def _cmd_show(args: argparse.Namespace) -> int:
    plan = await get_planner_store().get(args.plan_id)
    if plan is None:
        return _emit(args, _err("plan_not_found", plan_id=args.plan_id))
    return _emit(args, {"ok": True, "plan": plan.to_dict()})


async def _cmd_runs(args: argparse.Namespace) -> int:
    plan = await get_planner_store().get(args.plan_id)
    if plan is None:
        return _emit(args, _err("plan_not_found", plan_id=args.plan_id))
    runs = await reconstruct_runs_async(args.plan_id, limit=args.limit)
    in_flight = sum(1 for r in runs if r.status == "running")
    return _emit(
        args,
        {
            "ok": True,
            "plan_id": args.plan_id,
            "count": len(runs),
            "in_flight": in_flight,
            "runs": [r.to_dict() for r in runs],
        },
    )


async def _cmd_stats(args: argparse.Namespace) -> int:
    stats = await get_planner_store().stats()
    return _emit(args, {"ok": True, **stats})


async def _cmd_synthesize(args: argparse.Namespace) -> int:
    goal = (args.goal or "").strip()
    if not goal:
        return _emit(args, _err("empty_goal"))

    req = PlannerSynthesisRequest(
        goal=goal,
        thread_id=args.thread_id,
        pinned_pack=args.pinned_pack,
        available_playbooks=tuple(list_playbooks()),
        available_actions=_enumerate_actions(),
    )

    with thread_id_scope(args.thread_id), trace_scope() as tid:
        try:
            plan = synthesize_plan(req)
        except PlannerError as exc:
            return _emit(
                args,
                _err(exc.reason, message=str(exc), goal=goal),
            )

        # Persist with the live trace_id for cross-event correlation.
        plan = Plan(
            id=plan.id,
            goal=plan.goal,
            steps=plan.steps,
            status=plan.status,
            rationale=plan.rationale,
            model=plan.model,
            pack_slug=plan.pack_slug,
            playbook_id=plan.playbook_id,
            thread_id=plan.thread_id,
            trace_id=tid,
            estimated_cost_usd=plan.estimated_cost_usd,
        )
        stored = await get_planner_store().insert(plan)
    return _emit(args, {"ok": True, "plan": stored.to_dict()})


async def _cmd_set_status(
    args: argparse.Namespace, *, target: PlanStatus
) -> int:
    """Shared body for ``approve`` / ``reject`` (operator transitions)."""

    store = get_planner_store()
    existing = await store.get(args.plan_id)
    if existing is None:
        return _emit(args, _err("plan_not_found", plan_id=args.plan_id))
    if existing.status.is_terminal():
        return _emit(
            args,
            _err(
                f"plan_already_{existing.status.value}",
                plan_id=args.plan_id,
                status=existing.status.value,
            ),
        )
    updated = await store.set_status(args.plan_id, target)
    if updated is None:
        return _emit(args, _err("status_update_failed"))
    return _emit(args, {"ok": True, "plan": updated.to_dict()})


async def _cmd_approve(args: argparse.Namespace) -> int:
    return await _cmd_set_status(args, target=PlanStatus.APPROVED)


async def _cmd_reject(args: argparse.Namespace) -> int:
    return await _cmd_set_status(args, target=PlanStatus.REJECTED)


async def _cmd_run(args: argparse.Namespace) -> int:
    store = get_planner_store()
    plan = await store.get(args.plan_id)
    if plan is None:
        return _emit(args, _err("plan_not_found", plan_id=args.plan_id))

    mode = resolve_mode(header=None, request_arg=args.mode or None)
    with thread_id_scope(plan.thread_id), trace_scope(parent=plan.trace_id):
        try:
            result = await PlanRunner().run(args.plan_id, mode=mode)
        except PlanRunError as exc:
            return _emit(
                args,
                _err(exc.reason, message=str(exc), plan_id=args.plan_id),
            )
    return _emit(args, {"ok": result["ok"], "run": result})


async def _cmd_abort(args: argparse.Namespace) -> int:
    registry = get_run_registry()
    if not registry.is_running(args.plan_id):
        return _emit(args, _err("plan_not_running", plan_id=args.plan_id))
    flipped = registry.abort(args.plan_id)
    return _emit(
        args, {"ok": flipped, "plan_id": args.plan_id, "aborted": flipped}
    )


async def _cmd_clone(args: argparse.Namespace) -> int:
    """Snapshot ``plan_id`` as a fresh ``proposed`` plan.

    With ``--approve`` the clone is also flipped to ``approved``
    in the same call. With ``--run`` (which implies ``--approve``)
    the clone is then dispatched through :class:`PlanRunner` so
    operators can do a one-shot rerun without juggling three
    subcommands.
    """

    from backend.core.meeet import get_client

    store = get_planner_store()
    original = await store.get(args.plan_id)
    if original is None:
        return _emit(args, _err("plan_not_found", plan_id=args.plan_id))
    rebound_thread = (args.thread_id or "").strip() or None
    goal_override = (args.goal or "").strip() or None
    do_approve = bool(getattr(args, "approve", False) or getattr(args, "run", False))
    do_run = bool(getattr(args, "run", False))

    with thread_id_scope(
        rebound_thread or original.thread_id
    ), trace_scope() as new_trace_id:
        clone = await store.clone(
            args.plan_id,
            thread_id=rebound_thread or original.thread_id,
            trace_id=new_trace_id,
            goal_override=goal_override,
        )
        if clone is None:  # pragma: no cover - the race would be exotic
            return _emit(args, _err("plan_not_found", plan_id=args.plan_id))
        await get_client().emit(
            "planner.cloned",
            {
                "plan_id": clone.id,
                "source_plan_id": original.id,
                "source_status": original.status.value,
                "model": clone.model,
                "pack_slug": clone.pack_slug,
                "playbook_id": clone.playbook_id,
                "step_count": len(clone.steps),
                "thread_id_rebind": (
                    rebound_thread != original.thread_id
                    if rebound_thread is not None
                    else False
                ),
                "goal_overridden": goal_override is not None,
                "auto_approved": do_approve,
                "auto_run": do_run,
            },
        )

        if do_approve:
            await store.set_status(clone.id, PlanStatus.APPROVED)
            clone = await store.get(clone.id) or clone

        run_result: dict[str, Any] | None = None
        if do_run:
            mode_override = getattr(args, "mode", None)
            # argparse already restricts ``--mode`` to the three
            # known choices, so resolve_mode just promotes the
            # string to the typed enum (or falls back to the env /
            # default if argparse let ``None`` through, e.g. when
            # ``--mode`` is omitted).
            policy_mode = resolve_mode(request_arg=mode_override)
            try:
                run_result = await PlanRunner().run(
                    clone.id, mode=policy_mode
                )
            except PlanRunError as exc:
                # Surface the failure but still report the clone
                # was created so the operator can investigate.
                return _emit(
                    args,
                    _err(
                        "plan_run_failed",
                        message=exc.message,
                        reason=exc.reason,
                        plan_id=clone.id,
                        source_plan_id=original.id,
                    ),
                )
            clone = await store.get(clone.id) or clone

    return _emit(
        args,
        {
            "ok": True,
            "plan": clone.to_dict(),
            "source_plan_id": original.id,
            "auto_approved": do_approve,
            "auto_run": do_run,
            "run_result": run_result,
        },
    )


async def _cmd_delete(args: argparse.Namespace) -> int:
    store = get_planner_store()
    existing = await store.get(args.plan_id)
    if existing is None:
        return _emit(args, _err("plan_not_found", plan_id=args.plan_id))
    if not args.yes:
        return _emit(
            args,
            _err(
                "confirmation_required",
                message="pass --yes to confirm destructive delete",
                plan_id=args.plan_id,
                status_at_check=existing.status.value,
            ),
        )
    deleted = await store.delete(args.plan_id)
    return _emit(
        args,
        {
            "ok": deleted,
            "plan_id": args.plan_id,
            "deleted": deleted,
        },
    )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.planner.cli",
        description="Inspect and drive the TARS planner from the shell.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Print compact JSON (no indent). Defaults to indented.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List plans, newest first.")
    p_list.add_argument("--status", default=None, help="Filter by status.")
    p_list.add_argument(
        "--thread-id", default=None, help="Filter by thread id."
    )
    p_list.add_argument(
        "--limit", type=int, default=50, help="Max plans returned."
    )

    p_show = sub.add_parser("show", help="Print one plan by id.")
    p_show.add_argument("plan_id")

    p_runs = sub.add_parser(
        "runs", help="Reconstruct past executions of one plan."
    )
    p_runs.add_argument("plan_id")
    p_runs.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Per-event-kind cap for the meeet store query.",
    )

    sub.add_parser("stats", help="Plan totals + by_status counts.")

    p_synth = sub.add_parser(
        "synthesize", help="Synthesize + persist a plan from a goal."
    )
    p_synth.add_argument("goal", help="Free-form operator goal.")
    p_synth.add_argument("--pinned-pack", default=None)
    p_synth.add_argument("--thread-id", default=None)

    p_approve = sub.add_parser("approve", help="Flip status proposed→approved.")
    p_approve.add_argument("plan_id")

    p_reject = sub.add_parser("reject", help="Flip status proposed→rejected.")
    p_reject.add_argument("plan_id")

    p_run = sub.add_parser("run", help="Execute an approved plan.")
    p_run.add_argument("plan_id")
    p_run.add_argument(
        "--mode",
        default=None,
        choices=("autopilot", "confirm", "dry_run"),
        help="Override TARS_POLICY_MODE for this run.",
    )

    p_abort = sub.add_parser("abort", help="Abort an in-flight plan run.")
    p_abort.add_argument("plan_id")

    p_clone = sub.add_parser(
        "clone",
        help="Snapshot a plan as a fresh proposed plan (rerun without history mutation).",
    )
    p_clone.add_argument("plan_id")
    p_clone.add_argument(
        "--thread-id",
        default=None,
        help="Rebind the clone to a different chat thread (defaults to original).",
    )
    p_clone.add_argument(
        "--goal",
        default=None,
        help="Override the goal copy on the clone (steps stay verbatim).",
    )
    p_clone.add_argument(
        "--approve",
        action="store_true",
        help="After cloning, immediately flip the new plan to 'approved'.",
    )
    p_clone.add_argument(
        "--run",
        action="store_true",
        help=(
            "After cloning, approve and run the clone (one-shot rerun). "
            "Implies --approve."
        ),
    )
    p_clone.add_argument(
        "--mode",
        choices=("autopilot", "confirm", "dry_run"),
        default=None,
        help=(
            "Policy mode override for --run (defaults to TARS_POLICY_MODE "
            "env / 'confirm')."
        ),
    )

    p_delete = sub.add_parser("delete", help="Delete a plan (irreversible).")
    p_delete.add_argument("plan_id")
    p_delete.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation; without it the call is a dry-run.",
    )

    return p


_DISPATCH = {
    "list": _cmd_list,
    "show": _cmd_show,
    "runs": _cmd_runs,
    "stats": _cmd_stats,
    "synthesize": _cmd_synthesize,
    "approve": _cmd_approve,
    "reject": _cmd_reject,
    "run": _cmd_run,
    "abort": _cmd_abort,
    "clone": _cmd_clone,
    "delete": _cmd_delete,
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
