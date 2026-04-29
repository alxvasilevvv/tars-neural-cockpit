"""Agent autopilot loop contract tests.

Covers:

- Toggling the ``autopilot`` flag persists into the agent's metadata.
- A single ``tick_once`` picks up the oldest pending task and runs it
  through the council orchestrator.
- Agents without the flag are skipped.
- Paused/archived agents are skipped even if the flag is set.
- Multi-agent: each tick only takes ONE pending task per agent so a
  long inbox doesn't starve siblings.
- Loop is configurable: ``TARS_AGENTS_AUTOPILOT_INTERVAL_S=0`` short-
  circuits cleanly without raising.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.agents import reset_singleton_for_tests
from backend.core.agents.autopilot import autopilot_loop, tick_once
from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_autopilot_")
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


def test_toggle_autopilot_persists(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    on = client.post(f"/api/agents/{aid}/autopilot?enabled=true").json()
    assert on["autopilot"] is True
    off = client.post(f"/api/agents/{aid}/autopilot?enabled=false").json()
    assert off["autopilot"] is False


def test_toggle_unknown_agent_404(client: TestClient) -> None:
    r = client.post("/api/agents/agent_unknown/autopilot")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_tick_runs_pending_task_for_autopilot_agents(
    client: TestClient,
) -> None:
    a = client.post(
        "/api/agents",
        json={"name": "A", "pack_slug": "traders", "metadata": {"autopilot": True}},
    ).json()
    aid = a["agent"]["id"]
    tid = client.post(f"/api/agents/{aid}/tasks", json={"prompt": "go"}).json()[
        "task"
    ]["id"]
    out = await tick_once()
    assert out["agents_visited"] == 1
    assert out["tasks_run"] == 1
    refreshed = client.get(f"/api/tasks/{tid}").json()
    assert refreshed["task"]["status"] == "done"


@pytest.mark.asyncio
async def test_tick_skips_agents_without_flag(client: TestClient) -> None:
    a = client.post("/api/agents", json={"name": "A", "pack_slug": "traders"}).json()
    aid = a["agent"]["id"]
    client.post(f"/api/agents/{aid}/tasks", json={"prompt": "x"})
    out = await tick_once()
    assert out["agents_visited"] == 0
    assert out["tasks_run"] == 0


@pytest.mark.asyncio
async def test_tick_skips_paused_agents(client: TestClient) -> None:
    a = client.post(
        "/api/agents",
        json={"name": "A", "pack_slug": "traders", "metadata": {"autopilot": True}},
    ).json()
    aid = a["agent"]["id"]
    # Queue while still active.
    client.post(f"/api/agents/{aid}/tasks", json={"prompt": "x"})
    # Then pause.
    client.patch(f"/api/agents/{aid}", json={"status": "paused"})
    out = await tick_once()
    assert out["agents_visited"] == 0


@pytest.mark.asyncio
async def test_tick_only_pulls_one_task_per_agent(client: TestClient) -> None:
    a = client.post(
        "/api/agents",
        json={"name": "A", "pack_slug": "traders", "metadata": {"autopilot": True}},
    ).json()
    aid = a["agent"]["id"]
    for i in range(3):
        client.post(f"/api/agents/{aid}/tasks", json={"prompt": f"t{i}"})
    out = await tick_once()
    assert out["tasks_run"] == 1
    pending_after = client.get(f"/api/agents/{aid}/tasks?status=pending").json()
    assert pending_after["count"] == 2
    out2 = await tick_once()
    assert out2["tasks_run"] == 1


@pytest.mark.asyncio
async def test_loop_short_circuits_on_zero_interval(monkeypatch) -> None:
    monkeypatch.setenv("TARS_AGENTS_AUTOPILOT_INTERVAL_S", "0")
    # Should return immediately, never raise.
    await autopilot_loop()


@pytest.mark.asyncio
async def test_force_tick_endpoint(client: TestClient) -> None:
    a = client.post(
        "/api/agents",
        json={"name": "A", "pack_slug": "traders", "metadata": {"autopilot": True}},
    ).json()
    aid = a["agent"]["id"]
    client.post(f"/api/agents/{aid}/tasks", json={"prompt": "go"})
    r = client.post("/api/agents/autopilot/tick").json()
    assert r["ok"] is True
    assert r["agents_visited"] == 1
    assert r["tasks_run"] == 1
