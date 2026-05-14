"""W235 — consumption console + usage metering subsystem tests.

Five env-isolated cases:

1. ``record_usage`` writes both SQLite mirror + receipt ledger.
2. ``aggregate_today`` returns correct sums after 3 events.
3. ``aggregate_month`` honours the month-iso boundary.
4. Failure events (outcome != "ok") have cost_usd=0.
5. ``GET /api/usage/console`` returns the expected shape.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_metering(tmp_path, monkeypatch):
    """Point usage.sqlite + receipt store at a per-test directory."""

    usage_db = tmp_path / "usage.sqlite"
    receipts_dir = tmp_path / "receipts"
    receipts_db = tmp_path / "receipts.sqlite"
    host_key = tmp_path / "host-key.json"

    monkeypatch.setenv("TARS_USAGE_DB_PATH", str(usage_db))
    monkeypatch.setenv("TARS_RECEIPT_DIR", str(receipts_dir))
    monkeypatch.setenv("TARS_RECEIPT_DB_PATH", str(receipts_db))
    monkeypatch.setenv("TARS_RECEIPT_HOST_KEY_PATH", str(host_key))
    # Disable meeet POST so we don't try to hit the network.
    monkeypatch.delenv("MEEET_BASE_URL", raising=False)
    monkeypatch.delenv("MEEET_BRIDGE_SHARED_SECRET", raising=False)
    monkeypatch.setenv("MEEET_MODE", "off")
    monkeypatch.setenv("TARS_TIER", "PRO")

    # Reset the receipts singleton so it picks up new paths.
    from backend.core.receipts import reset_store as _reset_receipts
    _reset_receipts()

    yield tmp_path

    _reset_receipts()


def _make_event(**overrides):
    from backend.core.metering import UsageEvent

    base = dict(
        trace_id=overrides.get("trace_id") or os.urandom(8).hex(),
        ts_utc=time.time(),
        provider="anthropic",
        model="claude-sonnet-4-6",
        action="chat.message",
        tokens_in=1000,
        tokens_out=500,
        latency_ms=420.0,
        cost_usd=0.0105,  # 1k * 0.003 + 0.5k * 0.015
        cost_meeet=1.05,
        outcome="ok",
        tier="PRO",
        agent_id="tars-test",
        domain_pack="",
    )
    base.update(overrides)
    base.pop("trace_id_seed", None)
    return UsageEvent(**base)


def test_record_usage_writes_to_sqlite_and_receipt_ledger(isolated_metering):
    from backend.core.metering import record_usage
    from backend.core.metering.recorder import _usage_db_path

    ev = _make_event(trace_id="r1-trace-aaa")
    record_usage(ev)

    # 1) SQLite mirror
    conn = sqlite3.connect(_usage_db_path())
    try:
        rows = conn.execute(
            "SELECT trace_id, provider, model, cost_usd FROM usage_events"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "r1-trace-aaa"
    assert rows[0][1] == "anthropic"
    assert rows[0][2] == "claude-sonnet-4-6"
    assert abs(rows[0][3] - 0.0105) < 1e-9

    # 2) Receipt ledger
    receipts_db = isolated_metering / "receipts.sqlite"
    if receipts_db.exists():
        conn = sqlite3.connect(str(receipts_db))
        try:
            rows = conn.execute(
                "SELECT type, actor FROM receipts WHERE type = ?",
                ("usage",),
            ).fetchall()
        finally:
            conn.close()
        # ≥ 1 — record_usage records one "usage" receipt.
        assert any(r[0] == "usage" for r in rows)


def test_aggregate_today_sums_three_events(isolated_metering):
    from backend.core.metering import aggregate_today, record_usage

    now = time.time()
    for i in range(3):
        ev = _make_event(
            trace_id=f"agg-today-{i}",
            ts_utc=now + i * 0.001,
            cost_usd=0.10,
            cost_meeet=10.0,
            tokens_in=200,
            tokens_out=100,
        )
        record_usage(ev)

    agg = aggregate_today()
    assert agg["events_count"] == 3
    assert abs(agg["cost_usd"] - 0.30) < 1e-6
    assert abs(agg["cost_meeet"] - 30.0) < 1e-4
    assert agg["tokens_in"] == 600
    assert agg["tokens_out"] == 300
    assert "claude-sonnet-4-6" in agg["by_model"]
    assert agg["by_model"]["claude-sonnet-4-6"]["events"] == 3
    assert agg["by_outcome"]["ok"]["events"] == 3


def test_aggregate_month_honors_month_boundary(isolated_metering):
    from backend.core.metering import aggregate_month, record_usage
    from backend.core.metering.recorder import _open_db

    # Three "this month" events
    now = time.time()
    for i in range(3):
        record_usage(_make_event(trace_id=f"this-{i}", ts_utc=now + i * 0.001, cost_usd=0.05))

    # One forced "last month" row inserted directly bypassing record_usage,
    # so we can test that month-iso filtering excludes it. Crafted ts is
    # 45 days ago.
    last_month_ts = now - 45 * 86400.0
    last_month_dt = datetime.fromtimestamp(last_month_ts, tz=timezone.utc)
    last_month_day = last_month_dt.strftime("%Y-%m-%d")
    last_month_month = last_month_day[:7]
    conn = _open_db()
    try:
        conn.execute(
            "INSERT INTO usage_events (trace_id, ts_utc, provider, model, action,"
            " tokens_in, tokens_out, latency_ms, cost_usd, cost_meeet, outcome,"
            " tier, agent_id, domain_pack, day_iso, month_iso) VALUES"
            " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "last-month-x", last_month_ts, "anthropic", "claude-sonnet-4-6",
                "chat.message", 100, 50, 100.0, 1.00, 100.0, "ok",
                "PRO", "tars-test", "", last_month_day, last_month_month,
            ),
        )
    finally:
        conn.close()

    agg = aggregate_month()
    # Current month sees the 3 we recorded, NOT the 45-day-old row.
    assert agg["events_count"] == 3
    assert abs(agg["cost_usd"] - 0.15) < 1e-6
    assert agg["month"] != last_month_month


def test_failure_events_have_zero_cost(isolated_metering):
    from backend.core.metering import (
        UsageEvent,
        aggregate_today,
        compute_cost_usd,
        record_usage,
    )

    # provider_error must never cost anything; the orchestrator hook
    # zeroes it but the test exercises a direct record_usage call to
    # prove the SQLite row also reflects $0.
    ev = UsageEvent(
        trace_id="fail-1",
        ts_utc=time.time(),
        provider="anthropic",
        model="claude-sonnet-4-6",
        action="chat.message",
        tokens_in=1000,
        tokens_out=500,
        latency_ms=10.0,
        cost_usd=0.0,
        cost_meeet=0.0,
        outcome="provider_error",
        tier="PRO",
        agent_id="tars-test",
        domain_pack="",
    )
    record_usage(ev)

    agg = aggregate_today()
    assert agg["events_count"] == 1
    assert agg["cost_usd"] == 0.0
    assert agg["by_outcome"]["provider_error"]["events"] == 1

    # compute_cost_usd should still return the priced value (it is
    # the caller's responsibility to zero it for failures).
    assert compute_cost_usd("anthropic", "claude-sonnet-4-6", 1000, 500) > 0


def test_console_endpoint_returns_expected_shape(isolated_metering):
    from backend.core.metering import record_usage

    # Seed one event so today + month aren't empty.
    record_usage(_make_event(trace_id="console-1", cost_usd=0.02))

    from web_extras.app import app
    client = TestClient(app)

    res = client.get("/api/usage/console")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    for key in ("today", "month", "balance", "tier", "recent_events"):
        assert key in body, key
    assert body["tier"] == "PRO"
    assert body["balance"]["tier"] == "PRO"
    assert body["balance"]["hard_cap_usd"] == 25.0  # PRO tier cap
    assert isinstance(body["recent_events"], list)
    assert body["today"]["events_count"] >= 1
    assert body["month"]["events_count"] >= 1

    # healthz endpoint sanity check
    hres = client.get("/api/usage/healthz")
    assert hres.status_code == 200
    assert hres.json()["ok"] is True
