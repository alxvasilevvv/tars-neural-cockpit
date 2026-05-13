"""Daemon-side ``tars-doctor`` watcher (Wave 157).

When ``TARS_DAEMON_DOCTOR_ENABLED=1`` the background daemon runs
the doctor once per ``TARS_DAEMON_DOCTOR_EVERY_N`` ticks (default
every tick) and:

  1. Caches the last-seen status per check slug in memory.
  2. Diffs against the previous tick; any check that transitioned
     status (e.g. ``ok`` → ``warn``) joins a ``changes`` list.
  3. If ``changes`` is non-empty AND a webhook subsystem is
     importable, fires a ``doctor.status_changed`` event with the
     diff payload.

The watcher is best-effort: any exception is swallowed + logged
at debug. It never raises into the tick loop.

Honest framing:
  - This is NOT a replacement for the W117 synthetic monitor.
    That hits production routes from the internet; this watches
    local-process subsystems.
  - This is NOT a fix-mode. It diagnoses + alerts; remediation is
    still the operator's job (via ``tars-daemon restart`` etc.).
  - This is NOT throttled — every status change fires. Operators
    who want quieter signal should set
    ``TARS_DAEMON_DOCTOR_EVERY_N`` > 1.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any


log = logging.getLogger("tars.daemon.doctor_watch")


@dataclass
class DoctorWatchState:
    """Per-process cache of last-seen check statuses."""

    last_status_by_slug: dict[str, str] = field(default_factory=dict)
    last_run_at: float = 0.0
    runs: int = 0
    emits: int = 0


_state = DoctorWatchState()


def get_state() -> DoctorWatchState:
    return _state


def _reset_for_tests() -> None:
    global _state
    _state = DoctorWatchState()


def is_enabled() -> bool:
    flag = (os.getenv("TARS_DAEMON_DOCTOR_ENABLED") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _every_n() -> int:
    raw = os.getenv("TARS_DAEMON_DOCTOR_EVERY_N")
    if raw is None:
        return 1
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def should_run_this_tick(tick_count: int) -> bool:
    if not is_enabled():
        return False
    n = _every_n()
    if n <= 1:
        return True
    # tick_count starts at 1, so this fires on tick N, 2N, 3N…
    return tick_count % n == 0


def diff_statuses(
    new_results: list[Any],
    cached: dict[str, str],
) -> list[dict[str, Any]]:
    """Return the list of slugs whose status changed since last run.

    ``new_results`` is the list returned by ``run_all()`` from the
    doctor module — each entry must have ``.slug`` and ``.status``.
    ``cached`` is the previous tick's mapping.
    """

    changes: list[dict[str, Any]] = []
    for r in new_results:
        slug = getattr(r, "slug", None) or (r.get("slug") if isinstance(r, dict) else None)
        status = getattr(r, "status", None) or (r.get("status") if isinstance(r, dict) else None)
        if not slug or not status:
            continue
        prev = cached.get(slug)
        if prev is None:
            # First time we've seen this slug — record but don't
            # report as a transition (boot-time noise).
            continue
        if prev != status:
            summary = (
                getattr(r, "summary", "")
                if not isinstance(r, dict)
                else r.get("summary", "")
            )
            changes.append(
                {
                    "slug": slug,
                    "from": prev,
                    "to": status,
                    "summary": summary,
                }
            )
    return changes


async def run_once(*, force: bool = False) -> dict[str, Any]:
    """One pass of the watcher.

    Returns a small dict with ``{ran, changes, emitted, error?}`` so
    the daemon caller can log meaningful metrics. The dict is the
    primary test seam — tests assert against it instead of the
    side-effects.
    """

    if not (force or is_enabled()):
        return {"ran": False, "reason": "disabled"}

    # Lazy import to avoid module-init cycles
    try:
        from backend.core.doctor import run_all as doctor_run_all
    except Exception as exc:  # noqa: BLE001
        log.debug("doctor_watch: import failed: %s", exc)
        return {"ran": False, "error": f"import_failed: {exc}"}

    try:
        results = doctor_run_all()
    except Exception as exc:  # noqa: BLE001
        log.debug("doctor_watch: run_all failed: %s", exc)
        return {"ran": False, "error": f"run_all_failed: {exc}"}

    s = get_state()
    s.runs += 1
    s.last_run_at = time.time()
    changes = diff_statuses(results, s.last_status_by_slug)

    # Update the cache regardless of whether we emit.
    for r in results:
        s.last_status_by_slug[r.slug] = r.status

    emitted = False
    if changes:
        emitted = await _emit_changes(changes, results)
        if emitted:
            s.emits += 1

    return {
        "ran": True,
        "changes": changes,
        "emitted": emitted,
        "runs": s.runs,
    }


async def _emit_changes(changes: list[dict[str, Any]], results: list[Any]) -> bool:
    """Fire the webhook event. Returns True iff emit succeeded."""

    try:
        from backend.core.webhooks import emit  # type: ignore
    except Exception as exc:  # noqa: BLE001
        log.debug("doctor_watch: webhooks import failed: %s", exc)
        return False

    summary = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1

    payload = {
        "changes": changes,
        "summary": summary,
        "results": [r.to_dict() for r in results],
        "fired_at": time.time(),
    }

    try:
        await emit(event_type="doctor.status_changed", data=payload)
        log.info(
            "doctor_watch: emitted doctor.status_changed (%d change%s)",
            len(changes),
            "" if len(changes) == 1 else "s",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("doctor_watch: emit failed: %s", exc)
        return False
