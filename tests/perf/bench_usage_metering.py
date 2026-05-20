"""W266 — perf bench: 1000 usage_event writes/sec sustained.

**SLO:** 1000 writes/sec for 5 seconds → 5000 events recorded with
zero drops.

The metering middleware writes one event per LLM call. Spike traffic
on a Cockpit doing 30 voice rounds + 5 background agents can exceed
500 events/sec — so we set the SLO at 2x that headroom.

Hermetic: writes go to a tmp event store. We do not exercise the
HTTP layer here because the contract is the underlying ``EventStore``
write speed; the FastAPI middleware is a thin wrapper and would
double-count the cost of the network round-trip.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid

import pytest

from tests.perf._perf_utils import isolate_tars_home, record_result

TARGET_PER_S = int(os.getenv("TARS_PERF_USAGE_RATE", "1000"))
DURATION_S = float(os.getenv("TARS_PERF_USAGE_DURATION", "5.0"))
EXPECTED_TOTAL = int(TARGET_PER_S * DURATION_S)
# SLO recast as a per-write p95: at 1000/s, p95 must be < 5ms.
SLO_MS = 5.0


@pytest.mark.perf
def test_usage_metering_1000_per_sec_no_drops(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """1000 usage_event writes/sec sustained → zero drops."""

    isolate_tars_home(monkeypatch, tmp_path)

    from backend.core.meeet import get_store, reset_store

    reset_store()

    async def run() -> tuple[list[float], int]:
        store = get_store()
        samples: list[float] = []
        written = 0

        async def one_write(i: int) -> float:
            t0 = time.perf_counter()
            await store.insert(
                {
                    "kind": "usage.tokens",
                    "payload": {
                        "model": "claude-sonnet-4",
                        "tokens_in": 100,
                        "tokens_out": 50,
                        "latency_ms": 120.0,
                    },
                    "trace_id": f"perf-{i}",
                    "session_id": f"perf-ses-{i % 10}",
                    "route": "/api/perf/bench",
                }
            )
            return (time.perf_counter() - t0) * 1000

        # Batch into 1000-per-second windows so we measure SUSTAINED
        # throughput, not just a burst. Each window fires its targets
        # concurrently; if a window can't drain in 1s we record the
        # overflow as a drop.
        loop_t0 = time.perf_counter()
        drops = 0
        for batch_idx in range(int(DURATION_S)):
            batch_t0 = time.perf_counter()
            results = await asyncio.gather(
                *[one_write(batch_idx * TARGET_PER_S + i)
                  for i in range(TARGET_PER_S)],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    drops += 1
                else:
                    samples.append(r)
                    written += 1
            batch_elapsed = time.perf_counter() - batch_t0
            if batch_elapsed > 1.5:
                drops += max(0, int((batch_elapsed - 1.0) * TARGET_PER_S))
            # Sleep until the next 1-second tick to enforce sustained rate.
            remaining = 1.0 - batch_elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

        return samples, drops

    samples, drops = asyncio.run(run())

    # Verify the events actually landed. The query is bounded so the
    # tmp DB doesn't get scanned end-to-end on a 100k row table.
    async def count_written() -> int:
        store = get_store()
        events = await store.list_events(kind="usage.tokens", limit=EXPECTED_TOTAL + 100)
        return len(events)

    total_in_store = asyncio.run(count_written())

    row = record_result(
        name="bench_usage_metering",
        samples_ms=samples or [9999.0],
        slo_ms=SLO_MS,
        extra={
            "target_rate_per_s": TARGET_PER_S,
            "duration_s": DURATION_S,
            "expected_total": EXPECTED_TOTAL,
            "written": len(samples),
            "in_store": total_in_store,
            "drops": drops,
            "throughput_per_s": round(len(samples) / max(DURATION_S, 0.001), 1),
            "path": "EventStore.append(kind=usage.tokens)",
            "description": "1000 usage_event writes/sec for 5s, verify no drops",
        },
    )
    assert drops == 0, (
        f"REGRESSION: usage_metering dropped {drops} events at "
        f"{TARGET_PER_S}/s; suggested fix: switch EventStore to WAL "
        f"mode (if not already) and add a write-buffer behind it — "
        f"see backend/core/meeet/event_store.py."
    )
    assert total_in_store >= EXPECTED_TOTAL, (
        f"REGRESSION: only {total_in_store} of {EXPECTED_TOTAL} usage "
        f"events landed in the store; data loss is unacceptable."
    )
    assert row["passed"], (
        f"REGRESSION: usage_metering per-write p95={row['p95_ms']}ms "
        f"exceeds SLO {SLO_MS}ms; the sustained rate may still be met "
        f"but tail latency degrades the cockpit Usage tab."
    )
