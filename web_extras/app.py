"""FastAPI entry for the TARS cockpit backend.

Tiny on purpose: just mounts the domain packs router and a couple of
health/identity endpoints. The full cockpit (council, awareness, mac
actions, voice) attaches its routers here once it lands.

Lifespan:

- Background replay loop (Phase I): ticks every
  ``MEEET_REPLAY_INTERVAL_S`` seconds (default 60, ``0`` disables) and
  flushes any pending events from the durable store to the ingest URL.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.meeet import current_trace, get_client
from web_extras.routers import awareness as awareness_router
from web_extras.routers import council as council_router
from web_extras.routers import domains as domains_router
from web_extras.routers import meeet as meeet_router
from web_extras.routers import playbooks as playbooks_router
from web_extras.routers import policy as policy_router
from web_extras.routers import vault as vault_router

START_TS = time.time()
log = logging.getLogger("tars.app")


def _replay_interval_s() -> float:
    raw = os.getenv("MEEET_REPLAY_INTERVAL_S")
    if raw is None:
        return 60.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 60.0


async def _replay_loop() -> None:
    """Best-effort periodic replay.

    The loop never propagates exceptions — it logs and keeps ticking.
    Disabled when the interval is 0 or the ingest URL is unset.
    """

    interval = _replay_interval_s()
    if interval <= 0:
        return
    client = get_client()
    if not client.config.enabled or not client.config.ingest_url:
        return
    log.info("meeet replay loop active: interval_s=%.1f", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            out = await client.replay_unpushed()
            if out.get("pushed") or out.get("failed"):
                log.info(
                    "meeet replay: pushed=%s failed=%s remaining=%s",
                    out.get("pushed"), out.get("failed"), out.get("remaining"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("meeet replay loop tick failed: %s", exc)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_replay_loop(), name="meeet-replay-loop")
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


app = FastAPI(
    title="TARS",
    description="Local-first neural cockpit released under meeet.world.",
    version="0.9.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*", "x-meeet-trace-id", "x-tars-policy-mode"],
)

app.include_router(domains_router.router)
app.include_router(awareness_router.router)
app.include_router(meeet_router.router)
app.include_router(council_router.router)
app.include_router(policy_router.router)
app.include_router(playbooks_router.router)
app.include_router(vault_router.router)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "tars",
        "uptime_s": round(time.time() - START_TS, 3),
        "trace_id": current_trace(),
        "meeet_ingest": bool(os.getenv("MEEET_INGEST_URL")),
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "tars",
        "see": "/docs",
        "domains": "/api/domains",
    }
