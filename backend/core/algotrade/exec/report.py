"""Markdown session report renderer (W3-PR2).

W3-PR1 ships :class:`PnLAttribution`, :class:`SlippageReport`,
and :class:`SessionMetrics` as machine-readable dataclasses.
W3-PR2 turns those into the **human-readable handout** an
attendee actually shows their PM at the end of a workshop day:
one self-contained Markdown document with session metadata,
headline metrics, PnL by instrument and strategy, top
contributors / detractors, slippage stats, the active risk
policy, and a tiny ASCII PnL sparkline.

Design choices
--------------

- **Pure stdlib, deterministic**. No timezone calls (we render
  POSIX timestamps as UTC ISO strings via
  ``datetime.fromtimestamp(..., tz=timezone.utc)``). Same
  audit log → same Markdown bytes.
- **Stable structure**. Every section header is fixed text so
  downstream tools (the cockpit's report viewer, a council
  voice that wants to reference "the slippage section", a PDF
  exporter) can search by heading.
- **No external chart engine.** The sparkline is a 1-line
  ASCII bar made of ``▁▂▃▄▅▆▇█`` — safe to embed in
  Markdown, Slack, e-mail. The cockpit can re-render the same
  data as a proper chart from
  ``PnLAttribution.pnl_curve``.
- **Renderable in isolation.** The function takes plain
  dataclasses, not a runtime handle, so a saved JSONL audit
  can produce a report long after the session is gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from .analytics import (
    PnLAttribution,
    RoundTrip,
    SessionMetrics,
    SlippageReport,
)
from .risk import RiskPolicy
from .sessions import Session


# ---------------------------------------------------------------------
# Rendering primitives
# ---------------------------------------------------------------------


_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}{abs(x):,.4f}"


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _fmt_bps(x: float) -> str:
    return f"{x:+.2f} bps"


def _fmt_ts(ts: float | None) -> str:
    if ts is None or ts <= 0:
        return "—"
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60.0
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60.0
    return f"{hours:.2f}h"


def _sparkline(values: Iterable[float], *, width: int = 40) -> str:
    """Render a tiny unicode sparkline. Empty / single-point input
    returns an em-dash."""

    series = list(values)
    if len(series) < 2:
        return "—"
    if width > 0 and len(series) > width:
        chunks: list[list[float]] = []
        step = len(series) / float(width)
        for i in range(width):
            start = int(round(i * step))
            end = int(round((i + 1) * step)) or start + 1
            chunk = series[start:end]
            if chunk:
                chunks.append(chunk)
        series = [sum(c) / len(c) for c in chunks]

    lo = min(series)
    hi = max(series)
    span = hi - lo
    if span <= 0:
        return _SPARK_CHARS[len(_SPARK_CHARS) // 2] * len(series)
    out: list[str] = []
    for v in series:
        idx = int(round((v - lo) / span * (len(_SPARK_CHARS) - 1)))
        idx = max(0, min(len(_SPARK_CHARS) - 1, idx))
        out.append(_SPARK_CHARS[idx])
    return "".join(out)


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SessionReport:
    """Bundle of rendered Markdown + the structured payload that
    fed into it. The action layer returns both so the cockpit can
    render the markdown directly AND the council voices can
    reason over the structured payload without re-parsing."""

    markdown: str
    payload: dict


def render_session_report(
    *,
    session: Session,
    policy: RiskPolicy,
    metrics: SessionMetrics,
    attribution: PnLAttribution,
    slippage: SlippageReport,
    open_positions: Iterable[Mapping] = (),
    top_n_trades: int = 5,
    title: str | None = None,
) -> SessionReport:
    """Render a workshop-grade Markdown handout from the W3-PR1
    analytics dataclasses.

    Sections (fixed headings, search-stable):

    1. ``# {title}``
    2. ``## Session``
    3. ``## Headline metrics``
    4. ``## PnL attribution``
    5. ``## Top trades``
    6. ``## Slippage``
    7. ``## Risk policy``
    8. ``## Open positions`` (omitted if empty)
    """

    title = title or f"Session {session.session_id} — {session.strategy_fingerprint[:16]}"

    out: list[str] = []
    out.append(f"# {title}")
    out.append("")
    out.append(_render_session_block(session))
    out.append(_render_headline_block(metrics))
    out.append(_render_pnl_block(attribution))
    out.append(_render_trades_block(attribution.trades, top_n=top_n_trades))
    out.append(_render_slippage_block(slippage))
    out.append(_render_policy_block(policy))
    open_positions_list = list(open_positions)
    if open_positions_list:
        out.append(_render_positions_block(open_positions_list))

    markdown = "\n".join(out).rstrip() + "\n"

    payload = {
        "title": title,
        "session": session.to_dict(),
        "policy": policy.to_dict(),
        "metrics": metrics.to_dict(),
        "attribution": attribution.to_dict(),
        "slippage": slippage.to_dict(),
        "open_positions": [dict(p) for p in open_positions_list],
        "sparkline": _sparkline(
            (cum for _, cum in attribution.pnl_curve)
        ),
    }
    return SessionReport(markdown=markdown, payload=payload)


# ---------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------


def _render_session_block(session: Session) -> str:
    lines = [
        "## Session",
        "",
        f"- **ID**: `{session.session_id}`",
        f"- **Mode**: `{session.mode}` · adapter `{session.adapter}`",
        f"- **Status**: `{session.status.value}`",
        f"- **Strategy fingerprint**: `{session.strategy_fingerprint}`",
        f"- **Instrument**: `{session.instrument}`",
        f"- **Started**: {_fmt_ts(session.started_at)}",
        f"- **Closed**:  {_fmt_ts(session.closed_at)}",
    ]
    if session.sandbox_id:
        lines.append(f"- **Sandbox**: `{session.sandbox_id}`")
    if session.notes:
        lines.append(f"- **Notes**: {session.notes}")
    lines.append("")
    return "\n".join(lines)


def _render_headline_block(m: SessionMetrics) -> str:
    return "\n".join([
        "## Headline metrics",
        "",
        "| Metric                     | Value                          |",
        "| -------------------------- | ------------------------------ |",
        f"| Realised PnL               | **{_fmt_money(m.realized_pnl)}**           |",
        f"| Unrealised PnL             | {_fmt_money(m.unrealized_pnl)}            |",
        f"| Fees paid                  | {_fmt_money(m.fees_total)}                |",
        f"| Slippage cost              | {_fmt_money(m.total_slippage_cost)}       |",
        f"| Avg slippage               | {_fmt_bps(m.avg_slippage_bps)}            |",
        f"| Intents (accepted/total)   | {m.intents_accepted} / {m.intents_total} ({_fmt_pct(m.acceptance_rate)}) |",
        f"| Intents rejected           | {m.intents_rejected}                       |",
        f"| Orders / fills / cancels   | {m.orders_total} / {m.fills_total} / {m.cancels_total} |",
        f"| Bars consumed              | {m.bars_consumed}                          |",
        f"| Open positions             | {m.open_positions}                         |",
        f"| Duration                   | {_fmt_duration(m.duration_seconds)}        |",
        "",
    ])


def _render_pnl_block(attr: PnLAttribution) -> str:
    out = [
        "## PnL attribution",
        "",
        f"- **Realised total**:   `{_fmt_money(attr.realized_total)}`",
        f"- **Unrealised total**: `{_fmt_money(attr.unrealized_total)}`",
        f"- **Fees total**:       `{_fmt_money(attr.fees_total)}`",
        f"- **Round trips**:      {attr.trades_count}",
        "",
    ]
    if attr.pnl_curve:
        spark = _sparkline(cum for _, cum in attr.pnl_curve)
        out.append(f"**Cumulative PnL curve** ({len(attr.pnl_curve)} samples): `{spark}`")
        out.append("")

    if attr.by_instrument:
        out.append("### By instrument")
        out.append("")
        out.append("| Instrument         | Realised        | Fees            | Trades |")
        out.append("| ------------------ | --------------- | --------------- | ------ |")
        rows = sorted(
            attr.by_instrument.items(),
            key=lambda kv: kv[1].get("realized", 0.0),
            reverse=True,
        )
        for instrument, bucket in rows:
            out.append(
                f"| `{instrument:18s}` | {_fmt_money(bucket.get('realized', 0.0)):>15s} "
                f"| {_fmt_money(bucket.get('fees', 0.0)):>15s} | {int(bucket.get('trades', 0)):>6d} |"
            )
        out.append("")

    if attr.by_strategy:
        out.append("### By strategy")
        out.append("")
        out.append("| Strategy fingerprint                                            | Realised        | Fees            | Trades |")
        out.append("| --------------------------------------------------------------- | --------------- | --------------- | ------ |")
        rows = sorted(
            attr.by_strategy.items(),
            key=lambda kv: kv[1].get("realized", 0.0),
            reverse=True,
        )
        for fp, bucket in rows:
            short_fp = fp if len(fp) <= 60 else fp[:57] + "..."
            out.append(
                f"| `{short_fp:60s}` | {_fmt_money(bucket.get('realized', 0.0)):>15s} "
                f"| {_fmt_money(bucket.get('fees', 0.0)):>15s} | {int(bucket.get('trades', 0)):>6d} |"
            )
        out.append("")

    return "\n".join(out)


def _render_trades_block(trades: tuple[RoundTrip, ...], *, top_n: int) -> str:
    if not trades:
        return "## Top trades\n\n_No closed trades in this session._\n"
    sorted_by_pnl = sorted(trades, key=lambda t: t.pnl, reverse=True)
    winners = sorted_by_pnl[:top_n]
    losers = list(reversed(sorted_by_pnl[-top_n:]))

    out = [
        "## Top trades",
        "",
        f"### Top {len(winners)} winners",
        "",
        "| Side  | Instrument         | Qty   | Entry → Exit         | PnL             | Fees  |",
        "| ----- | ------------------ | ----- | -------------------- | --------------- | ----- |",
    ]
    for t in winners:
        out.append(_render_trade_row(t))
    out.append("")

    if losers != winners:
        out.append(f"### Top {len(losers)} detractors")
        out.append("")
        out.append("| Side  | Instrument         | Qty   | Entry → Exit         | PnL             | Fees  |")
        out.append("| ----- | ------------------ | ----- | -------------------- | --------------- | ----- |")
        for t in losers:
            out.append(_render_trade_row(t))
        out.append("")

    return "\n".join(out)


def _render_trade_row(t: RoundTrip) -> str:
    arrow = f"{t.entry_price:.4f} → {t.exit_price:.4f}"
    return (
        f"| {t.side:5s} | `{t.instrument:18s}` | {t.qty:5.4f} | {arrow:20s} "
        f"| {_fmt_money(t.pnl):>15s} | {_fmt_money(t.fees):>5s} |"
    )


def _render_slippage_block(slip: SlippageReport) -> str:
    out = [
        "## Slippage",
        "",
        f"- **Total slippage cost**: `{_fmt_money(slip.total_slippage_cost)}`",
        f"- **Avg / p50 / p95 / worst**: "
        f"{_fmt_bps(slip.avg_slippage_bps)} · "
        f"{_fmt_bps(slip.p50_slippage_bps)} · "
        f"{_fmt_bps(slip.p95_slippage_bps)} · "
        f"{_fmt_bps(slip.worst_slippage_bps)}",
        f"- **Coverage**: {slip.fills_with_reference} / {slip.fills_total} "
        f"fills had a reference price ({slip.fills_missing_reference} skipped).",
        "",
    ]
    if slip.by_instrument:
        out.append("### By instrument")
        out.append("")
        out.append("| Instrument         | Fills | Avg slippage     | Total cost        |")
        out.append("| ------------------ | ----- | ---------------- | ----------------- |")
        rows = sorted(
            slip.by_instrument.items(),
            key=lambda kv: kv[1].get("total_cost", 0.0),
            reverse=True,
        )
        for instrument, bucket in rows:
            out.append(
                f"| `{instrument:18s}` | {int(bucket.get('count', 0)):>5d} "
                f"| {_fmt_bps(bucket.get('avg_bps', 0.0)):>16s} "
                f"| {_fmt_money(bucket.get('total_cost', 0.0)):>17s} |"
            )
        out.append("")

    return "\n".join(out)


def _render_policy_block(policy: RiskPolicy) -> str:
    p = policy.to_dict()
    rows = [
        ("Kill switch", "ON ⚠" if p.get("kill_switch") else "off"),
        ("Allow short", "yes" if p.get("allow_short") else "no"),
        ("Max order qty", _fmt_or_dash(p.get("max_order_qty"))),
        ("Max position notional", _fmt_or_dash(p.get("max_position_notional"))),
        ("Max open positions", _fmt_or_dash(p.get("max_open_positions"))),
        ("Max daily loss", _fmt_or_dash(p.get("max_daily_loss"))),
        (
            "Allowed instruments",
            ", ".join(p.get("allowed_instruments") or []) or "(any)",
        ),
    ]
    body = "\n".join(f"| {label:22s} | {value:30s} |" for label, value in rows)
    notes = p.get("notes") or ""
    out = [
        "## Risk policy",
        "",
        "| Setting                | Value                          |",
        "| ---------------------- | ------------------------------ |",
        body,
    ]
    if notes:
        out.append("")
        out.append(f"_Notes_: {notes}")
    out.append("")
    return "\n".join(out)


def _render_positions_block(positions: list[Mapping]) -> str:
    out = [
        "## Open positions",
        "",
        "| Instrument         | Qty       | Avg price       | Realised        | Unrealised      |",
        "| ------------------ | --------- | --------------- | --------------- | --------------- |",
    ]
    for p in positions:
        out.append(
            f"| `{str(p.get('instrument', '')):18s}` | {float(p.get('qty', 0.0)):>9.4f} "
            f"| {_fmt_money(float(p.get('avg_price', 0.0))):>15s} "
            f"| {_fmt_money(float(p.get('realized_pnl', 0.0))):>15s} "
            f"| {_fmt_money(float(p.get('unrealized_pnl', 0.0))):>15s} |"
        )
    out.append("")
    return "\n".join(out)


def _fmt_or_dash(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int, float)):
        return _fmt_money(float(x))
    return str(x)
