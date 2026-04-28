"""Tests for the SSE awareness stream.

We exercise the producer directly (no FastAPI plumbing required) so the
test stays fast and deterministic. We force a small tick limit and a
near-zero pulse interval via env vars before importing the module.
"""

from __future__ import annotations

import asyncio
import json
import os
from importlib import reload

import pytest

os.environ["AWARENESS_PULSE_S"] = "0"
os.environ["AWARENESS_TICK_LIMIT"] = "3"

from web_extras.routers import awareness as awareness_router  # noqa: E402

reload(awareness_router)


def _parse_frame(frame: str) -> dict:
    assert frame.startswith("data: "), frame
    return json.loads(frame[len("data: ") :].strip())


def test_producer_emits_hello_pulses_and_bye() -> None:
    async def collect() -> list[dict]:
        out: list[dict] = []
        async for f in awareness_router._produce(limit=3):
            out.append(_parse_frame(f))
        return out

    frames = asyncio.run(collect())
    assert frames[0]["kind"] == "hello"
    assert "trace_id" in frames[0]
    pulses = [f for f in frames if f["kind"] == "system.pulse"]
    heartbeats = [f for f in frames if f["kind"] == "domain.heartbeat"]
    assert len(pulses) == 3
    assert len(heartbeats) == 3
    assert frames[-1]["kind"] == "bye"


def test_pulses_are_bounded_in_unit_interval() -> None:
    async def collect() -> list[dict]:
        out: list[dict] = []
        async for f in awareness_router._produce(limit=2):
            out.append(_parse_frame(f))
        return out

    pulses = [f for f in asyncio.run(collect()) if f["kind"] == "system.pulse"]
    for p in pulses:
        assert 0.0 <= p["cpu"] <= 1.0
        assert 0.0 <= p["ram"] <= 1.0
