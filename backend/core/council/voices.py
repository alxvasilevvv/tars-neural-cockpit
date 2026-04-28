"""Voices — deterministic and LLM-pluggable proposal generators.

Two real voices ship today:

- ``LocalVoice`` is rule-based, fast, and offline. It looks at the
  ``context`` dict for known shapes (market basket, KPI deltas,
  retention list) and produces a structured proposal.
- ``MockCloudVoice`` is a deliberately *different* deterministic policy
  (more conservative under dispersion, emphasizes downside) so the
  orchestrator has something to disagree with even with no LLM keys
  configured.

A third slot is reserved for a real LLM adapter — drop in a class that
inherits :class:`Voice` and registers itself.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Proposal:
    """A single voice's proposal."""

    model: str
    stance: str  # short, comparable label like "risk_off" / "risk_on" / "neutral"
    summary: str
    actions_recommended: tuple[str, ...] = ()
    confidence: float = 0.5
    rationale: str = ""
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "stance": self.stance,
            "summary": self.summary,
            "actions_recommended": list(self.actions_recommended),
            "confidence": round(float(self.confidence), 3),
            "rationale": self.rationale,
            "latency_ms": round(float(self.latency_ms), 3),
            "tokens": {"in": self.tokens_in, "out": self.tokens_out},
        }


class Voice(ABC):
    """Voices propose. The orchestrator decides."""

    model: str

    @abstractmethod
    async def propose(
        self, prompt: str, context: Mapping[str, Any]
    ) -> Proposal:  # pragma: no cover - abstract
        ...


# ---------------------------------------------------------------------------
# helpers shared by both deterministic voices
# ---------------------------------------------------------------------------

_RISK_OFF_THRESHOLD = -0.5
_RISK_ON_THRESHOLD = 0.5


def _market_stance(avg_change: float | None) -> str:
    if avg_change is None:
        return "uncertain"
    if avg_change <= _RISK_OFF_THRESHOLD:
        return "risk_off"
    if avg_change >= _RISK_ON_THRESHOLD:
        return "risk_on"
    return "neutral"


def _kpi_stance(deltas: list[Mapping[str, Any]] | None) -> str:
    if not deltas:
        return "uncertain"
    positives = 0
    negatives = 0
    for d in deltas:
        v = d.get("delta_pct")
        if not isinstance(v, (int, float)):
            continue
        if d.get("id") == "logo_churn_pct":
            # Down churn is good for the business stance.
            if v < 0:
                positives += 1
            elif v > 0:
                negatives += 1
            continue
        if v > 0:
            positives += 1
        elif v < 0:
            negatives += 1
    if positives > negatives:
        return "expanding"
    if negatives > positives:
        return "contracting"
    return "steady"


def _format_kpi_summary(stance: str, deltas: list[Mapping[str, Any]]) -> str:
    headline = next((d for d in deltas if d.get("id") == "mrr_usd"), None)
    if headline and isinstance(headline.get("delta_pct"), (int, float)):
        v = headline["delta_pct"]
        verb = "up" if v >= 0 else "down"
        return f"{stance.upper()} — MRR {verb} {abs(v):.1f}%."
    return f"{stance.upper()} — no MRR delta available."


def _format_market_summary(stance: str, avg_change: float | None) -> str:
    if avg_change is None:
        return f"{stance.upper()} — basket bias unclear (no 24h change data)."
    return f"{stance.upper()} — basket {avg_change:+.2f}% / 24h."


# ---------------------------------------------------------------------------
# Local rule-based voice
# ---------------------------------------------------------------------------


class LocalVoice(Voice):
    """Deterministic, rule-based, offline."""

    model = "tars-local-rules-v1"

    async def propose(
        self, prompt: str, context: Mapping[str, Any]
    ) -> Proposal:
        started = time.perf_counter()
        topic = (context.get("topic") or "").lower()
        if topic == "market":
            avg_change = context.get("avg_change_24h")
            stance = _market_stance(
                float(avg_change) if isinstance(avg_change, (int, float)) else None
            )
            summary = _format_market_summary(
                stance,
                float(avg_change) if isinstance(avg_change, (int, float)) else None,
            )
            actions: list[str] = []
            if stance == "risk_off":
                actions = ["tighten_stops", "reduce_alt_exposure"]
            elif stance == "risk_on":
                actions = ["scale_in_basket"]
            else:
                actions = ["hold"]
            confidence = 0.7 if stance != "uncertain" else 0.35
            rationale = (
                f"Average 24h move {avg_change}; below {_RISK_OFF_THRESHOLD}% means "
                f"de-risk. Above {_RISK_ON_THRESHOLD}% means lean in. Else hold."
            )
        elif topic == "kpi":
            deltas = list(context.get("deltas") or [])
            stance = _kpi_stance(deltas)
            summary = _format_kpi_summary(stance, deltas)
            calendar_today = list(context.get("calendar_today") or [])
            actions = []
            if calendar_today:
                actions.append(
                    f"prep_for_{calendar_today[0].get('kind', 'meeting')}"
                )
            if stance == "contracting":
                actions.append("review_pipeline_top_3")
            elif stance == "expanding":
                actions.append("double_down_on_winners")
            confidence = 0.65 if stance != "uncertain" else 0.3
            rationale = (
                "Counts positive vs negative deltas across mrr/pipeline/nps; "
                "treats logo_churn_pct as inverted."
            )
        else:
            stance = "uncertain"
            summary = (
                "LocalVoice has no domain template for this topic — passing."
            )
            actions = []
            confidence = 0.2
            rationale = "no_template"

        return Proposal(
            model=self.model,
            stance=stance,
            summary=summary,
            actions_recommended=tuple(actions),
            confidence=confidence,
            rationale=rationale,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            tokens_in=len(prompt) // 4,
            tokens_out=len(summary) // 4,
        )


# ---------------------------------------------------------------------------
# Mock cloud voice — deliberately disagrees under dispersion
# ---------------------------------------------------------------------------


class MockCloudVoice(Voice):
    """Stand-in for a real LLM voice.

    Implements a more conservative policy: under high dispersion or
    contradictions it tilts toward de-risking even when the basket
    average is mildly positive.
    """

    model = "tars-mock-cloud-v1"

    async def propose(
        self, prompt: str, context: Mapping[str, Any]
    ) -> Proposal:
        started = time.perf_counter()
        topic = (context.get("topic") or "").lower()
        if topic == "market":
            avg_change = context.get("avg_change_24h")
            avg = float(avg_change) if isinstance(avg_change, (int, float)) else None
            contradictions = list(context.get("contradictions") or [])
            base_stance = _market_stance(avg)
            # Conservative tilt under dispersion.
            if contradictions and base_stance == "neutral":
                stance = "risk_off"
            elif contradictions and base_stance == "risk_on" and avg is not None and avg < 1.5:
                stance = "neutral"
            else:
                stance = base_stance
            actions: list[str] = []
            if stance == "risk_off":
                actions = ["tighten_stops", "raise_cash_buffer"]
            elif stance == "risk_on":
                actions = ["partial_scale_in"]
            else:
                actions = ["watch_hourly_closes"]
            confidence = 0.65 if stance != "uncertain" else 0.35
            rationale = (
                "Conservative arbiter: respects basket bias but de-risks "
                "when dispersion contradictions are present."
            )
            summary = _format_market_summary(stance, avg)
        elif topic == "kpi":
            deltas = list(context.get("deltas") or [])
            base = _kpi_stance(deltas)
            calendar_today = list(context.get("calendar_today") or [])
            # Cloud voice flags churn even when MRR is up.
            churn = next(
                (d for d in deltas if d.get("id") == "logo_churn_pct"),
                None,
            )
            stance = base
            if churn and isinstance(churn.get("delta_pct"), (int, float)) and churn["delta_pct"] > 0 and base == "expanding":
                stance = "steady"
            actions = []
            if calendar_today:
                actions.append("send_pre_meeting_brief")
            if stance == "contracting":
                actions.append("retention_call_top_at_risk")
            elif stance == "steady":
                actions.append("audit_pipeline_health")
            else:
                actions.append("prepare_quarterly_update")
            summary = _format_kpi_summary(stance, deltas)
            confidence = 0.6
            rationale = (
                "Cross-checks churn against MRR; tones down expansion when "
                "churn is rising."
            )
        else:
            stance = "uncertain"
            summary = "MockCloudVoice has no template for this topic."
            actions = []
            confidence = 0.2
            rationale = "no_template"

        return Proposal(
            model=self.model,
            stance=stance,
            summary=summary,
            actions_recommended=tuple(actions),
            confidence=confidence,
            rationale=rationale,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            tokens_in=len(prompt) // 4,
            tokens_out=len(summary) // 4,
        )
