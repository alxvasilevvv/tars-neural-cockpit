"""Tests for the council orchestrator (Phase C)."""

from __future__ import annotations

import asyncio

import pytest

from backend.core.council import (
    CouncilOrchestrator,
    Deliberation,
    LocalVoice,
    MockCloudVoice,
    Proposal,
)
from backend.core.council.voices import Voice


def test_local_voice_market_risk_off() -> None:
    out = asyncio.run(
        LocalVoice().propose(
            "interpret",
            {"topic": "market", "avg_change_24h": -1.5},
        )
    )
    assert out.stance == "risk_off"
    assert "tighten_stops" in out.actions_recommended
    assert "RISK_OFF" in out.summary


def test_local_voice_market_neutral_when_flat() -> None:
    out = asyncio.run(
        LocalVoice().propose("interpret", {"topic": "market", "avg_change_24h": 0.1})
    )
    assert out.stance == "neutral"


def test_mock_cloud_voice_tilts_conservative_under_dispersion() -> None:
    ctx = {
        "topic": "market",
        "avg_change_24h": 0.1,  # neutral
        "contradictions": [{"detail": "a +5 vs b -3"}],
    }
    out = asyncio.run(MockCloudVoice().propose("x", ctx))
    assert out.stance == "risk_off"


def test_orchestrator_dual_vote_with_full_disagreement() -> None:
    council = CouncilOrchestrator()
    deliberation = asyncio.run(
        council.deliberate(
            "interpret",
            {
                "topic": "market",
                "avg_change_24h": 0.1,
                "contradictions": [{"detail": "x"}],
            },
            mode="dual_vote",
        )
    )
    assert isinstance(deliberation, Deliberation)
    assert len(deliberation.voices) == 2
    # Local is "neutral", mock is "risk_off" → agreement should be 0.5.
    assert deliberation.agreement == 0.5
    assert deliberation.contradictions
    assert deliberation.sampler_decision_id and deliberation.sampler_decision_id.startswith("smp_")


def test_orchestrator_dual_vote_with_full_agreement() -> None:
    council = CouncilOrchestrator()
    deliberation = asyncio.run(
        council.deliberate(
            "interpret",
            {"topic": "market", "avg_change_24h": -1.5},
            mode="dual_vote",
        )
    )
    assert deliberation.agreement == 1.0
    assert not deliberation.contradictions
    assert deliberation.chosen == "risk_off"


def test_orchestrator_single_mode_runs_one_voice() -> None:
    council = CouncilOrchestrator()
    deliberation = asyncio.run(
        council.deliberate(
            "interpret",
            {"topic": "market", "avg_change_24h": 1.0},
            mode="single",
        )
    )
    assert len(deliberation.voices) == 1
    assert deliberation.agreement == 1.0


def test_orchestrator_rejects_unknown_mode() -> None:
    council = CouncilOrchestrator()
    with pytest.raises(ValueError):
        asyncio.run(
            council.deliberate("interpret", {"topic": "market"}, mode="quad")
        )


def test_orchestrator_n_vote_with_three_voices() -> None:
    class StubVoice(Voice):
        def __init__(self, model: str, stance: str) -> None:
            self.model = model
            self.stance = stance

        async def propose(self, prompt, context):
            return Proposal(
                model=self.model,
                stance=self.stance,
                summary=f"{self.stance.upper()}",
                confidence=0.6,
            )

    council = CouncilOrchestrator(
        voices=[
            StubVoice("a", "risk_off"),
            StubVoice("b", "risk_off"),
            StubVoice("c", "risk_on"),
        ]
    )
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    assert deliberation.chosen == "risk_off"
    assert pytest.approx(deliberation.agreement, abs=1e-3) == 0.667
    assert deliberation.contradictions
