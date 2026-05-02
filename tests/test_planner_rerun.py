"""Tests for the one-shot rerun primitive (PR follow-up to #108).

CLI: ``clone --approve [--run [--mode ...]]``
HTTP: ``POST /api/planner/{plan_id}/rerun``

Both surfaces compose ``clone`` + ``approve`` + (optional)
``run`` into a single call so the cockpit's "Rerun" button is a
one-network-trip affair and the operator's bash workflow is a
one-line invocation. The ``planner.cloned`` event grows two
boolean flags — ``auto_approved`` and ``auto_run`` — so the
timeline can label the relationship as a one-shot rerun
(rendered as ``· rerun`` in the summariser) instead of a manual
clone followed by a manual approve.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TARS_PLANNER_DB_PATH", str(tmp_path / "planner.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_API_KEY", raising=False)
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


def _run_cli(argv: list[str]) -> tuple[int, dict[str, Any]]:
    from backend.core.planner.cli import main

    buf = StringIO()
    with patch("sys.stdout", new=buf):
        code = main(argv)
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else {})


def _seed_plan(goal: str = "traders.morning_check") -> dict[str, Any]:
    code, body = _run_cli(["synthesize", goal])
    assert code == 0, body
    return body["plan"]


@pytest.fixture()
def app_client():
    from web_extras.routers.planner import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


async def _fetch_events(kind: str) -> list[dict[str, Any]]:
    from backend.core.meeet import get_store

    rows = await get_store().list_events(limit=200, kind=kind)
    return [{"kind": r.kind, "payload": r.payload} for r in rows]


# ---------------------------------------------------------------------------
# CLI: clone --approve / --run
# ---------------------------------------------------------------------------


def test_cli_clone_approve_flips_status_to_approved():
    plan = _seed_plan()
    code, body = _run_cli(["--quiet", "clone", "--approve", plan["id"]])
    assert code == 0, body
    assert body["ok"] is True
    assert body["auto_approved"] is True
    assert body["auto_run"] is False
    assert body["plan"]["status"] == "approved"
    # The original is untouched.
    assert body["source_plan_id"] == plan["id"]
    code2, source_after = _run_cli(["--quiet", "show", plan["id"]])
    assert code2 == 0
    assert source_after["plan"]["status"] == plan["status"]


def test_cli_clone_run_implies_approve_and_executes():
    plan = _seed_plan()
    code, body = _run_cli(["--quiet", "clone", "--run", plan["id"]])
    assert code == 0, body
    assert body["ok"] is True
    assert body["auto_approved"] is True
    assert body["auto_run"] is True
    assert body["run_result"] is not None
    assert body["run_result"]["plan_id"] == body["plan"]["id"]
    # After --run the plan is in a terminal state (completed or
    # aborted depending on whether the underlying playbook
    # succeeded). Either way it's not "approved" / "running"
    # anymore.
    assert body["plan"]["status"] in ("completed", "aborted")


def test_cli_clone_emits_auto_run_flags_on_planner_cloned_event():
    import asyncio

    plan = _seed_plan()
    code, body = _run_cli(["--quiet", "clone", "--run", plan["id"]])
    assert code == 0, body

    rows = asyncio.run(_fetch_events("planner.cloned"))
    assert any(
        r["payload"].get("plan_id") == body["plan"]["id"]
        and r["payload"].get("auto_approved") is True
        and r["payload"].get("auto_run") is True
        for r in rows
    )


def test_cli_clone_without_flags_stays_proposed():
    """Backwards compatibility: bare ``clone`` keeps the legacy
    behaviour shipped in PR #108.
    """

    plan = _seed_plan()
    code, body = _run_cli(["--quiet", "clone", plan["id"]])
    assert code == 0, body
    assert body["auto_approved"] is False
    assert body["auto_run"] is False
    assert body["plan"]["status"] == "proposed"
    assert body["run_result"] is None


def test_cli_clone_run_with_invalid_mode_short_circuits_via_argparse():
    plan = _seed_plan()
    # argparse short-circuits invalid ``--mode`` choices itself by
    # raising ``SystemExit(2)`` before our handler runs. Let it
    # propagate and assert on the exit code so we pin the
    # validation contract regardless of whether argparse renders
    # the error to stderr or stdout.
    with pytest.raises(SystemExit) as excinfo:
        _run_cli(
            [
                "--quiet",
                "clone",
                "--run",
                "--mode",
                "not_a_real_mode",
                plan["id"],
            ]
        )
    assert excinfo.value.code == 2


def test_cli_clone_unknown_plan_returns_error_envelope_even_with_run():
    code, body = _run_cli(["--quiet", "clone", "--run", "pln_unknown"])
    assert code != 0
    assert body["ok"] is False
    assert body["reason"] == "plan_not_found"
    assert body["plan_id"] == "pln_unknown"


# ---------------------------------------------------------------------------
# HTTP: POST /api/planner/{plan_id}/rerun
# ---------------------------------------------------------------------------


def test_http_rerun_404_for_unknown_plan(app_client):
    resp = app_client.post("/api/planner/pln_unknown/rerun", json={})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "plan_not_found"


def test_http_rerun_happy_path_returns_clone_plus_run_result(app_client):
    seed_resp = app_client.post(
        "/api/planner/plan", json={"goal": "traders.morning_check"}
    )
    plan_id = seed_resp.json()["plan"]["id"]

    resp = app_client.post(f"/api/planner/{plan_id}/rerun", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["auto_approved"] is True
    assert body["auto_run"] is True
    assert body["source_plan_id"] == plan_id
    assert body["plan"]["id"] != plan_id
    assert body["plan"]["status"] in ("completed", "aborted")
    assert body["run_result"]["plan_id"] == body["plan"]["id"]


def test_http_rerun_emits_planner_cloned_with_auto_flags(app_client):
    import asyncio

    seed_resp = app_client.post(
        "/api/planner/plan", json={"goal": "traders.morning_check"}
    )
    plan_id = seed_resp.json()["plan"]["id"]

    resp = app_client.post(f"/api/planner/{plan_id}/rerun", json={})
    assert resp.status_code == 200, resp.text
    new_id = resp.json()["plan"]["id"]

    rows = asyncio.run(_fetch_events("planner.cloned"))
    matches = [
        r for r in rows
        if r["payload"].get("plan_id") == new_id
        and r["payload"].get("auto_approved") is True
        and r["payload"].get("auto_run") is True
    ]
    assert len(matches) == 1, rows


def test_http_rerun_unknown_mode_falls_back_to_env_default(app_client):
    """``resolve_mode`` is permissive — an unknown ``mode`` string
    silently falls through to the env / fallback chain instead of
    400-ing. Pin that behaviour so a typo from a cockpit dropdown
    can never accidentally lock an operator out of rerunning a
    plan; the actual policy is still chosen deterministically.
    """

    seed_resp = app_client.post(
        "/api/planner/plan", json={"goal": "traders.morning_check"}
    )
    plan_id = seed_resp.json()["plan"]["id"]
    resp = app_client.post(
        f"/api/planner/{plan_id}/rerun", json={"mode": "not_a_real_mode"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The run still completes (or aborts) deterministically.
    assert body["plan"]["status"] in ("completed", "aborted")


def test_http_rerun_respects_thread_id_override(app_client):
    seed_resp = app_client.post(
        "/api/planner/plan", json={"goal": "traders.morning_check"}
    )
    plan_id = seed_resp.json()["plan"]["id"]

    resp = app_client.post(
        f"/api/planner/{plan_id}/rerun",
        json={"thread_id": "thr_rebound_v1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"]["thread_id"] == "thr_rebound_v1"


# ---------------------------------------------------------------------------
# Timeline summariser — rerun label
# ---------------------------------------------------------------------------


def test_timeline_summariser_labels_one_shot_rerun_as_rerun():
    from backend.core.search.timeline import _summarise_event

    summary = _summarise_event(
        "planner.cloned",
        {
            "plan_id": "pln_clone_42",
            "source_plan_id": "pln_src_07",
            "step_count": 4,
            "auto_approved": True,
            "auto_run": True,
        },
    )
    assert "plan=pln_clone_42" in summary
    assert "from=pln_src_07" in summary
    assert "rerun" in summary
    # auto_run subsumes the auto-approved label.
    assert "auto-approved" not in summary


def test_timeline_summariser_labels_auto_approved_clone_distinctly():
    from backend.core.search.timeline import _summarise_event

    summary = _summarise_event(
        "planner.cloned",
        {
            "plan_id": "pln_clone_43",
            "source_plan_id": "pln_src_08",
            "step_count": 4,
            "auto_approved": True,
            "auto_run": False,
        },
    )
    assert "auto-approved" in summary
    assert "rerun" not in summary
