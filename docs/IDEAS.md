# TARS — proposals queue

Ideas for the next sprints. Triage by impact × cost and pull into
`AGENT_HANDOFF.md → Pending` once committed to.

> **Phase L roadmap is the canonical source of truth for the
> Claude-tier evolution (conversation, attachments, voice, sync,
> desktop, mobile, marketplace).** See `docs/PHASE_L_ROADMAP.md`.
> Items below remain useful for cross-cutting / smaller proposals;
> the ✅-marked ones already shipped through Phase K.

## Voice (post-L4.1)

- **Per-persona system-prompt overlay.** ✅ shipped
  (2026-05-01) — `Persona.system_prompt_overlay` field +
  built-in tone blocks for Jarvis / Stark / HAL 9000 / GLaDOS /
  TARS (operator opts out). New helpers
  `get_system_prompt_overlay(persona_id)` +
  `compose_system_prompt(*, role_overlay, pack_prompt,
  persona_overlay)` re-exported from `backend.core.voice`.
  Orchestrator stitches role → pack → persona; persona block
  carries a header (`## Voice persona — <name>`) and a safety
  footer reminding the model that voice overlays never override
  pack guardrails. Tests:
  `tests/test_persona_prompt_overlay.py` (23 cases).
  `Persona.to_dict()` now exposes
  `has_system_prompt_overlay`.
- **Per-thread persona pinning.** ✅ shipped (2026-05-01) —
  `threads.voice_persona_id` (additive migration), exposed on
  `Thread.to_dict()` and every API response. Set / clear via
  `POST /api/chat/threads` body or `PATCH /api/chat/threads/{id}`
  with validation against `iter_personas()`.
  `POST /api/voice/speak` accepts an optional `thread_id` field:
  when no explicit `persona` is supplied, the endpoint resolves
  the thread and uses its pinned id as a fallback (response header
  `x-tars-voice-persona-source` is `request` or `thread`). Tests:
  `tests/test_thread_persona_pinning.py` (26 cases). Cockpit
  voice picker UI is the Claude-lane follow-up.
- **Voice cloning kit (offline).** Document the path for an operator
  to capture 3 minutes of audio, mint an ElevenLabs IVC, paste the
  voice id into `TARS_PERSONA_OPERATOR_ELEVENLABS_ID`.
- **Native speech on mobile.** iOS: replace Web Speech in the companion
  with native `Speech` API where applicable. Android: wire
  `SpeechRecognizer` + `RecognitionService` (or ML Kit on-device ASR when
  L4 exposes a relay) for offline / lower-latency dictation.
- ~~**`speech.intents` extraction.**~~ ✅ **Shipped 2026-05-01** —
  `backend/core/speech/intents.py` is a deterministic parser for
  TARS slash + voice commands (`run` / `jump` / `search` /
  `snooze` / `help`). Wake-word stripping
  (`TARS, Hey TARS, Computer, Jarvis`), `dot`-keyword
  normalisation, JSON args, registry-aware playbook arbitration,
  duration parsing. HTTP: `POST /api/speech/intents`. Tests:
  `tests/test_speech_intents.py` (35 cases).

## Attachments + RAG (post-L2)

- **Cross-thread search.** Stand up `POST /api/search` that runs hybrid
  retrieval across every thread the operator can see; return chunks
  with their thread title + permalink. Pair with L8.
- **BM25 via SQLite FTS5.** Replace the hand-rolled tf scorer with
  an FTS5 virtual table over `attachment_chunks(text)` for production-
  grade keyword side; fuse with vectors as before.
- **Image vision routing.** When the chat voice is multimodal-capable
  (Anthropic Claude / OpenAI gpt-4o), pack image bytes into the
  request payload alongside the system prompt. Today images are
  stored but the assistant never sees them.
- ~~**`application/zip` walker.**~~ ✅ **Shipped 2026-05-01** —
  `backend/core/attachments/zip_walker.py` walks zip uploads, ingests
  each safe member as a child attachment linked via
  `meta.parent_attachment_id`, surfaces a `zip_walk` summary on the
  parent. Tunable via `TARS_ZIP_MAX_ENTRIES` / `TARS_ZIP_MAX_ENTRY_BYTES`
  / `TARS_ZIP_MAX_DEPTH`. Tests: `tests/test_zip_walker.py`.
- ~~**Streaming ingestion progress.**~~ ✅ **Shipped 2026-05-01** —
  every ingest call now accepts a
  `progress: ProgressCallback | None` kwarg that fires once per
  phase (`started` / `extracted` / `chunked` / `embedding` /
  `embedded` / `indexed` / `completed` / `dedup_hit` /
  `zip_walked` / `error`). New HTTP route
  `POST /api/chat/threads/{id}/attachments/stream` pipes that
  callback into an SSE `StreamingResponse` (one frame per phase
  + terminal `result` frame with the canonical upload envelope).
  Three new meeet events `attachment.extracting` /
  `attachment.embedding` / `attachment.indexed` for cross-cutting
  observability. Pinned by
  `tests/test_attachments_streaming_upload.py` (10 cases).
  Cockpit "indexing 12 chunks…" pill UI is the Claude-lane
  follow-up.
- **Per-attachment hover preview.** Replace the chip's tooltip with a
  floating card that previews the first chunk + heading list.
  Backend bridge ✅ shipped (2026-05-01) —
  `GET /api/chat/attachments/{id}/chunks/{chunk_id}/neighbours`
  (plus `/neighbors` US alias) returns the chunk plus its
  ord-adjacent neighbours; `before` / `after` clamp `[0, 10]`,
  `full_text=false` for preview-only payloads. See
  `backend/core/attachments/index.py::get_chunk_neighbours` and
  `tests/test_attachments_chunk_neighbours.py` (19 cases).
  Cockpit hover-card UI is the Claude-lane follow-up.
- ~~**Re-embed on demand.**~~ **shipped** (2026-05-01) —
  `reembed_attachment(attachment_id, *, embedder, embedder_name,
  session_id)` in `backend/core/attachments/pipeline.py` re-vectorises
  every chunk under a new embedder while preserving chunk ids and
  ords (so cockpit permalinks survive). `POST
  /api/chat/attachments/{id}/reembed` body
  `{model: "openai" | "hash" | "text-embedding-3-large"}`; defaults to
  `detect_embedder()` when omitted/blank/unknown. Emits
  `attachment.reembedded` + `usage.tokens`. Pinned by
  `tests/test_attachments_reembed.py` (21 cases). Cockpit
  "promote/swap embedder" UI is the Claude-lane follow-up.
- **Citation rendering in markdown.** Today the assistant says
  "as `[chunk_2]` shows…". Render `[chunk_N]` as a clickable pill in
  `<MessageBubble />` that scrolls to the matching source row.
- **Vector quantisation.** When corpora grow beyond ~5k chunks per
  thread, swap raw float32 blobs for int8 quantised vectors; gives
  4× space + ~2× speed for negligible accuracy loss.
- **Thread-scoped graph.** Track edges `attachment.cites_attachment`
  by retrieving each chunk's neighbours during ingestion; surface
  the resulting context graph in a side panel.

## Distribution & desktop (post-L9 scaffold)

- **Releases publishing CLI.** `python -m backend.core.product.publish
  path/to/build/dir --version=1.0.0` — copies artifacts into a staging
  folder, computes SHA256, writes `~/.tars/releases.json` and a
  signed copy at `dist/releases.json` for `meeet.world` SSR.
- ~~**Updater channel manifests.**~~ ✅ **Shipped 2026-05-01** —
  `backend/core/product/updater.py` `build_channel_from_release()`
  bridges `DownloadManifest` → `TauriChannel`; `web_extras/routers/
  product.py` exposes `GET /updates/{target}/{current}.json` (live
  Tauri-shaped manifest, lock-step with `/api/product/downloads`)
  + `GET /api/product/updater/targets`. Tests:
  `tests/test_updater_channel_http.py` (18 cases) including a
  lock-step assertion that channel `version` matches
  `/api/product/downloads/latest`. Publish CLI continues to write
  static files for static hosting.
- **Verify-on-download UI.** When `sha256` is present in the manifest,
  surface a "verified ✓" affordance on `<DownloadStrip />` (read the
  hash from `data-sha256`).
- **Linux .deb / AppImage track.** L9 v1 only ships macOS + Windows;
  add Linux once the signing dance for Apple/Authenticode is stable.
- **Apple notarisation log scrape.** Detect a failed notary submission
  in CI and bail before the `.dmg` is uploaded.

## Pairing & sync (post-L5 v1 — host stack shipped)

✅ Already shipped (2026-04-29): real X25519 + XChaCha20-Poly1305
envelope, BIP-39 24-word recovery seed (with `recovery.shown` audit
event carrying the fingerprint only), pairing endpoints with
`host_public_key` exposed, contract bumped to **1.1.0** additively.

Open ideas for the next layer:

- **Persistent host keyring.** Move the in-process X25519 host
  identity into Keychain / DPAPI / `secret-tool`; gate first-launch
  on the recovery-seed flow so the master key is reproducible from
  the 24 words on a fresh install.
- **Per-thread sync envelope batching.** Batch encrypted blobs into
  one `recipient_keys` block per thread to save bandwidth.
- **Audit log of pairing events.** Render `pair.linked` / `pair.revoked`
  / `recovery.{shown,verified}` on the cockpit timeline as a distinct
  gold-pill lane so an operator can see device topology + recovery
  events alongside chat activity.
- **Pairing relay rate-limit.** `meeet.world/pair/<id>` should expire
  after 120 s and rate-limit per source IP — the host re-mints on
  failure rather than retrying the same `pair_id`.
- **Multi-recipient envelope optimisation.** Today every recipient
  gets its own `crypto_box_seal` of the per-event content key. For
  high-fanout events (large fleets) we could move to a one-pass
  X25519 ECDH with a stored static-pubkey + per-event ephemeral and
  derive each wrapped key via HKDF — keep this on the back burner
  until fleet sizes justify the complexity.
- ~~**Recovery seed verification policy.**~~ **primitives shipped
  2026-05-01** — `backend/core/crypto/seed_challenge.py` lands the
  pure-stdlib state machine: `mint_challenge` picks N (default 3)
  random positions out of 24, `verify_challenge` does case +
  whitespace insensitive 1:1 matching with attempts decrement /
  TTL expiry. `SeedChallengeStore` is a thread-safe in-memory
  dict with expiry-aware reads. New HTTP routes
  `POST /api/recovery/challenge/{start,verify}` and
  `GET /api/recovery/challenge/{id}` emit
  `recovery.challenge.{started,passed,failed,expired,exhausted}`
  events on the existing audit lane. Pinned by
  `tests/test_seed_challenge.py` (30 cases). Follow-up:
  gate the destructive rotate-identity flow on a fresh
  `recovery.challenge.passed` event for the same fingerprint.

## Search & observability (post-L8)

- **Trace materialised view.** ✅ shipped (2026-05-01) — new
  `backend/core/meeet/trace_summary.py` carries a derived
  `trace_summary` SQLite table sharing the meeet WAL DB. Every row
  rolls up `event_count`, sorted `kinds`, `routes`, `primary_route`
  (`edge` / `cloud` / `fallback` / `mixed`), `total_cost_usd`,
  `tokens_in/out` (from `usage.tokens`), `contradictions` (from
  `sampler.decision`), `error_count`, `last_session_id`, and
  `started_at` / `ended_at` / `duration_ms`. New endpoints
  `GET /api/meeet/traces` (filters: limit/since/primary_route/
  session_id), `GET /api/meeet/traces/{trace_id}`, and
  `POST /api/meeet/traces/refresh`. Auto-refresh via the lifespan
  `_trace_summary_loop` every `TARS_TRACE_SUMMARY_INTERVAL_S`
  seconds (default 300, `0` disables). Pinned by
  `tests/test_meeet_trace_summary.py` (12 cases).
- **Cytoscape trace graph.** Toggleable from `<UsageStrip />`,
  rendering each trace as a DAG of events shaded by route
  (`local` / `cloud`) and decorated by cost. Click → drill into the
  underlying meeet payload.
- **Multi-mark BM25 highlights.** The backend already wraps matches
  in `<mark>`; the cockpit currently strips them. Render them as
  gold-on-bg pulses with hover-card chunk previews.
- ~~**Vector + BM25 blend for messages.** Currently messages are
  keyword-only; embedding them on insert (and reusing the L2
  embedder) would surface paraphrased question recall.~~ — Shipped
  2026-05-01: `embedding_model/dim/blob` columns on `messages`,
  `embed_pending_messages` helper + `POST /api/search/embed-messages`,
  `search_messages` now RRF-fuses BM25 with cosine just like chunk
  search. Periodic backfill via `_message_embed_loop` in `_lifespan`
  followed in the same day (PR #43) — opt-in via
  `TARS_MESSAGE_EMBED_INTERVAL_S` (default 0).
- ~~**Scoped operator filters.** Let the ⌘K palette accept
  `pack:business`, `role:tars`, `since:7d`, `mime:pdf`, etc.,
  parsing them out of the query before sanitising.~~ — Shipped
  2026-05-01: `backend/core/search/filters.py` parses
  `role:`, `pack:`, `thread:`, `trace:`, `kind:`, `since:`, `until:`,
  `mime:` (positive + negation `-role:tool`); time bounds accept
  relative (`7d`, `24h`, `45m`, `2w`) and ISO date / timestamp.
  `search` / `search_messages` / `search_traces` honour every token
  via the FTS path (messages get `pack`/`since`/`until` joins,
  traces get `since`/`until` joins). `search_chunks` initially only
  honoured `thread:`; the attachments-DB JOIN follow-up
  (2026-05-01) extended `fts_match_chunks` and `search_chunks` to
  accept `pack:` (JOIN `threads`), `mime:` (literal or `image/*`
  wildcard, JOIN `attachments`), and `since:`/`until:` (POSIX vs.
  `attachments.created_at`). `tests/test_search_filters.py`
  (29 cases) pin the parser + base engine + HTTP behaviour;
  `tests/test_search_chunk_filters.py` (19 cases) pin the chunks-
  specific JOIN behaviour.
- **Attachment hover-card preview.** When a chunk hit is highlighted
  in the palette, surface the surrounding ±1 chunk in a floating
  panel — the data is already on the chunk row.
- ~~**Saved searches.** Persist named searches (`my MRR slips`,
  `risk-flagged trades`) per operator into `~/.tars/chat.sqlite`;
  expose a "pinned" rail above the palette results.~~ — Shipped
  2026-05-01: `saved_searches` table + full CRUD on
  `/api/search/saved` + `POST /api/search/saved/{id}/run` (executes
  via the existing search engine, stamps `last_run_at`). Listing
  orders pinned first, then most-recently-updated.
  `tests/test_saved_searches.py` (16 cases) pin the path. Cockpit
  rail UI is the Claude-lane follow-up. **Alerts shipped same day:**
  `backend/core/search/alerts.py` + `POST /api/search/saved/{id}/poll`
  + `POST /api/search/saved/poll-all` fingerprint each hit
  (`chunk:<id>` / `message:<msg_id>` / `trace:<event_id>`), diff
  against the persisted snapshot, and emit
  `saved_search.new_hits` via the meeet bridge — first poll seeds
  quietly so saving a query doesn't trigger a flood. Snapshot
  capped at 1000 entries. `tests/test_saved_search_alerts.py`
  (18 cases) pin the cycle.
- ~~**Cross-thread Cmd+J jump.** ⌘K is a search; ⌘J should be a
  fuzzy thread / attachment / pack picker (lighter weight, no
  scope chips, just deep-link nav).~~ — Backend shipped 2026-05-01:
  `backend/core/search/jump.py` + `POST /api/search/jump`. Scoring
  is a deliberately cheap `fuzzy_score` (exact / prefix / substring
  / token-prefix / subsequence) and the fan-out covers threads,
  attachments, saved searches, packs, and playbooks. Empty query
  returns recency-first candidates. `tests/test_jump_picker.py`
  (23 cases) pin the scorer + rank + engine + HTTP. Cockpit ⌘J
  palette UI is the Claude-lane follow-up.
- ~~**FTS5 backfill on schema bump.** When the chat DB is migrated
  from a backup, run `backfill_chunk_fts` / `backfill_message_fts`
  on first boot if the index is empty but the source tables aren't.~~
  — Shipped 2026-05-01: `verify_and_repair_chat_fts` +
  `verify_and_repair_events_fts` compare FTS row counts to source
  counts and rebuild on drift (not just on empty FTS, so partial
  drift is also caught). `POST /api/search/fts-repair` for the
  manual path (body `{force?, scopes?}`); opt-in boot-time hook via
  `TARS_FTS_VERIFY_ON_BOOT=1` runs the same drift check on lifespan
  enter, never crashes the host. `tests/test_fts_auto_backfill.py`
  (15 cases) pin the path.

## Cross-cutting (meeet × TARS)

1. **Sampler decision events.** ✅ shipped — every council deliberation
   emits `sampler.decision` with `mode`, `models`, `winner`,
   `winning_stance`, `latency_ms`, `tokens_in/out`, `agreement`,
   `contradictions`. Wired in `traders.summarize_market` and
   `business.daily_brief`. Open work: real LLM voice adapter + a
   `route` flag (see #2).
2. **Edge-vs-cloud routing flag.** ✅ shipped (Phase K1) — every
   `trace_scope` carries a route (`edge` | `cloud` | `fallback` |
   `mixed`); LLM voices bump it to `cloud`, the SQLite store
   indexes by `(session_id, ts)` and `/api/usage` rolls cost up
   `by_route`.
3. **Session graph.** ✅ shipped (Phase K1) — `session_scope`
   tracks `session_id`, propagated via `x-tars-session-id` header,
   stamped on every event payload, filterable in
   `/api/meeet/events?session_id=…` and `/api/usage?session_id=…`.
   ✅ follow-up (2026-05-01) — `async_session_scope` emits explicit
   `session.opened` / `session.closed` events with `topic` +
   `participants` + `started_at` / `ended_at` / `duration_ms`.
   Sync `session_scope` stays silent for backward compat. Pinned by
   `tests/test_session_boundary_events.py` (7 cases).
4. **Cost ledger.** ✅ shipped (Phase K2/K3) — orchestrator emits
   `usage.tokens` per voice with `cost_usd`, aggregates land on
   `sampler.decision`. `backend/core/usage/ledger.py` derives
   rollups from the meeet store; `/api/usage` returns
   per-model / per-route / per-session buckets and the cockpit
   `<UsageStrip />` renders it live. Pricing overridable via
   `TARS_PRICE_OVERRIDES_JSON`.
5. **Policy guardrail events.** ✅ shipped — `policy.{allowed,blocked,
   queued,confirm,cancelled}` fire on every destructive-action attempt;
   confirmations persist in the SQLite store with token + TTL. Open work:
   confirmation UI in the cockpit and a "policy mode" badge per pack.
26. **Local trace UI.** ✅ infra shipped — `/api/meeet/events` returns the
    SQLite trail with filters by `kind` / `trace_id` / `since` /
    `only_unpushed`. Owner: design — render this on a dedicated page
    in v3.

## Domain pack improvements

6. **Real adapters, behind feature flags.**
   - ~~`traders.binance_pull_klines`~~ ✅ **Shipped 2026-05-01** —
     `backend/core/domains/packs/traders/binance.py` `pull_klines`
     handler against `api.binance.com/api/v3/klines` (no key).
     Symbol normalisation (`BTC/USDT` → `BTCUSDT`), interval
     enum, limit `1..1000`, defensive row parsing, derived
     `close_first/last` + `change_pct`. Emits
     `integration.binance.klines` events (request / completed /
     error). Tests: `tests/test_traders_binance_klines.py` (21
     cases).
   - ~~`business.hubspot_pull_pipeline`~~ ✅ **Shipped 2026-05-01**
     (read-only) — `backend/core/domains/packs/business/hubspot.py`
     `pull_pipeline` handler against
     `api.hubapi.com/crm/v3/objects/deals` (vault key
     `HUBSPOT_API_KEY`). Returns normalised deals with
     `stage_label` lookup + derived `active_count` /
     `won_count` / `lost_count` / `pipeline_amount` rollups +
     opaque `next_cursor` from HubSpot's `paging.next.after`.
     Defensive structural errors (`auth_missing` /
     `auth_invalid` / `invalid_limit` / `network_error` /
     `upstream_status` / `upstream_payload_invalid`). Emits
     `integration.hubspot.deals_list` events
     (`request` / `completed` / `error`). Tests:
     `tests/test_business_hubspot_pipeline.py` (35 cases).
   - `mlm.tg_outreach_draft` ✅ shipped (2026-05-01) — pure
     deterministic markdown drafter; six intents × three tones ×
     three languages (en/ru/es); `send_status="draft"` and
     `destructive=False` so the action is preview-only. See
     `backend/core/domains/packs/mlm/tg_outreach.py` and
     `tests/test_mlm_tg_outreach.py` (34 cases).
   - `science.arxiv_search` ✅ shipped — `science.search_literature`
     against the public Atom API.
   - `science.summarize_paper` ✅ shipped — Atom by id, returns
     title/authors/tldr/abstract.
   - `traders.fetch_quote` ✅ shipped — DexScreener public search.
   - `traders.summarize_market` ✅ shipped — basket aggregation +
     bias + dispersion contradictions.
   - `business.kpi_snapshot`, `business.daily_brief` ✅ shipped —
     local JSON-backed.
   - `mlm.downline_snapshot`, `mlm.retention_alert` ✅ shipped —
     local CSV-backed; `score_recruit`, `generate_post` upgraded to
     deterministic heuristics.
   Each remaining adapter must call
   `meeet.emit("integration.<vendor>.<call>", ...)`.
7. **Pack composition.** ✅ shipped (Phase K4) — `CompositePack`
   stitches sub-packs with namespaced ids `<sub_slug>__<id>`.
   `research_lab` (science + business) and `ops_room` (traders +
   mlm) ship by default. Open work: composite-aware playbooks.
8. **Per-pack memory partitions.** ✅ shipped in two slices
   (2026-05-01).
   - **Foundations (PR #56):** `backend/core/memory/` package with
     `MemoryEntry` + `MemoryStore` (SQLite at
     `~/.tars/memory.sqlite`, override `TARS_MEMORY_DB_PATH`).
     `pack_memory` table uniquely keyed on `(pack_slug, key)` so
     domain context cannot bleed. Optional TTL eviction.
     `web_extras/routers/memory.py` exposes pack-scoped + global
     CRUD/stats/purge endpoints.
   - **Action family (this slice):**
     `backend/core/domains/memory_actions.py` injects
     `pack.memory.set / get / list / delete / purge_expired /
     stats` into every pack via
     `DomainPack.all_actions()`. Composite packs flatten sub-pack
     memory under `<sub_slug>__pack.memory.*`. Only `delete` is
     `destructive=True` (policy-gated); reads/list/purge/stats are
     non-destructive. Pinned by `tests/test_memory_actions.py`
     (27 cases) on top of `tests/test_memory_store.py` (28 cases).
   - **Open follow-ups:** periodic `_memory_purge_loop` background
     task in `app.py`, cockpit "facts" view that consumes the new
     actions per pack.
9. **Pack marketplace JSON.** ✅ shipped (Phase K4) —
   `GET /api/domains/manifest` returns a stable, cache-friendly
   summary (slug / capabilities / action counts / composite
   linkage) for installer UIs.

## Showcase polish

10. **Idle camera path.** Bezier loop after 12s of no scroll/pointer; resets
    on input. Adds the "alive" feel without forcing engagement.
11. **GLB asset slot UI.** Drag-and-drop a GLB onto the page in dev to
    preview alternate cores; persist to `localStorage` until cleared.
12. **Audio.** ✅ shipped (lib/sound.ts) — ambient hum + UI cues +
    SoundToggle, muted by default. Open work: richer ambient bed
    with 4-5 tones + slow LFO; per-route presence (cockpit cooler,
    landing warmer).
13. **Page-to-cockpit transition.** ✅ shipped — `BrowserRouter` +
    `AnimatePresence` blur-slide between `/` and `/cockpit`. Open
    work: shared overlay sweep on route change.
14. **Dark / light variants.** A cooler "studio" lit variant for
    investor screenshots: still minimalist, but white background and ink
    type. Activated by `?theme=studio`.

## Local-first, privacy

15. **Local trace viewer.** ✅ infra shipped — `GET /api/meeet/events`
    + `/api/meeet/stats`. Frontend page is the next move (owner:
    design). The SQLite source of truth is `~/.tars/meeet.sqlite`.
16. **Encrypted vault.** Wrap the awareness store in libsodium; key stays in
    Keychain. Required before MLM / business adapters touch real data.
17. **Differential telemetry.** Default-off counters with k-anon aggregation
    that meeet can stream anonymised; opt-in switch in settings.
28. **Replay-on-reconnect.** ✅ shipped — `MeeetClient.replay_unpushed`
    + `POST /api/meeet/replay`. Open work: schedule a periodic replay
    (e.g. every 60s) when ingest is configured.

## Operator / cockpit

18. **Council debug panel.** Backend shipped — every deliberation
    persists in `/api/meeet/events?kind=sampler.decision` and
    `traders.summarize_market`/`business.daily_brief` responses carry
    a `council` block. Owner: design — render the dual-voice diff,
    confidence bars, latency, agreement %, contradictions list.
19. **Action playbooks.** ✅ shipped — JSON under
    `playbooks/<pack>/<name>.json`, runner + `/api/playbooks` HTTP
    surface. Sample playbooks: `traders.morning_check`,
    `business.morning_brief`, `mlm.retention_round`. Open work:
    cockpit palette UI, parallel step blocks. ✅ **schema validator
    shipped 2026-05-01** — `backend/core/playbooks/validator.py` +
    `POST /api/playbooks/_validate` + `GET /api/playbooks/_validate_all`,
    `tests/test_playbook_validator.py` (40 cases) including a CI
    smoke that pins every bundled playbook.
20. **Hotkey palette.** ⌘K opens a fuzzy palette over packs, awareness
    sources, playbooks, recent traces.
26. **Awareness ticker.** ✅ shipped — `<AwarenessTicker/>` consumes
    `/api/awareness/stream` SSE in the Cockpit page. Open work:
    sparkline chart variant, replay-from-trace mode.
27. **Smart response renderer.** Cockpit currently shows raw JSON
    plus the new `<UsageStrip />` cost card. Open work: per-action
    templates that pull `summary` / `top_gainers` / `at_risk` /
    `tldr` / `council.summary` into a HUD card on top of the JSON
    viewer.
29. **Pending confirmations panel.** Backend shipped —
    `/api/policy/pending` returns staged tokens with args/preview.
    Owner: design — a left-rail "approval inbox" with one-click
    confirm / cancel and an audit row.
30. **Awareness explorer.** Backend shipped —
    `/api/domains/<slug>/awareness/<id>/snapshot`. Owner: design —
    per-source live preview cards (calendar list, deals pipeline,
    arXiv abstracts).

## Engineering

21. **Contract tests against meeet ingest.** ✅ shipped (Phase K5) —
    `tests/test_meeet_contract.py` pins the on-the-wire shape, the
    session/route round-trip, and the durable buffer's persistence
    behaviour. Bump `contract_version` + this file together.
22. **Replay.** ✅ shipped (Phase K5) —
    `python -m backend.core.meeet.replay_cli` with
    `--stats / --export / --limit / --since / --kind / --session-id`.
    Doubles as the cold-start recovery story.
23. **Docs site.** Build `docs/` into a static site under `dist-docs/` using
    one of the existing scripts (no new deps).
31. **Composite playbooks.** ✅ shipped — runner already resolved the
    slug from `step.action` (not the playbook directory), so composite
    packs work end-to-end. This batch added the canonical samples
    `playbooks/research_lab/paper_to_pitch.json` and
    `playbooks/ops_room/morning_standup.json`, plus 8 pytest cases in
    `tests/test_composite_playbooks.py` pinning loader, awareness
    parsing for namespaced source ids, sequential + parallel composite
    execution, destructive-flag propagation through the policy gate,
    and cross-sub-pack templating. `docs/DOMAIN_PACKS.md` got a new
    "Composite playbooks" section. Open work: cockpit playbook palette
    grouped by composite-vs-atomic.
32. ~~**OAuth / JMAP outbound.**~~ **OAuth shipped (XOAUTH2 + refresh
    flow, 2026-05-01):** PR #40 added SASL XOAUTH2 to `smtplib`;
    follow-up PR adds stdlib-only `OAuth2 grant_type=refresh_token`
    exchange in `backend/core/domains/packs/business/oauth.py` with
    in-memory cache + 5-minute refresh lead. Provider shorthand
    `gmail` / `office365` / `outlook` resolves the token URL
    automatically. `tests/test_business_smtp_oauth_refresh.py`
    (18 cases) pin parser + cache + refresh + degradation paths.
    **Still pending:** initial consent / authorization-code flow
    (operator-side once-per-account) and JMAP (Fastmail-native
    protocol) — both require operator-side infrastructure (consent
    UI, persistent token store).

## Branding

24. **TARS one-liner.** Lock the tagline: "TARS — your machine, awakened."
    Carry through hero, app icon, social cards.
25. **Social cards.** Render OG cards from the showcase scene at build time
    (puppeteer is already a transitive of postprocessing dev tooling — no
    new top-level dep). Or fall back to static SVGs.
