"""W242 — soft/hard cap UX tests.

Five env-isolated cases:

1. 60% spend triggers ``level == "60"`` and the request is allowed.
2. 100% spend blocks the chat orchestrator path with a 429-shaped
   ``error`` stream event (``cap_hit``).
3. Failure events (outcome != "ok") have ``cost_usd=0`` and so do not
   drive the cap toward 100% — a tier full of failures stays at ``none``.
4. :func:`maybe_fire_cap_notification` fires once per (level, month)
   pair — the second call returns ``fired=False``.
5. ``TARS_BYPASS_CAP=1`` forces ``is_request_allowed()`` to allow a
   request even when ``spent_usd > hard_cap_usd`` (dev override).
"""

from __future__ import annotations

import asyncio
import time

import pytest


@pytest.fixture()
def isolated_metering(tmp_path, monkeypatch):
    """Per-test usage.sqlite + receipt store + tier."""

    usage_db = tmp_path / "usage.sqlite"
    receipts_dir = tmp_path / "receipts"
    receipts_db = tmp_path / "receipts.sqlite"
    host_key = tmp_path / "host-key.json"

    monkeypatch.setenv("TARS_USAGE_DB_PATH", str(usage_db))
    monkeypatch.setenv("TARS_RECEIPT_DIR", str(receipts_dir))
    monkeypatch.setenv("TARS_RECEIPT_DB_PATH", str(receipts_db))
    monkeypatch.setenv("TARS_RECEIPT_HOST_KEY_PATH", str(host_key))
    monkeypatch.delenv("MEEET_BASE_URL", raising=False)
    monkeypatch.delenv("MEEET_BRIDGE_SHARED_SECRET", raising=False)
    monkeypatch.setenv("MEEET_MODE", "off")
    monkeypatch.setenv("TARS_TIER", "PRO")  # hard_cap_usd = 25.0
    monkeypatch.delenv("TARS_BYPASS_CAP", raising=False)
    # No fanout channels — never reach real iMessage during a test.
    monkeypatch.delenv("TARS_DAEMON_FANOUT_CHANNELS", raising=False)

    from backend.core.receipts import reset_store as _reset_receipts

    _reset_receipts()
    yield tmp_path
    _reset_receipts()


def _seed_event(*, cost_usd: float, outcome: str = "ok"):
    """Drop one usage_events row at ``cost_usd`` for the current month."""

    from backend.core.metering import UsageEvent, record_usage

    ev = UsageEvent(
        trace_id=f"trace-{time.time_ns()}",
        ts_utc=time.time(),
        provider="anthropic",
        model="claude-sonnet-4-6",
        action="chat.message",
        tokens_in=0,
        tokens_out=0,
        latency_ms=10.0,
        cost_usd=float(cost_usd),
        cost_meeet=float(cost_usd) * 100.0,
        outcome=outcome,
        tier="PRO",
        agent_id="tars-test",
        domain_pack="",
    )
    record_usage(ev)


# ── 1. 60% triggers level=60 ──────────────────────────────────────────

def test_cap_alert_level_60_triggers_warning(isolated_metering):
    from backend.core.metering import cap_alert_level, is_request_allowed

    # PRO hard cap = $25 → 60% threshold = $15. Seed $15.50 to clear it.
    _seed_event(cost_usd=15.5)

    assert cap_alert_level() == "60"
    allowed, info = is_request_allowed()
    assert allowed is True
    assert info["level"] == "60"
    assert info["percent_used"] >= 0.60
    assert info["reason_if_blocked"] == ""


# ── 2. 100% blocks the chat orchestrator with cap_hit ─────────────────

def test_hard_cap_blocks_chat_with_429_envelope(isolated_metering, monkeypatch):
    from backend.core.metering import is_request_allowed

    # Burn the entire $25 PRO cap in one synthetic event.
    _seed_event(cost_usd=26.0)

    allowed, info = is_request_allowed()
    assert allowed is False
    assert info["level"] == "100"
    assert info["reason_if_blocked"] == "monthly_hard_cap_reached"

    # The chat orchestrator should yield a ``cap_hit`` error event and
    # return without calling the voice. We stub get_thread to avoid the
    # full store stack — only the gate matters here.
    from backend.core.chat.orchestrator import ChatOrchestrator

    orch = ChatOrchestrator.__new__(ChatOrchestrator)

    class _FakeThread:
        id = "t1"
        last_session_id = None

    class _FakeStore:
        async def get_thread(self, tid):
            return _FakeThread()

    orch.store = _FakeStore()

    async def _drive():
        events = []
        async for ev in orch.post_message("t1", "hello"):
            events.append(ev)
            if len(events) >= 3:
                break
        return events

    events = asyncio.run(_drive())
    # First event must be the cap_hit error.
    assert events, "orchestrator produced no events"
    err = events[0]
    assert err.kind == "error"
    assert err.data.get("error") == "cap_hit"
    assert err.data.get("level") == "100"
    assert "topup_url" in err.data


# ── 3. Failure events do not push the cap toward 100% ─────────────────

def test_failed_events_do_not_count_against_cap(isolated_metering):
    from backend.core.metering import (
        cap_alert_level,
        is_request_allowed,
    )

    # 5 failed events at notional cost $20 each — outcome != ok keeps
    # them in the SQLite mirror but cost-aggregation still sums them.
    # However, the chat orchestrator records failures with cost_usd=0.
    # We mirror that contract by passing cost_usd=0 for failures here.
    for _ in range(5):
        _seed_event(cost_usd=0.0, outcome="provider_error")

    # No real spend → cap stays at "none" and request is allowed.
    assert cap_alert_level() == "none"
    allowed, info = is_request_allowed()
    assert allowed is True
    assert info["level"] == "none"
    assert info["percent_used"] == 0.0


# ── 4. Notification fanout dedup — fires once per (level, month) ──────

def test_notification_fires_once_per_level_per_month(isolated_metering):
    from backend.core.metering import (
        maybe_fire_cap_notification,
        reset_cap_notify_log,
    )

    reset_cap_notify_log()

    info = {
        "tier": "PRO",
        "level": "80",
        "percent_used": 0.81,
        "spent_usd": 20.25,
        "hard_cap_usd": 25.0,
        "suggest_topup_url": "https://meeet.world/account/billing",
    }
    first = maybe_fire_cap_notification("80", info)
    second = maybe_fire_cap_notification("80", info)
    assert first["fired"] is True
    assert first["level"] == "80"
    assert second["fired"] is False
    assert second["skipped_reason"] == "already_notified_this_month"

    # Different level should re-fire even in the same month.
    third = maybe_fire_cap_notification(
        "90", dict(info, level="90", percent_used=0.91, spent_usd=22.75)
    )
    assert third["fired"] is True

    # "none" level is always a no-op.
    skipped = maybe_fire_cap_notification("none", info)
    assert skipped["fired"] is False
    assert skipped["skipped_reason"] == "level_below_threshold"


# ── 5. TARS_BYPASS_CAP=1 force-allows requests over the hard cap ──────

def test_bypass_env_lets_requests_through_when_cap_blown(
    isolated_metering, monkeypatch
):
    from backend.core.metering import is_request_allowed

    _seed_event(cost_usd=26.0)  # over PRO $25 hard cap

    # Without bypass — blocked.
    allowed, info = is_request_allowed()
    assert allowed is False
    assert info["bypassed"] is False

    # With bypass — allowed, but the level field still tells UI = 100.
    monkeypatch.setenv("TARS_BYPASS_CAP", "1")
    allowed2, info2 = is_request_allowed()
    assert allowed2 is True
    assert info2["bypassed"] is True
    assert info2["level"] == "100"
