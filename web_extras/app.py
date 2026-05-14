"""FastAPI entry for the TARS backend.

Tiny on purpose: mounts domain packs, chat, memory, policy, meeet, and related
routers. No static SPA is served here — clients are CLI, desktop, or custom HTTP
consumers.

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
from web_extras.routers import planner as planner_router
from web_extras.routers import playbooks as playbooks_router
from web_extras.routers import pairing as pairing_router
from web_extras.routers import policy as policy_router
from web_extras.routers import product as product_router
from web_extras.routers import qa as qa_router
from web_extras.routers import recovery as recovery_router
from web_extras.routers import memory as memory_router
from web_extras.routers import search as search_router
from web_extras.routers import usage as usage_router
from web_extras.routers import oauth_consent as oauth_consent_router
from web_extras.routers import vault as vault_router
from web_extras.routers import speech as speech_router
from web_extras.routers import voice as voice_router
from web_extras.routers import wallet as wallet_router
from web_extras.routers import webhooks as webhooks_router
from web_extras.routers import github as github_router
from web_extras.routers import connectors as connectors_router
from web_extras.routers import clone as clone_router
from web_extras.routers import cohort as cohort_router
from web_extras.routers import doctor as doctor_router
from web_extras.routers import org as org_router
from web_extras.routers import outreach as outreach_router
from web_extras.routers import receipts as receipts_router
from web_extras.routers import audit as audit_router_w255  # W255 -- receipt-anchored audit explorer
from web_extras.routers import scheduler as scheduler_router
# Wave 102 — /api/files document & file management surface.
from web_extras.routers import files as files_router
# Wave 103 — /api/reports report export module (PDF/PPTX/XLSX).
from web_extras.routers import reports as reports_router
# Wave 104 — /api/compliance audit-grade export bundle.
from web_extras.routers import compliance_export as compliance_export_router
# Wave 106 — /api/marketplace community registry + browse + install.
from web_extras.routers import marketplace as marketplace_router
# Wave 107 — /api/bundles per-org-type vertical bundle installer.
from web_extras.routers import bundles as bundles_router
# Wave 108 — /api/perf operational health + latency aggregator.
from web_extras.routers import perf as perf_router
# Wave 110 — /api/workspaces multi-tenant Workspaces MVP (additive).
# Schema-only foundation; v9.3 wires data fencing on existing stores.
from web_extras.routers import workspaces as workspaces_router
# Wave 203 — /api/vision (capture+analyze + OCR) and /api/auth/meeet (1-click).
from web_extras.routers import vision as vision_router
from web_extras.routers import auth_meeet as auth_meeet_router
# Wave 204 — /api/public/proof/* unauthenticated Merkle verifier
from web_extras.routers import public_proof as public_proof_router
# Wave 206 — /api/briefing/today daily-briefing snapshot
from web_extras.routers import briefing as briefing_router
# Wave 209 — /api/digest weekly digest run+latest
from web_extras.routers import digest as digest_router
# Wave 217 — /api/a11y accessibility helpers (OCR-to-speech)
from web_extras.routers import accessibility as a11y_router
# W220 — /api/voice/command dispatcher for the full-screen voice cockpit
from web_extras.routers import voice_command as voice_command_router
# W239 — /api/rules: operator-defined rules folded into the system prompt
from web_extras.routers import rules as rules_router
# W238 — /api/mcp/* desktop panel for external MCP servers
from web_extras.routers import mcp_panel as mcp_panel_router
# W237 — /api/providers models switcher (list / active / set_active)
from web_extras.routers import providers as providers_router
# W240 — /api/mentions @-mention chat context resolver
from web_extras.routers import mentions as mentions_router
# W244 -- /api/privacy/* privacy mode + data plane indicators
from web_extras.routers import privacy as privacy_router
# W243 — /api/notepads notepad templates (Cursor-style reusable AI workflows)
from web_extras.routers import notepads as notepads_router
# W241 — /api/bg_agents background-agent tray + long-running task status
from web_extras.routers import bg_agents as bg_agents_router
# W248 — unified WS real-time event bus
from web_extras.routers import realtime as realtime_router
# W245 — /api/codebase codebase indexer (incremental + language-aware)
from web_extras.routers import codebase as codebase_router
# W246 — /api/palette unified Cmd+K palette aggregator
from web_extras.routers import palette as palette_router
# W253 — /api/composer voice-driven Composer (multi-file edits with diff preview)
from web_extras.routers import composer as composer_router
# W257 — /api/gdpr/* GDPR data-subject access (export/delete/cancel) for BUSINESS tier
from web_extras.routers import gdpr as gdpr_router

START_TS = time.time()
log = logging.getLogger("tars.app")


def _cors_allow_origins() -> list[str]:
    """Production marketing origin + local desktop static shell + optional extras.

    Comma-separated override: ``TARS_CORS_ORIGINS`` (merged, not replaced).
    """

    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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


def _policy_expire_interval_s() -> float:
    """How often the policy gate sweeps stale ``pending`` confirmations.

    Default ``0`` (off) so distros that don't use the policy gate
    don't pay the SQLite hit. Operators enable with
    ``TARS_POLICY_EXPIRE_INTERVAL_S=60`` (or whatever cadence) once
    they have actions queued in confirm mode. The HTTP surface
    (``POST /api/policy/expire``) covers the manual / admin path.
    """

    raw = os.getenv("TARS_POLICY_EXPIRE_INTERVAL_S")
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


async def _policy_expire_loop() -> None:
    """Periodic ``PolicyStore.expire_stale`` so abandoned confirmations
    can't pile up in the cockpit's pending inbox.

    Same safety contract as the other lifespan loops:

    - Disabled when ``TARS_POLICY_EXPIRE_INTERVAL_S=0`` (default off).
    - Logs INFO when a tick expires rows; otherwise silent so a healthy
      machine doesn't fill the journal.
    - Each newly-expired token emits a ``policy.expired`` meeet event
      (token + slug + action + expired_at + originating trace_id)
      so the cockpit gold-pill audit lane / pairing-audit feed sees
      the auto-reap, not just the manual ``POST /api/policy/expire``
      path.
    - Catches everything (excluding ``CancelledError``) so a
      transient SQLite blip cannot crash the host.
    """

    interval = _policy_expire_interval_s()
    if interval <= 0:
        return
    from backend.core.policy import get_policy_store

    log.info("policy expire loop active: interval_s=%.1f", interval)
    client = get_client()
    store = get_policy_store()
    while True:
        try:
            await asyncio.sleep(interval)
            expired = await store.expire_stale()
            if not expired:
                continue
            log.info("policy expire tick: expired=%s", len(expired))
            for c in expired:
                payload: dict[str, object] = {
                    "token": c.token,
                    "slug": c.slug,
                    "action": c.action_id,
                    "expired_at": c.resolved_at,
                    "trace_id": c.trace_id,
                }
                if c.thread_id:
                    payload["thread_id"] = c.thread_id
                await client.emit("policy.expired", payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("policy expire loop tick failed: %s", exc)


def _memory_purge_interval_s() -> float:
    """How often the per-pack memory store sweeps expired rows.

    Default ``0`` (off) so distros that don't use the memory layer
    don't pay the SQLite hit. Operators flip on
    ``TARS_MEMORY_PURGE_INTERVAL_S=600`` (or whatever cadence) once
    they have TTL'd entries in the wild. The action layer
    (``pack.memory.purge_expired``) and HTTP surface
    (``POST /api/memory/_purge_expired``) cover the manual path.
    """

    raw = os.getenv("TARS_MEMORY_PURGE_INTERVAL_S")
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


async def _memory_purge_loop() -> None:
    """Periodic global ``MemoryStore.purge_expired`` so TTL'd rows
    don't accumulate without operator intervention.

    Same safety contract as the other lifespan loops:

    - Disabled when ``TARS_MEMORY_PURGE_INTERVAL_S=0`` (default off).
    - Disabled when the memory store is disabled
      (``MEMORY_STORE=disabled`` or no DB path resolved).
    - Logs INFO when a tick deletes rows; otherwise silent so a
      healthy machine doesn't fill the journal.
    - Catches everything (excluding ``CancelledError``) so a
      transient SQLite blip cannot crash the host.
    """

    interval = _memory_purge_interval_s()
    if interval <= 0:
        return
    from backend.core.memory import get_memory_store

    store = get_memory_store()
    if not store.enabled:
        return
    log.info(
        "memory purge loop active: interval_s=%.1f db=%s",
        interval, store.db_path,
    )
    while True:
        try:
            await asyncio.sleep(interval)
            out = await store.purge_expired()
            deleted = int(out.get("deleted", 0)) if out.get("ok") else 0
            if deleted:
                log.info("memory purge tick: deleted=%s", deleted)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("memory purge loop tick failed: %s", exc)


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


def _merkle_anchor_enabled() -> bool:
    """Opt-in via ``TARS_RECEIPT_ANCHOR_ENABLED=1``."""

    raw = (os.getenv("TARS_RECEIPT_ANCHOR_ENABLED") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _merkle_loop_interval_s() -> float:
    """How often the daily-Merkle-root loop ticks. Default 3600s (1h)."""

    raw = os.getenv("TARS_RECEIPT_MERKLE_INTERVAL_S")
    if raw is None:
        return 3600.0
    try:
        return max(60.0, float(raw))
    except ValueError:
        return 3600.0


async def _merkle_root_loop() -> None:
    """Wave 95 — daily Merkle-root computation + optional Solana anchor.

    Every ``TARS_RECEIPT_MERKLE_INTERVAL_S`` seconds (default 1h):

    1. After UTC midnight + 1h, ensure yesterday's Merkle root row
       exists (compute on demand from NDJSON).
    2. If ``TARS_RECEIPT_ANCHOR_ENABLED=1`` and the row hasn't been
       anchored yet, fire :func:`anchor_to_solana`. The anchor
       module silently no-ops when ``SOLANA_KEYPAIR_PATH`` is unset.

    Same safety contract as the other lifespan loops:
    never propagates exceptions, never crashes the host.
    """

    interval = _merkle_loop_interval_s()
    if interval <= 0:
        return
    from datetime import datetime, timedelta, timezone

    from backend.core.receipts import compute_root, get_store
    from backend.core.receipts.anchor import anchor_to_solana

    store = get_store()
    if store is None:
        return
    log.info("receipt merkle-root loop active: interval_s=%.1f", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            now = datetime.now(timezone.utc)
            # Only act when we are at least 1h past UTC midnight, so
            # late-night appends always make it into yesterday's
            # NDJSON file before we hash.
            if now.hour < 1:
                continue
            yesterday_iso = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            row = await store.get_merkle_root(yesterday_iso)
            if row is None:
                receipts = await store.replay_chain_for_day(yesterday_iso)
                hashes = [r.hash for r in receipts]
                root_hex = compute_root(hashes)
                row = await store.upsert_merkle_root(
                    day_iso=yesterday_iso,
                    root_hex=root_hex,
                    leaf_count=len(hashes),
                )
                if hashes:
                    log.info(
                        "receipt merkle-root computed: day=%s leaves=%s root=%s",
                        yesterday_iso, len(hashes), root_hex[:16],
                    )
            if (
                _merkle_anchor_enabled()
                and row is not None
                and not row.anchored_at
                and row.leaf_count > 0
            ):
                out = await anchor_to_solana(
                    yesterday_iso, row.root_hex
                )
                if out.get("anchored"):
                    log.info(
                        "receipt merkle-root anchored: day=%s sig=%s",
                        yesterday_iso, out.get("signature"),
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never crash the host
            log.warning("receipt merkle-root loop tick failed: %s", exc)




# W248 — periodic /health publisher onto the unified WS bus. Pushes
# every 30 s so the cockpit health chip stays accurate without polling.
async def _realtime_health_loop() -> None:
    """Push backend liveness onto the ``health`` topic every 30 s."""

    try:
        from backend.core.realtime import publish_event as _rt_publish
    except Exception:  # pragma: no cover — broker missing
        return
    while True:
        try:
            payload = {
                "ok": True,
                "service": "tars",
                "uptime_s": round(time.time() - START_TS, 3),
                "meeet_ingest": bool(os.getenv("MEEET_INGEST_URL")),
            }
            _rt_publish("health", payload)
        except Exception as exc:  # noqa: BLE001
            log.debug("realtime.health_loop tick failed: %s", exc)
        try:
            await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            return


def _register_realtime_snapshots() -> None:
    """W248 — register snapshot providers so {op:"snapshot"} works
    even on the very first connect (before any push has happened)."""

    try:
        from backend.core.realtime import set_snapshot_provider
    except Exception:  # pragma: no cover
        return

    def _health_snap() -> dict:
        return {
            "ok": True,
            "service": "tars",
            "uptime_s": round(time.time() - START_TS, 3),
            "meeet_ingest": bool(os.getenv("MEEET_INGEST_URL")),
        }

    def _cap_snap() -> dict:
        try:
            from backend.core.metering import cap_status as _cs
            return _cs()
        except Exception:
            return {}

    def _usage_snap() -> dict:
        try:
            from backend.core.metering import current_balance_local, aggregate_today
            return {"today": aggregate_today(), "balance": current_balance_local()}
        except Exception:
            return {}

    def _privacy_snap() -> dict:
        try:
            from backend.core.privacy import snapshot as _snap
            return _snap(limit=50)
        except Exception:
            return {}

    async def _bg_snap() -> dict:
        try:
            from web_extras.routers.bg_agents import get_bg_store
            rows = await get_bg_store().list_tasks(limit=20)
            return {"tasks": rows}
        except Exception:
            return {}

    set_snapshot_provider("health", _health_snap)
    set_snapshot_provider("cap_status", _cap_snap)
    set_snapshot_provider("usage", _usage_snap)
    set_snapshot_provider("privacy.data_plane", _privacy_snap)
    set_snapshot_provider("bg_agents", _bg_snap)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    from backend.core.agents.autopilot import autopilot_loop
    from backend.core.memory.reflection import reflection_loop
    from backend.core.observability.otel import init_otel

    init_otel()  # Wave 73 F6 — no-op unless OTEL_EXPORTER_OTLP_ENDPOINT set

    # W231 — boot-time DB init + minimum seed so every cockpit tab
    # has at least something to render on a fresh install. Never
    # raises (the bootstrap module captures all per-step exceptions
    # and logs them to stderr).
    try:
        from backend.core.storage import init_all_databases

        boot = await init_all_databases()
        log.info(
            "storage bootstrap: ok=%s warn=%s elapsed_ms=%s seeded=%s",
            len(boot.steps_ok),
            len(boot.steps_warn),
            boot.elapsed_ms,
            list(boot.seeded.keys()),
        )
    except Exception as exc:
        log.warning("storage bootstrap failed (continuing): %s", exc)

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
    memory_purge = asyncio.create_task(
        _memory_purge_loop(), name="memory-purge-loop"
    )
    policy_expire = asyncio.create_task(
        _policy_expire_loop(), name="policy-expire-loop"
    )
    reflection = asyncio.create_task(
        reflection_loop(), name="memory-reflection-loop"
    )
    # Wave 90 — webhooks dispatcher; OFF by default, opt-in via
    # ``TARS_WEBHOOKS_ENABLED=1``. The loop self-disables when the
    # flag is unset, so this create_task is a no-cost no-op for the
    # default cockpit configuration.
    from backend.core.webhooks.dispatcher_loop import webhooks_dispatcher_loop

    webhooks_loop = asyncio.create_task(
        webhooks_dispatcher_loop(), name="webhooks-dispatcher-loop"
    )
    # Wave 95 — daily Merkle-root scheduler. Loop self-disables when
    # ``TARS_RECEIPT_STORE=disabled``; Solana anchoring inside is
    # gated by ``TARS_RECEIPT_ANCHOR_ENABLED=1`` AND
    # ``SOLANA_KEYPAIR_PATH`` being set.
    merkle_loop = asyncio.create_task(
        _merkle_root_loop(), name="receipts-merkle-root-loop"
    )
    # Wave 97 — playbook scheduler engine. Opt-in via
    # ``TARS_SCHEDULER_ENABLED=1``; the loop self-disables when the
    # flag is unset, so this create_task is a no-cost no-op for the
    # default cockpit configuration. On boot the scheduler also runs
    # ``recover_state`` so post-restart ``next_run_at`` is fresh and
    # no scheduled fires get dropped.
    from backend.core.scheduler import scheduler_loop as _scheduler_loop

    scheduler_task = asyncio.create_task(
        _scheduler_loop(), name="scheduler-tick-loop"
    )
    # W248 — unified WS bus: register snapshot providers + start the
    # 30 s health publisher loop. Both are dependency-free; tear-down
    # rides on the `tasks` cancel sweep below.
    _register_realtime_snapshots()
    realtime_health = asyncio.create_task(
        _realtime_health_loop(), name="realtime-health-loop"
    )
    tasks = (
        realtime_health,
        replay,
        autopilot,
        trace_summary,
        message_embed,
        saved_search_poll,
        memory_purge,
        policy_expire,
        reflection,
        webhooks_loop,
        merkle_loop,
        scheduler_task,
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
    version="9.3.0-beta.1",
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

# Bug #4 fix from docs/SYSTEM_AUDIT_2026-05-02.md — per-IP token-
# bucket throttle on the four expensive cloud-touching endpoints
# (chat / planner / voice / council). Returns HTTP 429 +
# Retry-After before the entitlements gate decides on cap_hit.
from web_extras.middleware import install_expensive_routes_rate_limit  # noqa: E402

install_expensive_routes_rate_limit(app)

app.include_router(product_router.legacy_redirect_router)
app.include_router(domains_router.router)
app.include_router(awareness_router.router)
app.include_router(meeet_router.router)
app.include_router(council_router.router)
app.include_router(policy_router.router)
app.include_router(planner_router.router)
app.include_router(playbooks_router.router)
app.include_router(vault_router.router)
app.include_router(oauth_consent_router.router)
app.include_router(usage_router.router)
app.include_router(chat_router.router)
app.include_router(voice_router.router)
app.include_router(speech_router.router)
app.include_router(search_router.router)
app.include_router(search_router.timeline_router)
app.include_router(memory_router.router)
app.include_router(product_router.router)
app.include_router(product_router.updates_router)
app.include_router(pairing_router.router)
app.include_router(recovery_router.router)
app.include_router(agents_router.router)
app.include_router(wallet_router.router)
app.include_router(webhooks_router.router)
app.include_router(github_router.router)
app.include_router(connectors_router.router)
app.include_router(clone_router.router)
app.include_router(cohort_router.router)
app.include_router(doctor_router.router)
app.include_router(org_router.router)
app.include_router(outreach_router.router)
app.include_router(receipts_router.router)
app.include_router(receipts_router.audit_router)  # Wave 123: /api/audit/list alias
# W255 -- /api/audit/timeline /api/audit/receipt /api/audit/verify
app.include_router(audit_router_w255.router)
# W255 -- /api/receipts/export + /api/receipts/export/{job_id}
app.include_router(audit_router_w255.export_router)
app.include_router(scheduler_router.router)
app.include_router(files_router.router)
app.include_router(reports_router.router)
app.include_router(compliance_export_router.router)
app.include_router(marketplace_router.router)
app.include_router(bundles_router.router)
app.include_router(perf_router.router)
# Wave 110 — Workspaces backend MVP. New router only; existing
# stores stay single-tenant in v9.1.0. Workspaces register, do NOT
# fence data yet — v9.3 wires the cross-store enforcement.
app.include_router(workspaces_router.router)
from web_extras.routers import entitlements as entitlements_router  # noqa: E402
from web_extras.routers import roles as roles_router  # noqa: E402

app.include_router(entitlements_router.router)
app.include_router(roles_router.router)
app.include_router(qa_router.router)

# Wave 149 — Cowork HTTP surface. Wires the W129 backend module
# (backend/core/cowork/) into 10 routes per docs/contracts/COWORK.md.
# Operator can demo Cowork end-to-end via `make backend-tars-up`
# without depending on brother's core-bridge. Brother can copy
# web_extras/routers/cowork.py verbatim into core-bridge — same
# imports, same contract.
from web_extras.routers import cowork as cowork_router  # noqa: E402
app.include_router(cowork_router.router)
# W203 — vision + meeet-auth endpoints for the new TARS.app control center.
app.include_router(vision_router.router)
app.include_router(auth_meeet_router.router)
# W204 — public verifiable-proof endpoints (no auth)
app.include_router(public_proof_router.router)
# W206 — daily briefing snapshot
app.include_router(briefing_router.router)
# W209 — weekly digest
app.include_router(digest_router.router)
# W217 — accessibility helpers
app.include_router(a11y_router.router)
# W220 — voice-command dispatcher for the full-screen cockpit
app.include_router(voice_command_router.router)
# W239 — rules system (operator-defined system-prompt overlays)
app.include_router(rules_router.router)
app.include_router(mcp_panel_router.router)  # W238 — MCP servers panel
# W237 — /api/providers models switcher
app.include_router(providers_router.router)
# W240 — /api/mentions @-mention chat context resolver
app.include_router(mentions_router.router)
# W244 -- /api/privacy/* config + data plane
app.include_router(privacy_router.router)
# W243 — /api/notepads notepad templates (Cursor-style reusable AI workflows)
app.include_router(notepads_router.router)
# W241 — /api/bg_agents background-agent tray + long-running task status
app.include_router(bg_agents_router.router)
app.include_router(palette_router.router)  # W246 — Cmd+K palette v2
# W248 — /api/realtime WS event bus + /api/realtime/topics
app.include_router(realtime_router.router)
# W245 — /api/codebase codebase indexer
app.include_router(codebase_router.router)
# W253 — /api/composer voice-driven Composer
app.include_router(composer_router.router)
# W257 — GDPR endpoints
app.include_router(gdpr_router.router)


async def _health_payload() -> dict[str, object]:
    return {
        "ok": True,
        "service": "tars",
        "uptime_s": round(time.time() - START_TS, 3),
        "trace_id": current_trace(),
        "meeet_ingest": bool(os.getenv("MEEET_INGEST_URL")),
    }


@app.get("/health")
async def health() -> dict[str, object]:
    return await _health_payload()


# W199 — Also expose under /api/ prefix so client code that assumes
# the full namespace lives at /api/* gets a consistent surface.
@app.get("/api/health")
async def api_health() -> dict[str, object]:
    return await _health_payload()


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "tars",
        "see": "/docs",
        "domains": "/api/domains",
    }
