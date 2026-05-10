"""Workshop debrief renderer (W4-PR3).

One-shot Markdown bundle for the entire workshop or a single
attendee. Stitches the W3-PR1 analytics, the W3-PR2 session
report, the W3-PR3 council voices, and the W4-PR2 leaderboard
into a single document the facilitator can email out at the
end of the session.

Pure stdlib, deterministic — same audit logs always produce the
same bundle, same byte-for-byte. No third-party Markdown
formatter; we hand-roll headings + tables exactly the way the
W3-PR2 report does so the visual identity is consistent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from backend.core.algotrade.exec.analytics import (
    PnLAttribution,
    SessionMetrics,
    SlippageReport,
    compute_attribution,
    compute_session_metrics,
    compute_slippage,
)
from backend.core.algotrade.exec.report import render_session_report
from backend.core.algotrade.exec.router import AuditLog
from backend.core.algotrade.exec.runtime import get_runtime
from backend.core.algotrade.exec.sessions import Session
from backend.core.algotrade.exec.voices import CouncilReview, run_council

from .lab import (
    Attendee,
    LabStore,
    Leaderboard,
    LeaderboardEntry,
    Workshop,
    compute_leaderboard,
    get_lab_store,
)


@dataclass(frozen=True)
class AttendeeDebrief:
    attendee: Attendee
    rank: LeaderboardEntry | None
    sessions_markdown: tuple[str, ...]
    council_consensus: str
    """Worst severity any council voice raised across all of
    the attendee's sessions (``info|warn|alert``)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "attendee": self.attendee.to_dict(),
            "rank": (None if self.rank is None else self.rank.to_dict()),
            "sessions_markdown": list(self.sessions_markdown),
            "council_consensus": self.council_consensus,
        }


@dataclass(frozen=True)
class WorkshopDebrief:
    workshop: Workshop
    leaderboard: Leaderboard
    attendees: tuple[AttendeeDebrief, ...]
    markdown: str
    rendered_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "workshop": self.workshop.to_dict(),
            "leaderboard": self.leaderboard.to_dict(),
            "attendees": [a.to_dict() for a in self.attendees],
            "markdown": self.markdown,
            "rendered_at": float(self.rendered_at),
        }


# ---------------------------------------------------------------------
# Per-session helpers
# ---------------------------------------------------------------------


def _session_audit_path(session: Session):
    return get_runtime().root / "audit" / f"{session.session_id}.jsonl"


def _build_session_artifacts(
    session: Session,
) -> tuple[str, str | None]:
    """Render one session's W3-PR2 markdown report + the worst
    council severity for it. Returns ``(markdown, severity)``;
    ``severity`` is ``None`` when there's no audit data.
    """

    audit_path = _session_audit_path(session)
    if not audit_path.exists():
        return (
            f"### Session `{session.session_id}` — no audit data yet\n",
            None,
        )

    events = AuditLog(audit_path).read_all()
    if not events:
        return (
            f"### Session `{session.session_id}` — empty audit log\n",
            None,
        )

    wiring = get_runtime().get(session.session_id)
    policy = (
        wiring.gate.policy
        if wiring is not None
        else None
    )
    open_positions = (
        [p.to_dict() for p in wiring.positions.all()]
        if wiring is not None
        else []
    )

    metrics = compute_session_metrics(events)
    attribution = compute_attribution(events)
    slippage = compute_slippage(events)

    report = render_session_report(
        session=session,
        policy=policy or _default_policy(),
        metrics=metrics,
        attribution=attribution,
        slippage=slippage,
        open_positions=open_positions,
    )

    # Council needs a policy; if we can't recover it for a
    # rehydrated session (e.g. live), use the same default.
    review = run_council(
        policy=policy or _default_policy(),
        metrics=metrics,
        attribution=attribution,
        slippage=slippage,
    )
    return report.markdown, review.consensus


def _default_policy():
    """Used only when a session can't be rehydrated (live
    sessions after a worker restart). The council still runs
    against the audit log, but the risk-policy bullets that
    depend on the *active* policy will reference defaults."""

    from backend.core.algotrade.exec.risk import RiskPolicy

    return RiskPolicy()


# ---------------------------------------------------------------------
# Public renderer
# ---------------------------------------------------------------------


def render_workshop_debrief(
    workshop_id: str,
    *,
    store: LabStore | None = None,
    include_session_reports: bool = True,
) -> WorkshopDebrief:
    """Stitch the workshop-wide debrief.

    ``include_session_reports`` is on by default — the W3-PR2
    markdown is the meat of the document. Disable it (e.g. from
    the cockpit's "summary view") to render just the
    leaderboard + per-attendee headlines.
    """

    store = store or get_lab_store()
    workshop = store.get_workshop(workshop_id)
    if workshop is None:
        raise KeyError(f"workshop not found: {workshop_id}")

    leaderboard = compute_leaderboard(workshop_id, store=store)
    rank_by_attendee: dict[str, LeaderboardEntry] = {
        e.attendee_id: e for e in leaderboard.entries
    }

    runtime = get_runtime()
    attendees: list[AttendeeDebrief] = []
    for attendee in store.list_attendees(workshop_id):
        sessions = runtime.list_sessions(sandbox_id=attendee.sandbox_id)
        sessions_markdown: list[str] = []
        worst_consensus = "info"
        for session in sessions:
            md, severity = _build_session_artifacts(session)
            if include_session_reports:
                sessions_markdown.append(md)
            if severity is not None:
                worst_consensus = _max_severity(worst_consensus, severity)
        attendees.append(
            AttendeeDebrief(
                attendee=attendee,
                rank=rank_by_attendee.get(attendee.attendee_id),
                sessions_markdown=tuple(sessions_markdown),
                council_consensus=worst_consensus,
            )
        )

    rendered_at = time.time()
    md = _render_markdown(
        workshop=workshop,
        leaderboard=leaderboard,
        attendees=attendees,
        rendered_at=rendered_at,
        include_session_reports=include_session_reports,
    )
    return WorkshopDebrief(
        workshop=workshop,
        leaderboard=leaderboard,
        attendees=tuple(attendees),
        markdown=md,
        rendered_at=rendered_at,
    )


# ---------------------------------------------------------------------
# Markdown layout
# ---------------------------------------------------------------------


def _render_markdown(
    *,
    workshop: Workshop,
    leaderboard: Leaderboard,
    attendees: list[AttendeeDebrief],
    rendered_at: float,
    include_session_reports: bool,
) -> str:
    parts: list[str] = []
    parts.append(f"# Workshop debrief — {workshop.name}\n")
    parts.append(_workshop_header(workshop, leaderboard, rendered_at))
    parts.append(_leaderboard_table(leaderboard))
    if attendees:
        parts.append("## Per-attendee debrief\n")
        for ad in attendees:
            parts.append(_attendee_section(ad, include_session_reports))
    parts.append(_footer(workshop, rendered_at))
    return "\n".join(parts)


def _workshop_header(
    workshop: Workshop,
    leaderboard: Leaderboard,
    rendered_at: float,
) -> str:
    started = _fmt_ts(workshop.started_at)
    closed = (
        _fmt_ts(workshop.closed_at)
        if workshop.closed_at is not None
        else "—"
    )
    rows = [
        ("Workshop ID", f"`{workshop.workshop_id}`"),
        ("Status", workshop.status.value),
        ("Facilitator", workshop.facilitator or "—"),
        ("Started", started),
        ("Closed", closed),
        ("Rendered", _fmt_ts(rendered_at)),
        ("Attendees", str(leaderboard.attendees_total)),
        (
            "Attendees with sessions",
            str(leaderboard.attendees_with_sessions),
        ),
    ]
    if workshop.notes:
        rows.append(("Notes", workshop.notes.replace("\n", " ")))
    body = "\n".join(f"- **{k}**: {v}" for k, v in rows)
    return f"## Workshop\n\n{body}\n"


def _leaderboard_table(leaderboard: Leaderboard) -> str:
    if not leaderboard.entries:
        return "## Leaderboard\n\n_no attendees enrolled yet._\n"
    header = (
        "| Rank | Attendee | Sessions | Realised PnL | Fees | Slippage | "
        "Score | Accept rate |"
    )
    sep = "|---:|---|---:|---:|---:|---:|---:|---:|"
    rows = [header, sep]
    for e in leaderboard.entries:
        rows.append(
            "| {rank} | {name} | {sess} | {pnl} | {fees} | {slip} | "
            "{score} | {accept} |".format(
                rank=e.rank,
                name=e.display_name.replace("|", "\\|"),
                sess=e.sessions_total,
                pnl=_fmt_money(e.realized_pnl),
                fees=_fmt_money(e.fees_total),
                slip=_fmt_money(e.slippage_cost),
                score=_fmt_money(e.score),
                accept=f"{e.acceptance_rate * 100:.1f}%",
            )
        )
    return "## Leaderboard\n\n" + "\n".join(rows) + "\n"


def _attendee_section(
    debrief: AttendeeDebrief, include_session_reports: bool
) -> str:
    rank_line = (
        f"rank **#{debrief.rank.rank}**"
        if debrief.rank is not None
        else "unranked"
    )
    score = (
        _fmt_money(debrief.rank.score) if debrief.rank else "—"
    )
    sessions_total = (
        debrief.rank.sessions_total if debrief.rank else 0
    )

    header = (
        f"### {debrief.attendee.display_name} — {rank_line}\n\n"
        f"- **Attendee ID**: `{debrief.attendee.attendee_id}`\n"
        f"- **Sandbox**: `{debrief.attendee.sandbox_id}`\n"
        f"- **Sessions**: {sessions_total}\n"
        f"- **Score**: {score}\n"
        f"- **Council consensus**: {debrief.council_consensus}\n"
    )
    if not include_session_reports:
        return header
    if not debrief.sessions_markdown:
        return header + "\n_no sessions yet._\n"
    body = "\n".join(_indent_section_headings(md) for md in debrief.sessions_markdown)
    return header + "\n" + body + "\n"


def _indent_section_headings(md: str) -> str:
    """The W3-PR2 session report uses ``#``/``##``/``###``. We
    embed it under the attendee heading (``###``), so push every
    heading three levels deeper to keep the document outline
    valid (``# > ## > ### > #### > ##### > ######``)."""

    lines = []
    for line in md.split("\n"):
        if line.startswith("# "):
            lines.append("###" + line)  # # → ####
        elif line.startswith("## "):
            lines.append("###" + line)  # ## → #####
        elif line.startswith("### "):
            lines.append("###" + line)  # ### → ######
        else:
            lines.append(line)
    return "\n".join(lines)


def _footer(workshop: Workshop, rendered_at: float) -> str:
    return (
        f"---\n\n"
        f"_Generated by TARS algotrade — workshop "
        f"`{workshop.workshop_id}` at {_fmt_ts(rendered_at)}._\n"
    )


# ---------------------------------------------------------------------
# Severity ordering (mirrors voices.py)
# ---------------------------------------------------------------------


_SEVERITY_RANK = {"info": 0, "warn": 1, "alert": 2}


def _max_severity(a: str, b: str) -> str:
    return a if _SEVERITY_RANK.get(a, 0) >= _SEVERITY_RANK.get(b, 0) else b


# ---------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------


def _fmt_ts(ts: float) -> str:
    if ts is None:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(float(ts)))


def _fmt_money(value: float) -> str:
    if value is None:
        return "—"
    return f"{float(value):+,.2f}"
