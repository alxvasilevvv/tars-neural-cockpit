"""Playbook runner — dispatches each step through the same gates that
the HTTP layer uses (policy gate + meeet trace + action handler).
"""

from __future__ import annotations

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
        results: list[StepResult] = []

        with trace_scope() as trace_id:
            await client.emit(
                "playbook.started",
                {
                    "playbook_id": playbook.id,
                    "steps": len(playbook.steps),
                    "mode": mode.value,
                },
            )

            stop = False
            for step in playbook.steps:
                if stop:
                    results.append(
                        StepResult(
                            id=step.id,
                            action=step.action,
                            ok=False,
                            skipped=True,
                            blocked=False,
                            took_ms=0.0,
                            error="aborted_by_previous_step",
                        )
                    )
                    continue

                if not _check_when(step.when, ctx):
                    results.append(
                        StepResult(
                            id=step.id,
                            action=step.action,
                            ok=True,
                            skipped=True,
                            blocked=False,
                            took_ms=0.0,
                        )
                    )
                    continue

                started = time.perf_counter()
                args = _resolve_args(dict(step.args), ctx)
                step_result = await self._dispatch(step, args, gate=gate, mode=mode)
                step_result.took_ms = (time.perf_counter() - started) * 1000.0

                results.append(step_result)
                if step.store_as and step_result.ok and not step_result.blocked:
                    ctx["steps"][step.store_as] = step_result.result

                await client.emit(
                    "playbook.step.completed",
                    {
                        "playbook_id": playbook.id,
                        "step_id": step.id,
                        "ok": step_result.ok,
                        "blocked": step_result.blocked,
                        "took_ms": round(step_result.took_ms, 3),
                    },
                )

                if step_result.blocked and playbook.on_block == "stop":
                    stop = True
                    continue
                if not step_result.ok and step.on_error == "stop":
                    stop = True
                    continue

            await client.emit(
                "playbook.completed",
                {
                    "playbook_id": playbook.id,
                    "ok": not stop,
                    "steps_run": sum(1 for r in results if not r.skipped),
                    "steps_blocked": sum(1 for r in results if r.blocked),
                    "steps_failed": sum(
                        1 for r in results if not r.ok and not r.skipped and not r.blocked
                    ),
                },
            )

            return {
                "ok": not stop,
                "playbook_id": playbook.id,
                "trace_id": trace_id,
                "mode": mode.value,
                "steps": [r.to_dict() for r in results],
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
