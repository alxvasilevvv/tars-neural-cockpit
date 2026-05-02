"""Tests for the planner shell CLI (PR #107).

Covers each subcommand's happy path + the most common error
envelopes. Each test invokes :func:`backend.core.planner.cli.main`
directly with an ``argv`` list and captures stdout — no real
process spawning so the test is hermetic and fast.

The CLI prints exactly one top-level JSON object per call, so
``json.loads(captured)`` is the contract every assertion leans
on.

Notes:

- :func:`main` returns 0 on ``ok=True``, 1 otherwise. We assert
  on both the JSON body and the exit code.
- The ``--quiet`` flag is asserted on ``list`` to make sure the
  output stays a single line (cron / log shippers depend on it).
- ``delete`` requires ``--yes`` to actually drop the row; without
  it the CLI returns ``confirmation_required`` so a sleepy
  operator can't ``rm -rf`` a planned op by mistake.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    """Per-test isolated SQLite stores + meeet client."""

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
    """Invoke ``main(argv)`` and return ``(exit_code, parsed_stdout)``."""

    from backend.core.planner.cli import main

    buf = StringIO()
    with patch("sys.stdout", new=buf):
        code = main(argv)
    out = buf.getvalue().strip()
    body = json.loads(out) if out else {}
    return code, body


def _seed_plan_via_synthesize(goal: str = "traders.morning_check") -> str:
    """Synthesize a plan via the CLI and return its id.

    This is sync because :func:`_run_cli` already drives ``main``,
    which spins its own ``asyncio.run``. Wrapping it in another
    ``asyncio.run`` would nest event loops and crash.
    """

    code, body = _run_cli(["synthesize", goal])
    assert code == 0, body
    return body["plan"]["id"]


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_stats_prints_zeroes_for_fresh_db():
    code, body = _run_cli(["stats"])
    assert code == 0
    assert body["ok"] is True
    assert body["total"] == 0
    assert body["by_status"] == {}
    assert body["enabled"] is True


# ---------------------------------------------------------------------------
# synthesize / show / list
# ---------------------------------------------------------------------------


def test_synthesize_creates_a_plan_and_returns_it():
    code, body = _run_cli(["synthesize", "traders.morning_check"])
    assert code == 0
    plan = body["plan"]
    assert plan["status"] == "proposed"
    assert plan["id"].startswith("pln_")
    assert plan["step_count"] >= 1


def test_synthesize_empty_goal_returns_error_with_exit_1():
    code, body = _run_cli(["synthesize", ""])
    assert code == 1
    assert body["ok"] is False
    assert body["reason"] == "empty_goal"


def test_synthesize_no_match_returns_no_match_reason():
    code, body = _run_cli(["synthesize", "totally-unknown-goal-asdf"])
    assert code == 1
    assert body["reason"] == "no_match"
    assert "goal" in body


def test_show_unknown_plan_returns_404_envelope():
    code, body = _run_cli(["show", "pln_does_not_exist"])
    assert code == 1
    assert body["reason"] == "plan_not_found"
    assert body["plan_id"] == "pln_does_not_exist"


def test_show_known_plan_returns_full_dict():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["show", plan_id])
    assert code == 0
    assert body["plan"]["id"] == plan_id


def test_list_returns_count_and_plans():
    _seed_plan_via_synthesize()
    _seed_plan_via_synthesize("business.morning_brief")
    code, body = _run_cli(["list"])
    assert code == 0
    assert body["count"] == 2
    assert len(body["plans"]) == 2
    # Newest first → second seed comes first.
    assert body["plans"][0]["goal"] == "business.morning_brief"


def test_list_filters_by_status():
    plan_id = _seed_plan_via_synthesize()
    # Approve so a status filter has something to differentiate.
    _run_cli(["approve", plan_id])
    code, body = _run_cli(["list", "--status", "approved"])
    assert code == 0
    assert body["count"] == 1
    assert body["plans"][0]["status"] == "approved"


def test_list_unknown_status_returns_envelope_with_allowed():
    code, body = _run_cli(["list", "--status", "blarg"])
    assert code == 1
    assert body["reason"] == "unknown_status"
    assert "allowed" in body
    assert "approved" in body["allowed"]


def test_quiet_flag_emits_compact_json():
    """Cron / log shippers expect a single line per invocation."""

    from backend.core.planner.cli import main

    buf = StringIO()
    with patch("sys.stdout", new=buf):
        code = main(["--quiet", "stats"])
    assert code == 0
    out = buf.getvalue().strip()
    # Compact JSON has no indentation → exactly one line.
    assert "\n" not in out
    json.loads(out)  # Still parses.


# ---------------------------------------------------------------------------
# approve / reject
# ---------------------------------------------------------------------------


def test_approve_flips_status_to_approved():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["approve", plan_id])
    assert code == 0
    assert body["plan"]["status"] == "approved"


def test_reject_flips_status_to_rejected():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["reject", plan_id])
    assert code == 0
    assert body["plan"]["status"] == "rejected"


def test_approve_unknown_plan_returns_envelope():
    code, body = _run_cli(["approve", "pln_unknown"])
    assert code == 1
    assert body["reason"] == "plan_not_found"


def test_approve_terminal_plan_refuses_with_status_marker():
    plan_id = _seed_plan_via_synthesize()
    _run_cli(["reject", plan_id])  # → terminal
    code, body = _run_cli(["approve", plan_id])
    assert code == 1
    assert body["reason"] == "plan_already_rejected"
    assert body["status"] == "rejected"


# ---------------------------------------------------------------------------
# run / abort
# ---------------------------------------------------------------------------


def test_run_unknown_plan_returns_envelope():
    code, body = _run_cli(["run", "pln_unknown"])
    assert code == 1
    assert body["reason"] == "plan_not_found"


def test_run_unapproved_plan_refuses_with_plan_not_runnable():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["run", plan_id])
    assert code == 1
    assert body["reason"] == "plan_not_runnable"


def test_abort_unknown_plan_returns_envelope():
    code, body = _run_cli(["abort", "pln_unknown"])
    assert code == 1
    assert body["reason"] == "plan_not_running"


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------


def test_runs_unknown_plan_returns_envelope():
    code, body = _run_cli(["runs", "pln_unknown"])
    assert code == 1
    assert body["reason"] == "plan_not_found"


def test_runs_returns_empty_list_for_known_plan_with_no_history():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["runs", plan_id])
    assert code == 0
    assert body["count"] == 0
    assert body["in_flight"] == 0
    assert body["runs"] == []


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_without_yes_is_a_dry_run():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["delete", plan_id])
    assert code == 1
    assert body["reason"] == "confirmation_required"
    # And the plan is still there.
    code2, body2 = _run_cli(["show", plan_id])
    assert code2 == 0


def test_delete_with_yes_actually_drops_the_plan():
    plan_id = _seed_plan_via_synthesize()
    code, body = _run_cli(["delete", plan_id, "--yes"])
    assert code == 0
    assert body["deleted"] is True
    code2, body2 = _run_cli(["show", plan_id])
    assert code2 == 1
    assert body2["reason"] == "plan_not_found"


def test_delete_unknown_plan_returns_envelope():
    code, body = _run_cli(["delete", "pln_unknown"])
    assert code == 1
    assert body["reason"] == "plan_not_found"


# ---------------------------------------------------------------------------
# End-to-end: synthesize → approve → list → delete
# ---------------------------------------------------------------------------


def test_end_to_end_lifecycle_round_trip():
    """One operator session: build a plan, approve it, see it in
    the inbox, drop it. Each call is a fresh argv-driven invocation
    just like a shell session."""

    code, body = _run_cli(["synthesize", "traders.morning_check"])
    assert code == 0
    plan_id = body["plan"]["id"]

    code, body = _run_cli(["approve", plan_id])
    assert code == 0
    assert body["plan"]["status"] == "approved"

    code, body = _run_cli(["list", "--status", "approved"])
    assert code == 0
    assert body["count"] == 1
    assert body["plans"][0]["id"] == plan_id

    code, body = _run_cli(["delete", plan_id, "--yes"])
    assert code == 0

    code, body = _run_cli(["stats"])
    assert code == 0
    assert body["total"] == 0
