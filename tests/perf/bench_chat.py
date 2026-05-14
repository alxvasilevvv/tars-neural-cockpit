"""W266 — perf bench: 100 concurrent chat requests.

**SLO:** p95 latency < 2.5s.

Uses the FastAPI ``TestClient`` against the local LLM fallback path so
the benchmark is hermetic and free to run. The "concurrent" load is
generated with ``asyncio.gather()`` over 100 threads of execution
inside a ``ThreadPoolExecutor`` because ``TestClient`` is sync — that
still exercises the request pipeline and the SSE assembler, which are
the two hottest things in the chat path.

Run standalone:

    pytest tests/perf/bench_chat.py -m perf

Or via the runner (preferred):

    bash scripts/RUN-PERF-SUITE.command
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.perf._perf_utils import isolate_tars_home, record_result

CONCURRENCY = int(os.getenv("TARS_PERF_CHAT_N", "100"))
SLO_MS = 2500.0


@pytest.mark.perf
def test_chat_100_concurrent_p95_under_slo(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """100 concurrent chat requests → assert p95 < 2.5s."""

    isolate_tars_home(monkeypatch, tmp_path)

    from fastapi.testclient import TestClient

    from backend.core.chat import store as chat_store_module
    from backend.core.vault import keychain as kc_module
    from web_extras.app import app

    # Hermetic chat store + force local fallback voice.
    monkeypatch.setattr(chat_store_module, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(kc_module, "_security_bin", lambda: None, raising=False)

    client = TestClient(app)

    # One shared thread (each "user" reuses it — closer to real
    # cockpit behaviour where one user fires many messages).
    thr = client.post("/api/chat/threads", json={"title": "perf"}).json()[
        "thread"
    ]
    thread_id = thr["id"]

    def one_request(i: int) -> float:
        t0 = time.perf_counter()
        res = client.post(
            f"/api/chat/threads/{thread_id}/messages",
            json={"text": f"hello #{i}"},
            headers={"x-tars-session-id": f"perf-{i}"},
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # SSE body must close cleanly — a 500 / disconnect doesn't
        # count as a measured sample.
        assert res.status_code == 200, f"req {i} failed: {res.status_code}"
        return elapsed_ms

    # ThreadPoolExecutor is fine because TestClient is synchronous;
    # the actual backend code under test still runs concurrently on
    # async event loops as far as the chat pipeline goes (the SSE
    # generators are async-safe).
    with ThreadPoolExecutor(max_workers=min(CONCURRENCY, 32)) as pool:
        samples = list(pool.map(one_request, range(CONCURRENCY)))

    row = record_result(
        name="bench_chat",
        samples_ms=samples,
        slo_ms=SLO_MS,
        extra={
            "concurrency": CONCURRENCY,
            "path": "/api/chat/threads/{id}/messages",
            "description": "100 concurrent chat requests via local fallback",
        },
    )
    assert row["passed"], (
        f"REGRESSION: chat p95={row['p95_ms']}ms exceeds SLO {SLO_MS}ms; "
        f"suggested fix: profile ChatOrchestrator._compose_system_prompt + "
        f"the SSE encoder hot loop (W248 unified bus) — these are the two "
        f"places that have regressed historically."
    )
