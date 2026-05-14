"""W266 — perf bench: 50 concurrent ``POST /api/voice/command``.

**SLO:** p95 latency < 800ms.

The cockpit's voice cockpit (W220) fires ``/api/voice/command`` every
time the user finishes speaking. The dispatcher matches regex intents
first (doctor / agents / today) and only falls through to an LLM
when nothing matched — the SLO targets the regex-hit path, which is
what cockpit users hit 90%+ of the time.

To keep the benchmark hermetic the LLM fallback is monkey-patched to
a fast stub, matching the pattern in ``tests/test_voice_command_router.py``.
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import pytest

from tests.perf._perf_utils import isolate_tars_home, record_result

CONCURRENCY = int(os.getenv("TARS_PERF_VOICE_N", "50"))
SLO_MS = 800.0


@pytest.mark.perf
def test_voice_command_50_concurrent_p95_under_slo(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """50 concurrent voice commands → assert p95 < 800ms."""

    isolate_tars_home(monkeypatch, tmp_path)

    # Mix of regex-matched and LLM-fallback transcripts so we don't
    # only measure the fast path. 60% regex, 40% fallback (stubbed).
    transcripts = [
        ("doctor status", "regex"),
        ("agents list", "regex"),
        ("today", "regex"),
        ("doctor please", "regex"),
        ("what is the airspeed velocity of an unladen swallow", "llm"),
    ]

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from web_extras.routers import voice_command as vc_mod

    # Stub the LLM fallback to a fixed 1ms response so we benchmark
    # the dispatcher itself, not the upstream provider.
    async def _stub(_text: str, _lang: str | None = None) -> str:
        return "stubbed response"

    monkeypatch.setattr(
        vc_mod, "_llm_fallback", AsyncMock(side_effect=_stub), raising=False
    )

    app = FastAPI()
    app.include_router(vc_mod.router)
    client = TestClient(app)

    def one_request(i: int) -> float:
        transcript, _kind = transcripts[i % len(transcripts)]
        t0 = time.perf_counter()
        res = client.post(
            "/api/voice/command",
            json={"transcript": transcript},
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert res.status_code == 200, (
            f"req {i} ({transcript!r}) failed: {res.status_code}"
        )
        return elapsed_ms

    with ThreadPoolExecutor(max_workers=min(CONCURRENCY, 16)) as pool:
        samples = list(pool.map(one_request, range(CONCURRENCY)))

    row = record_result(
        name="bench_voice_command",
        samples_ms=samples,
        slo_ms=SLO_MS,
        extra={
            "concurrency": CONCURRENCY,
            "path": "/api/voice/command",
            "description": "50 concurrent /api/voice/command, mixed regex+LLM-stub",
        },
    )
    assert row["passed"], (
        f"REGRESSION: voice_command p95={row['p95_ms']}ms exceeds SLO "
        f"{SLO_MS}ms; suggested fix: profile the regex pre-pass in "
        f"web_extras/routers/voice_command.py — most cockpit hits "
        f"should resolve in <50ms before the LLM fallback runs."
    )
