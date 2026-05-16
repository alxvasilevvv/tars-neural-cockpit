# Phase L — TARS as the flagship product of meeet.world

> Status: **planning approved**, sub-phases sequenced, L1 starts now.
> Owner: Cursor agent (functional). Design polish: Claude Code.
> Bridge: every cross-boundary call still flows through `backend/core/meeet/`
> with `contract_version=1.0.0` (will bump to `1.1.0` when L5 lands).

This document is the canonical plan for evolving TARS from the current
operator cockpit into a Claude-tier neural product, distributed natively
on macOS, Windows, **iOS and Android**, with `meeet.world` as the encrypted spine.

If you're an autonomous agent picking up this work, read this top-to-
bottom once, then per sub-phase as you ship it. Each phase has a clear
deliverable contract and acceptance criteria — do not skip them.

---

## 1. Vision

**One sentence:** TARS is the local-first neural cockpit for operators —
threads, voice, automations, files and full observability — released
under the `meeet.world` brand and synced E2E-encrypted across every
device the operator owns.

**Three things that must be true after Phase L ships:**

1. A new operator downloads TARS for Mac or Windows from the **official
   website** (plain HTTPS installer — `.dmg` / `.exe`; no App Store or
   Microsoft Store required for desktop v1), installs in under 60 seconds,
   and feels a Claude-grade conversation experience inside the first message.
2. The same operator pulls out their phone (iPhone or Android) anywhere,
   sees the same threads (decrypted on-device with a key that never left
   the secure store — Keychain on iOS, Keystore-backed storage on Android),
   and continues mid-thought.
3. Anything an LLM voice could "tell" the operator, TARS can also
   **do** — through the policy gate, with confirmation, costed in USD,
   logged to the durable buffer.

**One thing that must not be true:** TARS does not phone home in any
way the operator hasn't explicitly opted into. `MEEET_INGEST_URL` stays
opt-in; encrypted sync (L5) is a deliberate "pair this device" act.

---

## 2. North star — meeet.world topology

```
                ┌──────────────── meeet.world ──────────────────┐
                │  • identity / billing                         │
                │  • encrypted ingest (contract 1.x)            │
                │  • domain-pack marketplace                    │
                │  • read-only delta API for cross-device sync  │
                └────────────▲───────────────▲──────────────────┘
                             │               │
   E2E-encrypted             │               │  E2E-encrypted
   ingest + pull             │               │  ingest + pull
                             │               │
            ┌────────────────┴───────┐   ┌───┴────────────────┐
            │  TARS · macOS (Tauri)  │   │  TARS · Windows    │
            │  (full backend, FT5,   │   │  (Tauri, full      │
            │   council, packs)      │   │   backend)         │
            └─────────▲──────────────┘   └────────────────────┘
                      │
                      │ local LAN bonjour
                      │
            ┌─────────┴──────────────┐
            │  Mobile · thin clients │
            │  iOS (Swift) · Android │
            │  (Kotlin) — no backend │
            │  on-phone for v1       │
            └────────────────────────┘
```

`meeet.world` never holds plaintext memory or attachments — it stores
opaque ciphertext + metadata (ts, kind, route, session_id). All decrypt
keys live in the user's macOS Keychain; on mobile, iOS **Secure Enclave**
and Android **Keystore / StrongBox** hold sync material.

---

## 3. Where we are today (inventory, latest first)

Everything below is **shipped and tested** as of the Phase K close-out
(159 pytest tests green; frontend builds clean). New work in Phase L
attaches to these.

### 3.1 Backend modules (load-bearing)

- `backend/core/meeet/` — durable SQLite WAL buffer, replay, trace
  scope, **session_id + route tagging (K1)**, contract pin, CLI
  (`replay_cli.py`).
- `backend/core/usage/` — cost ledger derived from the meeet store,
  per-model/route/session rollups (K2/K3).
- `backend/core/council/` — three voice families (Local, MockCloud,
  Anthropic/OpenAI), `dual_vote/n_vote/single` modes, agreement +
  contradictions detection, emits `usage.tokens` + `sampler.decision`.
- `backend/core/policy/` — destructive-action gate, three modes
  (`autopilot`/`confirm`/`dry_run`), persistent token store, TTL,
  `policy.{allowed,blocked,queued,confirm,cancelled}` events.
- `backend/core/playbooks/` — JSON-defined multi-step automations,
  parallel groups (`asyncio.gather`), templating, `when` clauses,
  `store_as`, `on_error`.
- `backend/core/vault/` — env → macOS Keychain → missing resolver,
  never echoes secret values, only sources.
- `backend/core/domains/` — pluggable packs (`traders`, `business`,
  `mlm`, `science`) + composites (`research_lab`, `ops_room`).
- `backend/core/awareness/` — calendar, memory, code_index,
  mac_actions (load-bearing, do not refactor without scope).

### 3.2 HTTP surface

```
GET  /health
GET  /api/domains
GET  /api/domains/manifest                          (K4)
GET  /api/domains/{slug}
GET  /api/domains/{slug}/awareness
GET  /api/domains/{slug}/awareness/{id}/snapshot
GET  /api/domains/{slug}/prompt
POST /api/domains/{slug}/actions/{action_id}        (policy-gated)
GET  /api/awareness/stream                          (SSE)
GET  /api/meeet/stats|events|health
POST /api/meeet/replay
POST /api/council/deliberate
GET  /api/policy/pending|recent
POST /api/policy/{confirm,cancel}/{token}
POST /api/policy/expire
GET  /api/playbooks
GET  /api/playbooks/{id}
POST /api/playbooks/{id}/run
POST /api/playbooks/_reload
GET  /api/vault/status
GET  /api/usage                                     (K3)
GET  /api/usage/lines                               (K3)
GET  /api/usage/prices                              (K3)
```

### 3.3 Frontend

- `experiments/neural-showcase-v3/` — React 18 + TS + Tailwind v4 +
  framer-motion + R3F; routes `/` (Landing) and `/cockpit`.
- `lib/{api,policy,council,playbooks,meeet,vault,usage,session}.ts`
  typed clients + React polling hooks.
- `components/{OperatorStrip,UsageStrip,AwarenessTicker}.tsx` already
  surface the K-tier endpoints; visual integration owned by Claude.

### 3.4 Tests

```
tests/
├── test_meeet.py / test_meeet_store.py / test_meeet_health_and_replay_loop.py
├── test_meeet_contract.py                          (K5 — pins wire shape)
├── test_council.py / test_vault_and_llm_voice.py
├── test_policy.py / test_playbooks.py
├── test_domains.py / test_real_adapters.py / test_batch2_adapters.py
├── test_awareness_fetchers.py / test_awareness_stream.py
├── test_mlm_db.py
├── test_usage_ledger.py / test_usage_router_and_manifest.py    (K2/K3)
├── test_composite_packs.py                                     (K4)
├── test_replay_cli.py                                          (K5)
└── test_business_smtp.py                                       (K6)
```

---

## 4. Gap analysis vs Claude-tier

| Capability                        | Claude.ai      | TARS today           | Phase L delta              |
| --------------------------------- | -------------- | -------------------- | -------------------------- |
| Conversational threads + stream   | ✅ flagship    | partial (council)    | **L1**                     |
| Tool use / function-calling       | ✅ via MCP     | domain action router | **L1** (unifies as `tool_call` events) |
| Files / images / PDFs / code      | ✅             | ❌                   | **L2**                     |
| Long-term memory / projects       | ✅ Projects    | per-pack memory keys | **L1 + L2** (project rooms)|
| Code execution / artifacts        | ✅ artifacts   | ❌                   | **L3**                     |
| Voice mode                        | ✅ Sonnet      | UI-cue only          | **L4**                     |
| Native desktop apps               | ✅ Mac/Win     | 🟡 scaffold + manifest | **L9** (Tauri 2 scaffolded; **`.dmg`/`.exe` from official site** — pyoxidizer + signing pending) |
| iOS / Android native apps          | ✅             | 🟡 stubs              | **L10** (Swift + Kotlin/Compose stubs landed; full apps pending) |
| Multi-device sync (E2E)           | cloud, not E2E | local-only           | **L5**                     |
| Search across history             | ✅             | trace_id/kind only   | **L8**                     |
| Skill / pack marketplace          | artefacts      | manifest endpoint    | **L7**                     |
| Local-first privacy               | ❌             | ✅                   | already a moat — keep      |
| Cost / route observability        | ❌             | ✅ `/api/usage`      | already a moat — surface   |
| Policy gate for destructive ops   | ❌             | ✅                   | already a moat — surface   |

---

## 5. Phase L sub-phases (detailed)

Each sub-phase below is **independently shippable**, has a clear
contract, tests, and an explicit "definition of done" so a fresh agent
can pick it up.

---

### L1 — Conversation Layer

**Goal in one line:** turn the cockpit into a real thread-based
conversation surface with token-by-token streaming and tool-call
visibility, on top of every K-tier component we already shipped.

**Why first:** L2 (attachments), L4 (voice), L9 (Tauri shell), L10
(mobile companions) all assume threads exist. L1 unblocks everything.

#### L1.1 Data model

New module: `backend/core/chat/`.

```
backend/core/chat/
├── __init__.py
├── models.py        # Thread, Message, ToolCall, Attachment dataclasses
├── store.py         # SQLite-backed (~/.tars/chat.sqlite, WAL)
├── orchestrator.py  # ChatOrchestrator: ties council + policy + meeet
└── streaming.py     # async generator yielding StreamEvent objects
```

**Schema (SQLite):**

```sql
CREATE TABLE threads (
    id TEXT PRIMARY KEY,                -- thr_<urlsafe>
    title TEXT,
    pack_slug TEXT,                     -- optional: pinned domain pack
    project_id TEXT,                    -- optional: groups threads
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_session_id TEXT,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,                -- msg_<urlsafe>
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,                 -- "operator" | "tars" | "tool"
    content TEXT NOT NULL,              -- markdown
    created_at REAL NOT NULL,
    trace_id TEXT,
    parent_msg_id TEXT,
    cost_usd REAL,
    route TEXT,
    council_id TEXT,                    -- FK to sampler.decision id
    tokens_in INTEGER, tokens_out INTEGER,
    voice_model TEXT,
    FOREIGN KEY (thread_id) REFERENCES threads (id)
);

CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,                -- tcl_<urlsafe>
    message_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    action_id TEXT NOT NULL,
    args_json TEXT NOT NULL,
    status TEXT NOT NULL,               -- pending|allowed|blocked|completed|failed
    policy_token TEXT,
    result_json TEXT,
    cost_usd REAL,
    started_at REAL NOT NULL,
    completed_at REAL
);

CREATE TABLE attachments (              -- L2 will populate; create now
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    message_id TEXT,
    mime TEXT NOT NULL,
    filename TEXT,
    bytes_total INTEGER,
    storage_path TEXT NOT NULL,         -- ~/.tars/attachments/<id>
    extracted_text TEXT,
    embedding_id TEXT,
    created_at REAL NOT NULL
);
```

All writes go through `ChatStore` which wraps `asyncio.to_thread`
(same pattern as `MeeetStore`). Singleton at `~/.tars/chat.sqlite`,
disable with `TARS_CHAT_STORE=disabled`, override path with
`TARS_CHAT_DB_PATH`.

#### L1.2 Orchestrator contract

```python
class ChatOrchestrator:
    async def post_message(
        thread_id: str,
        operator_text: str,
        *,
        session_id: str | None = None,
        attachments: list[AttachmentRef] = (),
    ) -> AsyncIterator[StreamEvent]:
        """Yield a token/tool stream until the assistant turn is closed."""
```

`StreamEvent` is a small union; serialised as SSE `event: <kind>\ndata: <json>\n\n`:

| event             | when                                       |
| ----------------- | ------------------------------------------ |
| `message.started` | model picked, route decided                |
| `token`           | every text chunk                           |
| `tool_call.proposed`   | LLM wants to invoke a domain action   |
| `tool_call.queued`     | policy gate returned awaiting_confirmation |
| `tool_call.allowed`    | policy gate let it through            |
| `tool_call.completed`  | action handler returned ok            |
| `tool_call.failed`     | action handler raised                 |
| `usage`           | tokens_in/out + cost_usd                  |
| `message.completed`| final markdown body                      |
| `error`           | terminal failure                          |

Internally:

1. Open `trace_scope(session=session_id, route="edge")`. New trace per
   message.
2. Persist the operator message synchronously.
3. Build context: thread history (last N messages) + pinned pack's
   `system_prompt()` + attached files (extracted text from L2).
4. Pick voice — same logic as `CouncilOrchestrator.deliberate(mode="single")`
   when no contention is needed, escalate to `dual_vote` for ambiguous
   prompts (heuristic: explicit keywords, low-confidence first answer).
5. Stream tokens through `voice.propose_streaming(...)` (new method on
   `Voice`; default impl: chunk the existing `propose()` result on
   sentence boundaries so deterministic voices look the same).
6. On detecting a tool-call structure in the stream (`<tool>{...}</tool>`
   sentinel), pause text emission, hit the existing
   `web_extras/routers/domains.py::invoke_action` pipeline → policy
   gate → handler. Stream the structured result back as
   `tool_call.completed`.
7. After the assistant message is final, persist it with `cost_usd`,
   `route`, `council_id` from the existing ledger.

This means **every conversation message is a meeet trace + a
sampler.decision + (optionally) a tool_call → policy event chain** —
the cockpit's existing `<UsageStrip />` and `<OperatorStrip />` light
up automatically without any change.

#### L1.3 HTTP surface

```
POST   /api/chat/threads                         {title?, pack_slug?} → Thread
GET    /api/chat/threads                         ?archived=&pack=     → list
GET    /api/chat/threads/{id}                                          → Thread + last N messages
PATCH  /api/chat/threads/{id}                    {title?, archived?, pack_slug?}
DELETE /api/chat/threads/{id}                    (soft delete = archive)
GET    /api/chat/threads/{id}/messages           ?cursor= ?limit=
POST   /api/chat/threads/{id}/messages           {text, attachments?}  → starts stream
GET    /api/chat/threads/{id}/stream             (SSE — same stream as POST, idempotent re-attach)
POST   /api/chat/threads/{id}/cancel             (interrupts the active stream)
```

All routes inherit `x-meeet-trace-id`, `x-tars-session-id`,
`x-tars-policy-mode` headers (already supported app-wide).

#### L1.4 Frontend deliverables

```
experiments/neural-showcase-v3/src/
├── lib/chat.ts                  # typed client, useThread / useChatStream hooks
├── components/ChatPane.tsx       # main thread panel
├── components/ChatComposer.tsx   # operator input box, attachments slot ready
├── components/ChatMessage.tsx    # role-aware bubble, tool-call inline cards
├── components/ToolCallCard.tsx   # expand args/result/cost, confirm inline
└── pages/Cockpit.tsx             # mounts <ChatPane /> as primary surface
```

Streaming uses native `EventSource` for SSE. `useChatStream(threadId)`
returns `{messages, sending, error, send(text), cancel()}`.

Tool-call cards reuse the existing `usePendingConfirmations` hook so
"confirm to send email" is one click inline in the chat.

#### L1.5 Tests

- `tests/test_chat_models.py` — dataclasses round-trip, store CRUD,
  thread ordering, archive flow.
- `tests/test_chat_orchestrator.py` — token streaming with
  deterministic LocalVoice, tool-call extraction, policy gate
  integration, cancel mid-stream.
- `tests/test_chat_router.py` — FastAPI TestClient: post-then-stream,
  SSE event shape, headers propagation, attachments pass-through stub
  (real attachments land in L2).
- Target: **≥ 12 new tests, suite stays green.**

#### L1.6 Definition of done

- [ ] All endpoints in §L1.3 implemented.
- [ ] `<ChatPane />` mounted on `/cockpit` as the primary panel
  (existing JSON invocation grid moves to a "Tools" tab).
- [ ] `lib/chat.ts` types + hooks shipped.
- [ ] ≥ 12 new pytest tests; full suite green.
- [ ] Frontend `npm run build` green.
- [ ] AGENT_HANDOFF.md, CHANGELOG_AGENTS.md updated.

---

### L2 — Attachments & Context Graph ✅ shipped 2026-04-29

**Goal:** drop a PDF / image / .csv / code file into a thread, have it
indexed locally, and have the next assistant turn cite it.

> **Status:** shipped — see `docs/CHANGELOG_AGENTS.md` (2026-04-29 ·
> Phase L2). 39 new tests, suite at 249 / 249. The actual implementation
> diverged slightly from the original sketch — notes below.

#### L2.1 Pipeline (as shipped)

```
upload → mime sniff → storage (~/.tars/attachments/<id>/<safe_filename>)
       → text extractor (per-mime adapter, best-effort)
       → chunker (token-aware ~800-token target via 4-char heuristic,
                  paragraph-first then sentence-aware, overlap=320,
                  resolves nearest heading + PDF page)
       → embedder (cloud: OpenAI text-embedding-3-small via stdlib
                   urllib + vault key; offline: deterministic
                   hash-bigram embedder, normalised cosine
                   meaningful, zero deps)
       → chunk store (SQLite WAL + raw little-endian float32 blobs
                      in attachment_chunks; auto-migrates
                      attachments table)
       → emit `attachment.ingested` + `usage.tokens` meeet events
       → bump trace route to "cloud" when OpenAI embedder ran
```

Per-mime extractors (best-effort — errors land in `meta["error"]`):

- `text/*`, `text/markdown` — passthrough with line-ending normalisation.
- `application/json` — pretty-printed + `kind` shape (object/array/...).
- `text/csv` — first 50 rows as markdown table preview + raw csv body.
- `application/pdf` — `pypdf` page-by-page → `## page N` markers
  (only new dep, MIT, pure-python, lazy import).
- `image/*` — bytes stored, text empty; vision routing via the chat
  voice ships in L4.
- `application/zip` — **deferred** to next sprint (recursive walk +
  per-entry attachments).

#### L2.2 Retrieval (as shipped)

- Hybrid: cosine over float32 vector blobs + tf-style keyword overlap
  with log-length normalisation, fused via reciprocal rank (k=60).
- Chunks with mismatched embedding dim (e.g. operator switched from
  hash → openai mid-thread) are gracefully skipped instead of erroring.
- `_maybe_retrieve()` in `ChatOrchestrator` runs per turn; skipped for
  prompts < 6 chars (greetings, "yes", emoji).
- `_compose_system_prompt()` injects a `## Reference materials` block
  with stable `[chunk_N]` ids and instructs the assistant to cite.

#### L2.3 HTTP surface (as shipped)

```
POST   /api/chat/threads/{id}/attachments     multipart upload
GET    /api/chat/threads/{id}/attachments     list records
GET    /api/chat/attachments/{att_id}         describe + chunk previews
GET    /api/chat/attachments/{att_id}/download
GET    /api/chat/attachments/{att_id}/extracted   plain text
DELETE /api/chat/attachments/{att_id}
POST   /api/chat/threads/{id}/retrieve        {query, top_k?} hybrid retrieval
```

Stream-side: new SSE event `context.retrieved` on every assistant
turn. `message.completed` carries `sources: [...]`; persisted in
`message.extra.sources`.

#### L2.4 Frontend (as shipped)

- `lib/attachments.ts` — typed client + `useThreadAttachments` +
  `useDropZone` (drag-depth-counted to avoid flicker).
- `<ChatPane />` — drag-and-drop overlay, `<AttachmentChipStrip />`,
  `+ file` button + native file input, error toast.
- `<MessageBubble />` — collapsible **Sources** footer with live
  retrieval previews during streaming and persisted citations on
  reload (`message.extra.sources`).
- `useChatThread` reducer — `context.retrieved` → `turn.retrieved`
  threaded through to the bubble.

#### L2.5 Open follow-ups

- BM25-via-FTS5 for keyword side (currently lo-fi tf overlap).
- `application/zip` recursive walk.
- Image vision routing through Anthropic / OpenAI multimodal payloads.
- Streaming ingestion progress via SSE.
- Cross-thread search router (paired with L8).
- Chunk hover preview as floating card in the cockpit.

---

### L3 — Code Execution & Artifacts

**Goal:** "write a Python script that summarises this CSV" → assistant
runs it, returns the table — through the policy gate.

#### L3.1 Sandbox

```
backend/core/runtime/
├── __init__.py
├── runner.py        # subprocess + per-OS sandbox-exec / firejail
├── pyodide.py       # WASM fallback (in-browser) — used by Tauri shell
└── artifacts.py     # output classifier (markdown/html/json/png/csv)
```

- **macOS:** `sandbox-exec` profile (no network, no FS outside
  workdir).
- **Linux:** `firejail` if installed, else hard cgroup limits via
  `resource.setrlimit`.
- **Windows / Tauri:** Pyodide runs inside a hidden web view —
  zero-config, no network.

New action: `runtime.run_code` — destructive, gated by policy.

#### L3.2 Artifact viewer

`<ArtifactPanel />` in cockpit handles:

- text/markdown — full render with `react-markdown` + Shiki.
- text/html — sandboxed `<iframe sandbox="allow-scripts">`.
- application/json — collapsible tree.
- text/csv — virtualised table.
- image/png — `<img>` with download/copy.
- application/x-tars-table — internal "DataFrame" type from CSV
  pipeline (L2).

---

### L4 — Voice Mode

> **Status: L4.1 (TTS persona layer) shipped 2026-04-29** — see Done
> log in `docs/AGENT_HANDOFF.md`. Personas (Jarvis, Stark, HAL 9000,
> GLaDOS, Interstellar TARS, Operator) live; three provider tiers
> with ElevenLabs → OpenAI → mac `say` fallback; cockpit picker +
> per-message speak button + autoplay + Web Speech mic dictation.
> The remainder of L4 (faster-whisper STT relay, push-to-talk
> session events, iOS native voice loop) is below.

**Goal:** push-to-talk in cockpit (and continuous mode on iPhone)
that streams operator audio → STT → council → TTS, with full policy
gating for destructive tool calls.

#### L4.1 Pipeline

```
audio_in (16kHz mono) → faster-whisper (already in venv via L0
                                         video transcription)
                      → ChatOrchestrator (L1)
                      → tts streamer (Piper ONNX, offline)
                      → audio_out (browser/native sink)
```

- **macOS native voice fallback:** `say -v <voice>` via `subprocess`
  for low-effort high-quality.
- **iOS:** `AVSpeechSynthesizer` + `Speech.framework` STT — totally
  on-device, fastest path.

#### L4.2 New events

```
voice.session.opened     {session_id, sample_rate, model}
voice.utterance          {text, partial, ts}
voice.tts.chunk          {bytes_emitted, voice}
voice.session.closed     {duration_ms, partials, finals, cost_usd}
```

All wired through the existing meeet bridge — no new transport.

---

### L5 — Encrypted sync via meeet.world

**Status:** ✅ **host stack shipped 2026-04-29 (real crypto, host-only)**.

What's live:

- `POST/GET /api/pairing/*` (real X25519 host identity, validated
  `client_epk`, `host_public_key` exposed) — `tests/test_pairing_contract.py`.
- `POST/GET /api/recovery/*` for the BIP-39 24-word recovery seed —
  `tests/test_recovery_seed.py` (15 cases, including the spec
  PBKDF2-HMAC-SHA512 vector).
- `backend/core/crypto/envelope.py` — XChaCha20-Poly1305 + X25519
  sealed-event primitive, `tests/test_crypto_envelope.py`.
- `backend/core/crypto/recovery.py` — stdlib BIP-39 (canonical 2048-word
  English wordlist bundled), PBKDF2-HMAC-SHA512 → seed → X25519 master.
- meeet contract **1.1.0** — additive `ciphertext` + `envelope` fields
  on `TARSEvent`, the SQLite store + replay round-trip them; existing
  1.0.0 events ride the same wire.
- End-to-end test: pair a device → encrypt for it → decrypt back from
  the SQLite meeet store with the device's secret key
  (`tests/test_pairing_envelope_e2e.py`).

What's still pending (next Cursor blocks K1–L2):

- Persistent host keyring (Keychain / DPAPI / `secret-tool`) — today
  the host keypair is in-process.
- Cockpit pairing + recovery UX wiring (endpoints exist; React
  components yet to land — see `docs/handoff-claude.md`).
- Mobile companions (iOS / Android) executing the begin / accept flow.
- `tauri-plugin-updater` channel publisher.

**Goal:** the same threads, settings and memory available on every
device the operator pairs, with `meeet.world` storing only opaque
ciphertext + metadata.

#### L5.1 Crypto envelope

Bumps `contract_version` to `1.1.0`. Field-level addition:

```json
{
  "trace_id": "trc_…",
  "kind": "chat.message.created",
  "ts": 1714000000.123,
  "session_id": "ses_…",
  "route": "edge",
  "source": "tars",
  "contract_version": "1.1.0",
  "payload_envelope": {
    "alg": "aes-256-gcm",
    "kid": "k_<sha256-of-pubkey>",
    "iv": "<b64>",
    "aad": {
      "trace_id": "trc_…",
      "kind": "chat.message.created",
      "ts": 1714000000.123
    },
    "ciphertext": "<b64>",
    "tag": "<b64>"
  }
}
```

`payload` is omitted entirely when the envelope is present —
old consumers that only know `1.0.0` ignore unknown fields and skip
the event without crashing.

#### L5.2 Key management

- **Master sync key:** generated on first device, stored in macOS
  Keychain under `tars-sync-key`. Backed up via QR pairing flow
  (next device scans QR → key copied to its Keychain).
- **Per-thread keys derived via HKDF** so a single device leak
  doesn't expose the full corpus.
- **Vault entries:** never sync. `secrets vault` is per-device by
  contract.

#### L5.3 Pull endpoint contract

`meeet.world` exposes `GET /v1/pull?since=<ts>&device=<id>` which
returns up to 1000 events newer than `since` for the calling user.
TARS hits this on a 60s pull loop (`MEEET_PULL_INTERVAL_S`) when the
operator is signed in.

Conflict resolution: `(trace_id, ts)` is canonical; if the same
trace already exists locally with the same ts, drop the duplicate.
Otherwise insert. Soft deletes use a `tombstone: true` payload
attribute.

#### L5.4 Selective sync

Per-pack flag `sync_class`:

| class       | what                                                |
| ----------- | --------------------------------------------------- |
| `never`     | pure local. Default for `vault`, `policy.tokens`.   |
| `local`     | local SQLite only, never enveloped. Default for `mlm.downline`. |
| `encrypted` | enveloped + pushed. Default for `chat.*`, `usage.*`.|
| `public`    | pushed in plaintext (operator opted in). Useful for `awareness.*` shared with team. |

Flag lives on `DomainPack.sync_class`; defaults inherited per kind
prefix.

---

### L6 — Planner / Agent loop

**Goal:** the assistant can plan a multi-step task, ask permission
for the destructive steps, and execute the rest autonomously, with
the operator able to `pause/resume/abort` any time.

#### L6.1 Pieces

- New voice mixin `Planner` produces a `Plan` object (list of
  proposed steps in playbook JSON format).
- New runner `PlannerLoop` ingests a `Plan`, hands it to
  `PlaybookRunner` (already exists), but in `interactive` mode that
  yields `plan.step.{requested,allowed,completed}` events.
- The cockpit grows a `<PlanTimeline />` next to `<ChatPane />`
  showing live progress.

#### L6.2 New events

```
plan.proposed     {plan_id, steps, est_cost_usd}
plan.step.requested {plan_id, step_id, dest, args}
plan.step.allowed   {plan_id, step_id, mode}
plan.step.completed {plan_id, step_id, result_summary, cost_usd}
plan.completed      {plan_id, status, total_cost_usd}
plan.aborted        {plan_id, reason}
```

All persist to the meeet store; `/api/usage?session_id=…` automatically
shows the cost across a plan run.

---

### L7 — Skill / domain-pack marketplace

**Goal:** a third party can publish a TARS pack, an operator can
install it from `meeet.world/packs/<slug>`, signed and sandboxed.

#### L7.1 Pack package format

```
research-papers-1.2.3.tars-pack/
├── manifest.json           # DomainManifest + author + version
├── pack.py                 # entry point (must subclass DomainPack)
├── actions.py / awareness.py / prompts.py
├── data/                   # bundled local fixtures
├── README.md
└── pack.sig                # ed25519 signature over sha256 of every other file
```

Distribution over plain HTTPS from `meeet.world/packs/`. Signing key
comes from the author's meeet.world identity.

#### L7.2 Install flow

```
POST /api/domains/install   {url, expected_sha256, expected_pubkey}
```

Steps:

1. Download zip → tmp.
2. Verify sha256 + ed25519 over `pack.sig`.
3. Run static-analysis pre-flight (no `os.system`, no `eval`,
   restricted imports). This is best-effort, not a security
   boundary — that's what L3 sandboxing is for.
4. Unpack to `~/.tars/packs/<slug>/`.
5. Re-import the registry (existing `_reload` pattern).
6. Emit `pack.installed` event.

#### L7.3 Discovery & UI

- New endpoint `GET /api/domains/marketplace?q=` proxies
  `meeet.world/packs/index.json` and decorates with local install
  state.
- Cockpit `<MarketplaceSheet />` (modal) shows curated packs,
  install/update/uninstall buttons.

---

### L8 — Search & observability v2 ✅ shipped 2026-04-29

**Goal:** "find the time my MRR forecast was off by >10%" should be
one query.

#### L8.1 Indexes — shipped

- SQLite **FTS5** virtual tables (`unicode61 remove_diacritics 2`,
  cyrillic-friendly) over three corpora:
  - `chunks_fts` over `attachment_chunks.text`
  - `messages_fts` over `messages.content`
  - `events_fts` over `events.payload`
- Tables auto-create on first call to
  `backend.core.search.fts.ensure_fts_indexes()` /
  `ensure_events_fts()` and backfill from the source rows.
- Forward-write hooks: `ChatStore.insert_message` and the attachment
  pipeline now mirror their writes into the FTS index (best-effort,
  non-fatal). Bulk helper `index_chunks_bulk` keeps ingestion fast.
- `attachment.delete_attachment` clears the chunk index slice.
- Public helpers `backfill_chunk_fts` / `backfill_message_fts`
  rebuild on demand (covered by tests).

Embedding side reuses Phase L2's `Embedder` interface — no new
dependency. The L2 in-thread retrieval also moved off the hand-rolled
TF overlap onto FTS5 BM25 with a graceful fallback.

The "trace materialised view" is currently **deferred** — `meeet`
events already expose `trace_id`/`session_id`/`route` indices, and
the new `events_fts` is enough for free-text trace search. A 5-min
rollup is on the post-L8 follow-up list (see below).

#### L8.2 New endpoints — shipped

```
POST /api/search                  unified hybrid search
POST /api/search/chunks           cross-thread (or scoped) chunk hybrid
POST /api/search/messages         keyword search over messages
POST /api/search/traces           free-text search over meeet events
GET  /api/chat/threads/{id}/timeline
                                  structured per-thread feed
                                  (messages + tool_calls + attachments + events)
```

All endpoints honour `x-tars-session-id` and `x-meeet-trace-id`. The
unified endpoint streams hits with stable `kind` discriminators
(`chunk` / `message` / `trace`) so the frontend can render every
source in one list.

Sanitiser strips FTS5 syntax (`AND/OR/NOT/NEAR`, punctuation, stray
quotes) and quotes individual tokens to avoid injection.

#### L8.3 Cockpit additions — shipped

- New `lib/search.ts` client + hooks:
  `unifiedSearch` / `searchChunks` / `searchMessages` /
  `searchTraces`, plus `useDebouncedSearch` (220 ms debounce, abort
  on stale typing), `useGlobalShortcut` (⌘K / Ctrl-K), and
  `useThreadTimeline` (auto-refresh).
- `<CommandPalette />` (`/cockpit` mounted) — global ⌘K overlay with
  scope chips (`all` · `files` · `messages` · `traces`),
  arrow-key navigation, BM25 `<mark>` highlights, deep links via the
  `tars:open-thread` custom event.
- `<ThreadTimeline />` collapsible panel under each chat —
  chronological merge of messages + tool calls + attachment ingests
  + relevant meeet events, with auto-refresh while open.
- Cytoscape trace graph deferred — handed to Claude as a follow-up
  visual (see AGENT_HANDOFF).

#### L8.4 Open follow-ups (post-ship)

- 5-min materialised view `(trace_id → event_count, total_cost,
  contradictions, route)` for the trace explorer rollup.
- BM25 highlighting in the cockpit that surfaces multi-mark snippets
  (currently `<mark>` is stripped by `CommandPalette`).
- Vector + BM25 blend for messages (currently keyword-only there).
- Attachment hover-card preview when a chunk hit is highlighted.
- Cytoscape trace-graph view with cost / route shading.

---

### L9 — Tauri 2 desktop shell (macOS + Windows)

**Status:** 🟡 **scaffolded + sidecar runtime 2026-05** — `desktop/` layout,
FastAPI manifest API, and Rust sidecar (`src-tauri/src/sidecar.rs`: bundled
binary, `TARS_BACKEND_BIN`, or `python3 serve.py` + `/health` poll + crash
watch) are live. **Next slice:** CI-bundled PyInstaller/pyoxidizer binary in
`bundle.externalBin`, Apple ID / Authenticode signing, first signed `.dmg` /
`.exe` on the release channel.

**Goal:** signed `TARS-<version>.dmg` (macOS) and `TARS-<version>-Setup.exe`
(Windows) that launch the Python backend as a sidecar and load the
cockpit web build inside a native window — **distributed by direct download
from the official site** (`meeet.world` / product landing over HTTPS).
No dependency on Apple App Store or Microsoft Store for the initial
desktop release (store listings optional later).

**As-shipped (2026-04-29 batch)**

- `desktop/` Tauri 2 workspace with `pnpm tauri:dev` / `tauri:build`.
- `src-tauri/Cargo.toml` (deps: `tauri-plugin-shell`, `notification`,
  `updater`); `tauri.conf.json` allows `127.0.0.1:8765` + `meeet.world`
  in CSP and pins the updater endpoint at
  `meeet.world/updates/{target}/{current_version}.json`.
- `src/sidecar.rs` resolves `TARS_BACKEND_BIN`, bundled `tars-sidecar*`, or
  falls back to `python3 serve.py` at the repo root (local dev); health-poll
  + mid-session crash detection are implemented — replace the bundled binary
  with a PyInstaller/pyoxidizer build when CI produces stable artefacts.
- `backend/core/product/` + `web_extras/routers/product.py` ship the
  `/api/product/downloads`, `/downloads/latest`, `/version` endpoints.
- Cockpit `<DownloadStrip />` (`src/components/DownloadStrip.tsx`)
  renders OS-targeted CTAs from the manifest in the Hero section.
- Wire shape pinned by `docs/contracts/MEEET_DOWNLOADS.md` +
  `docs/contracts/download_manifest.schema.json` (validated runtime
  in `tests/test_product_schema.py`).
- **Release publishing CLI** (`python -m backend.core.product.publish
  <build-dir> --version=<v>`) sniffs artifacts, computes SHA256, and
  writes the contract-shaped `releases.json` consumed by the API
  (`tests/test_product_publish.py` × 9).

#### L9.1 Project layout

```
desktop/
├── src-tauri/
│   ├── tauri.conf.json
│   ├── src/main.rs              # spawn sidecar, manage tray, hotkeys
│   ├── icons/
│   └── capabilities/
├── package.json                  # scripts: dev / build / bundle
└── README.md
```

The web build comes from `experiments/neural-showcase-v3/dist/` (we
already build it for free).

#### L9.2 Backend packaging

- **Default:** `pyoxidizer` builds a standalone Python with our
  source tree embedded; ~60MB binary, no system Python required.
- **Fallback:** users with Python 3.11+ already installed can use the
  "lite" installer (~15MB) that runs `pip install -r requirements.lock`
  on first launch.

#### L9.3 Native integrations

- macOS Keychain — already wired through `subprocess`; native Rust
  crate `security-framework` will replace it for speed but contract
  stays.
- Notifications — `tauri-plugin-notification`.
- Global hotkey `⌥ Space` toggles the cockpit window.
- Auto-update via `tauri-plugin-updater` against
  `meeet.world/updates/<channel>.json`.
- Code signing: Apple Developer ID + Authenticode (operator-funded;
  agent does the wiring, owner provides certs).

#### L9.4 Website distribution (primary channel)

Desktop builds ship as **installer artifacts hosted on our own HTTPS
origin**, not routed through desktop app stores for v1:

- **Landing:** buttons or a `/download` route on **meeet.world** (or a
  `tars.meeet.world` subdomain) pointing to stable URLs per OS + arch —
  e.g. `darwin-arm64.dmg`, `darwin-x64.dmg`, `win-x64-Setup.exe`.
- **Versioning:** each release uploads artifacts under versioned paths
  (`/releases/1.0.0/…`) plus "latest" symlinks / redirect rules so the site
  always advertises the current build without editing marketing copy each
  time (mirrors patterns used by Slack, Discord, Cursor).
- **Integrity:** publish **SHA256 checksums** and (where applicable)
  Authenticode / Apple signatures on the same page so operators can verify
  offline.
- **`tauri-plugin-updater`** consumes `GET meeet.world/updates/<channel>.json`
  as already scoped in L9.3 — incremental updates also pull **from our
  CDN/origin**, not store CDNs.

Optional later: listings on Mac App Store / Microsoft Store — out of scope
until the web-direct channel is stable.

---

### L10 — Mobile companions (iOS + Android)

**Status:** 🟡 **stubs scaffolded 2026-04-29** — `mobile/` tree,
`mobile/ios/TARSCompanion/` Swift Package skeleton +
`mobile/android/TARSCompanion/` Gradle settings landed. No working
build yet; full Xcode / Android Studio projects materialise on the
first L10 implementation slice.

**Goal:** thin, native mobile clients that pair with desktop TARS over
the LAN (Bonjour / NSD) and remotely via `meeet.world` — **same
contracts, two codebases** (no shared UI framework required for v1;
optional **Kotlin Multiplatform** or shared **Rust** crypto core can land
later if we want one sync layer).

Both apps are **read/write windows** into threads + voice + optional
camera attachments. No Python backend on-phone for v1 — the phone talks
SSE/HTTPS to a paired Mac/PC (**L9**) or, when alone, only to encrypted
sync + a minimal hosted relay if we add one (see **L5**).

#### L10.1 Repos

```
mobile/
├── ios/TARSCompanion/            # Xcode, SwiftUI
│   ├── TARSCompanionApp.swift
│   ├── Models/
│   ├── Networking/               # SSE + URLSession
│   ├── Crypto/                   # mirrors L5 envelope
│   ├── Views/
│   │   ├── ThreadListView.swift
│   │   ├── ThreadView.swift      # streaming SSE
│   │   ├── ComposeView.swift     # text + voice + photo
│   │   └── SettingsView.swift
│   └── Resources/
└── android/TARSCompanion/        # Android Studio, Kotlin + Jetpack Compose
    ├── app/src/main/
    │   ├── java/.../tars/
    │   │   ├── MainActivity.kt
    │   │   ├── ui/               # Compose screens
    │   │   ├── net/              # OkHttp SSE, same paths as iOS
    │   │   └── crypto/           # Android Keystore + L5 envelope parity
    │   └── res/
    └── build.gradle.kts
```

Feature parity target for v1: thread list, streaming chat, secure
pairing, voice in/out (platform STT/TTS), photo pick → attachment
upload, settings (base URL, persona). **Play Store / App Store**
release tracks are separate; internal distribution (TestFlight +
Play internal testing) first.

#### L10.2 Pairing UX (shared)

1. Desktop TARS shows a QR code under **Settings → Pair phone**.
2. Phone scans → receives sync key + base URL (LAN preferred for
   sub-100 ms turns).
3. iOS stores secrets in **Secure Enclave**; Android in **Keystore**
   (StrongBox when available). Future sessions are silent.

#### L10.3 Platform-specific notes

- **iOS:** `AVSpeechSynthesizer` + `Speech.framework` for the native
  voice loop (already sketched under L4).
- **Android:** `SpeechRecognizer` + `TextToSpeech` (or on-device
  models when L4 adds a relay); respect **background execution**
  limits — voice push-to-talk as foreground service when recording.

#### L10.4 Store policy

- App review: disclose LLM + data handling; meeet.world as optional
  sync — **no** forced cloud account for local-only pairing.
- Android: same privacy labels in Play Data safety; optional F-Droid
  track is out of scope for v1 unless requested.

## 6. Cross-platform sequencing

```
sprint 1  ┃ L1  ── Conversation Layer (this batch)
sprint 2  ┃ L2  ── Attachments + L8 search foundations
sprint 3  ┃ L9  ── Tauri shell  ────────┐
                                        │  parallel:
sprint 3  ┃ L5  ── Encrypted sync  ─────┘  meeet contract bumps to 1.1.0
sprint 4  ┃ L4  ── Voice mode       ────┐  parallel:
sprint 4  ┃ L10 ── Mobile (iOS + Android) ─┘  Swift + Kotlin project bootstrap
sprint 5  ┃ L3  ── Code exec sandbox
sprint 6  ┃ L6  ── Planner loop
sprint 7  ┃ L7  ── Marketplace v1
sprint 8+ ┃ Polish, marketing, public beta
```

Each "sprint" is a logical unit of agent work — usually a single
Cursor-or-Claude session producing a Phase-K-sized commit.

---

## 7. Acceptance criteria across Phase L

A Phase L sub-phase is "done" when:

1. Public HTTP / event contract documented in this file.
2. ≥ 10 new pytest tests (more if multiple sub-modules), full suite
   green.
3. Frontend `npm run build` green; `tsc -b` clean (`noUnusedLocals`).
4. `AGENT_HANDOFF.md` Done section updated, `CHANGELOG_AGENTS.md`
   gets a per-batch entry, `IDEAS.md` ✅-marks the closed items.
5. Smoke test recorded in `AGENT_HANDOFF.md` curl recipes if a new
   endpoint shipped.
6. No new Python deps unless explicitly listed (`pypdf`,
   `sentence-transformers`, `faiss-cpu`, `cryptography` —
   each gated by an env-var fallback so the offline-first dev loop
   never breaks).

---

## 8. Risks & mitigations

| Risk                                                    | Mitigation                                      |
| ------------------------------------------------------- | ----------------------------------------------- |
| LLM voice key rate-limits in chat streaming             | Local fallback voice (already shipped);  stream "downgraded" notice in UI |
| SQLite WAL fights with macOS sandboxing in Tauri        | Test sandbox profile early in L9; fall back to `~/Library/Application Support/TARS/` |
| Pyoxidizer + PyTorch (sentence-transformers) bloats DMG | Ship embedder as optional add-on; default to OpenAI-key embedder if vault has one |
| meeet.world ingest contract drifts                      | `tests/test_meeet_contract.py` already pins shape; bump version, never silently break |
| iPhone / Android app store review delays                | TestFlight + Play internal first; PWA fallback only if store blocks |
| Cost ledger gives false zeroes for unknown models       | Already returns `cost_usd: null` rather than 0; UI shows "n/a" |
| Code execution sandbox escape                           | L3 isolates by OS sandbox + denies network by default; destructive policy gate as second layer |

---

## 9. What we are explicitly NOT doing in Phase L

- **Multi-tenant SaaS for TARS.** TARS stays single-operator. Teams
  use multiple paired devices via L5.
- **Custom model training.** We are an inference + tooling cockpit,
  not a training stack.
- **Web-only "use TARS in the browser" without an account.** The
  whole point is local-first; a hosted webapp as the *only* runtime would
  defeat it. **Direct download of the macOS/Windows native installer from
  the official site (L9)** is explicitly in scope — that is native TARS,
  not a SaaS shell.
- **Replacing the existing `frontend/` vanilla surface.** It stays
  for raw operator debug. The cockpit (`neural-showcase-v3`) is the
  product.

---

## 10. Pointer to next concrete work

**Now starting:** L1.1 → L1.6, in order. Implementation lives under
`backend/core/chat/`, `web_extras/routers/chat.py`,
`experiments/neural-showcase-v3/src/{lib/chat.ts,components/Chat*.tsx}`.

Watch `docs/CHANGELOG_AGENTS.md` for the per-step diary and
`tests/test_chat_*.py` for the proof.
