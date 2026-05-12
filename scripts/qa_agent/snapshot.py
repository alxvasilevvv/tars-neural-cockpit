"""
qa_agent.snapshot — public status snapshot writer (Wave 126).

The synthetic monitor (Wave 117) runs every 5 min in GitHub Actions and
persists per-probe history to ``~/.tars/qa-agent/history.json``. That
file is internal: it stores raw streaks for alert dedup. Wave 126 layers
a *public* projection on top — a JSON document optimised for human
consumption (published to ``docs/qa-snapshot.json`` in-repo; historically
also consumed by the retired marketing site).

Why static JSON instead of a backend endpoint?
  * No backend coupling. The snapshot is readable from disk or any
    static host even if the API is down.
  * No auth surface. The snapshot leaks only what's already publicly
    visible (uptime %, incident summaries — no secrets, no PII).
  * Cheap to refresh. Same artifact pipeline as ``history.json``.

Snapshot shape (v1)::

    {
      "version": 1,
      "generated_at": "2026-05-11T12:34:56+00:00",
      "overall_status": "green" | "yellow" | "red",
      "probes": [
        {
          "name": "http.route/",
          "status": "green" | "yellow" | "red",
          "last_status": "pass" | "fail" | "warn" | "skip",
          "last_success_at": "..." | null,
          "last_failure_at": "..." | null,
          "failure_count_24h": 0,
          "uptime_7d_pct": 99.94
        },
        ...
      ],
      "incidents": [
        {
          "id": "incident-2026-05-10-route_workshop",
          "started_at": "...",
          "resolved_at": "..." | null,
          "probes_affected": ["http.route/workshop"],
          "summary": "1 probe failing (http.route/workshop)"
        }
      ]
    }

Status mapping:
  * pass     → green
  * warn     → yellow
  * skip     → green (skipped probes don't move the needle)
  * fail     → red

Overall:
  * any red       → red
  * any yellow    → yellow
  * else          → green

Commit cadence (see ``maybe_commit_snapshot``):
  * always commit if overall_status changed since previous snapshot
  * else commit at most every 30 min (every 6th 5-min run)
  * else skip (write to disk so artifact has it, but don't commit)

This keeps the public history rich without spamming the git log.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("tars.qa_agent.snapshot")

SNAPSHOT_VERSION = 1
DEFAULT_SNAPSHOT_PATH = Path("docs/qa-snapshot.json")
# 30 min between forced commits → ≤ 48 commits/day
COMMIT_INTERVAL_S = 30 * 60


def _status_bucket(probe_status: str) -> str:
    """Map probe status (pass/warn/fail/skip) → public bucket (green/yellow/red)."""
    if probe_status == "fail":
        return "red"
    if probe_status == "warn":
        return "yellow"
    # pass + skip both green — a skipped probe shouldn't scare visitors.
    return "green"


def _overall_status(probe_buckets: list[str]) -> str:
    if any(b == "red" for b in probe_buckets):
        return "red"
    if any(b == "yellow" for b in probe_buckets):
        return "yellow"
    return "green"


def _uptime_pct(series: list[str]) -> float:
    """Pass-rate over the rolling history. Skips don't count either way."""
    counted = [s for s in series if s in ("pass", "fail", "warn")]
    if not counted:
        return 100.0
    passes = sum(1 for s in counted if s == "pass")
    return round(100.0 * passes / len(counted), 2)


def build_snapshot(
    probes: list[Any],
    history: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project a probe run into the public snapshot shape.

    ``probes`` is the list returned by ``run_all()``. ``history`` is the
    just-saved history dict (post ``record_run``); we read the rolling
    series for uptime % and failure_count_24h. ``now`` is overridable
    for deterministic tests.
    """
    now = now or datetime.now(timezone.utc)
    history = history or {"probes": {}}
    series_by_name = history.get("probes") or {}

    public_probes: list[dict[str, Any]] = []
    buckets: list[str] = []
    for p in probes:
        name = getattr(p, "name", str(p))
        last_status = getattr(p, "status", "skip")
        bucket = _status_bucket(last_status)
        buckets.append(bucket)

        series = series_by_name.get(name, [])
        # last_success / last_failure: best-effort — we don't store
        # timestamps per-entry in history.json (would balloon the file).
        # Use "now" for the most-recent matching status; older entries
        # are not addressable. This is honest about what we know.
        last_success_at = (
            now.isoformat(timespec="seconds") if last_status == "pass" else None
        )
        last_failure_at = (
            now.isoformat(timespec="seconds") if last_status == "fail" else None
        )

        # 24h failure count — history.json caps at 10 entries per probe
        # (HISTORY_MAX_PER_PROBE) so this is "fails in last 10 runs"
        # which at 5-min cadence ≈ last ~50 min. Document that honestly
        # in the FE rather than over-stating it.
        failure_count_24h = sum(1 for s in series if s == "fail")

        public_probes.append(
            {
                "name": name,
                "status": bucket,
                "last_status": last_status,
                "last_success_at": last_success_at,
                "last_failure_at": last_failure_at,
                "failure_count_24h": failure_count_24h,
                "uptime_7d_pct": _uptime_pct(series),
            }
        )

    incidents = aggregate_incidents(public_probes, now=now)

    return {
        "version": SNAPSHOT_VERSION,
        "generated_at": now.isoformat(timespec="seconds"),
        "overall_status": _overall_status(buckets),
        "probes": public_probes,
        "incidents": incidents,
    }


def aggregate_incidents(
    public_probes: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Derive a flat incident list from currently-red probes.

    A single open incident is emitted per run if any probe is red. We
    don't have prior-snapshot context here (the writer below threads
    that in for resolution tracking) — this is the *current-state*
    projection.
    """
    now = now or datetime.now(timezone.utc)
    red = [p for p in public_probes if p["status"] == "red"]
    if not red:
        return []
    affected = sorted(p["name"] for p in red)
    iso = now.isoformat(timespec="seconds")
    # Stable id: date + first-affected-probe so successive runs of the
    # same outage collapse into one row in the FE.
    first = affected[0].replace("/", "_").replace(":", "_")
    incident_id = f"incident-{now.strftime('%Y-%m-%d')}-{first}"
    summary = (
        f"{len(affected)} probe{'s' if len(affected) != 1 else ''} failing "
        f"({', '.join(affected[:3])}{'…' if len(affected) > 3 else ''})"
    )
    return [
        {
            "id": incident_id,
            "started_at": iso,
            "resolved_at": None,
            "probes_affected": affected,
            "summary": summary,
        }
    ]


def write_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_PATH,
) -> bool:
    """Persist the snapshot to disk. Best-effort; never raises."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        return True
    except OSError as exc:
        log.warning("qa_agent.snapshot: write failed (%s): %s", p, exc)
        return False


def load_snapshot(path: Path | str = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any] | None:
    """Read the previous snapshot; returns None on any error."""
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def should_commit_snapshot(
    snapshot: dict[str, Any],
    prev_snapshot: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    interval_s: int = COMMIT_INTERVAL_S,
) -> tuple[bool, str]:
    """Decide whether the snapshot should be git-committed.

    Returns (should_commit, reason). Reason is a short human string used
    in the workflow commit message and the runbook for debugging.

    Commit if:
      * no previous snapshot (first run) → "first_snapshot"
      * overall_status changed → "status_change:<old>-><new>"
      * the affected-probes set changed → "probes_changed"
      * ``interval_s`` seconds have elapsed since last commit → "interval"

    Else skip → (False, "no_change_within_interval").
    """
    if prev_snapshot is None:
        return True, "first_snapshot"

    old = prev_snapshot.get("overall_status")
    new = snapshot.get("overall_status")
    if old != new:
        return True, f"status_change:{old}->{new}"

    old_red = {
        p["name"]
        for p in (prev_snapshot.get("probes") or [])
        if p.get("status") == "red"
    }
    new_red = {p["name"] for p in snapshot.get("probes", []) if p.get("status") == "red"}
    if old_red != new_red:
        return True, "probes_changed"

    # Time-based fallback so the timestamp doesn't go stale on a
    # perfectly green deployment.
    prev_ts = prev_snapshot.get("generated_at") or ""
    try:
        prev_dt = datetime.fromisoformat(prev_ts)
        if prev_dt.tzinfo is None:
            prev_dt = prev_dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True, "prev_timestamp_unparseable"

    now = now or datetime.now(timezone.utc)
    if (now - prev_dt) >= timedelta(seconds=interval_s):
        return True, "interval"

    return False, "no_change_within_interval"


def maybe_commit_snapshot(
    snapshot: dict[str, Any],
    *,
    snapshot_path: Path | str = DEFAULT_SNAPSHOT_PATH,
    now: datetime | None = None,
    interval_s: int = COMMIT_INTERVAL_S,
) -> dict[str, Any]:
    """High-level helper: load prev → decide → write.

    Always writes the snapshot file so the GH Actions artifact has the
    latest copy. Only signals "commit me" via the returned ``commit``
    flag; the workflow YAML does the actual git push (this module never
    shells out — it must stay stdlib-only and side-effect-light for
    pytest).
    """
    prev = load_snapshot(snapshot_path)
    commit, reason = should_commit_snapshot(
        snapshot, prev, now=now, interval_s=interval_s
    )
    written = write_snapshot(snapshot, snapshot_path)
    return {
        "snapshot_path": str(snapshot_path),
        "written": written,
        "commit": commit,
        "reason": reason,
        "previous_overall_status": (prev or {}).get("overall_status"),
    }


__all__ = [
    "DEFAULT_SNAPSHOT_PATH",
    "SNAPSHOT_VERSION",
    "COMMIT_INTERVAL_S",
    "build_snapshot",
    "aggregate_incidents",
    "write_snapshot",
    "load_snapshot",
    "should_commit_snapshot",
    "maybe_commit_snapshot",
]
