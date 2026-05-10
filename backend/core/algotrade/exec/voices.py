"""Trading council voices (W3-PR3).

Three deterministic, stdlib-only "agents" that read the W3-PR1
analytics dataclasses (or the W3-PR2 report payload) and emit
structured commentary the cockpit can render alongside the
markdown report. Each voice is a pure function — no LLM call —
because:

- **Workshop transparency.** Attendees can read every line of
  the reasoning and trust that the same numbers always produce
  the same verdict. A black-box LLM would undermine the "we
  audit everything" pitch.
- **Reproducibility.** Same audit log → same voices → same
  council consensus, so reports replay byte-for-byte.
- **Cost.** Workshops run dozens of sessions; spinning up an
  LLM for each is wasteful when the rules are this explicit.

Voices
------

- :func:`risk_analyst_voice` — reads the active
  :class:`RiskPolicy`, the realised PnL, the rejected-verdict
  count, and the slippage cost. Flags kill-switch breaches,
  daily-loss-limit proximity, repeated rejections, and slippage
  costs that swallow a large share of realised PnL.
- :func:`execution_trader_voice` — reads the
  :class:`SlippageReport` and execution counters. Flags
  outsized worst-fill slippage, low coverage (live adapter
  without reference prices), and low intent acceptance rate.
- :func:`pnl_auditor_voice` — reads the
  :class:`PnLAttribution`. Computes win rate, win/loss ratio,
  largest winner / detractor, fees-as-share-of-realised, and
  by-strategy concentration. Flags lopsided distributions and
  fee-heavy strategies.

Aggregation
-----------

:func:`run_council` returns an ordered ``CouncilReview`` whose
``consensus`` is the worst severity any voice raised
(``info`` < ``warn`` < ``alert``). The cockpit can colour-code
the review banner off ``consensus``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .analytics import PnLAttribution, SessionMetrics, SlippageReport
from .risk import RiskPolicy


_SEVERITY_ORDER = {"info": 0, "warn": 1, "alert": 2}


@dataclass(frozen=True)
class Voice:
    """One council voice's verdict on a session."""

    name: str
    """Stable identifier — the cockpit keys avatars off this."""
    role: str
    """Human-readable role label (``"Risk analyst"``, …)."""
    severity: str  # "info" | "warn" | "alert"
    headline: str
    """One-line summary the cockpit puts in the voice's card."""
    bullets: tuple[str, ...] = ()
    """Bullet-list rationale; cockpit renders as ``- bullet``."""
    metrics_consulted: tuple[str, ...] = ()
    """Audit trail: which numbers from the payload drove the
    verdict. Useful when an attendee asks "where did this
    bullet come from?"."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "severity": self.severity,
            "headline": self.headline,
            "bullets": list(self.bullets),
            "metrics_consulted": list(self.metrics_consulted),
        }


@dataclass(frozen=True)
class CouncilReview:
    """Bundle of voices + the overall consensus severity."""

    voices: tuple[Voice, ...]
    consensus: str  # "info" | "warn" | "alert"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "consensus": self.consensus,
            "voices": [v.to_dict() for v in self.voices],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------


def risk_analyst_voice(
    *,
    policy: RiskPolicy,
    metrics: SessionMetrics,
    slippage: SlippageReport,
) -> Voice:
    """Verdict: are we still inside the risk policy?"""

    bullets: list[str] = []
    severity = "info"
    consulted = ["policy.kill_switch", "metrics.intents_rejected"]

    if policy.kill_switch:
        severity = "alert"
        bullets.append(
            "Kill-switch is **ON** — the session is locked down. "
            "Any pending intent will be rejected at the gate."
        )
    if metrics.intents_total > 0:
        rate = metrics.intents_rejected / metrics.intents_total
        if rate >= 0.5:
            severity = _max_severity(severity, "alert")
            bullets.append(
                f"Rejection rate is **{rate * 100:.0f}%** "
                f"({metrics.intents_rejected}/{metrics.intents_total}) "
                "— policy is over-clamping or strategy is "
                "consistently mis-sized."
            )
        elif rate >= 0.2:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Rejection rate is **{rate * 100:.0f}%** "
                f"({metrics.intents_rejected}/{metrics.intents_total}) "
                "— investigate which rule fired most."
            )

    if policy.max_daily_loss is not None and metrics.realized_pnl < 0:
        loss = abs(metrics.realized_pnl)
        cushion = policy.max_daily_loss - loss
        consulted.append("policy.max_daily_loss")
        consulted.append("metrics.realized_pnl")
        if cushion <= 0:
            severity = _max_severity(severity, "alert")
            bullets.append(
                f"Daily-loss cap **breached**: realised loss "
                f"{loss:,.4f} ≥ max {policy.max_daily_loss:,.4f}. "
                "Live trading would auto-flatten."
            )
        elif cushion <= policy.max_daily_loss * 0.25:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Daily-loss cushion is **thin**: only "
                f"{cushion:,.4f} left of {policy.max_daily_loss:,.4f}. "
                "Consider tightening sizing."
            )

    if metrics.realized_pnl > 0 and slippage.total_slippage_cost > 0:
        share = slippage.total_slippage_cost / metrics.realized_pnl
        consulted.append("slippage.total_slippage_cost")
        if share >= 0.5:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Slippage cost is **{share * 100:.0f}%** of "
                "realised PnL — execution is eating the edge."
            )

    if not bullets:
        bullets.append(
            "Policy is healthy: rejection rate low, daily-loss "
            "cushion wide, slippage cost reasonable vs realised PnL."
        )

    return Voice(
        name="risk_analyst",
        role="Risk analyst",
        severity=severity,
        headline=_risk_headline(severity, policy, metrics),
        bullets=tuple(bullets),
        metrics_consulted=tuple(consulted),
    )


def execution_trader_voice(
    *,
    metrics: SessionMetrics,
    slippage: SlippageReport,
) -> Voice:
    """Verdict: are we filling cleanly?"""

    bullets: list[str] = []
    severity = "info"
    consulted = [
        "slippage.avg_slippage_bps",
        "slippage.worst_slippage_bps",
        "slippage.fills_with_reference",
        "slippage.fills_total",
    ]

    if slippage.fills_total == 0:
        return Voice(
            name="execution_trader",
            role="Execution trader",
            severity="info",
            headline="No fills yet — nothing to grade.",
            bullets=("Submit some intents and feed bars to "
                     "generate fills before requesting a council "
                     "review.",),
            metrics_consulted=tuple(consulted),
        )

    if slippage.fills_with_reference == 0:
        severity = _max_severity(severity, "warn")
        bullets.append(
            "**Zero fills had a reference price** — the live "
            "adapter is not populating `Fill.reference_price`, so "
            "slippage stats are unavailable. Cockpit cannot grade "
            "execution quality."
        )
    else:
        if slippage.avg_slippage_bps >= 10.0:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Average slippage is **{slippage.avg_slippage_bps:+.1f} bps** "
                "— above the 10 bp comfort threshold."
            )
        if slippage.worst_slippage_bps >= 30.0:
            severity = _max_severity(severity, "alert")
            bullets.append(
                f"Worst single fill paid **{slippage.worst_slippage_bps:+.1f} bps**. "
                "Investigate that bar (thin liquidity? news event?)."
            )
        coverage = slippage.fills_with_reference / slippage.fills_total
        if coverage < 0.9:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Reference-price coverage is **{coverage * 100:.0f}%** "
                "— some fills were skipped from slippage stats."
            )

    if metrics.intents_total > 0:
        accept_rate = metrics.intents_accepted / metrics.intents_total
        consulted.append("metrics.acceptance_rate")
        if accept_rate < 0.7:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Intent acceptance rate is **{accept_rate * 100:.0f}%** "
                "— gate is rejecting too much; trader is being "
                "throttled."
            )

    if metrics.fills_total > 0 and metrics.cancels_total / max(1, metrics.orders_total) >= 0.3:
        severity = _max_severity(severity, "warn")
        bullets.append(
            f"Cancel ratio is **{metrics.cancels_total}/{metrics.orders_total} "
            f"({metrics.cancels_total / metrics.orders_total * 100:.0f}%)** "
            "— consider switching to limit orders inside spread."
        )

    if not bullets:
        bullets.append(
            f"Execution looks clean: avg slippage "
            f"{slippage.avg_slippage_bps:+.1f} bps, worst "
            f"{slippage.worst_slippage_bps:+.1f} bps, full "
            "reference coverage."
        )

    return Voice(
        name="execution_trader",
        role="Execution trader",
        severity=severity,
        headline=_execution_headline(severity, slippage),
        bullets=tuple(bullets),
        metrics_consulted=tuple(consulted),
    )


def pnl_auditor_voice(
    *,
    attribution: PnLAttribution,
    metrics: SessionMetrics,
) -> Voice:
    """Verdict: how is the strategy actually making (or losing) money?"""

    bullets: list[str] = []
    severity = "info"
    consulted = ["attribution.trades", "attribution.realized_total"]

    trades = attribution.trades
    if not trades:
        return Voice(
            name="pnl_auditor",
            role="PnL auditor",
            severity="info",
            headline="No closed round-trips — PnL audit deferred.",
            bullets=("Run the strategy until at least one trade "
                     "closes before requesting a council review.",),
            metrics_consulted=tuple(consulted),
        )

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]
    win_rate = len(winners) / len(trades)
    avg_win = sum(t.pnl for t in winners) / len(winners) if winners else 0.0
    avg_loss = (
        sum(t.pnl for t in losers) / len(losers) if losers else 0.0
    )
    biggest = max(trades, key=lambda t: t.pnl)
    worst = min(trades, key=lambda t: t.pnl)

    consulted.extend([
        "attribution.trades.pnl",
        "attribution.fees_total",
        "attribution.by_strategy",
    ])

    bullets.append(
        f"**Win rate {win_rate * 100:.0f}%** "
        f"({len(winners)} winners / {len(losers)} losers / "
        f"{len(trades)} round-trips)."
    )
    if winners and losers:
        ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
        ratio_str = f"{ratio:.2f}x" if ratio != float("inf") else "∞"
        bullets.append(
            f"Avg win **{avg_win:,.4f}** vs avg loss "
            f"**{avg_loss:,.4f}** → win/loss ratio **{ratio_str}**."
        )
        if win_rate < 0.4 and ratio < 2.0:
            severity = _max_severity(severity, "alert")
            bullets.append(
                "Edge is fragile: low win-rate AND low win/loss "
                "ratio. Strategy needs a sizing or filter pass."
            )
        elif win_rate < 0.4:
            severity = _max_severity(severity, "warn")
            bullets.append(
                "Low win-rate — only viable if the win/loss ratio "
                "stays high; review filter conditions."
            )

    if biggest.pnl > 0 and biggest.pnl > 0.5 * attribution.realized_total > 0:
        severity = _max_severity(severity, "warn")
        bullets.append(
            f"**Concentration risk**: biggest single trip "
            f"({biggest.instrument}, +{biggest.pnl:,.4f}) is over "
            "50% of total realised PnL — the run isn't repeatable."
        )

    if attribution.realized_total != 0 and attribution.fees_total > 0:
        fee_share = attribution.fees_total / abs(attribution.realized_total)
        consulted.append("attribution.fees_total")
        if fee_share >= 0.3:
            severity = _max_severity(severity, "warn")
            bullets.append(
                f"Fees consumed **{fee_share * 100:.0f}%** of "
                "realised PnL — strategy is fee-heavy; consider "
                "fewer / larger trades."
            )

    if attribution.by_strategy and len(attribution.by_strategy) >= 2:
        top = max(
            attribution.by_strategy.items(),
            key=lambda kv: kv[1].get("realized", 0.0),
        )
        consulted.append("attribution.by_strategy")
        bullets.append(
            f"Top contributor: `{_short_fp(top[0])}` with "
            f"realised **{top[1].get('realized', 0.0):,.4f}**."
        )

    if worst.pnl < 0:
        bullets.append(
            f"Worst trip: {worst.side} on {worst.instrument}, "
            f"PnL **{worst.pnl:,.4f}** "
            f"(entry {worst.entry_price:.4f} → exit {worst.exit_price:.4f})."
        )

    return Voice(
        name="pnl_auditor",
        role="PnL auditor",
        severity=severity,
        headline=_pnl_headline(severity, attribution, win_rate),
        bullets=tuple(bullets),
        metrics_consulted=tuple(consulted),
    )


# ---------------------------------------------------------------------
# Council
# ---------------------------------------------------------------------


def run_council(
    *,
    policy: RiskPolicy,
    metrics: SessionMetrics,
    attribution: PnLAttribution,
    slippage: SlippageReport,
) -> CouncilReview:
    """Invoke all three voices, return the bundled review."""

    voices = (
        risk_analyst_voice(
            policy=policy, metrics=metrics, slippage=slippage
        ),
        execution_trader_voice(metrics=metrics, slippage=slippage),
        pnl_auditor_voice(attribution=attribution, metrics=metrics),
    )
    consensus = "info"
    for v in voices:
        consensus = _max_severity(consensus, v.severity)
    notes = _consensus_note(consensus)
    return CouncilReview(voices=voices, consensus=consensus, notes=notes)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _max_severity(a: str, b: str) -> str:
    return a if _SEVERITY_ORDER.get(a, 0) >= _SEVERITY_ORDER.get(b, 0) else b


def _short_fp(fp: str) -> str:
    return fp if len(fp) <= 22 else fp[:19] + "..."


def _risk_headline(
    severity: str, policy: RiskPolicy, metrics: SessionMetrics
) -> str:
    if severity == "alert":
        if policy.kill_switch:
            return "Kill-switch engaged — session locked."
        return "Risk policy is being breached."
    if severity == "warn":
        return "Risk policy is holding but warrants attention."
    return "Risk policy is healthy."


def _execution_headline(severity: str, slippage: SlippageReport) -> str:
    if severity == "alert":
        return "Execution quality is materially degraded."
    if severity == "warn":
        return "Execution is workable but worth tightening."
    if slippage.fills_total == 0:
        return "No fills graded yet."
    return "Execution looks clean."


def _pnl_headline(
    severity: str, attribution: PnLAttribution, win_rate: float
) -> str:
    if severity == "alert":
        return "PnL distribution looks fragile."
    if severity == "warn":
        return "PnL is positive but skewed — investigate."
    if attribution.realized_total > 0:
        return (
            f"Strategy is profitable: realised "
            f"{attribution.realized_total:,.4f}, "
            f"win rate {win_rate * 100:.0f}%."
        )
    return "PnL is at-or-below break-even; review the trade ledger."


def _consensus_note(consensus: str) -> str:
    if consensus == "alert":
        return (
            "At least one voice raised an ALERT. The cockpit "
            "should highlight this session in the review queue."
        )
    if consensus == "warn":
        return (
            "Voices flagged some tighten-able items but no "
            "alerts. Safe to continue."
        )
    return "Council agrees the session looks healthy."
