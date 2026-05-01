"""Tests for parallel council deliberation.

Pre-PR the orchestrator awaited each ``voice.propose(...)`` serially,
so a panel of three real LLM voices (each with a 12s transport
timeout) could take up to ~36s wall-clock to deliberate. The new
``asyncio.gather`` fan-out collapses that to ``max(latency)`` while
preserving:

- input-order ``proposals`` (so the cockpit voice list stays stable);
- per-voice ``usage.tokens`` events emitted *after* the gather, in
  input order, for a deterministic cost ledger;
- a single ``sampler.decision`` event at the end carrying the
  *wall-clock* ``latency_ms`` (the bound) plus a new
  ``cumulative_latency_ms`` field (sum of per-voice latencies, for
  per-model leaderboards) and a ``parallel`` flag.

Failure isolation is the second guarantee: a voice that raises now
materialises as an ``unavailable`` proposal so a single broken
adapter cannot crash a council turn.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Mapping

import pytest

from backend.core.council import CouncilOrchestrator, Proposal
from backend.core.council.orchestrator import (
    _exception_proposal,
    _propose_one,
)
from backend.core.council.voices import Voice
from backend.core.meeet import (
    get_client,
    reset_client,
    reset_store,
)
from backend.core.meeet.store import MeeetStore


@pytest.fixture()
def fresh_meeet(tmp_path, monkeypatch):
    """Isolate each test in its own SQLite event store.

    Both the ``MeeetStore`` and ``MeeetClient`` singletons are reset so
    they re-read ``MEEET_STORE_PATH`` and the (deliberately unset)
    ``MEEET_INGEST_URL`` for this test only.
    """

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    reset_store()
    reset_client()
    yield get_client().store
    reset_store()
    reset_client()


class _SleepyVoice(Voice):
    """Voice that sleeps ``delay_s`` before returning a fixed proposal.

    Used to prove the orchestrator runs voices in parallel: with three
    voices each sleeping 0.2s the wall-clock should be ~0.2s, not 0.6s.
    """

    def __init__(self, model: str, stance: str, delay_s: float) -> None:
        self.model = model
        self.stance = stance
        self.delay_s = delay_s

    async def propose(self, prompt: str, context: Mapping[str, Any]) -> Proposal:
        await asyncio.sleep(self.delay_s)
        return Proposal(
            model=self.model,
            stance=self.stance,
            summary=f"{self.stance.upper()} — slept {self.delay_s}s",
            confidence=0.6,
            tokens_in=10,
            tokens_out=20,
        )


class _RaisingVoice(Voice):
    """Voice that raises mid-deliberation. Pinned by the isolation tests."""

    def __init__(self, model: str = "boom") -> None:
        self.model = model

    async def propose(self, prompt: str, context: Mapping[str, Any]) -> Proposal:
        raise RuntimeError("upstream_blew_up")


class _UntimedVoice(Voice):
    """Voice that forgets to stamp ``latency_ms``.

    The ``_propose_one`` wrapper backfills the latency so the cost
    ledger never shows a 0 ms LLM call.
    """

    def __init__(self, model: str = "untimed") -> None:
        self.model = model

    async def propose(self, prompt: str, context: Mapping[str, Any]) -> Proposal:
        await asyncio.sleep(0.01)
        return Proposal(
            model=self.model,
            stance="neutral",
            summary="NO_TIMING",
            confidence=0.5,
            latency_ms=0.0,
        )


# ---------------------------------------------------------------------------
# Parallel fan-out
# ---------------------------------------------------------------------------


def test_three_sleepy_voices_run_in_parallel(fresh_meeet) -> None:
    """Three voices each sleeping 0.2s should finish in ~0.2s, not ~0.6s."""

    council = CouncilOrchestrator(
        voices=[
            _SleepyVoice("a", "risk_off", 0.2),
            _SleepyVoice("b", "risk_off", 0.2),
            _SleepyVoice("c", "risk_on", 0.2),
        ]
    )
    started = time.perf_counter()
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 0.5, f"deliberation took {elapsed:.3f}s — fan-out broken"
    assert len(deliberation.voices) == 3
    assert deliberation.chosen == "risk_off"


def test_proposals_preserve_input_order(fresh_meeet) -> None:
    """The cockpit pins voices to a stable list — order must match input."""

    voices = [
        _SleepyVoice("alpha", "risk_off", 0.05),
        _SleepyVoice("beta", "neutral", 0.01),  # finishes first
        _SleepyVoice("gamma", "risk_on", 0.03),
    ]
    council = CouncilOrchestrator(voices=voices)
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    assert [p.model for p in deliberation.voices] == ["alpha", "beta", "gamma"]


def test_dual_vote_only_runs_first_two_voices(fresh_meeet) -> None:
    """``dual_vote`` must keep its two-voice contract even with parallelism."""

    voices = [
        _SleepyVoice("a", "risk_off", 0.01),
        _SleepyVoice("b", "neutral", 0.01),
        _SleepyVoice("c", "risk_on", 0.01),  # third voice must be ignored
    ]
    council = CouncilOrchestrator(voices=voices)
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="dual_vote")
    )
    assert len(deliberation.voices) == 2
    assert {p.model for p in deliberation.voices} == {"a", "b"}


def test_single_mode_runs_one_voice_no_concurrency(fresh_meeet) -> None:
    """Single mode still works through the gather path without weirdness."""

    voices = [_SleepyVoice("solo", "risk_off", 0.01)]
    council = CouncilOrchestrator(voices=voices)
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="single")
    )
    assert len(deliberation.voices) == 1
    assert deliberation.voices[0].model == "solo"


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


def test_raising_voice_does_not_crash_deliberation(fresh_meeet) -> None:
    """A voice that raises must not propagate; surface as unavailable."""

    council = CouncilOrchestrator(
        voices=[
            _SleepyVoice("good", "risk_off", 0.01),
            _RaisingVoice("boom"),
            _SleepyVoice("good2", "risk_off", 0.01),
        ]
    )
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    by_model = {p.model: p for p in deliberation.voices}
    assert by_model["boom"].stance == "unavailable"
    assert by_model["boom"].confidence == 0.0
    assert "RuntimeError" in by_model["boom"].rationale
    assert by_model["good"].stance == "risk_off"
    assert by_model["good2"].stance == "risk_off"
    # Quorum still picks the live voices' stance.
    assert deliberation.chosen == "risk_off"


def test_all_voices_failing_yields_safe_envelope(fresh_meeet) -> None:
    """All-failure case: orchestrator must not raise; agreement falls to 0."""

    council = CouncilOrchestrator(
        voices=[_RaisingVoice("boom1"), _RaisingVoice("boom2")]
    )
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="dual_vote")
    )
    assert all(p.stance == "unavailable" for p in deliberation.voices)
    assert deliberation.agreement == 0.0
    assert deliberation.contradictions == ()


def test_exception_proposal_helper_shape() -> None:
    """``_exception_proposal`` is the canonical translator — pin its shape."""

    p = _exception_proposal("test/model", RuntimeError("boom"), latency_ms=12.5)
    assert p.model == "test/model"
    assert p.stance == "unavailable"
    assert p.confidence == 0.0
    assert p.tokens_in == 0
    assert p.tokens_out == 0
    assert p.latency_ms == 12.5
    assert "RuntimeError" in p.summary
    assert "boom" in p.rationale


def test_exception_proposal_handles_blank_model() -> None:
    """A voice without a ``.model`` attribute must still get a stable label."""

    p = _exception_proposal("", ValueError("eek"), latency_ms=0.0)
    assert p.model == "unknown"
    assert p.stance == "unavailable"


# ---------------------------------------------------------------------------
# Latency back-fill via _propose_one
# ---------------------------------------------------------------------------


def test_propose_one_backfills_zero_latency(fresh_meeet) -> None:
    """Voices that don't stamp latency get backfilled to a non-zero value."""

    voice = _UntimedVoice("untimed")
    p = asyncio.run(_propose_one(voice, "x", {"topic": "market"}))
    assert p.model == "untimed"
    assert p.latency_ms > 0.0


def test_propose_one_preserves_stamped_latency(fresh_meeet) -> None:
    """A voice that already stamps latency_ms keeps its number."""

    class _StampedVoice(Voice):
        model = "stamped"

        async def propose(self, prompt, context):
            return Proposal(
                model=self.model,
                stance="risk_off",
                summary="x",
                latency_ms=99.0,
            )

    p = asyncio.run(_propose_one(_StampedVoice(), "x", {"topic": "market"}))
    assert p.latency_ms == 99.0


# ---------------------------------------------------------------------------
# Event ordering: usage.tokens then sampler.decision then deliberation.completed
# ---------------------------------------------------------------------------


def _read_events(store: MeeetStore) -> list[dict[str, Any]]:
    """Return stored events as plain dicts so tests can subscript freely."""

    rows = asyncio.run(store.list_events(limit=200))
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "ts": r.ts,
                "kind": r.kind,
                "trace_id": r.trace_id,
                "payload": r.payload,
                "session_id": r.session_id,
                "route": r.route,
            }
        )
    return out


def test_usage_tokens_emitted_in_input_order(fresh_meeet) -> None:
    """The cost ledger's deterministic ordering depends on input order."""

    voices = [
        _SleepyVoice("alpha", "risk_off", 0.05),  # finishes last
        _SleepyVoice("beta", "neutral", 0.005),   # finishes first
        _SleepyVoice("gamma", "risk_on", 0.025),
    ]
    council = CouncilOrchestrator(voices=voices)
    asyncio.run(council.deliberate("x", {"topic": "market"}, mode="n_vote"))

    events = _read_events(fresh_meeet)
    usage = [e for e in events if e["kind"] == "usage.tokens"]
    assert len(usage) == 3
    # Events are returned newest-first → reverse to get insert order.
    usage_chrono = list(reversed(usage))
    assert [e["payload"]["model"] for e in usage_chrono] == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_sampler_decision_carries_parallel_flag_and_latencies(fresh_meeet) -> None:
    """The sampler.decision rollup must surface the new fields."""

    voices = [
        _SleepyVoice("a", "risk_off", 0.05),
        _SleepyVoice("b", "risk_off", 0.05),
    ]
    council = CouncilOrchestrator(voices=voices)
    asyncio.run(council.deliberate("x", {"topic": "market"}, mode="dual_vote"))

    events = _read_events(fresh_meeet)
    sampler = next(e for e in events if e["kind"] == "sampler.decision")
    payload = sampler["payload"]
    assert payload["parallel"] is True
    assert payload["latency_ms"] > 0.0
    # cumulative >= wall-clock (sum vs. max of two ~50ms voices).
    assert payload["cumulative_latency_ms"] >= payload["latency_ms"]
    # Two voices summed should comfortably exceed the wall-clock max.
    assert payload["cumulative_latency_ms"] >= 0.9 * payload["latency_ms"]


def test_single_mode_marks_parallel_false(fresh_meeet) -> None:
    """``parallel=False`` only when there's literally one voice — pin it."""

    council = CouncilOrchestrator(voices=[_SleepyVoice("only", "neutral", 0.0)])
    asyncio.run(council.deliberate("x", {"topic": "market"}, mode="single"))
    events = _read_events(fresh_meeet)
    sampler = next(e for e in events if e["kind"] == "sampler.decision")
    assert sampler["payload"]["parallel"] is False


def test_council_deliberation_started_lists_voices_in_input_order(fresh_meeet) -> None:
    """The pre-flight event also pins the model list in input order so the
    cockpit timeline shows the same voice names in the same slot every time."""

    voices = [
        _SleepyVoice("first", "risk_off", 0.0),
        _SleepyVoice("second", "neutral", 0.0),
        _SleepyVoice("third", "risk_on", 0.0),
    ]
    council = CouncilOrchestrator(voices=voices)
    asyncio.run(council.deliberate("x", {"topic": "market"}, mode="n_vote"))

    events = _read_events(fresh_meeet)
    started_evt = next(
        e for e in events if e["kind"] == "council.deliberation.started"
    )
    assert started_evt["payload"]["voices"] == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# Cloud route detection still fires under fan-out
# ---------------------------------------------------------------------------


def test_cloud_route_bumps_when_any_cloud_voice_returns(fresh_meeet) -> None:
    """A voice whose model id starts with ``anthropic/`` or ``openai/``
    bumps the trace route to ``cloud`` even when a local voice also runs."""

    voices = [
        _SleepyVoice("local-rules", "risk_off", 0.0),
        _SleepyVoice("anthropic/claude-3-5", "risk_off", 0.0),
    ]
    council = CouncilOrchestrator(voices=voices)
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    assert deliberation.route == "cloud"


def test_cloud_route_stays_local_when_only_local_voices_run(fresh_meeet) -> None:
    voices = [
        _SleepyVoice("local-rules", "risk_off", 0.0),
        _SleepyVoice("local-mock", "risk_off", 0.0),
    ]
    council = CouncilOrchestrator(voices=voices)
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    # Default route is None / "local" depending on the trace scope; the
    # important contract is *not* "cloud".
    assert deliberation.route != "cloud"


def test_unavailable_cloud_voice_does_not_bump_route(fresh_meeet) -> None:
    """An unavailable cloud voice (no key, transport error, …) must NOT
    trip the route flag — that flag should only fire when a real cloud
    call actually happened."""

    class _UnavailableCloud(Voice):
        model = "anthropic/claude-disabled"

        async def propose(self, prompt, context):
            return Proposal(
                model=self.model,
                stance="unavailable",
                summary="UNAVAILABLE — api_key_missing.",
                confidence=0.0,
                rationale="api_key_missing",
            )

    voices = [
        _SleepyVoice("local-rules", "risk_off", 0.0),
        _UnavailableCloud(),
    ]
    council = CouncilOrchestrator(voices=voices)
    deliberation = asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="n_vote")
    )
    assert deliberation.route != "cloud"
