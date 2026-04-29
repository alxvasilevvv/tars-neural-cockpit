"""HTTP contract for the multi-agent surface (Phase M).

Covers create/list/get/patch agents, queue/list/get tasks, run a task
end-to-end (it deliberates through the council and persists the
result), cancel, transition validation, and ``agent.*`` event emission
into the meeet store.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.agents import reset_singleton_for_tests
from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.meeet import get_store as get_meeet_store
from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store


@pytest.fixture(autouse=True)
def isolated_stores(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_agents_")
    monkeypatch.setenv("TARS_AGENTS_DB_PATH", os.path.join(tmp, "agents.sqlite"))
    monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("TARS_CHAT_STORE", "disabled")
    reset_singleton_for_tests()
    reset_meeet_store()
    reset_meeet_client()
    yield
    reset_singleton_for_tests()
    reset_meeet_store()
    reset_meeet_client()


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


# ---------- agents -------------------------------------------------------


def test_create_agent_round_trips(client: TestClient) -> None:
    r = client.post(
        "/api/agents",
        json={
            "name": "Trader Bot",
            "pack_slug": "traders",
            "description": "watches WBTC",
            "wallet_address": "0xABCDEF0000000000000000000000000000000000",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    a = body["agent"]
    assert a["pack_slug"] == "traders"
    assert a["wallet_address"] == "0xabcdef0000000000000000000000000000000000"
    assert a["status"] == "active"
    assert a["id"].startswith("agent_")


def test_create_agent_rejects_unknown_pack(client: TestClient) -> None:
    r = client.post(
        "/api/agents",
        json={"name": "X", "pack_slug": "no_such_pack"},
    )
    assert r.status_code == 400
    assert "unknown pack_slug" in r.json()["detail"]


def test_list_agents_filters_archived(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "science"}).json()
    aid = a["agent"]["id"]
    client.post("/api/agents", json={"name": "B", "pack_slug": "business"})
    # Archive A
    r = client.patch(f"/api/agents/{aid}", json={"status": "archived"})
    assert r.status_code == 200
    assert r.json()["agent"]["status"] == "archived"

    listed = client.get("/api/agents").json()
    assert listed["count"] == 1
    assert listed["agents"][0]["pack_slug"] == "business"

    listed_all = client.get("/api/agents?include_archived=true").json()
    assert listed_all["count"] == 2


def test_patch_agent_invalid_transition(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "mlm"}).json()
    aid = a["agent"]["id"]
    client.patch(f"/api/agents/{aid}", json={"status": "archived"})
    # archived → active is illegal
    r = client.patch(f"/api/agents/{aid}", json={"status": "active"})
    assert r.status_code == 400
    assert "transition" in r.json()["detail"]


def test_patch_agent_pause_resume(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    assert client.patch(f"/api/agents/{aid}", json={"status": "paused"}).status_code == 200
    assert client.patch(f"/api/agents/{aid}", json={"status": "active"}).status_code == 200


# ---------- tasks --------------------------------------------------------


def test_queue_task_requires_active_agent(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    client.patch(f"/api/agents/{aid}", json={"status": "paused"})
    r = client.post(f"/api/agents/{aid}/tasks", json={"prompt": "do X"})
    assert r.status_code == 409


def test_run_task_lands_on_done(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    qr = client.post(
        f"/api/agents/{aid}/tasks",
        json={
            "prompt": "Should we buy WBTC at the dip?",
            "metadata": {"topic": "trade_setup"},
        },
    ).json()
    tid = qr["task"]["id"]

    rr = client.post(f"/api/tasks/{tid}/run", json={"council_mode": "dual_vote"}).json()
    assert rr["ok"] is True
    final = rr["task"]
    assert final["status"] == "done"
    assert final["result"] is not None
    assert "chosen" in final["result"]
    assert final["trace_id"]


def test_cancel_pending_task(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "science"}).json()
    aid = a["agent"]["id"]
    tid = client.post(f"/api/agents/{aid}/tasks", json={"prompt": "research"}).json()["task"]["id"]
    cancelled = client.post(f"/api/tasks/{tid}/cancel").json()
    assert cancelled["task"]["status"] == "cancelled"
    # Re-running a terminal task is rejected.
    again = client.post(f"/api/tasks/{tid}/run")
    assert again.status_code == 409


def test_run_unknown_task_404(client: TestClient) -> None:
    r = client.post("/api/tasks/task_deadbeef/run")
    assert r.status_code == 404


def test_failed_task_can_be_re_run(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    qr = client.post(f"/api/agents/{aid}/tasks", json={"prompt": "Should we buy?"}).json()
    tid = qr["task"]["id"]
    # First run completes successfully (deterministic LocalVoice).
    first = client.post(f"/api/tasks/{tid}/run").json()
    assert first["task"]["status"] == "done"
    # Done is terminal; re-run is 409.
    assert client.post(f"/api/tasks/{tid}/run").status_code == 409


def test_list_tasks_for_agent(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "mlm"}).json()
    aid = a["agent"]["id"]
    for i in range(3):
        client.post(f"/api/agents/{aid}/tasks", json={"prompt": f"task {i}"})
    listed = client.get(f"/api/agents/{aid}/tasks").json()
    assert listed["count"] == 3
    only_pending = client.get(f"/api/agents/{aid}/tasks?status=pending").json()
    assert only_pending["count"] == 3


# ---------- meeet bridge ------------------------------------------------


def test_create_agent_emits_meeet_event(client: TestClient) -> None:
    import asyncio

    r = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"})
    assert r.status_code == 200
    store = get_meeet_store()
    events = asyncio.run(store.list_events(limit=20))
    kinds = [e.kind for e in events]
    assert "agent.created" in kinds
    payload = next(e.payload for e in events if e.kind == "agent.created")
    assert payload["pack_slug"] == "traders"
    assert payload["agent_id"].startswith("agent_")


def test_run_task_emits_started_and_completed(client: TestClient) -> None:
    import asyncio

    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    tid = client.post(f"/api/agents/{aid}/tasks", json={"prompt": "hello"}).json()["task"]["id"]
    client.post(f"/api/tasks/{tid}/run")

    store = get_meeet_store()
    events = asyncio.run(store.list_events(limit=80))
    kinds = [e.kind for e in events]
    assert "agent.task.queued" in kinds
    assert "agent.task.started" in kinds
    assert "agent.task.completed" in kinds


# ---------- model contract ----------------------------------------------


def test_invalid_status_string_is_rejected(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    r = client.patch(f"/api/agents/{aid}", json={"status": "weird"})
    assert r.status_code == 400


def test_task_to_dict_decodes_result(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    tid = client.post(f"/api/agents/{aid}/tasks", json={"prompt": "x"}).json()["task"]["id"]
    final = client.post(f"/api/tasks/{tid}/run").json()["task"]
    assert isinstance(final["result"], dict)
    assert {"chosen", "agreement", "voices"}.issubset(final["result"].keys())
    json.dumps(final)  # round-trips
