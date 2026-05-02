"""Tests for the ``thread_id`` linkage through the council orchestrator.

After PR #97 the policy gate threads ``x-tars-thread-id`` end-to-end
through every ``policy.*`` event so the cockpit per-thread audit lane
fills in for chat-driven destructive actions.

Council deliberations were the next gap. The timeline already accepts
``council.deliberation.{started,completed}`` and ``sampler.decision``
(see ``backend/core/search/timeline.py::_RELEVANT_EVENT_KINDS``) but
none of those events carried a ``thread_id``, so the cockpit timeline
never showed the council voices that participated in answering a
chat turn.

This module pins:

- ``CouncilOrchestrator.deliberate(thread_id=...)`` flows the id to
  every event it emits (started / per-voice usage.tokens / sampler
  decision / completed);
- absence of ``thread_id`` keeps the legacy payload exactly as-is
  (no stray ``thread_id: None`` keys — the timeline filter is
  exact-match);
- the HTTP surface ``POST /api/council/deliberate`` reads
  ``x-tars-thread-id`` from the request headers and forwards it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

from backend.core.council import CouncilOrchestrator, Proposal
from backend.core.council.voices import Voice
from backend.core.meeet import (
    get_client,
    reset_client,
    reset_store,
)


@pytest.fixture(autouse=True)
def fresh_meeet(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    reset_store()
    reset_client()
    yield get_client().store
    reset_store()
    reset_client()


class _SimpleVoice(Voice):
    def __init__(self, model: str, stance: str = "neutral") -> None:
        self.model = model
        self.stance = stance

    async def propose(self, prompt: str, context: Mapping[str, Any]) -> Proposal:
        return Proposal(
            model=self.model,
            stance=self.stance,
            summary=f"{self.model} {self.stance}",
            confidence=0.5,
            tokens_in=10,
            tokens_out=20,
        )


def _events(store, kind: str | None = None) -> list[dict[str, Any]]:
    rows = asyncio.run(store.list_events(kind=kind, limit=200))
    return [
        {"kind": r.kind, "payload": r.payload, "trace_id": r.trace_id}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Orchestrator: thread_id flows into every emit
# ---------------------------------------------------------------------------


def test_thread_id_lands_on_council_started(fresh_meeet) -> None:
    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])
    asyncio.run(
        council.deliberate(
            "x", {"topic": "market"}, mode="dual_vote", thread_id="thr_council_001"
        )
    )
    started = _events(fresh_meeet, kind="council.deliberation.started")
    assert started
    assert started[0]["payload"]["thread_id"] == "thr_council_001"


def test_thread_id_lands_on_council_completed(fresh_meeet) -> None:
    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])
    asyncio.run(
        council.deliberate(
            "x", {"topic": "market"}, mode="dual_vote", thread_id="thr_council_002"
        )
    )
    completed = _events(fresh_meeet, kind="council.deliberation.completed")
    assert completed
    assert completed[0]["payload"]["thread_id"] == "thr_council_002"


def test_thread_id_lands_on_sampler_decision(fresh_meeet) -> None:
    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])
    asyncio.run(
        council.deliberate(
            "x", {"topic": "market"}, mode="dual_vote", thread_id="thr_council_003"
        )
    )
    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert sampler[0]["payload"]["thread_id"] == "thr_council_003"


def test_thread_id_lands_on_every_usage_tokens_event(fresh_meeet) -> None:
    """Every per-voice usage.tokens event must carry the thread id so
    the cost ledger can be sliced per conversation."""

    council = CouncilOrchestrator(
        voices=[_SimpleVoice("a"), _SimpleVoice("b"), _SimpleVoice("c")]
    )
    asyncio.run(
        council.deliberate(
            "x", {"topic": "market"}, mode="n_vote", thread_id="thr_council_004"
        )
    )
    usage = _events(fresh_meeet, kind="usage.tokens")
    assert len(usage) == 3
    for evt in usage:
        assert evt["payload"]["thread_id"] == "thr_council_004"


def test_no_thread_id_means_no_thread_id_field(fresh_meeet) -> None:
    """Default deliberate() (no thread_id) must NOT inject a
    ``thread_id: None`` key — the timeline filter is exact-match and a
    null would silently match nothing."""

    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])
    asyncio.run(council.deliberate("x", {"topic": "market"}, mode="dual_vote"))

    for kind in (
        "council.deliberation.started",
        "council.deliberation.completed",
        "sampler.decision",
        "usage.tokens",
    ):
        for evt in _events(fresh_meeet, kind=kind):
            assert "thread_id" not in evt["payload"], (
                f"unexpected thread_id key in {kind} payload: {evt['payload']}"
            )


def test_empty_string_thread_id_is_ignored(fresh_meeet) -> None:
    """An empty string is falsy → must NOT land in the payload (would
    pollute the exact-match timeline filter)."""

    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])
    asyncio.run(
        council.deliberate("x", {"topic": "market"}, mode="dual_vote", thread_id="")
    )
    started = _events(fresh_meeet, kind="council.deliberation.started")
    assert started
    assert "thread_id" not in started[0]["payload"]


def test_single_mode_still_threads_thread_id(fresh_meeet) -> None:
    """Single mode bypasses the n-voice fan-out path; pin that the
    thread_id still lands in every event."""

    council = CouncilOrchestrator(voices=[_SimpleVoice("solo")])
    asyncio.run(
        council.deliberate(
            "x", {"topic": "market"}, mode="single", thread_id="thr_solo"
        )
    )
    for kind in (
        "council.deliberation.started",
        "council.deliberation.completed",
        "sampler.decision",
    ):
        for evt in _events(fresh_meeet, kind=kind):
            assert evt["payload"]["thread_id"] == "thr_solo"


# ---------------------------------------------------------------------------
# HTTP surface: x-tars-thread-id header → orchestrator
# ---------------------------------------------------------------------------


def _make_council_client(monkeypatch):
    """Pin the orchestrator singleton to deterministic voices so the
    test doesn't depend on whatever ENV-detected LLM voices exist."""

    from backend.core.council import orchestrator as council_mod

    council_mod.reset_council()
    instance = CouncilOrchestrator(
        voices=[_SimpleVoice("a"), _SimpleVoice("b")]
    )
    monkeypatch.setattr(council_mod, "_SINGLETON", instance, raising=False)

    from fastapi import FastAPI
    from web_extras.routers.council import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_council_router_forwards_x_tars_thread_id(fresh_meeet, monkeypatch):
    client = _make_council_client(monkeypatch)
    resp = client.post(
        "/api/council/deliberate",
        json={"prompt": "x", "context": {"topic": "market"}, "mode": "dual_vote"},
        headers={"x-tars-thread-id": "thr_http_001"},
    )
    assert resp.status_code == 200, resp.text

    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert sampler[0]["payload"]["thread_id"] == "thr_http_001"


def test_council_router_omits_thread_id_when_header_absent(
    fresh_meeet, monkeypatch
):
    client = _make_council_client(monkeypatch)
    resp = client.post(
        "/api/council/deliberate",
        json={"prompt": "x", "context": {"topic": "market"}, "mode": "dual_vote"},
    )
    assert resp.status_code == 200

    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert "thread_id" not in sampler[0]["payload"]


def test_council_router_with_blank_header_treats_as_unset(
    fresh_meeet, monkeypatch
):
    client = _make_council_client(monkeypatch)
    resp = client.post(
        "/api/council/deliberate",
        json={"prompt": "x", "context": {"topic": "market"}, "mode": "dual_vote"},
        headers={"x-tars-thread-id": ""},
    )
    assert resp.status_code == 200

    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert "thread_id" not in sampler[0]["payload"]
