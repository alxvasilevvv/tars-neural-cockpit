"""Tests for the ``planner full`` CLI subcommand and the
``aggregate_usage_lifetime`` helper that backs both the CLI and the
HTTP ``/api/planner/{id}/full`` endpoint.

The CLI mirror was added so an operator without a cockpit window can
still inspect a plan in one command and pipe the JSON straight into
``jq``. This file pins:

- The helper alone (no DB / no SQLite, just dataclass arithmetic):
  zero runs, single priced run, all-unpriced runs, mixed runs.
- The CLI happy path (plan + zero runs + zero-valued lifetime).
- The CLI error envelope for an unknown plan id.
- The CLI ``--limit`` flag pass-through.
- The CLI's stable envelope shape so the cockpit's typed client can
  rely on the keys.

The CLI tests share the per-test isolated SQLite + meeet stores
fixture from :mod:`tests.test_planner_cli` style.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from backend.core.planner import aggregate_usage_lifetime
from backend.core.planner.history import PlanRun


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    """Per-test isolated SQLite stores + meeet client (mirrors test_planner_cli)."""

    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
    monkeypatch.delenv("PLANNER_STORE", raising=False)
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")

    from backend.core.meeet import reset_client, reset_store
    from backend.core.planner import reset_planner_store, reset_run_registry
    from backend.core.planner import store as planner_store_mod

    reset_store()
    reset_client()
    reset_planner_store()
    reset_run_registry()
    monkeypatch.setattr(planner_store_mod, "_SINGLETON", None, raising=False)

    yield

    reset_store()
    reset_client()
    reset_planner_store()
    reset_run_registry()
    monkeypatch.setattr(planner_store_mod, "_SINGLETON", None, raising=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str]) -> tuple[int, dict[str, Any]]:
    from backend.core.planner.cli import main

    buf = StringIO()
    with patch("sys.stdout", new=buf):
        code = main(argv)
    out = buf.getvalue().strip()
    body = json.loads(out) if out else {}
    return code, body


def _make_run(
    *,
    calls: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float | None = None,
    latency_ms_total: float = 0.0,
    has_priced_models: bool = False,
    status: str = "completed",
) -> PlanRun:
    return PlanRun(
        plan_id="pln_x",
        started_at=0.0,
        started_event_id=0,
        usage_calls=calls,
        usage_tokens_in=tokens_in,
        usage_tokens_out=tokens_out,
        usage_cost_usd=cost_usd,
        usage_latency_ms_total=latency_ms_total,
        usage_has_priced_models=has_priced_models,
        status=status,
    )


# ---------------------------------------------------------------------------
# aggregate_usage_lifetime — pure helper
# ---------------------------------------------------------------------------


def test_aggregate_lifetime_zero_runs_returns_zero_block_with_null_cost():
    block = aggregate_usage_lifetime([])
    assert block == {
        "calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": None,
        "latency_ms_total": 0.0,
        "has_priced_models": False,
        "runs_aggregated": 0,
    }


def test_aggregate_lifetime_single_priced_run_sums_correctly():
    runs = [
        _make_run(
            calls=3,
            tokens_in=120,
            tokens_out=45,
            cost_usd=0.0234,
            latency_ms_total=150.0,
            has_priced_models=True,
        )
    ]
    block = aggregate_usage_lifetime(runs)
    assert block["calls"] == 3
    assert block["tokens_in"] == 120
    assert block["tokens_out"] == 45
    assert block["cost_usd"] == pytest.approx(0.0234)
    assert block["latency_ms_total"] == pytest.approx(150.0)
    assert block["has_priced_models"] is True
    assert block["runs_aggregated"] == 1


def test_aggregate_lifetime_all_unpriced_runs_keep_cost_null():
    runs = [
        _make_run(calls=1, tokens_in=10, tokens_out=5, cost_usd=None,
                  has_priced_models=False),
        _make_run(calls=2, tokens_in=20, tokens_out=10, cost_usd=None,
                  has_priced_models=False),
    ]
    block = aggregate_usage_lifetime(runs)
    assert block["cost_usd"] is None  # Not 0.0!
    assert block["has_priced_models"] is False
    assert block["calls"] == 3
    assert block["tokens_in"] == 30
    assert block["tokens_out"] == 15
    assert block["runs_aggregated"] == 2


def test_aggregate_lifetime_mixed_priced_and_unpriced_sums_only_priced_costs():
    """The lifetime cost is the sum of the priced runs' costs only.

    A run that ran but emitted no priced model contributes its
    calls / tokens / latency but NOT to ``cost_usd``. Result:
    ``cost_usd`` is the sum of *only* the priced runs.
    """

    runs = [
        _make_run(
            calls=2, tokens_in=50, tokens_out=25, cost_usd=0.01,
            latency_ms_total=10.0, has_priced_models=True,
        ),
        _make_run(
            calls=1, tokens_in=10, tokens_out=5, cost_usd=None,
            latency_ms_total=20.0, has_priced_models=False,
        ),
        _make_run(
            calls=3, tokens_in=100, tokens_out=50, cost_usd=0.05,
            latency_ms_total=30.0, has_priced_models=True,
        ),
    ]
    block = aggregate_usage_lifetime(runs)
    assert block["calls"] == 6
    assert block["tokens_in"] == 160
    assert block["tokens_out"] == 80
    assert block["cost_usd"] == pytest.approx(0.06)  # 0.01 + 0.05, NOT 0.06+None
    assert block["latency_ms_total"] == pytest.approx(60.0)
    assert block["has_priced_models"] is True
    assert block["runs_aggregated"] == 3


def test_aggregate_lifetime_ignores_priced_run_with_none_cost():
    """``has_priced_models=True`` but ``cost_usd=None`` should not
    poison the running total — the helper guards against it."""

    runs = [
        _make_run(
            calls=1, tokens_in=10, tokens_out=5, cost_usd=None,
            has_priced_models=True,
        ),
        _make_run(
            calls=2, tokens_in=20, tokens_out=10, cost_usd=0.02,
            has_priced_models=True,
        ),
    ]
    block = aggregate_usage_lifetime(runs)
    assert block["cost_usd"] == pytest.approx(0.02)
    assert block["has_priced_models"] is True


def test_aggregate_lifetime_accepts_tuple_input():
    """Per the typed signature, both list and tuple work."""

    runs = (
        _make_run(calls=1, has_priced_models=True, cost_usd=0.5),
        _make_run(calls=1, has_priced_models=True, cost_usd=0.5),
    )
    assert aggregate_usage_lifetime(runs)["cost_usd"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# planner full CLI
# ---------------------------------------------------------------------------


def _seed_plan_via_synthesize(goal: str = "traders.morning_check") -> str:
    code, body = _run_cli(["synthesize", goal])
    assert code == 0, body
    return body["plan"]["id"]


def test_full_unknown_plan_returns_error_envelope():
    code, body = _run_cli(["full", "pln_does_not_exist"])
    assert code == 1
    assert body["ok"] is False
    assert body["reason"] == "plan_not_found"
    assert body["plan_id"] == "pln_does_not_exist"


def test_full_happy_path_returns_envelope_with_zero_runs_and_null_cost():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["full", plan_id])
    assert code == 0, body
    # Top-level envelope keys are stable for the cockpit client.
    assert set(body.keys()) == {"ok", "plan_id", "plan", "runs", "usage_lifetime"}
    assert body["ok"] is True
    assert body["plan_id"] == plan_id
    assert body["plan"]["id"] == plan_id

    # Newly-synthesized plan: no runs yet.
    assert set(body["runs"].keys()) == {"count", "in_flight", "items"}
    assert body["runs"]["count"] == 0
    assert body["runs"]["in_flight"] == 0
    assert body["runs"]["items"] == []

    # Lifetime block is zero-valued, cost is null (n/a in cockpit).
    lifetime = body["usage_lifetime"]
    assert set(lifetime.keys()) == {
        "calls",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "latency_ms_total",
        "has_priced_models",
        "runs_aggregated",
    }
    assert lifetime["calls"] == 0
    assert lifetime["tokens_in"] == 0
    assert lifetime["tokens_out"] == 0
    assert lifetime["cost_usd"] is None
    assert lifetime["latency_ms_total"] == 0.0
    assert lifetime["has_priced_models"] is False
    assert lifetime["runs_aggregated"] == 0


def test_full_passes_limit_flag_through_to_history_query(monkeypatch):
    """``--limit N`` reaches reconstruct_runs_async unchanged."""

    plan_id = _seed_plan_via_synthesize()

    captured: dict[str, int] = {}

    from backend.core.planner import history as history_mod

    real = history_mod.reconstruct_runs_async

    async def _spy(*args, **kwargs):
        captured["limit"] = kwargs.get("limit")
        return await real(*args, **kwargs)

    monkeypatch.setattr(history_mod, "reconstruct_runs_async", _spy)
    # The CLI imports the symbol locally; patch it there too.
    from backend.core.planner import cli as cli_mod
    monkeypatch.setattr(cli_mod, "reconstruct_runs_async", _spy)

    code, _body = _run_cli(["full", plan_id, "--limit", "42"])
    assert code == 0
    assert captured.get("limit") == 42


def test_full_quiet_flag_keeps_output_to_one_json_line():
    plan_id = _seed_plan_via_synthesize()
    # ``--quiet`` is global → must precede the subcommand.
    code, body = _run_cli(["--quiet", "full", plan_id])
    assert code == 0
    assert body["plan_id"] == plan_id
