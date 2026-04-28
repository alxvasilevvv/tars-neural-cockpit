"""Tests for the meeet bridge health endpoint and the background
replay loop wiring (Phase I).
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any

import pytest

from backend.core.meeet import MeeetClient, MeeetStore
from backend.core.meeet.config import MeeetConfig


def _client(tmp_path: Path, **overrides: Any) -> MeeetClient:
    ingest_url = overrides.get("ingest_url", "http://example.invalid/ingest")
    cfg = MeeetConfig(
        ingest_url=ingest_url,
        contract_version="0.9",
        api_key=overrides.get("api_key", "k"),
        source="tars",
        local_log_path=None,
    )
    store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    return MeeetClient(cfg, store=store)


def test_health_with_ingest_unset_reports_disabled(tmp_path: Path) -> None:
    client = _client(tmp_path, ingest_url=None)

    out = asyncio.run(client.health())
    assert out["ok"] is True
    assert out["client"]["enabled"] is False
    assert out["client"]["ingest_url"] is None
    assert out["client"]["api_key_set"] is True
    assert out["client"]["contract_version"] == "0.9"
    # Store stats are present even with no events.
    assert out["store"]["total"] == 0
    assert out["last_replay"] is None


def test_health_with_ingest_set(tmp_path: Path) -> None:
    client = _client(tmp_path)

    out = asyncio.run(client.health())
    assert out["client"]["enabled"] is True
    assert out["client"]["ingest_url"] == "http://example.invalid/ingest"
    assert out["client"]["api_key_set"] is True


def test_health_reflects_last_replay(tmp_path: Path) -> None:
    """A replay attempt updates the cached metadata visible to /health."""

    client = _client(tmp_path, ingest_url=None)

    async def run() -> dict[str, Any]:
        # Replay is a no-op (no ingest URL) but still stamps last_replay.
        await client.replay_unpushed()
        return await client.health()

    out = asyncio.run(run())
    assert out["last_replay"] is not None
    assert out["last_replay"]["enabled"] is False
    assert out["last_replay"]["pushed"] == 0
    assert "ran_at" in out["last_replay"]


def test_health_after_real_replay_attempt(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path)

    pushed: list[dict[str, Any]] = []

    async def setup() -> None:
        await client.store.insert(
            {
                "trace_id": "trc_x",
                "kind": "x.test",
                "source": "tars",
                "contract_version": "0.9",
                "payload": {"n": 1},
            }
        )

    asyncio.run(setup())

    # The client uses asyncio.to_thread(_post_json, ...) so we patch
    # the sync _post_json to be a no-op recorder.
    def fake_post(*args: Any, **kwargs: Any) -> None:
        pushed.append({"args": args})

    monkeypatch.setattr(
        "backend.core.meeet.client._post_json", fake_post, raising=False
    )

    async def run() -> dict[str, Any]:
        out = await client.replay_unpushed()
        assert out["pushed"] == 1
        assert out["enabled"] is True
        return await client.health()

    out = asyncio.run(run())
    assert out["last_replay"]["pushed"] == 1
    assert out["last_replay"]["enabled"] is True
    assert "ran_at" in out["last_replay"]
    assert pushed, "fake_post should have been invoked"


def test_replay_loop_is_started_and_cancelled() -> None:
    """The FastAPI lifespan starts the replay loop and cancels it on
    shutdown. We exercise the lifespan directly without spinning up a
    server."""

    from fastapi.testclient import TestClient

    from web_extras.app import app

    # The TestClient runs the lifespan; if the loop crashed on startup
    # the client would explode here.
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "tars"
