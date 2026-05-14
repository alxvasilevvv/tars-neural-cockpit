"""Server-Sent Events awareness stream.

Endpoint: ``GET /api/awareness/stream`` — emits a sequence of JSON
events that the cockpit can subscribe to for a live ticker. Designed
to be cheap and dependency-free: a single asyncio loop pushing
``data: <json>\\n\\n`` frames with a slight jitter.

Event kinds:
- ``hello``         — first frame, identifies stream + meeet trace_id
- ``system.pulse``  — synthetic CPU/RAM pulses (deterministic curve)
- ``domain.heartbeat`` — round-robin tick across registered domain packs
- ``bye``           — final frame on graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from typing import Any, AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import all_packs
from backend.core.meeet import current_trace, new_trace_id, trace_scope

router = APIRouter(prefix="/api/awareness", tags=["awareness"])

PULSE_INTERVAL_S = float(os.getenv("AWARENESS_PULSE_S", "1.2"))
DEFAULT_TICK_LIMIT = int(os.getenv("AWARENESS_TICK_LIMIT", "240"))
KEEPALIVE_S = 15.0


def _frame(kind: str, payload: dict[str, Any]) -> str:
    body = {"kind": kind, "ts": round(time.time(), 3), **payload}
    return f"data: {json.dumps(body, separators=(',', ':'))}\n\n"


async def _produce(limit: int) -> AsyncIterator[str]:
    trace_id = current_trace() or new_trace_id()
    domain_slugs = [p.manifest.slug for p in all_packs()]
    started = time.time()

    yield _frame(
        "hello",
        {
            "service": "tars",
            "trace_id": trace_id,
            "version": "10.0.0-rc.1",
            "domains": domain_slugs,
            "interval_s": PULSE_INTERVAL_S,
        },
    )

    rng = random.Random(int(started))
    for tick in range(limit):
        t = time.time() - started
        cpu = round(0.18 + 0.16 * (math.sin(t / 4.7) ** 2) + rng.uniform(-0.04, 0.04), 4)
        ram = round(0.32 + 0.08 * math.sin(t / 9.1) + rng.uniform(-0.02, 0.02), 4)
        yield _frame(
            "system.pulse",
            {
                "tick": tick,
                "cpu": max(0.0, min(cpu, 1.0)),
                "ram": max(0.0, min(ram, 1.0)),
                "uptime_s": round(t, 2),
            },
        )

        if domain_slugs:
            slug = domain_slugs[tick % len(domain_slugs)]
            yield _frame(
                "domain.heartbeat",
                {
                    "tick": tick,
                    "slug": slug,
                    "armed": True,
                    "queue_depth": rng.randint(0, 3),
                },
            )

        await asyncio.sleep(PULSE_INTERVAL_S)

    yield _frame("bye", {"reason": "tick_limit_reached", "ticks": limit})


@router.get("/stream")
async def stream() -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        with trace_scope():
            try:
                async for frame in _produce(limit=DEFAULT_TICK_LIMIT):
                    yield frame
            except asyncio.CancelledError:
                yield _frame("bye", {"reason": "client_disconnect"})
                raise

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no",
            "connection": "keep-alive",
        },
    )
