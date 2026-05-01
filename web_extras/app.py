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
from backend.core.meeet import (
    current_trace,
    get_client,
    get_trace_summary_store,
)
from web_extras.routers import agents as agents_router
from web_extras.routers import awareness as awareness_router
from web_extras.routers import chat as chat_router
from web_extras.routers import council as council_router
from web_extras.routers import domains as domains_router
from web_extras.routers import meeet as meeet_router
from web_extras.routers import playbooks as playbooks_router
from web_extras.routers import pairing as pairing_router
from web_extras.routers import policy as policy_router
from web_extras.routers import product as product_router
from web_extras.routers import qa as qa_router
from web_extras.routers import recovery as recovery_router
from web_extras.routers import search as search_router
from web_extras.routers import usage as usage_router
from web_extras.routers import vault as vault_router
from web_extras.routers import voice as voice_router
from web_extras.routers import wallet as wallet_router

START_TS = time.time()
log = logging.getLogger("tars.app")


def _cors_allow_origins() -> list[str]:
    """Production marketing origin + local Vite defaults + optional extras.

    Comma-separated override: ``TARS_CORS_ORIGINS`` (merged, not replaced).
    """

    defaults = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://tars.meeet.world",
    ]
    raw = os.getenv("TARS_CORS_ORIGINS", "").strip()
    extras = [x.strip() for x in raw.split(",") if x.strip()]
    merged = [*defaults, *extras]
    return list(dict.fromkeys(merged))


def _replay_interval_s() -> float:
    raw = os.getenv("MEEET_REPLAY_INTERVAL_S")
    if raw is None:
        return 60.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 60.0


def _trace_summary_interval_s() -> float:
    """How often the trace-summary materialised view rebuilds.

    Default 300 s (5 min). ``0`` disables the loop entirely; the
    `POST /api/meeet/traces/refresh` endpoint still works for
    on-demand rebuilds.
    """

    raw = os.getenv("TARS_TRACE_SUMMARY_INTERVAL_S")
    if raw is None:
        return 300.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 300.0


def _message_embed_interval_s() -> float:
    """How often the message-embed background loop ticks.

    Default ``0`` (off) — the loop is opt-in until operators
    confirm the embedder cost / latency profile they want to run
    with. The `POST /api/search/embed-messages` endpoint covers the
    on-demand path.
    """

    raw = os.getenv("TARS_MESSAGE_EMBED_INTERVAL_S")
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def _message_embed_batch_limit() -> int:
    raw = os.getenv("TARS_MESSAGE_EMBED_LIMIT")
    if raw is None:
        return 100
    try:
        return max(1, min(int(raw), 1000))
    except ValueError:
        return 100


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


async def _trace_summary_loop() -> None:
    """Periodic rebuild of the meeet ``trace_summary`` materialised view.

    Same shape as the replay loop: never propagates, never crashes the
    host. Disabled when ``TARS_TRACE_SUMMARY_INTERVAL_S=0`` or when the
    durable store is disabled.
    """

    interval = _trace_summary_interval_s()
    if interval <= 0:
        return
    summary_store = get_trace_summary_store()
    if not summary_store.enabled:
        return
    log.info("trace-summary loop active: interval_s=%.1f", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            out = await summary_store.rebuild()
            if out.get("traces") or out.get("scanned_events"):
                log.info(
                    "trace-summary refresh: traces=%s scanned=%s elapsed_ms=%s",
                    out.get("traces"),
                    out.get("scanned_events"),
                    out.get("elapsed_ms"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("trace-summary loop tick failed: %s", exc)


async def _message_embed_loop() -> None:
    """Periodic backfill of message embeddings.

    Walks rows whose ``embedding_blob`` is null and pushes them through
    whatever :class:`Embedder` is reachable so hybrid search has fresh
    vectors. Same safety contract as the other loops:

    - Disabled when ``TARS_MESSAGE_EMBED_INTERVAL_S=0`` (default off
      until operators opt in).
    - Disabled when the chat store is disabled.
    - Never propagates exceptions.
    """

    interval = _message_embed_interval_s()
    if interval <= 0:
        return
    from backend.core.chat.embeddings import embed_pending_messages
    from backend.core.chat.store import get_chat_store

    chat = get_chat_store()
    if not chat.enabled:
        return
    limit = _message_embed_batch_limit()
    log.info(
        "message-embed loop active: interval_s=%.1f limit=%s",
        interval, limit,
    )
    while True:
        try:
            await asyncio.sleep(interval)
            out = await embed_pending_messages(chat=chat, limit=limit)
            if not out.get("ok"):
                # Embedder unavailable / store disabled — log once per
                # tick and keep ticking so the loop self-heals when the
                # upstream comes back.
                log.debug(
                    "message-embed skip: %s", out.get("reason") or "unknown",
                )
                continue
            if out.get("embedded") or out.get("failed"):
                log.info(
                    "message-embed tick: embedded=%s failed=%s remaining=%s",
                    out.get("embedded"),
                    out.get("failed"),
                    out.get("remaining"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("message-embed loop tick failed: %s", exc)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    from backend.core.agents.autopilot import autopilot_loop

    replay = asyncio.create_task(_replay_loop(), name="meeet-replay-loop")
    autopilot = asyncio.create_task(autopilot_loop(), name="agents-autopilot-loop")
    trace_summary = asyncio.create_task(
        _trace_summary_loop(), name="meeet-trace-summary-loop"
    )
    message_embed = asyncio.create_task(
        _message_embed_loop(), name="chat-message-embed-loop"
    )
    tasks = (replay, autopilot, trace_summary, message_embed)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


app = FastAPI(
    title="TARS",
    description="Local-first neural cockpit released under meeet.world.",
    version="0.9.0",
    lifespan=_lifespan,
)

# Phase O1 — unified error envelope. Every error now carries a stable
# `error_code` (taxonomy in web_extras/errors.py) plus the legacy
# FastAPI `detail` field for backward compatibility.
from web_extras import errors as _tars_errors

_tars_errors.install(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "*",
        "x-meeet-trace-id",
        "x-tars-policy-mode",
        "x-tars-session-id",
    ],
)

app.include_router(domains_router.router)
app.include_router(awareness_router.router)
app.include_router(meeet_router.router)
app.include_router(council_router.router)
app.include_router(policy_router.router)
app.include_router(playbooks_router.router)
app.include_router(vault_router.router)
app.include_router(usage_router.router)
app.include_router(chat_router.router)
app.include_router(voice_router.router)
app.include_router(search_router.router)
app.include_router(search_router.timeline_router)
app.include_router(product_router.router)
app.include_router(pairing_router.router)
app.include_router(recovery_router.router)
app.include_router(agents_router.router)
app.include_router(wallet_router.router)
from web_extras.routers import entitlements as entitlements_router  # noqa: E402
from web_extras.routers import roles as roles_router  # noqa: E402

app.include_router(entitlements_router.router)
app.include_router(roles_router.router)
app.include_router(qa_router.router)


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
