"""Playbook runner — dispatches each step through the same gates that
the HTTP layer uses (policy gate + meeet trace + action handler).

Steps are sequential by default. A step with ``parallel: true`` is
batched with the previous parallel sibling and the whole group runs
through ``asyncio.gather``. Templating across siblings inside the
same parallel batch does NOT see each other's outputs — the context
is updated once the whole batch completes.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from backend.core.domains.registry import get_pack
from backend.core.meeet import get_client, trace_scope
from backend.core.policy import PolicyMode, get_gate

from .loader import Playbook, PlaybookStep


_TEMPLATE_RE = re.compile(r"\$\{([^}]+)\}")


def _walk(value: Any, path: str) -> Any:
    """Walk a dotted path through dicts and indexed lists."""

    cur: Any = value
    for raw in path.split("."):
        if cur is None:
            return None
        token = raw.strip()
        if not token:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(token)]
            except (ValueError, IndexError):
                return None
            continue
        if isinstance(cur, Mapping):
            cur = cur.get(token)
            continue
        return None
    return cur


def _resolve_template(value: str, ctx: Mapping[str, Any]) -> Any:
    """Resolve a single value:

    - if the entire string is a single ``${...}``, returns the bound value
      (so ints/lists survive without being coerced to str);
    - otherwise interpolates inline, coercing each match with ``str()``.
    """

    matches = list(_TEMPLATE_RE.finditer(value))
    if not matches:
        return value
    if len(matches) == 1 and matches[0].span() == (0, len(value)):
        return _walk(ctx, matches[0].group(1).strip())

    def repl(m: re.Match[str]) -> str:
        out = _walk(ctx, m.group(1).strip())
        return "" if out is None else str(out)

    return _TEMPLATE_RE.sub(repl, value)


def _resolve_args(args: Any, ctx: Mapping[str, Any]) -> Any:
    if isinstance(args, str):
        return _resolve_template(args, ctx)
    if isinstance(args, list):
        return [_resolve_args(a, ctx) for a in args]
    if isinstance(args, dict):
        return {k: _resolve_args(v, ctx) for k, v in args.items()}
    return args


def _check_when(expr: str | None, ctx: Mapping[str, Any]) -> bool:
    if not expr:
        return True
    # Substitute first; then evaluate with a tiny safe scope.
    rendered = _resolve_template(expr, ctx)
    if isinstance(rendered, bool):
        return rendered
    if rendered is None:
        return False
    if isinstance(rendered, (int, float)):
        return bool(rendered)
    if isinstance(rendered, str):
        s = rendered.strip().lower()
        if s in {"true", "1", "yes", "on"}:
            return True
        if s in {"false", "0", "no", "off", ""}:
            return False
        # Allow simple comparisons like "${steps.x.value} > 0" via eval-light.
        try:
            return bool(eval(rendered, {"__builtins__": {}}, {}))
        except Exception:
            return False
    return bool(rendered)


@dataclass
class StepResult:
    id: str
    action: str
    ok: bool
    skipped: bool
    blocked: bool
    took_ms: float
    result: Any = None
    error: str | None = None
    confirmation_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "ok": self.ok,
            "skipped": self.skipped,
            "blocked": self.blocked,
            "took_ms": round(float(self.took_ms), 3),
            "result": self.result,
            "error": self.error,
            "confirmation_token": self.confirmation_token,
        }


@dataclass
class PlaybookRunner:
    async def run(
        self,
        playbook: Playbook,
        *,
        context: Mapping[str, Any] | None = None,
        mode: PolicyMode = PolicyMode.CONFIRM,
    ) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "context": dict(context or {}),
            "steps": {},
        }
        client = get_client()
        gate = get_gate()
        results_by_id: dict[str, StepResult] = {}
        results_in_order: list[StepResult] = []

        with trace_scope() as trace_id:
            _started_payload = {
                "playbook_id": playbook.id,
                "steps": len(playbook.steps),
                "mode": mode.value,
            }
            await client.emit("playbook.started", _started_payload)
            # Wave 90 — outbound webhook fan-out. Wrapped so a webhook
            # store error never breaks the playbook run.
            try:
                from backend.core.webhooks import emit as _wh_emit

                await _wh_emit("playbook.started", _started_payload)
            except Exception:
                pass
            # Wave 94 — cohort hook. Best-effort: only records when the
            # playbook context carries an attendee email and that email
            # matches a known cohort attendee.
            try:
                from backend.core.cohort import record_action_if_member as _coh_record

                _attendee_email = (ctx.get("attendee_email") if isinstance(ctx, dict) else None)
                if _attendee_email:
                    await _coh_record(
                        _attendee_email,
                        "playbook_start",
                        _started_payload,
                    )
            except Exception:
                pass

            stop = False
            groups = _group_steps(playbook.steps)
            for group in groups:
                if stop:
                    for step in group:
                        sr = StepResult(
                            id=step.id,
                            action=step.action,
                            ok=False,
                            skipped=True,
                            blocked=False,
                            took_ms=0.0,
                            error="aborted_by_previous_step",
                        )
                        results_in_order.append(sr)
                        results_by_id[step.id] = sr
                    continue

                # Filter group by when clauses (resolved against the
                # *current* ctx snapshot — siblings do not see each
                # other's outputs inside the same group).
                executable: list[PlaybookStep] = []
                for step in group:
                    if _check_when(step.when, ctx):
                        executable.append(step)
                    else:
                        sr = StepResult(
                            id=step.id,
                            action=step.action,
                            ok=True,
                            skipped=True,
                            blocked=False,
                            took_ms=0.0,
                        )
                        results_in_order.append(sr)
                        results_by_id[step.id] = sr

                if not executable:
                    continue

                # Run the group: 1 step → sequential, >1 → asyncio.gather.
                if len(executable) == 1:
                    step = executable[0]
                    started = time.perf_counter()
                    args = _resolve_args(dict(step.args), ctx)
                    sr = await self._dispatch(step, args, gate=gate, mode=mode)
                    sr.took_ms = (time.perf_counter() - started) * 1000.0
                    finished_now = [(step, sr)]
                else:

                    async def _run_one(step: PlaybookStep) -> tuple[PlaybookStep, StepResult]:
                        started = time.perf_counter()
                        args = _resolve_args(dict(step.args), ctx)
                        sr = await self._dispatch(step, args, gate=gate, mode=mode)
                        sr.took_ms = (time.perf_counter() - started) * 1000.0
                        return step, sr

                    finished_now = await asyncio.gather(
                        *(_run_one(s) for s in executable)
                    )

                for step, sr in finished_now:
                    results_in_order.append(sr)
                    results_by_id[step.id] = sr
                    if step.store_as and sr.ok and not sr.blocked:
                        ctx["steps"][step.store_as] = sr.result
                    await client.emit(
                        "playbook.step.completed",
                        {
                            "playbook_id": playbook.id,
                            "step_id": step.id,
                            "ok": sr.ok,
                            "blocked": sr.blocked,
                            "parallel": step.parallel or len(executable) > 1,
                            "took_ms": round(sr.took_ms, 3),
                        },
                    )

                # Decide if we should stop after this group.
                for step, sr in finished_now:
                    if sr.blocked and playbook.on_block == "stop":
                        stop = True
                        break
                    if not sr.ok and step.on_error == "stop":
                        stop = True
                        break

            _completed_payload = {
                "playbook_id": playbook.id,
                "ok": not stop,
                "steps_run": sum(1 for r in results_in_order if not r.skipped),
                "steps_blocked": sum(1 for r in results_in_order if r.blocked),
                "steps_failed": sum(
                    1 for r in results_in_order if not r.ok and not r.skipped and not r.blocked
                ),
            }
            await client.emit("playbook.completed", _completed_payload)
            # Wave 90 — outbound webhook fan-out for finished playbooks.
            try:
                from backend.core.webhooks import emit as _wh_emit

                if _completed_payload["steps_failed"] > 0:
                    await _wh_emit("playbook.failed", _completed_payload)
                else:
                    await _wh_emit("playbook.finished", _completed_payload)
            except Exception:
                pass
            # Wave 94 — cohort hook for completion (mirror of started).
            try:
                from backend.core.cohort import record_action_if_member as _coh_record

                _attendee_email = (ctx.get("attendee_email") if isinstance(ctx, dict) else None)
                if _attendee_email:
                    _coh_action = (
                        "error"
                        if _completed_payload["steps_failed"] > 0
                        else "playbook_finish"
                    )
                    await _coh_record(_attendee_email, _coh_action, _completed_payload)
            except Exception:
                pass

            # Re-emit the steps in the playbook's declared order so the
            # response is deterministic regardless of completion order.
            ordered = [
                results_by_id[s.id]
                for s in playbook.steps
                if s.id in results_by_id
            ]

            return {
                "ok": not stop,
                "playbook_id": playbook.id,
                "trace_id": trace_id,
                "mode": mode.value,
                "steps": [r.to_dict() for r in ordered],
                "context": ctx,
            }

    async def _dispatch(
        self,
        step: PlaybookStep,
        args: dict[str, Any],
        *,
        gate,
        mode: PolicyMode,
    ) -> StepResult:
        action = step.action

        # Awareness snapshot syntax: "<slug>.awareness.<source_id>.snapshot"
        if ".awareness." in action and action.endswith(".snapshot"):
            try:
                slug, source_id = _parse_awareness_target(action)
            except ValueError as exc:
                return StepResult(
                    id=step.id, action=action, ok=False, skipped=False,
                    blocked=False, took_ms=0.0, error=str(exc),
                )
            pack = get_pack(slug)
            if pack is None:
                return StepResult(
                    id=step.id, action=action, ok=False, skipped=False,
                    blocked=False, took_ms=0.0, error="domain_not_found",
                )
            source = pack.find_awareness(source_id)
            if source is None:
                return StepResult(
                    id=step.id, action=action, ok=False, skipped=False,
                    blocked=False, took_ms=0.0, error="awareness_not_found",
                )
            if source.fetcher is None:
                return StepResult(
                    id=step.id, action=action, ok=False, skipped=False,
                    blocked=False, took_ms=0.0,
                    error="fetcher_unavailable",
                )
            try:
                data = await source.fetcher({**dict(source.config), **args})
            except Exception as exc:
                return StepResult(
                    id=step.id, action=action, ok=False, skipped=False,
                    blocked=False, took_ms=0.0, error=str(exc),
                )
            return StepResult(
                id=step.id, action=action, ok=True, skipped=False,
                blocked=False, took_ms=0.0, result=data,
            )

        # Domain action syntax: "<slug>.<action_id>"
        if "." not in action:
            return StepResult(
                id=step.id, action=action, ok=False, skipped=False,
                blocked=False, took_ms=0.0, error="invalid_action_format",
            )
        slug, action_id = action.split(".", 1)
        pack = get_pack(slug)
        if pack is None:
            return StepResult(
                id=step.id, action=action, ok=False, skipped=False,
                blocked=False, took_ms=0.0, error="domain_not_found",
            )
        spec = pack.find_action(action_id)
        if spec is None:
            return StepResult(
                id=step.id, action=action, ok=False, skipped=False,
                blocked=False, took_ms=0.0, error="action_not_found",
            )

        decision = await gate.check(
            slug=slug,
            action_id=action_id,
            args=args,
            destructive=spec.destructive,
            mode=mode,
        )
        if not decision.allowed:
            return StepResult(
                id=step.id, action=action, ok=True, skipped=False,
                blocked=True, took_ms=0.0,
                result={
                    "policy": {
                        "mode": decision.mode.value,
                        "reason": decision.reason,
                        "preview": decision.preview,
                        "confirmation_token": decision.confirmation_token,
                    }
                },
                confirmation_token=decision.confirmation_token,
            )

        try:
            result = await spec.handler(args)
        except Exception as exc:
            return StepResult(
                id=step.id, action=action, ok=False, skipped=False,
                blocked=False, took_ms=0.0, error=str(exc),
            )
        return StepResult(
            id=step.id, action=action, ok=True, skipped=False,
            blocked=False, took_ms=0.0, result=result,
        )


def _group_steps(steps: tuple["PlaybookStep", ...]) -> list[list["PlaybookStep"]]:
    """Split steps into execution groups.

    The first step of any chain is sequential. A step with
    ``parallel: true`` is appended to the previous group (forming a
    parallel batch). The next non-parallel step starts a new group.
    """

    groups: list[list[PlaybookStep]] = []
    for step in steps:
        if step.parallel and groups:
            groups[-1].append(step)
        else:
            groups.append([step])
    return groups


def _parse_awareness_target(action: str) -> tuple[str, str]:
    # "<slug>.awareness.<source_id>.snapshot"
    parts = action.split(".")
    if len(parts) < 4 or parts[1] != "awareness" or parts[-1] != "snapshot":
        raise ValueError("invalid_awareness_target")
    slug = parts[0]
    source_id = ".".join(parts[2:-1])
    return slug, source_id


async def run_playbook(
    playbook: Playbook,
    *,
    context: Mapping[str, Any] | None = None,
    mode: PolicyMode = PolicyMode.CONFIRM,
) -> dict[str, Any]:
    return await PlaybookRunner().run(playbook, context=context, mode=mode)
