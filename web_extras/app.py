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


def _saved_search_poll_interval_s() -> float:
    """How often the saved-search alert loop ticks.

    Default ``0`` (off). Operators flip on
    ``TARS_SAVED_SEARCH_POLL_INTERVAL_S=120`` (or whatever cadence
    they want) once they've decided which saved searches should be
    passive watchers. The on-demand path
    (``POST /api/search/saved/{id}/poll`` /
    ``POST /api/search/saved/poll-all``) covers manual triggers.
    """

    raw = os.getenv("TARS_SAVED_SEARCH_POLL_INTERVAL_S")
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def _saved_search_poll_top_k() -> int:
    raw = os.getenv("TARS_SAVED_SEARCH_POLL_TOP_K")
    if raw is None:
        return 25
    try:
        return max(1, min(int(raw), 100))
    except ValueError:
        return 25


def _saved_search_poll_limit() -> int:
    raw = os.getenv("TARS_SAVED_SEARCH_POLL_LIMIT")
    if raw is None:
        return 100
    try:
        return max(1, min(int(raw), 500))
    except ValueError:
        return 100


async def _saved_search_poll_loop() -> None:
    """Periodic ``poll_all_saved_searches`` so saved-search alerts
    fire without manual cockpit triggers.

    Same safety contract as the other lifespan loops:

    - Disabled when ``TARS_SAVED_SEARCH_POLL_INTERVAL_S=0`` (default
      off — operators opt in once they trust the cadence + meeet
      bridge).
    - Disabled when the chat store is disabled.
    - Never propagates exceptions; the alerts module already
      isolates per-search failures, so the loop just logs +
      continues.
    """

    interval = _saved_search_poll_interval_s()
    if interval <= 0:
        return
    from backend.core.chat.store import get_chat_store
    from backend.core.search.alerts import poll_all_saved_searches

    chat = get_chat_store()
    if not chat.enabled:
        return
    top_k = _saved_search_poll_top_k()
    limit = _saved_search_poll_limit()
    log.info(
        "saved-search poll loop active: interval_s=%.1f top_k=%s limit=%s",
        interval, top_k, limit,
    )
    while True:
        try:
            await asyncio.sleep(interval)
            out = await poll_all_saved_searches(
                chat=chat, top_k=top_k, limit=limit
            )
            if out.get("ok") and out.get("alerted"):
                log.info(
                    "saved-search poll: polled=%s alerted=%s",
                    out.get("polled"),
                    out.get("alerted"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("saved-search poll loop tick failed: %s", exc)


def _fts_verify_on_boot() -> bool:
    """Opt-in via ``TARS_FTS_VERIFY_ON_BOOT=1``.

    Default off — running on every cold-start would scan large
    chat / events DBs unnecessarily. Ops that restore from backup or
    bump the FTS schema should flip this on for one boot, then turn
    it off again (or hit
    ``POST /api/search/fts-repair`` instead).
    """

    raw = (os.getenv("TARS_FTS_VERIFY_ON_BOOT") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def _verify_fts_on_boot() -> None:
    """Best-effort drift-check + auto-rebuild for the chat + events
    FTS indexes. Never raises."""

    if not _fts_verify_on_boot():
        return
    try:
        from backend.core.chat.store import get_chat_store
        from backend.core.search.fts import (
            verify_and_repair_chat_fts,
            verify_and_repair_events_fts,
        )

        chat_out = await asyncio.to_thread(
            verify_and_repair_chat_fts,
            chat=get_chat_store(),
            force=False,
        )
        if chat_out.get("rebuilt"):
            log.info(
                "fts boot-repair: chat rebuilt %s",
                chat_out.get("rebuilt"),
            )
        store = get_meeet_store()
        if store and getattr(store, "enabled", False) and store.db_path:
            events_out = await asyncio.to_thread(
                verify_and_repair_events_fts,
                store.db_path,
                force=False,
            )
            if events_out.get("rebuilt"):
                log.info(
                    "fts boot-repair: events rebuilt %s",
                    events_out.get("rebuilt"),
                )
    except Exception as exc:  # never crash the host
        log.warning("fts boot-repair failed: %s", exc)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    from backend.core.agents.autopilot import autopilot_loop

    await _verify_fts_on_boot()

    replay = asyncio.create_task(_replay_loop(), name="meeet-replay-loop")
    autopilot = asyncio.create_task(autopilot_loop(), name="agents-autopilot-loop")
    trace_summary = asyncio.create_task(
        _trace_summary_loop(), name="meeet-trace-summary-loop"
    )
    message_embed = asyncio.create_task(
        _message_embed_loop(), name="chat-message-embed-loop"
    )
    saved_search_poll = asyncio.create_task(
        _saved_search_poll_loop(), name="search-saved-poll-loop"
    )
    tasks = (
        replay, autopilot, trace_summary, message_embed, saved_search_poll
    )
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
