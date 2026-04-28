"""Council orchestrator.

Modes:

- ``single``     — one voice, no contention.
- ``dual_vote``  — two voices propose; arbiter picks; agreement reported.
- ``n_vote``     — generic over N voices; majority-by-stance wins; ties
                   resolved by highest mean confidence.

Every deliberation emits a ``sampler.decision`` event so meeet can
build per-model leaderboards across products.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from backend.core.meeet import current_trace, get_client, new_trace_id, trace_scope

from .llm import detect_llm_voice
from .voices import LocalVoice, MockCloudVoice, Proposal, Voice


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
    ) -> Deliberation:
        if mode not in {"single", "dual_vote", "n_vote"}:
            raise ValueError(f"unknown council mode: {mode}")

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
            await client.emit(
                "council.deliberation.started",
                {
                    "mode": mode,
                    "voices": [v.model for v in chosen_voices],
                    "topic": context.get("topic"),
                },
            )

            proposals: list[Proposal] = []
            for voice in chosen_voices:
                p = await voice.propose(prompt, context)
                proposals.append(p)

            winner = _winner(proposals)
            agreement = _agreement(proposals)
            contradictions = _contradictions(proposals)
            sampler_id = new_trace_id().replace("trc_", "smp_")

            await client.emit(
                "sampler.decision",
                {
                    "id": sampler_id,
                    "mode": mode,
                    "models": [v.model for v in chosen_voices],
                    "winner": winner.model,
                    "winning_stance": winner.stance,
                    "latency_ms": round(
                        sum(v.latency_ms for v in proposals), 3
                    ),
                    "tokens_in": sum(v.tokens_in for v in proposals),
                    "tokens_out": sum(v.tokens_out for v in proposals),
                    "agreement": agreement,
                    "contradictions": contradictions,
                },
            )

            await client.emit(
                "council.deliberation.completed",
                {
                    "mode": mode,
                    "chosen": winner.stance,
                    "winner_model": winner.model,
                    "agreement": agreement,
                },
            )

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
