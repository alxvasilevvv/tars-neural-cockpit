"""Tests for the ``thread_id`` ContextVar bridge.

The previous two PRs (#97, #98) plumbed ``x-tars-thread-id`` through
the policy gate and the council orchestrator's HTTP entry. The
remaining gap was action handlers that call
``get_council().deliberate(...)`` from inside ``invoke_action``
(e.g. ``business.daily_brief``, ``traders.summarize_market``):
those handlers don't see the request thread_id directly, so the
council events they triggered never carried it.

This PR adds a ``backend/core/meeet/tracing.py::thread_id_scope``
context manager backed by a ``ContextVar``. ``invoke_action`` now
opens that scope, and the council orchestrator falls back to
``current_thread_id()`` when no explicit ``thread_id`` kwarg is
passed. Net result: an action invoked from a chat thread auto-
propagates ``thread_id`` into every council / sampler event it
triggers, no per-handler plumbing needed.

This module pins:

- ContextVar default (None), set / reset, nested scopes don't leak;
- empty string is treated as no-op (timeline filter is exact-match);
- the council orchestrator falls back to the contextvar when its
  ``thread_id`` kwarg is None;
- explicit kwarg still wins over contextvar (call-site override);
- ``invoke_action`` opens the scope so action-handler-driven
  deliberations propagate it automatically;
- the policy ``confirm`` route opens the scope from the persisted
  row, so a confirmed destructive action's council events also
  inherit the thread id.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.council import CouncilOrchestrator, Proposal
from backend.core.council.voices import Voice
from backend.core.meeet import (
    current_thread_id,
    get_client,
    reset_client,
    reset_store,
    thread_id_scope,
)


@pytest.fixture(autouse=True)
def fresh_meeet(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    reset_store()
    reset_client()
    # PolicyStore shares the meeet sqlite path via ``_resolve_db_path``
    # but caches its own connection in a separate singleton. If a
    # previous test (e.g. test_rate_limit_expensive_routes) pointed
    # MEEET_STORE_PATH at a tempdir that's since been deleted, the
    # cached PolicyStore still tries to write to it, producing
    # ``no such table: confirmations`` on the next confirm call.
    # Dropping the singleton forces a re-init against the current
    # MEEET_STORE_PATH so ``_ensure_schema`` runs against the fresh
    # tmp DB used by this test.
    from backend.core.policy import store as policy_store_mod
    from backend.core.policy import gate as policy_gate_mod

    policy_store_mod._SINGLETON = None
    policy_gate_mod._SINGLETON = None
    yield get_client().store
    reset_store()
    reset_client()
    policy_store_mod._SINGLETON = None
    policy_gate_mod._SINGLETON = None


# ---------------------------------------------------------------------------
# ContextVar primitives
# ---------------------------------------------------------------------------


def test_default_thread_id_is_none() -> None:
    assert current_thread_id() is None


def test_thread_id_scope_sets_and_resets() -> None:
    assert current_thread_id() is None
    with thread_id_scope("thr_a"):
        assert current_thread_id() == "thr_a"
    assert current_thread_id() is None


def test_thread_id_scope_nests_correctly() -> None:
    with thread_id_scope("thr_outer"):
        assert current_thread_id() == "thr_outer"
        with thread_id_scope("thr_inner"):
            assert current_thread_id() == "thr_inner"
        assert current_thread_id() == "thr_outer"
    assert current_thread_id() is None


def test_thread_id_scope_none_is_noop() -> None:
    """``thread_id_scope(None)`` must keep the outer value visible
    (so a router that didn't get the header doesn't accidentally
    clobber the value an outer scope had set)."""

    with thread_id_scope("thr_outer"):
        with thread_id_scope(None):
            assert current_thread_id() == "thr_outer"
        assert current_thread_id() == "thr_outer"


def test_thread_id_scope_empty_string_is_noop() -> None:
    """Same contract as None — empty string can't filter anything,
    so treat it as ``no header present``."""

    with thread_id_scope("thr_outer"):
        with thread_id_scope(""):
            assert current_thread_id() == "thr_outer"


def test_thread_id_scope_does_not_leak_on_exception() -> None:
    with pytest.raises(RuntimeError):
        with thread_id_scope("thr_x"):
            assert current_thread_id() == "thr_x"
            raise RuntimeError("boom")
    assert current_thread_id() is None


# ---------------------------------------------------------------------------
# Council orchestrator falls back to contextvar
# ---------------------------------------------------------------------------


class _SimpleVoice(Voice):
    def __init__(self, model: str) -> None:
        self.model = model

    async def propose(self, prompt: str, context: Mapping[str, Any]) -> Proposal:
        return Proposal(
            model=self.model,
            stance="neutral",
            summary=f"{self.model}",
            confidence=0.5,
            tokens_in=10,
            tokens_out=20,
        )


def _events(store, kind: str | None = None) -> list[dict[str, Any]]:
    rows = asyncio.run(store.list_events(kind=kind, limit=200))
    return [{"kind": r.kind, "payload": r.payload} for r in rows]


def test_orchestrator_inherits_thread_id_from_contextvar(fresh_meeet) -> None:
    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])

    async def run() -> None:
        with thread_id_scope("thr_inherit"):
            await council.deliberate("x", {"topic": "market"}, mode="dual_vote")

    asyncio.run(run())

    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert sampler[0]["payload"]["thread_id"] == "thr_inherit"


def test_explicit_kwarg_wins_over_contextvar(fresh_meeet) -> None:
    """Call-site override beats the ambient scope (some handlers may
    legitimately want to retag a deliberation, e.g. an internal
    background job that was kicked off from a chat thread but is now
    operating on its own task ledger)."""

    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])

    async def run() -> None:
        with thread_id_scope("thr_outer"):
            await council.deliberate(
                "x",
                {"topic": "market"},
                mode="dual_vote",
                thread_id="thr_explicit",
            )

    asyncio.run(run())

    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert sampler[0]["payload"]["thread_id"] == "thr_explicit"


def test_orchestrator_no_contextvar_no_kwarg_omits_thread_id(fresh_meeet) -> None:
    council = CouncilOrchestrator(voices=[_SimpleVoice("a"), _SimpleVoice("b")])
    asyncio.run(council.deliberate("x", {"topic": "market"}, mode="dual_vote"))

    sampler = _events(fresh_meeet, kind="sampler.decision")
    assert sampler
    assert "thread_id" not in sampler[0]["payload"]


# ---------------------------------------------------------------------------
# invoke_action wraps the scope so action-handler-driven deliberations inherit
# ---------------------------------------------------------------------------


def _make_app_client():
    from fastapi import FastAPI
    from web_extras.routers.domains import router as domains_router
    from web_extras.routers.policy import router as policy_router

    app = FastAPI()
    app.include_router(domains_router)
    app.include_router(policy_router)
    return TestClient(app)


# A purpose-built domain pack used by the invoke_action tests below.
# Built fresh for each test via ``_register_probe_pack`` so we can swap
# the handler per test without touching the frozen production specs.
from backend.core.domains.base import (
    ActionSpec,
    AwarenessSource,
    DomainManifest,
    DomainPack,
)
from backend.core.domains.registry import _REGISTRY as _DOMAIN_REGISTRY
from backend.core.domains.registry import register as _register_pack


_PROBE_MANIFEST = DomainManifest(
    slug="thread_probe",
    name="Thread Probe",
    short="Test pack to capture current_thread_id() inside the handler.",
    description="Test-only pack — registered fresh per test.",
    color="#67E8F9",
    capabilities=("test",),
    audience="agents",
)


def _register_probe_pack(handler, *, destructive: bool = True) -> None:
    """Register a fresh probe pack with a single ``capture`` action.

    The registry is keyed by slug so re-registering with the same slug
    overwrites — perfect for per-test handler swaps.
    """

    spec = ActionSpec(
        id="capture",
        name="Capture thread id",
        description="Calls the test-supplied handler.",
        handler=handler,
        schema={"type": "object", "properties": {}},
        destructive=destructive,
    )

    class _ProbePack(DomainPack):
        manifest = _PROBE_MANIFEST

        def actions(self):
            return (spec,)

        def awareness(self):
            return ()

        def system_prompt(self) -> str:
            return ""

    _register_pack(_ProbePack())


@pytest.fixture()
def remove_probe_pack():
    yield
    _DOMAIN_REGISTRY.pop("thread_probe", None)


def test_invoke_action_propagates_thread_id_into_action_handler(
    fresh_meeet, monkeypatch, remove_probe_pack
):
    """An action handler that calls ``current_thread_id()`` (or
    ``get_council().deliberate(...)``) inside ``invoke_action`` sees
    the request thread_id without any per-handler plumbing."""

    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    captured: dict[str, str | None] = {"value": "missing"}

    async def fake_handler(args):
        captured["value"] = current_thread_id()
        return {"ok": True}

    _register_probe_pack(fake_handler, destructive=False)

    client = _make_app_client()
    resp = client.post(
        "/api/domains/thread_probe/actions/capture",
        json={},
        headers={"x-tars-thread-id": "thr_handler_001"},
    )
    assert resp.status_code == 200, resp.text
    assert captured["value"] == "thr_handler_001"


def test_invoke_action_thread_id_does_not_leak_outside_request(
    fresh_meeet, monkeypatch, remove_probe_pack
):
    """After the request returns, the contextvar in the test thread
    must NOT carry the request's thread id."""

    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    async def fake_handler(args):
        return {"ok": True}

    _register_probe_pack(fake_handler, destructive=False)

    client = _make_app_client()
    client.post(
        "/api/domains/thread_probe/actions/capture",
        json={},
        headers={"x-tars-thread-id": "thr_no_leak"},
    )
    assert current_thread_id() is None


def test_policy_confirm_route_propagates_persisted_thread_id_into_handler(
    fresh_meeet, monkeypatch, remove_probe_pack
):
    """When an operator confirms a queued destructive action, the
    handler that finally runs sees the thread_id that was on the
    confirmation row (so any council it triggers is tagged)."""

    monkeypatch.setenv("TARS_POLICY_MODE", "confirm")

    captured: dict[str, str | None] = {"value": "missing"}

    async def fake_handler(args):
        captured["value"] = current_thread_id()
        return {"ok": True}

    _register_probe_pack(fake_handler, destructive=True)

    client = _make_app_client()
    queued = client.post(
        "/api/domains/thread_probe/actions/capture",
        json={},
        headers={"x-tars-thread-id": "thr_persisted"},
    )
    token = queued.json()["result"]["policy"]["confirmation_token"]
    assert token

    confirm = client.post(f"/api/policy/confirm/{token}")
    assert confirm.status_code == 200, confirm.text
    assert captured["value"] == "thr_persisted"
