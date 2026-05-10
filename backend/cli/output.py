"""CLI output formatters.

Two modes:

- ``json`` — pretty-printed JSON (default for scripts /
  ``--json`` flag). Stable shape for piping into ``jq``.
- ``human`` — opinionated Markdown / table layout (default
  when stdout is a TTY). Optimised for reading at a workshop.

Each formatter returns a string the caller writes to stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Sequence


def is_tty() -> bool:
    return sys.stdout.isatty()


def render(payload: Any, *, mode: str) -> str:
    """Top-level entry. ``mode`` is one of ``json`` / ``human``.
    ``human`` falls back to ``json`` for shapes we don't have
    an explicit pretty renderer for, so the user always gets
    *something* readable.
    """

    if mode == "json":
        return _to_json(payload)
    if mode == "human":
        return _human(payload)
    return _to_json(payload)


def _to_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------
# Human renderers — dispatch on common payload shapes
# ---------------------------------------------------------------------


def _human(payload: Any) -> str:
    if isinstance(payload, Mapping):
        if payload.get("ok") is False:
            return _render_error(payload)
        # Known shapes (cheapest test first).
        if "recipes" in payload and isinstance(payload["recipes"], list):
            return _render_recipes(payload)
        if "strategies" in payload and isinstance(payload["strategies"], list):
            return _render_strategies(payload)
        if "sessions" in payload and isinstance(payload["sessions"], list):
            return _render_sessions(payload)
        if "workshops" in payload and isinstance(payload["workshops"], list):
            return _render_workshops(payload)
        if "attendees" in payload and isinstance(payload["attendees"], list):
            return _render_attendees(payload)
        if "leaderboard" in payload and isinstance(payload["leaderboard"], Mapping):
            return _render_leaderboard(payload["leaderboard"])
        if (
            "debrief" in payload
            and isinstance(payload["debrief"], Mapping)
            and isinstance(payload["debrief"].get("markdown"), str)
        ):
            return payload["debrief"]["markdown"]
        if "markdown" in payload and isinstance(payload["markdown"], str):
            return payload["markdown"]
        if "playbooks" in payload and isinstance(payload["playbooks"], list):
            return _render_playbooks(payload)
        if "version" in payload:
            return _render_version(payload)
    return _to_json(payload)


def _render_error(payload: Mapping[str, Any]) -> str:
    err = payload.get("error", "unknown_error")
    detail = payload.get("detail")
    msg = f"❌ {err}" if not is_tty() or not _supports_unicode() else f"error: {err}"
    if detail:
        msg += f"\n  {detail}"
    return msg


def _supports_unicode() -> bool:
    enc = (sys.stdout.encoding or "").lower()
    return enc.startswith("utf")


# ---------------------------------------------------------------------
# Renderers per shape
# ---------------------------------------------------------------------


def _render_recipes(payload: Mapping[str, Any]) -> str:
    names = list(payload.get("recipes") or [])
    if not names:
        return "No recipes available."
    lines = ["Recipes:"]
    for n in names:
        lines.append(f"  - {n}")
    return "\n".join(lines)


def _render_strategies(payload: Mapping[str, Any]) -> str:
    rows = list(payload.get("strategies") or [])
    if not rows:
        return "Registry is empty."
    lines = [
        f"{payload.get('count', len(rows))} strategies in registry:",
        "",
    ]
    cols = ("name", "fingerprint", "instrument", "timeframe", "side", "version")
    table = _table(rows, cols, title=None)
    lines.append(table)
    return "\n".join(lines)


def _render_sessions(payload: Mapping[str, Any]) -> str:
    rows = list(payload.get("sessions") or [])
    if not rows:
        return "No sessions."
    lines = [f"{len(rows)} sessions:", ""]
    cols = (
        "session_id",
        "mode",
        "adapter",
        "instrument",
        "status",
        "sandbox_id",
    )
    lines.append(_table(rows, cols, title=None))
    return "\n".join(lines)


def _render_workshops(payload: Mapping[str, Any]) -> str:
    rows = list(payload.get("workshops") or [])
    if not rows:
        return "No workshops."
    lines = [f"{payload.get('total', len(rows))} workshops:", ""]
    cols = (
        "workshop_id",
        "name",
        "status",
        "facilitator",
        "started_at",
    )
    lines.append(_table(rows, cols, title=None, ts_keys={"started_at"}))
    return "\n".join(lines)


def _render_attendees(payload: Mapping[str, Any]) -> str:
    rows = list(payload.get("attendees") or [])
    if not rows:
        return "No attendees."
    lines = [
        f"{payload.get('total', len(rows))} attendees in "
        f"`{payload.get('workshop_id', '?')}`:",
        "",
    ]
    cols = ("attendee_id", "display_name", "sandbox_id", "joined_at")
    lines.append(_table(rows, cols, title=None, ts_keys={"joined_at"}))
    return "\n".join(lines)


def _render_leaderboard(lb: Mapping[str, Any]) -> str:
    entries = list(lb.get("entries") or [])
    title = (
        f"Leaderboard — {lb.get('workshop_name')} "
        f"({lb.get('workshop_id')})"
    )
    if not entries:
        return f"{title}\n\n_no attendees enrolled yet._"
    lines = [
        title,
        "",
        f"  Total attendees: {lb.get('attendees_total', 0)}  "
        f"(with sessions: {lb.get('attendees_with_sessions', 0)})",
        "",
    ]
    cols = (
        "rank",
        "display_name",
        "sessions_total",
        "realized_pnl",
        "fees_total",
        "slippage_cost",
        "score",
        "acceptance_rate",
    )
    lines.append(
        _table(
            entries,
            cols,
            title=None,
            money_keys={
                "realized_pnl",
                "fees_total",
                "slippage_cost",
                "score",
            },
            pct_keys={"acceptance_rate"},
        )
    )
    return "\n".join(lines)


def _render_playbooks(payload: Mapping[str, Any]) -> str:
    rows = list(payload.get("playbooks") or [])
    if not rows:
        return "No playbooks."
    lines = [f"{payload.get('count', len(rows))} playbooks:", ""]
    cols = ("id", "name", "pack", "tags")
    lines.append(_table(rows, cols, title=None))
    return "\n".join(lines)


def _render_version(payload: Mapping[str, Any]) -> str:
    lines = [f"tars {payload.get('version', '?')}"]
    if "python" in payload:
        lines.append(f"  python: {payload['python']}")
    if "tars_home" in payload:
        lines.append(f"  TARS_HOME: {payload['tars_home']}")
    if "packs" in payload:
        lines.append("  packs:")
        for p in payload["packs"]:
            lines.append(f"    - {p['slug']} v{p['version']} ({p['phase']})")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Table primitives — pure stdlib
# ---------------------------------------------------------------------


def _table(
    rows: Sequence[Mapping[str, Any]],
    cols: Sequence[str],
    *,
    title: str | None = None,
    money_keys: set[str] | None = None,
    pct_keys: set[str] | None = None,
    ts_keys: set[str] | None = None,
) -> str:
    money_keys = money_keys or set()
    pct_keys = pct_keys or set()
    ts_keys = ts_keys or set()

    formatted: list[list[str]] = []
    for row in rows:
        rendered = []
        for col in cols:
            v = row.get(col)
            if v is None:
                rendered.append("—")
            elif col in money_keys:
                rendered.append(f"{float(v):+,.2f}")
            elif col in pct_keys:
                rendered.append(f"{float(v) * 100:.1f}%")
            elif col in ts_keys:
                rendered.append(_short_ts(v))
            elif isinstance(v, list):
                rendered.append(",".join(str(x) for x in v))
            else:
                rendered.append(str(v))
        formatted.append(rendered)

    widths = [
        max(len(c), max((len(r[i]) for r in formatted), default=0))
        for i, c in enumerate(cols)
    ]

    header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    sep = "  ".join("-" * widths[i] for i in range(len(cols)))
    body = "\n".join(
        "  ".join(r[i].ljust(widths[i]) for i in range(len(cols)))
        for r in formatted
    )
    out = "\n".join([header, sep, body])
    if title:
        out = f"{title}\n\n{out}"
    return out


def _short_ts(v: Any) -> str:
    try:
        import time

        return time.strftime("%Y-%m-%d %H:%M", time.gmtime(float(v)))
    except (TypeError, ValueError):
        return str(v)
