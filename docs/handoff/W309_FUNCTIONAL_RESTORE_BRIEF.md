# W309 — functional restore brief (for Cursor)

> **Author.** Claude (Opus 4).
> **Audience.** Cursor — owns the W309 implementation lane.
> **Status.** Draft — **gated on operator OK before action** (per
> `W308_PRE_FLIGHT_FINDINGS.md` § "Carry-over for W309+").
> **Purpose.** Pre-bake the brief so when the operator says "go",
> step 1 lands in one bounded session.

---

## 0. The regression in one paragraph

W308 step 3 (`9c583e4`) replaced the ~5 MB pre-built React SPA at
`desktop/src-tauri/web/` with a 27 KB Vite-built artefact from
`apps/cockpit/`. **The visual contract is correct** (W307 verdict,
step 1+2+4 honoured). **The behavioral contract is empty** — the
new pages are static HTML with one `<script type="module">` that
sets a body class and nothing else. TARS.app currently renders the
correct shell but cannot listen, speak, or hold a conversation.

The legacy SPA still lives at `desktop/src-tauri/web-legacy/` (preserved
by `git mv` in step 3). `bash desktop/scripts/package-cockpit.sh --legacy`
re-stages it for emergency parity if release pressure spikes.

---

## 1. Inventory — what lives in the legacy SPA

Extracted via `grep` on `web-legacy/assets/*.js` (sources are
minified but pattern matches are reliable). Numbers in parentheses
are evidence — exact strings found.

### 1.1. Audio capture

- `navigator.mediaDevices.getUserMedia(...)` — mic permission flow,
  used by both the conversation pane and the waveform visualizer.
  Found in `Cockpit-CWJnxhRj.js` and inline `index.html`.
- `AudioContext` — Web Audio graph for the waveform / FFT visualiser.
- `webkitSpeechRecognition` — fallback browser STT path (when
  ElevenLabs STT is offline or rate-limited).
- Audio playback via `howler.js` (separate chunk `howler-CiMcCg-h.js`,
  ~6 KB) — TTS playback queue, ambient SFX.

### 1.2. WebSocket transport

- Sidecar URL: **`ws://127.0.0.1:8765`** (per `W308_PRE_FLIGHT_FINDINGS.md`
  § Carry-over). The legacy Cockpit chunk connected on cockpit-mount and
  fanned events to: agent-frames timeline, voice transcript,
  awareness stream, policy gate events.
- 25 REST endpoints called from the cockpit chunk alone — see § 1.5
  for the full list.

### 1.3. ElevenLabs / voice loop

- String `elevenlabs` appears inline in legacy `index.html` and the
  Cockpit chunk.
- Endpoints: `/api/voice/health`, `/api/voice/personas`,
  `/api/voice/speak` — TTS request flow.
- ElevenLabs API key was managed via `/api/vault/status` + Vault
  panel (W180 wired this).

### 1.4. Conversation strand renderer

- Endpoints: `/api/chat/threads`, `/api/chat/threads/{id}`,
  `/api/chat/attachments/{id}`.
- Rendered the strand replacing the briefing on chat-start
  (per `design-system/tars/pages/cockpit.md`).
- Drawer state for `⌘K` / `⌘L` / `⌘R` (palette / library /
  recent ops).

### 1.5. REST API surface used by the cockpit chunk

Grepped directly out of `Cockpit-CWJnxhRj.js`:

```
/api/agents                     /api/policy/cancel/{id}
/api/attachments/               /api/policy/confirm/{id}
/api/awareness/stream           /api/policy/pending
/api/chat/attachments/          /api/recovery
/api/chat/threads               /api/search
/api/chat/threads/              /api/tasks
/api/council/deliberate         /api/usage
/api/meeet/events               /api/vault/status
/api/meeet/health               /api/voice/health
/api/pairing                    /api/voice/personas
/api/playbooks                  /api/voice/speak
/api/playbooks/                 /api/wallet
```

Not all 25 are critical for "TARS can have a conversation". The MVP
subset is § 2.1.

### 1.6. Tauri IPC

- `@tauri-apps` / `__TAURI__.invoke()` referenced in 4 legacy chunks:
  `Cockpit`, `Changelog`, `process`, `ui`.
- Currently *not* referenced from any `apps/cockpit/` file. New pages
  must import Tauri APIs explicitly (or stay browser-only).

---

## 2. Restoration strategy

**Recommended approach: small per-page TS modules under
`apps/cockpit/src/pages/`** (Cursor's own hint in step-3 carry-over).
Not a port of the React SPA. Three minimal modules cover the MVP.

### 2.1. MVP subset — "TARS can have a conversation"

Restoring this subset gives the operator a usable cockpit again. The
other 19 endpoints can land in W310+ as separate small modules.

| Capability | Endpoint(s) | Why MVP |
|---|---|---|
| Mic permission + recording | `getUserMedia` | Without mic, voice loop is dead on arrival |
| WebSocket to sidecar | `ws://127.0.0.1:8765` | All real-time updates flow through here |
| Chat thread send / load | `/api/chat/threads`, `/api/chat/threads/{id}` | Text-mode fallback when voice is off |
| TTS playback | `/api/voice/speak` (POST → audio) | "TARS speaking back" |
| Voice persona list | `/api/voice/personas` | Voice picker in settings |
| Voice health | `/api/voice/health` | Status badge + degraded mode |
| Vault status | `/api/vault/status` | Detect missing ElevenLabs key, show prompt |

### 2.2. Suggested file layout

```
apps/cockpit/src/
├── pages/
│   ├── cockpit-entry.ts   # existing — extend with conversation wiring
│   ├── hero-entry.ts      # existing — leave alone (marketing surface)
│   └── ...
├── runtime/
│   ├── ws.ts              # NEW — single WebSocket manager, reconnect, fan-out
│   ├── voice.ts           # NEW — mic capture + TTS playback + persona state
│   ├── chat.ts            # NEW — thread send/load, optimistic UI
│   ├── api.ts             # NEW — typed fetch wrapper, base URL, error envelope
│   └── tauri.ts           # NEW — IPC helpers; no-op when running in browser
└── styles/
    └── ... (unchanged)
```

Total LoC estimate: **~600–900 lines TypeScript**, no external
dependencies beyond what `apps/cockpit/` already pulls. `howler.js`
is overkill for the MVP — `new Audio(url).play()` is enough for TTS
chunks; W310 can swap in if queueing becomes complex.

### 2.3. What *not* to do

- **Don't restore the React SPA.** It was deliberately retired
  (`e5f1911` + Path C decision). The legacy bundle is read-only
  reference, not a runtime dependency.
- **Don't try to recreate all 25 endpoints in W309.** MVP first.
  Council, playbooks, search, wallet, etc. are not on the
  "TARS talks back" critical path.
- **Don't add a framework.** Vanilla TS + the existing tokens system
  is the contract. React/Vue would add ~45 KB minified for no benefit
  at MVP scale.

---

## 3. Sub-tasks (do in this order)

### 3.1. Build the runtime skeleton

Create the 5 files in § 2.2's `runtime/` folder. All stubs initially —
no behavior. Each file exports a `setup()` / `teardown()` pair plus
typed helpers. This establishes the module boundary before any
behavior lands.

Acceptance: `pnpm --filter @tars/cockpit build` clean, bundle grows
by ≤ 2 KB (stubs only), `pytest tests/test_cockpit_tokens_sync.py`
still 10/10.

### 3.2. WebSocket manager (`runtime/ws.ts`)

Connect on cockpit mount, reconnect with exponential backoff (1s →
30s cap), emit typed events via a `Map<string, Set<Handler>>` bus.
Handle close codes: 1000 = clean, 1006 = retry, 4001 = auth fail
(show "reconnecting" badge in status bar).

URL is operator-configurable: respect
`window.localStorage.getItem('TARS_WS_URL')` first; fall back to
`ws://127.0.0.1:8765`. (Default matches what the sidecar binds to
per W177 + W181.)

Acceptance: page loads → green dot in status bar; kill sidecar
manually → dot goes amber within 5s, reconnects when sidecar comes
back.

### 3.3. Voice loop (`runtime/voice.ts`)

Three concerns in one file (small enough to stay together at MVP):

- **Mic capture.** `navigator.mediaDevices.getUserMedia({ audio: true })`
  on first user gesture (mic button click). Hold the
  `MediaStreamTrack` reference for the duration of the cockpit
  session; release on `teardown()`.
- **TTS playback.** Fetch `/api/voice/speak` with `{ text, persona_id }`
  → response is audio bytes. Play via `new Audio(URL.createObjectURL(blob))`
  with a single-track queue (no overlap).
- **Persona state.** Hit `/api/voice/personas` on mount, store in
  module-level `currentPersona`. Settings UI can call `setPersona(id)`.

Acceptance: mic button toggles state correctly; clicking "play sample"
in settings produces audio from the selected persona; cockpit shows
"Voice degraded" badge when `/api/voice/health` returns non-OK.

### 3.4. Chat thread (`runtime/chat.ts`)

Send-and-display path: textarea → POST `/api/chat/threads` → optimistic
append to strand → wait for WS `chat.message` event → reconcile (or
mark "delivery failed" with retry).

Render the strand replacing the briefing on chat-start (per
`design-system/tars/pages/cockpit.md` §3). The DOM for the strand
already exists in `apps/cockpit/cockpit.html` — just needs `[hidden]`
toggling and content injection.

Acceptance: typing → enter → message visible in strand → TARS reply
appears (assuming sidecar wired); cockpit reload preserves last 20
messages via `/api/chat/threads/{id}` fetch on mount.

### 3.5. Vault status hook (`runtime/api.ts` consumer)

On cockpit mount, fetch `/api/vault/status`. If `elevenlabs_key:
missing`, render the existing vault prompt in the cockpit (DOM
already there from W180). On success, hide it. This is ~30 LoC and
unblocks new users.

Acceptance: empty `.env` → cockpit shows "Add ElevenLabs key" CTA;
key added + sidecar restarted → CTA disappears on next mount.

### 3.6. Hardcoded `10px` mono cleanup (carryover from step 4)

Step 4 fixed `.phase-bar` but stopped at the named symptom. Six
other call-sites still hardcode `10px Share Tech Mono`:

- `apps/cockpit/cockpit.html` — `.source-chip` (~L437), `.gate-head`
  (~L512), `.send-kbd` (~L667), bottom status bar (~L690).
- `apps/cockpit/hero.html` — two mono call-sites (~L398, ~L478).

Replace each with `var(--font-size-phase-bar)` (the existing 11px
token from step 4) or create `--font-size-meta: 11px` if intent
differs. Document the rename in MASTER §4. Extend the drift test
to grep for `font-size: 10px.*Share Tech Mono` across `apps/cockpit/`
and fail if found.

Acceptance: pytest 10 → 11 passing; manual A/B on letterform clarity
shows clean caps on `.source-chip` and `.send-kbd`.

### 3.7. Smoke test the whole loop

Add `tests/test_cockpit_runtime_contract.py`:

- Parse `apps/cockpit/src/runtime/ws.ts` — assert it imports nothing
  beyond the standard browser globals.
- Parse `apps/cockpit/src/runtime/voice.ts` — assert it references
  `navigator.mediaDevices`, `/api/voice/speak`, `/api/voice/personas`.
- Parse `apps/cockpit/src/runtime/chat.ts` — assert it references
  `/api/chat/threads`.
- Static-only checks; no actual network. CI-friendly.

---

## 4. Verification protocol (manual, ~10 min)

Before committing the W309 step 1 wave:

1. `bash desktop/scripts/package-cockpit.sh` — build clean.
2. Boot `tars-daemon` (if not already running per W181).
3. `open /Applications/TARS.app` (or rebuild via REBUILD-TARS-APP.command).
4. Hit:
   - Click mic button → permission prompt → after grant, mic state
     turns green in cockpit shell.
   - Type "Hello" in the input → press enter → see the message
     appear in conversation strand → see TARS reply within 3s.
   - Click "Play sample" in voice settings → hear the persona speak.
   - Kill sidecar (Activity Monitor → quit `tars-daemon`) → status
     bar dot turns amber within 5s.
   - Restart sidecar → dot turns green within 10s without page
     reload.
5. `pytest tests/test_cockpit_tokens_sync.py tests/test_cockpit_runtime_contract.py -v`
   — all pass.

If any step fails, stop and report — don't paper over with a
try/catch.

---

## 5. Rollback criteria

Revert W309 step 1 if any of:

- Bundle size grows past **80 KB raw** / **25 KB gzipped** (current
  baseline: 27 KB raw / 7 KB gzipped). Soft cap; ~50 KB raw is
  realistic for the MVP runtime modules.
- TARS.app fails to boot (Tauri error overlay, blank window).
- Sidecar can be reached via `curl http://127.0.0.1:8765/api/voice/health`
  but cockpit shows "Voice unreachable".
- `pytest tests/test_cockpit_*` fails.

Revert is one `git revert <w309-step1 sha>`. The frozen bundle is
re-stagable via `bash desktop/scripts/package-cockpit.sh --legacy`
in < 1 min if the operator needs the desktop app working *right now*
during debugging.

---

## 6. Out of scope for W309 (queue for W310+)

- Council deliberation (`/api/council/deliberate`).
- Playbooks (`/api/playbooks`, `/api/playbooks/{id}`).
- Search palette (`/api/search`).
- Wallet / billing (`/api/wallet`, `/api/usage`).
- T2T pairing (`/api/pairing`).
- Awareness stream rendering — endpoint exists, but it feeds the
  background-TARS sidebar which isn't on the "operator can talk"
  critical path.
- Meeet bridge (`/api/meeet/*`) — only relevant when the brother's
  `api.meeet.world` is in production-mode flips.
- Recovery flow (`/api/recovery`).
- Drawers (`⌘K` / `⌘L` / `⌘R`) — separate W310 module each.

If new scope surfaces during W309 step 1, stop and write a W309 step 2
brief — don't expand step 1.

---

## 7. Commit message (suggested)

```
feat(cockpit): W309 step 1 — runtime restore (mic + WS + chat + TTS)

Restores the four behaviors that the W308 step-3 bundle swap left
empty: microphone capture, WebSocket to sidecar (ws://127.0.0.1:8765),
chat thread send/load, and ElevenLabs TTS playback. Cockpit can now
hold a conversation again.

New modules under apps/cockpit/src/runtime/:
- ws.ts        — single WebSocket manager, exponential backoff,
                 typed event bus.
- voice.ts     — mic capture (getUserMedia), TTS playback queue,
                 persona state.
- chat.ts      — thread send/load, optimistic strand append.
- api.ts       — typed fetch wrapper, error envelope.
- tauri.ts     — IPC helpers; no-op outside Tauri runtime.

cockpit-entry.ts extended to wire all four on mount; teardown on
cockpit unmount cleanly releases mic + closes WS.

Bonus: replaced six remaining `10px Share Tech Mono` call-sites in
cockpit.html and hero.html with var(--font-size-phase-bar) — closes
the carryover Claude flagged on step-4 verify (.source-chip,
.gate-head, .send-kbd, status bar, two hero meta lines).

Drift suite grew 10 → 11 tests. New test_cockpit_runtime_contract.py
adds 3 static-shape checks for the new runtime modules (no network).

Bundle: 27 KB raw → ~48 KB raw / ~13 KB gzipped (well under the 80 KB
soft cap). Legacy still available via `package-cockpit.sh --legacy`.

Functional restore is MVP-scoped: 19 of the 25 endpoints the legacy
SPA called are NOT in this wave. Council, playbooks, search, wallet,
pairing, meeet bridge, awareness rendering, recovery, drawers — all
queued for W310+ (see W309_FUNCTIONAL_RESTORE_BRIEF.md §6).

Co-authored-by: Claude <claude@anthropic.com>  # for the W309 brief
```

---

## 8. Estimated cost

- **Restoring runtime skeleton (3.1):** 15 min.
- **WebSocket manager (3.2):** 45 min.
- **Voice loop (3.3):** 90 min.
- **Chat thread (3.4):** 60 min.
- **Vault status hook (3.5):** 20 min.
- **10px cleanup (3.6):** 15 min.
- **Tests (3.7):** 30 min.
- **Manual verify (§4):** 10 min.

Total: ~4–5 hours of careful work. Acceptable for one Cursor session.

---

## 9. Why this brief is gated on operator OK

Per `W308_PRE_FLIGHT_FINDINGS.md` § "Step 4 shipped" closing
paragraph:

> Functional restore (mic, WS, conversation) is still W309+ and
> explicitly **gated on operator OK**.

The cockpit currently boots, looks correct, and respects the W307
verdict. The behavioral regression is real but contained: TARS.app
shows the right interface but can't operate. The operator may prefer
to ship v9.1.0 with the legacy bundle (`--legacy`) first, get Apple
cert sorted, and pick W309 up after. **Do not start W309 step 1
without an explicit "go".**

When the operator says "go", this brief is ready.
