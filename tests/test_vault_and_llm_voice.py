"""Tests for the secrets vault and the LLM-backed council voice (Phase F).

Network calls are stubbed out — the LLM voice is exercised against a
fake POST function so the suite stays offline.
"""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

from backend.core.council import (
    AnthropicVoice,
    CouncilOrchestrator,
    OpenAIVoice,
    Proposal,
)
from backend.core.council import llm as llm_module
from backend.core.council.orchestrator import (
    _agreement,
    _contradictions,
    _winner,
)
from backend.core.vault import KNOWN_KEYS, get_secret, list_known
from backend.core.vault import keychain as kc_module


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------


def test_vault_env_takes_priority(monkeypatch) -> None:
    monkeypatch.setenv("TARS_ANTHROPIC_API_KEY", "from-env")
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: "from-keychain")
    assert get_secret("TARS_ANTHROPIC_API_KEY") == "from-env"


def test_vault_falls_back_to_keychain(monkeypatch) -> None:
    monkeypatch.delenv("TARS_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: "from-keychain")
    assert get_secret("TARS_ANTHROPIC_API_KEY") == "from-keychain"


def test_vault_returns_none_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("TARS_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)
    assert get_secret("TARS_ANTHROPIC_API_KEY") is None


def test_list_known_reports_each_key(monkeypatch) -> None:
    for k in KNOWN_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TARS_OPENAI_API_KEY", "x")
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)
    refs = list_known()
    keys = {r.key: r for r in refs}
    assert keys["TARS_OPENAI_API_KEY"].available is True
    assert keys["TARS_OPENAI_API_KEY"].source == "env"
    assert keys["TARS_ANTHROPIC_API_KEY"].available is False
    assert keys["TARS_ANTHROPIC_API_KEY"].source == "missing"


# ---------------------------------------------------------------------------
# LLM voice — Anthropic
# ---------------------------------------------------------------------------


def test_anthropic_voice_unavailable_when_no_key(monkeypatch) -> None:
    monkeypatch.delenv("TARS_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)
    voice = AnthropicVoice()
    out = asyncio.run(voice.propose("x", {"topic": "market"}))
    assert out.stance == "unavailable"
    assert out.confidence == 0.0
    assert "api_key_missing" in out.summary


def test_anthropic_voice_parses_valid_response(monkeypatch) -> None:
    monkeypatch.setenv("TARS_ANTHROPIC_API_KEY", "test-key")

    captured: dict = {}

    def fake_post(url, body, headers, timeout_s):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "stance": "risk_off",
                            "summary": "RISK_OFF — basket -1.5%",
                            "actions_recommended": [
                                "tighten_stops",
                                "raise_cash_buffer",
                                "  ",
                                "x" * 200,
                            ],
                            "confidence": 0.74,
                            "rationale": "Avg change is -1.5%.",
                        }
                    ),
                }
            ],
            "usage": {"input_tokens": 120, "output_tokens": 64},
        }

    monkeypatch.setattr(llm_module, "_post_json", fake_post)

    voice = AnthropicVoice(timeout_s=5.0)
    out = asyncio.run(voice.propose("interpret", {"topic": "market", "avg_change_24h": -1.5}))
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["body"]["model"].startswith("claude-")
    assert out.stance == "risk_off"
    assert out.confidence == pytest.approx(0.74)
    assert "tighten_stops" in out.actions_recommended
    assert out.tokens_in == 120 and out.tokens_out == 64
    assert out.model.startswith("anthropic/")


def test_anthropic_voice_handles_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("TARS_ANTHROPIC_API_KEY", "test-key")

    def fake_post(url, body, headers, timeout_s):
        return {"content": [{"type": "text", "text": "not really json {nope"}]}

    monkeypatch.setattr(llm_module, "_post_json", fake_post)
    out = asyncio.run(AnthropicVoice().propose("x", {"topic": "market"}))
    assert out.stance == "unavailable"
    assert "invalid_json_response" in out.rationale


def test_anthropic_voice_normalises_unknown_stance(monkeypatch) -> None:
    monkeypatch.setenv("TARS_ANTHROPIC_API_KEY", "test-key")

    def fake_post(url, body, headers, timeout_s):
        return {
            "content": [
                {
                    "type": "text",
                    "text": '{"stance":"YOLO","summary":"x","confidence":2.0}',
                }
            ]
        }

    monkeypatch.setattr(llm_module, "_post_json", fake_post)
    out = asyncio.run(AnthropicVoice().propose("x", {"topic": "market"}))
    assert out.stance == "uncertain"  # YOLO is not in the market set
    assert 0.0 <= out.confidence <= 1.0


def test_anthropic_voice_strips_fenced_block(monkeypatch) -> None:
    monkeypatch.setenv("TARS_ANTHROPIC_API_KEY", "test-key")

    def fake_post(url, body, headers, timeout_s):
        text = '```json\n{"stance":"neutral","summary":"NEUTRAL","confidence":0.5}\n```'
        return {"content": [{"type": "text", "text": text}]}

    monkeypatch.setattr(llm_module, "_post_json", fake_post)
    out = asyncio.run(AnthropicVoice().propose("x", {"topic": "market"}))
    assert out.stance == "neutral"


# ---------------------------------------------------------------------------
# Orchestrator with unavailable voices
# ---------------------------------------------------------------------------


def test_orchestrator_skips_unavailable_voice(monkeypatch) -> None:
    """An unavailable LLM voice must not vote and must not be counted."""

    monkeypatch.delenv("TARS_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)

    council = CouncilOrchestrator(
        voices=[
            AnthropicVoice(),  # unavailable
            *CouncilOrchestrator().voices[:2],  # local + mock
        ]
    )
    deliberation = asyncio.run(
        council.deliberate(
            "interpret",
            {"topic": "market", "avg_change_24h": -1.5},
            mode="n_vote",
        )
    )
    # Three voices proposed, but only two voted (unavailable filtered).
    assert len(deliberation.voices) == 3
    voted = [v for v in deliberation.voices if v.stance != "unavailable"]
    assert len(voted) == 2
    assert deliberation.agreement == 1.0  # both voters say risk_off
    assert deliberation.chosen == "risk_off"


def test_winner_falls_back_when_all_unavailable() -> None:
    a = Proposal(model="m1", stance="unavailable", summary="x", confidence=0.0)
    b = Proposal(model="m2", stance="unavailable", summary="y", confidence=0.0)
    chosen = _winner([a, b])
    assert chosen.stance == "unavailable"
    assert _agreement([a, b]) == 0.0
    assert _contradictions([a, b]) == []


# ---------------------------------------------------------------------------
# Default panel detection
# ---------------------------------------------------------------------------


def test_default_panel_excludes_llm_when_no_keys(monkeypatch) -> None:
    for k in ("TARS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "TARS_OPENAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)
    council = CouncilOrchestrator()
    assert len(council.voices) == 2
    assert all(not v.model.startswith(("anthropic/", "openai/")) for v in council.voices)


def test_default_panel_includes_anthropic_when_key_present(monkeypatch) -> None:
    monkeypatch.setenv("TARS_ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)
    council = CouncilOrchestrator()
    assert len(council.voices) == 3
    assert any(v.model.startswith("anthropic/") for v in council.voices)
