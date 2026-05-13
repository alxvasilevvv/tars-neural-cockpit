# Cowork Backend — Production Health Snapshot

**Date:** 2026-05-14 · **Module:** `backend/core/cowork/` · **Contract:** v1.0 · **Wave:** W129

Post-launch audit of what's live, what's mocked, and what's pending for the TARS Cowork subsystem.

---

## Subsystem state

### 1. Sessions store — `store.py`
**LIVE.** SQLite-backed `CoworkStore` at `~/.tars/cowork.sqlite` (override via `TARS_COWORK_DB_PATH`) implements full async CRUD for `sessions`, `members`, `cursors`, and `handoffs` tables. Uses WAL + `asyncio.to_thread` discipline, with a lazy `get_store()` singleton and `TARS_COWORK_STORE=disabled` kill-switch. Schema auto-creates on first connect; cursor upsert uses `ON CONFLICT (session_id, member_id, path)` for idempotency.

### 2. Presence tracker — `presence.py`
**LIVE.** In-process `PresenceTracker` keyed on `(session_id, member_id) -> PresenceState` with `PRESENCE_TTL_S = 25.0` seconds. Frontend pings every 10s; `who_is_present()` filters stale records lazily, and `gc()` is available for the periodic sweep. Single-tenant only — v9.3 migration to Redis is API-compatible.

### 3. Stream pub/sub — `stream.py`
**LIVE.** Per-session `asyncio.Queue` fan-out registry, max depth 256 (drops oldest on overflow rather than back-pressuring publishers). `subscribe()` is an async generator yielding events with a synthetic `heartbeat` envelope every `HEARTBEAT_INTERVAL_S = 15.0` seconds; envelope shape is type-discriminated with `id`/`type`/`occurred_at`/`data`.

### 4. Handoff atomicity — `handoff.py`
**LIVE.** Single-use tokens via `new_token()` (32-byte URL-safe) with a 15-min default TTL. `accept_handoff()` calls `store.mark_handoff_accepted()` which runs a conditional `UPDATE … WHERE accepted_at IS NULL AND revoked_at IS NULL AND expires_at > ?` — concurrent accepts lose the race deterministically. Successful accept atomically swaps `owner_user_id` and publishes `handoff.accepted`.

### 5. Orchestrator integration — `backend/core/agents/runner.py`
**LIVE.** Imports `emit_agent_frame` defensively (try/except yields a no-op stub on import failure). `run_task()` reads `metadata['cowork_session_id']` and fires `task.started` / `task.completed` / `task.failed` frames on the cowork stream alongside the existing meeet emit. Hot path swallows exceptions — a Cowork outage cannot block agent execution.

### 6. Frontend — `experiments/neural-showcase-v3/src/pages/Cowork.tsx`
**NONE in primary SPA.** W129 UI was deleted in the e5f1911 SPA cleanup. The brother handoff doc at `docs/handoff/COWORK_WIRING_FOR_CURSOR.md` is the v9.1.1 contract for the FastAPI core-bridge wiring; client expects routes documented in `docs/contracts/COWORK.md`.

### 7. Test coverage
**38/38 PASS** (`python3 -m unittest tests.test_cowork_store tests.test_cowork_presence tests.test_cowork_edge_cases` — 1.027s). Covers store CRUD, handoff atomicity (race-loser deterministic), presence TTL, stream fan-out, and edge cases.

---

## What WORKS today (single Python process)

- Full session lifecycle: create / list / get-by-slug / end / status transitions
- Member join with token issuance + lookup, `last_seen_at` touch, removal with cursor cascade
- Cursor upsert + per-path listing under `(session_id, member_id, path)` uniqueness
- Heartbeat presence with 25s TTL window + explicit `leave()` + bulk `gc()`
- Pub/sub fan-out with overflow protection (drop-oldest at depth 256) and 15s SSE heartbeat
- Handoff create → accept (atomic, single-winner) → ownership transfer → broadcast
- Handoff revoke by originator with state guards
- Orchestrator `agent.task.{started,completed,failed}` frames wired into runner, opt-in via metadata
- Module disable switch (`TARS_COWORK_STORE=disabled`) and `emit_agent_frame` exception swallowing keep the host bullet-proof

## What's MOCKED (frontend deleted)

The W129 React surface (`/cowork`, `/cowork/:slug`, `/cowork/handoff/:token`) was stripped in e5f1911. There is no live UI consuming this backend in production. Any FE-side mock fallback referenced in the brother handoff document is moot until UI is rebuilt or the core-bridge serves API consumers directly.

## PENDING for v9.1.1

Per `docs/handoff/COWORK_WIRING_FOR_CURSOR.md`, brother (Cursor session) wires 10 FastAPI routes onto the core-bridge to expose this module over HTTP/SSE:

`POST /api/cowork/sessions` · `GET /api/cowork/sessions` · `GET /api/cowork/sessions/:slug` · `POST /api/cowork/sessions/:id/members` · `GET /api/cowork/sessions/:id/members` · `POST /api/cowork/sessions/:id/heartbeat` · `POST /api/cowork/sessions/:id/cursor` · `POST /api/cowork/sessions/:id/handoff` · `POST /api/cowork/handoff/:token/accept` · `GET /api/cowork/sessions/:id/stream` (SSE).

Routes are pure transport — all logic already lives in `backend/core/cowork/`. Estimated 25-40 min for a competent FastAPI dev.

## PENDING for v9.3

Per `docs/contracts/COWORK.md` § Multi-tenant: workspace fencing. `workspace_id` column already exists on `sessions` but is not enforced. v9.3 will (a) move presence to Redis pub/sub (API-compatible swap), (b) replace stream fan-out with Redis Streams for cross-process delivery, (c) rotate member tokens to per-workspace HMAC instead of plaintext bearer, and (d) gate every read/write by `workspace_id` membership.
