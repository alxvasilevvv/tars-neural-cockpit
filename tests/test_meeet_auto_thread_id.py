"""Tests for MeeetClient.emit auto-injecting thread_id from contextvar.

After the ContextVar bridge (PR #99), every router that handles
``x-tars-thread-id`` opens ``thread_id_scope(...)`` so the active
chat thread id rides on the asyncio context. This PR completes the
loop by having ``MeeetClient.emit(...)`` automatically copy the
contextvar's value into ``payload['thread_id']`` when:

1. the contextvar is set (truthy), AND
2. the caller didn't already place ``thread_id`` in the payload.

This collapses the manual ``if x_tars_thread_id: payload['thread_id']
= ...`` blocks scattered across routers and orchestrators down to a
single auto-injection at the bridge boundary. Existing call-sites
that explicitly set ``thread_id`` always win — the contextvar is a
fallback, not an override — so the policy router's per-row re-attach
keeps the same behaviour.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from backend.core.meeet import (
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
    yield get_client().store
    reset_store()
    reset_client()


async def _last_payload(store, kind: str) -> dict[str, Any]:
    rows = await store.list_events(kind=kind, limit=1)
    assert rows, f"no event of kind {kind} found"
    return rows[0].payload


# ---------------------------------------------------------------------------
# Auto-injection happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_auto_injects_thread_id_when_contextvar_set(fresh_meeet):
    client = get_client()
    with thread_id_scope("thr_auto_001"):
        await client.emit("test.event", {"k": "v"})
    payload = await _last_payload(fresh_meeet, "test.event")
    assert payload["thread_id"] == "thr_auto_001"
    assert payload["k"] == "v"


@pytest.mark.asyncio
async def test_emit_does_not_inject_when_contextvar_unset(fresh_meeet):
    """Without an active scope the payload is exact-match clean."""

    client = get_client()
    await client.emit("test.event", {"k": "v"})
    payload = await _last_payload(fresh_meeet, "test.event")
    assert "thread_id" not in payload


@pytest.mark.asyncio
async def test_emit_does_not_inject_for_empty_string_thread_id(fresh_meeet):
    """``thread_id_scope("")`` is a no-op → contextvar stays at outer
    value (``None`` here) → no injection."""

    client = get_client()
    with thread_id_scope(""):
        await client.emit("test.event", {})
    payload = await _last_payload(fresh_meeet, "test.event")
    assert "thread_id" not in payload


# ---------------------------------------------------------------------------
# Explicit payload always wins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_thread_id_in_payload_wins_over_contextvar(fresh_meeet):
    """A call-site that already placed ``thread_id`` in the payload
    must NOT be overwritten by the contextvar fallback."""

    client = get_client()
    with thread_id_scope("thr_outer"):
        await client.emit("test.event", {"thread_id": "thr_explicit"})
    payload = await _last_payload(fresh_meeet, "test.event")
    assert payload["thread_id"] == "thr_explicit"


@pytest.mark.asyncio
async def test_explicit_none_thread_id_blocks_injection(fresh_meeet):
    """If a call-site sets ``thread_id=None`` explicitly (rare, but
    possible), respect it — the key is in the dict, so the auto path
    skips. (Downstream consumers must filter Falsy themselves.)"""

    client = get_client()
    with thread_id_scope("thr_outer"):
        await client.emit("test.event", {"thread_id": None})
    payload = await _last_payload(fresh_meeet, "test.event")
    assert payload["thread_id"] is None


# ---------------------------------------------------------------------------
# Nested scopes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_uses_innermost_thread_id_scope(fresh_meeet):
    client = get_client()
    with thread_id_scope("thr_outer"):
        with thread_id_scope("thr_inner"):
            await client.emit("test.inner", {})
        await client.emit("test.outer", {})
    inner = await _last_payload(fresh_meeet, "test.inner")
    outer = await _last_payload(fresh_meeet, "test.outer")
    assert inner["thread_id"] == "thr_inner"
    assert outer["thread_id"] == "thr_outer"


# ---------------------------------------------------------------------------
# Side effects unchanged: payload is still copied (caller dict unmodified)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_does_not_mutate_caller_payload(fresh_meeet):
    """The auto-injection must operate on a copy of the caller's dict
    so the caller's reference stays clean."""

    client = get_client()
    caller_dict: dict[str, Any] = {"k": "v"}
    with thread_id_scope("thr_no_mutate"):
        await client.emit("test.event", caller_dict)
    assert caller_dict == {"k": "v"}, "caller's payload was mutated"


@pytest.mark.asyncio
async def test_emit_handles_none_payload_with_contextvar(fresh_meeet):
    """``client.emit(kind)`` (no payload) + active scope → payload is
    ``{"thread_id": ...}`` rather than crashing on ``None``."""

    client = get_client()
    with thread_id_scope("thr_solo"):
        await client.emit("test.event")
    payload = await _last_payload(fresh_meeet, "test.event")
    assert payload["thread_id"] == "thr_solo"
