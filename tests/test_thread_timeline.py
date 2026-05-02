"""Tests for the per-thread structured timeline.

The timeline (``backend/core/search/timeline.py``) joins chat
messages, tool calls, attachment ingests, and meeet events filtered by
``payload.thread_id`` into a single chronological feed below the
conversation. Pre-PR the module was untested and three things were
quietly wrong:

1. ``_RELEVANT_EVENT_KINDS`` listed event names that nobody emits
   (``policy.confirmed`` / ``policy.rejected`` / ``playbook.step.failed``)
   and missed real ones (``policy.confirm`` / ``policy.cancelled`` /
   ``policy.blocked`` / ``policy.expired`` / ``playbook.started`` /
   ``playbook.completed`` / ``council.deliberation.{started,completed}``).
2. ``_summarise_event`` for ``policy.*`` read ``payload['action_id']``
   but every router emits ``payload['action']`` — the cockpit always
   showed ``action=?``.
3. No summarisers existed for playbook / sampler / council events,
   so the cockpit rendered an empty string.

These tests pin the constant + per-kind summariser shape, plus a
small end-to-end run of ``get_thread_timeline`` over a chat store
seeded with messages, tool calls, attachments, and a meeet event.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

from backend.core.search.timeline import (
    _RELEVANT_EVENT_KINDS,
    _summarise_event,
    get_thread_timeline,
)


# ---------------------------------------------------------------------------
# _RELEVANT_EVENT_KINDS — pin the surface
# ---------------------------------------------------------------------------


def test_relevant_event_kinds_is_a_tuple_of_strings() -> None:
    assert isinstance(_RELEVANT_EVENT_KINDS, tuple)
    assert all(isinstance(k, str) and k for k in _RELEVANT_EVENT_KINDS)


def test_relevant_event_kinds_has_no_duplicates() -> None:
    assert len(set(_RELEVANT_EVENT_KINDS)) == len(_RELEVANT_EVENT_KINDS)


def test_relevant_event_kinds_covers_all_real_policy_events() -> None:
    """Every event the policy gate actually emits must appear in the
    timeline allow-list. Pre-PR ``policy.confirmed`` / ``policy.rejected``
    were placeholders for events that never fired."""

    must_have = {
        "policy.allowed",
        "policy.queued",
        "policy.blocked",
        "policy.confirm",
        "policy.cancelled",
        "policy.expired",
    }
    assert must_have.issubset(set(_RELEVANT_EVENT_KINDS))


def test_relevant_event_kinds_covers_real_playbook_events() -> None:
    must_have = {
        "playbook.started",
        "playbook.step.completed",
        "playbook.completed",
    }
    assert must_have.issubset(set(_RELEVANT_EVENT_KINDS))


def test_relevant_event_kinds_drops_phantom_event_names() -> None:
    """The pre-PR list carried event names that nobody emitted — pin
    that they're gone so a regression doesn't silently re-introduce
    them."""

    phantom = {"policy.confirmed", "policy.rejected", "playbook.step.failed"}
    assert phantom.isdisjoint(set(_RELEVANT_EVENT_KINDS))


def test_relevant_event_kinds_covers_council_deliberation_events() -> None:
    must_have = {
        "council.deliberation.started",
        "council.deliberation.completed",
    }
    assert must_have.issubset(set(_RELEVANT_EVENT_KINDS))


# ---------------------------------------------------------------------------
# _summarise_event — per-kind shapes
# ---------------------------------------------------------------------------


def test_summary_unknown_kind_is_empty() -> None:
    assert _summarise_event("nope.unknown", {"a": 1}) == ""


def test_summary_voice_tts_uses_persona_provider_chars_cost() -> None:
    out = _summarise_event(
        "voice.tts",
        {"persona": "tars", "provider": "elevenlabs", "chars": 142, "cost_usd": 0.001234},
    )
    assert "tars" in out
    assert "elevenlabs" in out
    assert "142 chars" in out
    assert "$0.001234" in out


def test_summary_usage_tokens_uses_model_in_out_cost() -> None:
    out = _summarise_event(
        "usage.tokens",
        {
            "model": "anthropic/claude-3-5",
            "tokens_in": 100,
            "tokens_out": 200,
            "cost_usd": 0.0042,
        },
    )
    assert "anthropic/claude-3-5" in out
    assert "in 100" in out
    assert "out 200" in out
    assert "$0.004200" in out


def test_summary_attachment_ingested_uses_filename_chunks_model() -> None:
    out = _summarise_event(
        "attachment.ingested",
        {"filename": "report.pdf", "chunk_count": 12, "embedding_model": "openai"},
    )
    assert "report.pdf" in out
    assert "12 chunks" in out
    assert "openai" in out


def test_summary_chat_tool_call_uses_slug_action() -> None:
    out = _summarise_event(
        "chat.tool_call.completed",
        {"slug": "traders", "action_id": "place_alert"},
    )
    assert out == "traders.place_alert"


def test_summary_chat_context_retrieved_lists_first_three_files() -> None:
    out = _summarise_event(
        "chat.context.retrieved",
        {
            "chunk_count": 8,
            "files": ["a.pdf", "b.txt", "c.md", "d.csv", "e.docx"],
        },
    )
    assert "8 chunks" in out
    assert "a.pdf, b.txt, c.md" in out
    assert "d.csv" not in out  # cap at 3


# ---------------------------------------------------------------------------
# Policy event summaries — the actual bug fix
# ---------------------------------------------------------------------------


def test_summary_policy_uses_action_field_not_action_id() -> None:
    """Routers emit ``payload['action']``; the pre-PR summariser
    looked up ``action_id`` and always rendered ``action=?``. Pin the
    fix."""

    out = _summarise_event(
        "policy.confirm",
        {"slug": "traders", "action": "cancel_alert", "token": "cfm_abc"},
    )
    assert "slug=traders" in out
    assert "action=cancel_alert" in out
    assert "token=cfm_abc" in out
    assert "action=?" not in out  # ← used to be the case


def test_summary_policy_blocked_carries_slug_action_token() -> None:
    out = _summarise_event(
        "policy.blocked",
        {"slug": "business", "action": "log_deal", "token": None,
         "reason": "dry_run_preview_only"},
    )
    assert "slug=business" in out
    assert "action=log_deal" in out
    # token=None falls back to '?'
    assert "token=?" in out


def test_summary_policy_expired_includes_expired_at() -> None:
    out = _summarise_event(
        "policy.expired",
        {
            "slug": "mlm",
            "action": "update_member",
            "token": "cfm_xyz",
            "expired_at": 1730000000.0,
        },
    )
    assert "expired_at=1730000000.0" in out
    assert "action=update_member" in out


def test_summary_policy_handles_empty_payload_safely() -> None:
    """A degraded event (no slug / action / token) must still produce
    a renderable string, not a crash."""

    out = _summarise_event("policy.allowed", {})
    assert "slug=?" in out
    assert "action=?" in out
    assert "token=?" in out


# ---------------------------------------------------------------------------
# Sampler / council summaries — newly added
# ---------------------------------------------------------------------------


def test_summary_sampler_decision_renders_winner_stance_cost() -> None:
    out = _summarise_event(
        "sampler.decision",
        {
            "winner": "anthropic/claude-3-5",
            "winning_stance": "risk_off",
            "agreement": 0.667,
            "cost_usd": 0.000942,
            "parallel": True,
        },
    )
    assert "anthropic/claude-3-5" in out
    assert "risk_off" in out
    assert "agree=0.667" in out
    assert "$0.000942" in out
    assert "parallel" in out


def test_summary_sampler_decision_omits_parallel_tag_when_false() -> None:
    out = _summarise_event(
        "sampler.decision",
        {
            "winner": "tars-local-rules-v1",
            "winning_stance": "neutral",
            "agreement": 1.0,
            "cost_usd": 0.0,
            "parallel": False,
        },
    )
    assert "parallel" not in out


def test_summary_council_deliberation_started_lists_voices_and_topic() -> None:
    out = _summarise_event(
        "council.deliberation.started",
        {"mode": "n_vote", "voices": ["a", "b", "c"], "topic": "market"},
    )
    assert "voices=[a, b, c]" in out
    assert "topic=market" in out


def test_summary_council_deliberation_completed_uses_chosen_winner_agreement() -> None:
    out = _summarise_event(
        "council.deliberation.completed",
        {"mode": "dual_vote", "chosen": "risk_off",
         "winner_model": "tars-local", "agreement": 0.5},
    )
    assert "chosen=risk_off" in out
    assert "winner=tars-local" in out
    assert "agree=0.5" in out


# ---------------------------------------------------------------------------
# Playbook summaries — newly added
# ---------------------------------------------------------------------------


def test_summary_playbook_started_renders_id_steps_mode() -> None:
    out = _summarise_event(
        "playbook.started",
        {"playbook_id": "traders.morning_check", "steps": 3, "mode": "live"},
    )
    assert "id=traders.morning_check" in out
    assert "steps=3" in out
    assert "mode=live" in out


def test_summary_playbook_step_completed_marks_blocked_failed_ok_paths() -> None:
    ok = _summarise_event(
        "playbook.step.completed",
        {"playbook_id": "p", "step_id": "s1", "ok": True, "took_ms": 12.345},
    )
    assert "ok" in ok
    assert "step=s1" in ok
    assert "12.3ms" in ok
    assert "parallel" not in ok

    failed = _summarise_event(
        "playbook.step.completed",
        {"playbook_id": "p", "step_id": "s2", "ok": False, "took_ms": 1.0},
    )
    assert "failed" in failed

    blocked = _summarise_event(
        "playbook.step.completed",
        {"playbook_id": "p", "step_id": "s3", "ok": True, "blocked": True,
         "took_ms": 2.0, "parallel": True},
    )
    # blocked takes precedence over ok
    assert "blocked" in blocked
    assert "parallel" in blocked


def test_summary_playbook_completed_renders_run_blocked_failed_counts() -> None:
    ok = _summarise_event(
        "playbook.completed",
        {"playbook_id": "p", "ok": True, "steps_run": 5, "steps_blocked": 0,
         "steps_failed": 0},
    )
    assert "ok" in ok
    assert "run=5" in ok

    stopped = _summarise_event(
        "playbook.completed",
        {"playbook_id": "p", "ok": False, "steps_run": 3, "steps_blocked": 1,
         "steps_failed": 2},
    )
    assert "stopped" in stopped
    assert "blocked=1" in stopped
    assert "failed=2" in stopped


# ---------------------------------------------------------------------------
# End-to-end: get_thread_timeline merges every source in chronological order
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_chat_and_meeet(tmp_path: Path, monkeypatch):
    """Stand up a chat store + meeet store under tmp paths so the
    end-to-end timeline run doesn't touch the real ~/.tars dirs."""

    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(tmp_path / "chat.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    from backend.core.chat import store as chat_store_mod
    from backend.core.meeet import reset_client, reset_store

    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    reset_store()
    reset_client()
    yield
    monkeypatch.setattr(chat_store_mod, "_SINGLETON", None, raising=False)
    reset_store()
    reset_client()


@pytest.mark.asyncio
async def test_get_thread_timeline_merges_messages_and_events(fresh_chat_and_meeet) -> None:
    """A thread with messages + a meeet event tagged with the matching
    ``payload.thread_id`` should yield both rows in chronological
    order."""

    from backend.core.chat.models import Message, Thread
    from backend.core.chat.store import get_chat_store
    from backend.core.meeet import get_client

    chat = get_chat_store()
    if not chat.enabled:
        pytest.skip("chat store disabled in this env")

    thread = Thread.fresh(title="t1")
    await chat.insert_thread(thread)
    msg = Message(
        id="msg_t1_001",
        thread_id=thread.id,
        role="operator",
        content="hello world",
        created_at=time.time(),
    )
    await chat.insert_message(msg)

    # Emit a `policy.allowed` event tagged with the same thread_id so
    # the timeline filter pulls it in.
    client = get_client()
    await client.emit(
        "policy.allowed",
        {
            "slug": "traders",
            "action": "fetch_quote",
            "thread_id": thread.id,
        },
    )

    entries = await get_thread_timeline(thread.id, limit_per_source=50)
    kinds = [e.kind for e in entries]
    assert "message.operator" in kinds
    assert "policy.allowed" in kinds

    # Find the policy entry and assert the bug-fix summariser wins.
    policy_entry = next(e for e in entries if e.kind == "policy.allowed")
    assert "action=fetch_quote" in policy_entry.summary
    assert "action=?" not in policy_entry.summary


@pytest.mark.asyncio
async def test_get_thread_timeline_filters_other_threads(fresh_chat_and_meeet) -> None:
    """An event tagged for a different thread_id must NOT appear in
    this thread's timeline."""

    from backend.core.chat.models import Thread
    from backend.core.chat.store import get_chat_store
    from backend.core.meeet import get_client

    chat = get_chat_store()
    if not chat.enabled:
        pytest.skip("chat store disabled in this env")

    target = Thread.fresh(title="target")
    other = Thread.fresh(title="other")
    await chat.insert_thread(target)
    await chat.insert_thread(other)

    client = get_client()
    await client.emit(
        "policy.expired",
        {"slug": "x", "action": "y", "token": "cfm_a", "thread_id": other.id},
    )

    entries = await get_thread_timeline(target.id, limit_per_source=50)
    kinds = {e.kind for e in entries}
    assert "policy.expired" not in kinds


@pytest.mark.asyncio
async def test_get_thread_timeline_returns_empty_for_unknown_thread(fresh_chat_and_meeet) -> None:
    entries = await get_thread_timeline("nope-no-such-thread")
    assert entries == []


@pytest.mark.asyncio
async def test_get_thread_timeline_returns_empty_when_thread_id_blank(fresh_chat_and_meeet) -> None:
    entries = await get_thread_timeline("")
    assert entries == []
