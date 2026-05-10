"""Policy gate — runs in front of every destructive domain action."""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional


class PolicyMode(str, enum.Enum):
    AUTOPILOT = "autopilot"
    CONFIRM = "confirm"
    DRY_RUN = "dry_run"

    @classmethod
    def from_str(cls, value: str | None) -> Optional["PolicyMode"]:
        if not value:
            return None
        try:
            return cls(value.strip().lower())
        except ValueError:
            return None


def resolve_mode(
    *,
    header: str | None = None,
    request_arg: str | None = None,
    fallback: PolicyMode = PolicyMode.CONFIRM,
) -> PolicyMode:
    """Determine the active policy mode.

    Precedence: explicit per-request arg → header → env → fallback.
    """

    for raw in (request_arg, header, os.getenv("TARS_POLICY_MODE")):
        m = PolicyMode.from_str(raw)
        if m is not None:
            return m
    return fallback


@dataclass(frozen=True)
class GateDecision:
    allowed: bool  # True if the action handler may run NOW
    mode: PolicyMode
    reason: str
    confirmation_token: str | None = None
    preview: dict[str, Any] | None = None


class PolicyGate:
    """Decides whether a destructive action runs immediately, gets staged,
    or only previewed.
    """

    async def check(
        self,
        *,
        slug: str,
        action_id: str,
        args: Mapping[str, Any],
        destructive: bool,
        mode: PolicyMode,
        confirmed: bool = False,
        trace_id: str | None = None,
        requested_by: str | None = None,
        thread_id: str | None = None,
    ) -> GateDecision:
        if confirmed:
            return GateDecision(
                allowed=True,
                mode=mode,
                reason="confirmed_by_token",
            )
        if not destructive:
            return GateDecision(
                allowed=True,
                mode=mode,
                reason="not_destructive",
            )
        if mode == PolicyMode.AUTOPILOT:
            return GateDecision(
                allowed=True,
                mode=mode,
                reason="autopilot",
            )
        if mode == PolicyMode.DRY_RUN:
            preview = {
                "slug": slug,
                "action_id": action_id,
                "args": dict(args),
                "would": "execute_destructive_action",
            }
            return GateDecision(
                allowed=False,
                mode=mode,
                reason="dry_run_preview_only",
                preview=preview,
            )
        # confirm mode
        from .store import get_policy_store  # local import to avoid cycles

        token = await get_policy_store().create(
            slug=slug,
            action_id=action_id,
            args=args,
            requested_by=requested_by,
            trace_id=trace_id,
            thread_id=thread_id,
        )
        preview = {
            "slug": slug,
            "action_id": action_id,
            "args": dict(args),
            "would": "execute_destructive_action",
        }
        # Wave 90 — outbound webhook fan-out for HIL gate. Wrapped so
        # a webhook store error never blocks the gate decision.
        try:
            from backend.core.webhooks import emit as _wh_emit

            await _wh_emit(
                "hil.requested",
                {
                    "token": token,
                    "slug": slug,
                    "action_id": action_id,
                    "trace_id": trace_id,
                    "thread_id": thread_id,
                    "requested_by": requested_by,
                },
            )
        except Exception:
            pass
        return GateDecision(
            allowed=False,
            mode=mode,
            reason="awaiting_confirmation",
            confirmation_token=token,
            preview=preview,
        )


_SINGLETON: PolicyGate | None = None


def get_gate() -> PolicyGate:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = PolicyGate()
    return _SINGLETON
