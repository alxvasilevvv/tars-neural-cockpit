"""Council orchestrator.

Modes:

- ``single``     — one voice, no contention.
- ``dual_vote``  — two voices propose; arbiter picks; agreement reported.
- ``n_vote``     — generic over N voices; majority-by-stance wins; ties
                   resolved by highest mean confidence.

Every deliberation emits a ``sampler.decision`` event so meeet can
build per-model leaderboards across products.

Voices are queried **in parallel** via ``asyncio.gather``. With three
LLM voices configured (each capped at the LLM client's 12s timeout),
serial deliberation could take up to ~36s; gather collapses that to
``max(latency_per_voice)`` so a slow cloud voice never starves the
local voice's contribution. Individual voice failures are isolated:
they materialise as ``unavailable`` proposals (``stance='unavailable'``,
``confidence=0.0``) and the orchestrator continues. ``usage.tokens``
events are still emitted serially after the gather in input order so
the cost ledger remains deterministic.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from backend.core.meeet import (
    current_route,
    current_thread_id,
    get_client,
    new_trace_id,
    set_route,
    trace_scope,
)
from backend.core.usage import default_price_table

from .llm import detect_llm_voice
from .voices import LocalVoice, MockCloudVoice, Proposal, Voice


_PRICE_TABLE = default_price_table()


def _is_cloud_voice(model: str) -> bool:
    if not model:
        return False
    return model.startswith(("anthropic/", "openai/"))


def _default_voice_panel() -> list[Voice]:
    """Build the default voice panel.

    Always includes the deterministic pair. Adds a third LLM voice if
    a provider key is configured.
    """

    panel: list[Voice] = [LocalVoice(), MockCloudVoice()]
    llm = detect_llm_voice()
    if llm is not None:
        panel.append(llm)
    return panel


def _exception_proposal(model: str, exc: BaseException, latency_ms: float) -> Proposal:
    """Materialise a per-voice exception as an ``unavailable`` proposal.

    The orchestrator runs voices in parallel via ``asyncio.gather`` with
    ``return_exceptions=True``; that means a single voice raising can
    never crash the deliberation. We surface the failure as the same
    ``unavailable`` shape ``llm.py`` already uses for missing keys /
    transport errors so downstream code (``_winner`` / ``_agreement``
    / ``_contradictions``) keeps a single contract.
    """

    return Proposal(
        model=model or "unknown",
        stance="unavailable",
        summary=f"UNAVAILABLE — {type(exc).__name__}.",
        actions_recommended=(),
        confidence=0.0,
        rationale=f"{type(exc).__name__}: {exc}",
        latency_ms=latency_ms,
        tokens_in=0,
        tokens_out=0,
    )


async def _propose_one(voice: Voice, prompt: str, context: Mapping[str, Any]) -> Proposal:
    """Run one voice with its own latency stopwatch.

    The timing fallback is here (and not on each voice) so even voices
    that forget to stamp ``latency_ms`` themselves still get a useful
    number for the cost ledger / sampler.decision rollup.
    """

    started = time.perf_counter()
    p = await voice.propose(prompt, context)
    if not getattr(p, "latency_ms", 0):
        p = Proposal(
            model=p.model,
            stance=p.stance,
            summary=p.summary,
            actions_recommended=p.actions_recommended,
            confidence=p.confidence,
            rationale=p.rationale,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            tokens_in=p.tokens_in,
            tokens_out=p.tokens_out,
        )
    return p


@dataclass(frozen=True)
class Deliberation:
    mode: str
    chosen: str
    summary: str
    agreement: float  # 0..1
    voices: tuple[Proposal, ...]
    contradictions: tuple[str, ...] = ()
    actions_recommended: tuple[str, ...] = ()
    trace_id: str | None = None
    sampler_decision_id: str | None = None
    arbiter: str | None = None
    cost_usd: float | None = None
    route: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "chosen": self.chosen,
            "summary": self.summary,
            "agreement": round(float(self.agreement), 3),
            "voices": [v.to_dict() for v in self.voices],
            "contradictions": list(self.contradictions),
            "actions_recommended": list(self.actions_recommended),
            "trace_id": self.trace_id,
            "sampler_decision_id": self.sampler_decision_id,
            "arbiter": self.arbiter,
            "cost_usd": self.cost_usd,
            "route": self.route,
        }


def _is_available(p: Proposal) -> bool:
    return p.stance != "unavailable"


def _agreement(voices: Iterable[Proposal]) -> float:
    voted = [v for v in voices if _is_available(v)]
    if not voted:
        return 0.0
    if len(voted) == 1:
        return 1.0
    counts = Counter(v.stance for v in voted)
    top_count = counts.most_common(1)[0][1]
    return round(top_count / len(voted), 3)


def _winner(voices: list[Proposal]) -> Proposal:
    """Pick a winner among voices.

    Strategy: count stances; the most-common stance wins. Ties go to the
    voice with the highest confidence in that stance. With a single
    voice it just returns it. ``unavailable`` proposals are ignored.
    """

    if not voices:
        raise ValueError("no voices to choose from")
    voted = [v for v in voices if _is_available(v)]
    if not voted:
        # All voices unavailable — fall back to the first proposal so the
        # orchestrator still emits a deterministic shape.
        return voices[0]
    if len(voted) == 1:
        return voted[0]
    counts = Counter(v.stance for v in voted)
    top_count = counts.most_common(1)[0][1]
    top_stances = {s for s, c in counts.items() if c == top_count}
    candidates = [v for v in voted if v.stance in top_stances]
    candidates.sort(key=lambda v: (v.confidence, len(v.summary)), reverse=True)
    return candidates[0]


def _contradictions(voices: list[Proposal]) -> list[str]:
    voted = [v for v in voices if _is_available(v)]
    if len(voted) < 2:
        return []
    counts = Counter(v.stance for v in voted)
    if len(counts) <= 1:
        return []
    out: list[str] = []
    seen: set[tuple[str, str]] = set()
    for a in voted:
        for b in voted:
            if a.model >= b.model:
                continue
            if a.stance == b.stance:
                continue
            key = (a.model, b.model)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                f"{a.model}({a.stance}) ↔ {b.model}({b.stance})"
            )
    return out


class CouncilOrchestrator:
    """Runs multiple voices and arbitrates."""

    def __init__(self, voices: list[Voice] | None = None) -> None:
        self.voices: list[Voice] = list(voices) if voices is not None else _default_voice_panel()

    async def deliberate(
        self,
        prompt: str,
        context: Mapping[str, Any],
        *,
        mode: str = "dual_vote",
        thread_id: str | None = None,
    ) -> Deliberation:
        if mode not in {"single", "dual_vote", "n_vote"}:
            raise ValueError(f"unknown council mode: {mode}")

        if not thread_id:
            thread_id = current_thread_id()

        if mode == "single":
            chosen_voices = self.voices[:1]
        elif mode == "dual_vote":
            chosen_voices = self.voices[:2]
        else:  # n_vote — use every voice configured (incl. LLM if present)
            chosen_voices = list(self.voices)

        if not chosen_voices:
            raise ValueError("no voices configured")

        client = get_client()
        with trace_scope() as tid:
            started_payload: dict[str, Any] = {
                "mode": mode,
                "voices": [v.model for v in chosen_voices],
                "topic": context.get("topic"),
            }
            if thread_id:
                started_payload["thread_id"] = thread_id
            await client.emit("council.deliberation.started", started_payload)

            # Run every voice concurrently. ``return_exceptions=True``
            # means one slow / broken voice never starves the others —
            # the failure becomes an ``unavailable`` proposal so the
            # arbiter still has a deterministic shape to work with.
            raw_results = await asyncio.gather(
                *(_propose_one(voice, prompt, context) for voice in chosen_voices),
                return_exceptions=True,
            )

            proposals: list[Proposal] = []
            for voice, result in zip(chosen_voices, raw_results):
                if isinstance(result, BaseException):
                    proposals.append(_exception_proposal(voice.model, result, latency_ms=0.0))
                else:
                    proposals.append(result)

            # Bump the trace route to ``cloud`` if any cloud voice
            # actually returned. Idempotent on the trace scope, so
            # multiple cloud voices coexist cleanly.
            for p in proposals:
                if _is_cloud_voice(p.model) and p.stance != "unavailable":
                    set_route("cloud")

            # Emit usage.tokens serially after gather so the cost
            # ledger keeps deterministic ordering (in input order).
            for p in proposals:
                cost = _PRICE_TABLE.cost_usd(p.model, p.tokens_in, p.tokens_out)
                usage_payload: dict[str, Any] = {
                    "model": p.model,
                    "tokens_in": int(p.tokens_in),
                    "tokens_out": int(p.tokens_out),
                    "latency_ms": round(float(p.latency_ms), 3),
                    "cost_usd": cost,
                    "stance": p.stance,
                    "topic": context.get("topic"),
                }
                if thread_id:
                    usage_payload["thread_id"] = thread_id
                await client.emit("usage.tokens", usage_payload)

            winner = _winner(proposals)
            agreement = _agreement(proposals)
            contradictions = _contradictions(proposals)
            sampler_id = new_trace_id().replace("trc_", "smp_")

            total_cost = 0.0
            for p in proposals:
                c = _PRICE_TABLE.cost_usd(p.model, p.tokens_in, p.tokens_out)
                if c is not None:
                    total_cost += c

            # ``latency_ms`` here is the wall-clock cost of the
            # deliberation. With voices fanned out via asyncio.gather
            # the bound is ``max(per-voice latency)``; ``cumulative_ms``
            # keeps the sum-of-per-voice number for cost accounting
            # and per-model leaderboards.
            wall_latency_ms = max((v.latency_ms for v in proposals), default=0.0)
            cumulative_latency_ms = sum(v.latency_ms for v in proposals)
            sampler_payload: dict[str, Any] = {
                "id": sampler_id,
                "mode": mode,
                "models": [v.model for v in chosen_voices],
                "winner": winner.model,
                "winning_stance": winner.stance,
                "latency_ms": round(wall_latency_ms, 3),
                "cumulative_latency_ms": round(cumulative_latency_ms, 3),
                "tokens_in": sum(v.tokens_in for v in proposals),
                "tokens_out": sum(v.tokens_out for v in proposals),
                "cost_usd": round(total_cost, 6),
                "agreement": agreement,
                "contradictions": contradictions,
                "parallel": len(proposals) > 1,
            }
            if thread_id:
                sampler_payload["thread_id"] = thread_id
            await client.emit("sampler.decision", sampler_payload)

            completed_payload: dict[str, Any] = {
                "mode": mode,
                "chosen": winner.stance,
                "winner_model": winner.model,
                "agreement": agreement,
            }
            if thread_id:
                completed_payload["thread_id"] = thread_id
            await client.emit("council.deliberation.completed", completed_payload)

            return Deliberation(
                mode=mode,
                chosen=winner.stance,
                summary=winner.summary,
                agreement=agreement,
                voices=tuple(proposals),
                contradictions=tuple(contradictions),
                actions_recommended=tuple(winner.actions_recommended),
                trace_id=tid,
                sampler_decision_id=sampler_id,
                arbiter="confidence_weighted_majority",
                cost_usd=round(total_cost, 6) if total_cost > 0 else None,
                route=current_route(),
            )


_SINGLETON: Optional[CouncilOrchestrator] = None


def get_council() -> CouncilOrchestrator:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = CouncilOrchestrator()
    return _SINGLETON


def reset_council() -> None:
    global _SINGLETON
    _SINGLETON = None
