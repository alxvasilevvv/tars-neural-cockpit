# W309 step 2 — behavioural coverage + STT + persona picker

> **Author.** Cursor (Sonnet 4.6).
> **Audience.** Cursor — owns the W309 step 2 implementation lane.
> **Status.** Draft — **gated on PR #187 merge + operator OK** (see § 9).
> **Purpose.** Close the three biggest gaps left by W309 step 1: no
> behavioural tests, mic permission goes nowhere, no voice picker UI.
> One bounded session, ~3–4 hours.

---

## 0. Why a step 2 exists

W309 step 1 (PR #187, `545cd4d`) restored the four MVP behaviours and
landed 31/31 contract tests, but three honest gaps remain:

1. **All 20 runtime tests are static.** They grep source for the right
   strings, prove imports and shape, and catch removals. They do **not**
   prove the cockpit can hold a conversation end-to-end. Claude's PR #187
   review made this explicit: *"the cheapest behavioral guard you'd
   actually trust"* is a Playwright smoke against a mock SSE server.
2. **Mic permission goes nowhere.** `voice.ensureMic()` requests
   `getUserMedia({audio: true})` and caches the `MediaStream`, but the
   stream is never piped to `/api/voice/transcribe`. The mic button
   toggles a state badge; the operator gets no transcript. This was
   deliberate in step 1 (brief §3.3 marked STT as W310+), but it leaves
   the voice loop half-open.
3. **Voice picker has no UI.** `voice.getPersonas()` and `voice.setPersona(id)`
   exist; the status bar reads `Voice · …` from `/api/voice/health` but
   never surfaces the persona list. Operators can't pick Jarvis vs
   GLaDOS without touching localStorage.

Step 2 closes all three in one bundle. Anything bigger (drawers,
council, playbooks, etc.) stays on the W310+ queue per W309 brief §6.

---

## 1. Inventory — what's already in place

### 1.1. Behavioural-test substrate

- Playwright is **not yet in `package.json`**. Brief §3.1 adds
  `@playwright/test` as a dev-only dep under `apps/cockpit/package.json`.
- `pytest` already runs the static contract tests; the new Playwright
  spec runs via `pnpm --filter @tars/cockpit test:e2e` and is wired
  into `make ci-cockpit` (new target) but not yet into the broader
  `make ci` (kept opt-in until the harness proves stable).

### 1.2. STT endpoint

- `web_extras/routers/voice.py` exposes `POST /api/voice/transcribe`
  (per `backend/core/voice/__init__.py` — Phase L4 shipped this).
  Accepts `multipart/form-data` with a single `audio` field, returns
  `{ok: bool, text: str, engine: str, confidence?: float}`.
- Browser-side capture uses `MediaRecorder` (well-supported in modern
  Chromium / WebKit; the legacy SPA used the older
  `webkitSpeechRecognition` browser API which we deliberately skip —
  it's Chrome-only and the sidecar STT is the source of truth).

### 1.3. Persona list

- `voice.getPersonas()` returns the array fetched on `setup()`.
- `voice.setPersona(id)` mutates the in-module state but doesn't
  persist. Step 2 adds localStorage persistence so the choice survives
  reloads (per W309 step 1 brief §3.3 — explicitly deferred).
- `apps/cockpit/cockpit.html` status bar (~L690) is where the picker
  lands. CSS already supports `[data-state]` on status spans (added
  in step 1).

---

## 2. Restoration strategy

**No new runtime modules.** Step 2 extends the existing five:

| File | Change |
|---|---|
| `apps/cockpit/src/runtime/voice.ts` | + `startRecording()` / `stopRecording()` / `getTranscript()` |
| `apps/cockpit/src/pages/cockpit-entry.ts` | + persona picker render, + STT button binding, + transcript→input wiring |
| `apps/cockpit/cockpit.html` | + persona `<select>` markup in status bar + STT button next to mic |
| `apps/cockpit/src/styles/global.css` | + minimal styles for `.persona-picker` + `.stt-btn` |
| `tests/test_cockpit_runtime_contract.py` | + 5 new pin-ups (STT endpoint, MediaRecorder ref, persona picker DOM, localStorage knob, e2e harness presence) |
| `apps/cockpit/tests/e2e/` | **NEW** — Playwright spec, mock sidecar, fixture audio |

**No framework, no React, no Vue.** Same vanilla-TS contract as step 1.

### 2.1. What *not* to do

- **Don't add MediaRecorder polyfills.** Modern Tauri WebView (WKWebView
  / WebView2) supports it natively; if WKWebView lacks a specific
  codec, fall back gracefully to "STT unavailable" rather than ship a
  polyfill. Step 3 can revisit if a real codec gap surfaces.
- **Don't replace the strand renderer with a virtual DOM.** Step 1's
  full re-render approach is fine for ≤ 20 messages. The Claude review
  flagged "re-render the whole list" as cheap-and-correct; don't
  optimise prematurely.
- **Don't add WS chat-message reconciliation.** Brief §3.4 already
  noted that SSE-on-POST is the right transport at MVP; WS handles
  cross-cutting events (typing indicators, multi-device sync) in
  W310+ when those endpoints actually exist.
- **Don't expand contract tests to assert exact behaviour.** Keep them
  as "catch the bug class, allow implementation flexibility" per the
  step 1 fix-up philosophy.

---

## 3. Sub-tasks (do in this order)

### 3.1. Playwright behavioural smoke

Add `@playwright/test` as a dev dep under `apps/cockpit/package.json`.
Lock to a specific minor (e.g. `1.49.x`) to keep the install
deterministic. Browsers downloaded on first run only — gate behind
`pnpm --filter @tars/cockpit exec playwright install --with-deps chromium`
which the make target wraps.

Create `apps/cockpit/tests/e2e/cockpit.spec.ts`:

- **Mock sidecar.** Use Playwright's `page.route()` to intercept
  `**/api/**`. Return canned JSON for `/api/voice/personas`,
  `/api/voice/health`, `/api/vault/status`, `/api/chat/threads`.
- **Mock SSE.** `page.route()` for
  `**/api/chat/threads/*/messages` returns a streamed body that emits
  three SSE frames (`event: trace`, then two `data:` deltas, then
  `event: stream.closed`). Asserts the frame parser turns these into
  a growing assistant bubble.
- **Mock WebSocket.** Stub via `page.addInitScript()` that replaces
  `window.WebSocket` with a class that fires `open` on next tick and
  emits a `hello` envelope. Asserts the backend badge flips to online.
- **Assertions** (the minimum that proves the behaviour is wired):
  1. After mount: backend badge has `data-state="online"`, voice
     badge has `data-state="online"` (mocked health), persona picker
     lists the mocked personas.
  2. Typing "hello" + Enter: user message appears in strand with
     `data-status="delivered"`, then assistant bubble appears and
     grows as deltas arrive.
  3. After SSE close: assistant bubble has `data-status="delivered"`.
  4. Empty vault response: vault CTA renders with `"Add key"` link
     and `rel="noopener noreferrer"`.
- **No real mic.** Permission flow uses
  `context.grantPermissions(['microphone'])` to bypass the OS prompt
  but we never call `getUserMedia` in the spec — covered separately
  by the static `test_voice_ensure_mic_*` tests.

Acceptance:
`pnpm --filter @tars/cockpit test:e2e` passes locally. Spec runs in
**< 10s** on the host (the bar Claude implicitly set with "cheapest
behavioral guard"). Make target `make ci-cockpit` runs static + e2e.

### 3.2. STT upload (`runtime/voice.ts` extension)

Add three exports:

```ts
export async function startRecording(): Promise<void>
export async function stopRecording(): Promise<string>  // resolves with transcript
export function isRecording(): boolean
```

Implementation contract:

- `startRecording()` requires `ensureMic()` first (don't request twice).
  Constructs a `MediaRecorder(stream, { mimeType })` — `mimeType`
  resolution order:
  1. `audio/webm;codecs=opus` (Chromium native, smallest)
  2. `audio/mp4` (WKWebView default)
  3. browser default (let the UA pick)
  Pin the chosen type in `state.recordingMime` so the upload
  `Content-Type` matches.
- `stopRecording()` flushes the recorder, packs chunks into a single
  `Blob`, builds `FormData`, POSTs to `/api/voice/transcribe` via
  `apiBinary` (well, a variant — see below). Returns the `text` field
  or throws `ApiError`.
- The transcribe endpoint takes multipart, not JSON. Add `apiMultipart`
  to `runtime/api.ts` as a new helper (small — ~20 LoC). Same
  defensive content-type checks as `apiBinary`.
- Concurrent `startRecording()` calls (double-click) short-circuit
  the second one — same pattern as `ensureMic()`'s `micPromise`.
- `teardown()` aborts any in-flight recording, stops the recorder,
  drops queued chunks.

In `cockpit-entry.ts`: STT button binds to a single click handler.
Click while idle: `startRecording()` + flip button to recording state.
Click while recording: `stopRecording()` → drop transcript into the
input textarea (preserving any text the operator typed). If transcribe
fails, surface in the status bar (`Voice · STT failed`) for 3s.

Acceptance:
- Static: `test_voice_module_shape` extended with `/api/voice/transcribe`
  + `MediaRecorder` checks.
- Behavioural: Playwright spec mocks the transcribe endpoint and
  asserts the input fills with the canned transcript after the
  stop-recording click.
- Manual (§4): real mic → real sidecar → real transcript appears.

### 3.3. Persona picker UI

Minimal `<select>` in the status bar (between the backend and voice
badges). Options come from `voice.getPersonas()`; selecting one calls
`voice.setPersona(id)` and persists to
`window.localStorage.TARS_VOICE_PERSONA`. On `voice.setup()`, restore
the saved id if it still exists in the persona list (fall back to
server default if not).

CSS: match the status bar's `Share Tech Mono` 11px treatment. Use
`<select>` not a custom dropdown — keyboard accessibility + screen
reader support are free.

Acceptance:
- Picker visible in the status bar with the persona list.
- Reload preserves the choice.
- `/api/voice/personas` returns empty array → picker hidden (no
  empty `<select>`).
- New `test_persona_picker_persists_choice` + `test_persona_picker_hidden_when_no_personas`
  (both Playwright).

### 3.4. Tests — five new static pin-ups + Playwright suite

Add to `tests/test_cockpit_runtime_contract.py`:

```python
def test_voice_module_supports_stt_upload() -> None:
    """voice.ts must call /api/voice/transcribe and use MediaRecorder."""

def test_persona_picker_persists_to_localstorage() -> None:
    """cockpit-entry must read/write TARS_VOICE_PERSONA on the picker."""

def test_cockpit_html_includes_persona_picker_mount() -> None:
    """cockpit.html must declare the persona <select> the picker binds against."""

def test_cockpit_html_includes_stt_button() -> None:
    """cockpit.html must declare the .stt-btn next to .mic."""

def test_e2e_suite_present_under_apps_cockpit() -> None:
    """apps/cockpit/tests/e2e/cockpit.spec.ts must exist with @playwright/test."""
```

Total: 20 (step 1) + 5 = **25 static runtime contract tests** + the
Playwright suite (separate runner, separate make target). All static
tests stay sub-second; Playwright stays < 10s.

### 3.5. Documentation

- Update `docs/handoff/W309_FUNCTIONAL_RESTORE_BRIEF.md` § 6 — strike
  STT and persona picker off the W310+ list, add a "(shipped in step 2)"
  marker.
- Update `docs/CHANGELOG_AGENTS.md` per step-1 conventions (technical
  summary, files, verification).
- Update `docs/AGENT_HANDOFF.md` SYNC line.

---

## 4. Verification protocol (~15 min)

**Pre-flight:**

1. PR #187 must be merged to `main` (W309 step 1 baseline).
2. `git checkout -b cursor/w309-step2-coverage` (or equivalent fresh
   branch name).
3. `bash desktop/scripts/package-cockpit.sh` — build clean.

**Static + Playwright:**

4. `pnpm --filter @tars/cockpit exec tsc --noEmit` — clean.
5. `python3 -m pytest tests/test_cockpit_runtime_contract.py tests/test_cockpit_tokens_sync.py -v` — **36/36 green** (11 drift + 25 runtime).
6. `pnpm --filter @tars/cockpit test:e2e` — Playwright spec passes in < 10s.

**Manual (live daemon):**

7. Boot `tars-daemon` per `docs/handoff/STARTUP.md`.
8. `open /Applications/TARS.app` (rebuild via REBUILD-TARS-APP.command
   if signing changed).
9. Click STT button → permission prompt → grant → speak a 3-second
   phrase → click again → transcript appears in input box. If
   transcript is wrong, that's an STT engine issue, not a W309 step 2
   bug — log and move on.
10. Open persona picker → change persona → speak again or send chat
    with `/api/voice/speak` → reply uses the new persona voice. Reload
    the page → picker still shows the new choice.
11. Type "hello" + Enter → message in strand → reply streams in token-
    by-token (SSE working).

If any step 4–6 fails, fix before commit. If step 7–11 fails, root-
cause first — it's usually a sidecar setup issue, not the cockpit.

---

## 5. Rollback criteria

Revert W309 step 2 if any of:

- Bundle grows past **35 KB raw** / **12 KB gzipped** (current step-1
  baseline: 22.9 / 8.4 KB). The estimated overhead for STT + picker +
  glue is **~6–8 KB raw**; the cap leaves headroom but flags bloat.
- Playwright spec is flaky in CI (> 1 in 20 fails on a stable PR).
  Better to revert and re-engineer the mock than to ship a flaky
  guard.
- TARS.app fails to boot.
- Any of the 36 contract tests fails.

Revert is one `git revert <step2 sha>`. No bundle re-staging needed —
step 1's `cockpit-CGVJOS_p.js` reasserts as the staged artefact.

---

## 6. Out of scope for step 2 (still W310+)

Unchanged from W309 step 1 brief §6:

- Council deliberation, playbooks, search, wallet, T2T pairing, meeet
  bridge, awareness stream rendering, recovery, drawers (⌘K / ⌘L /
  ⌘R).

Plus deliberately deferred from step 2:

- **Waveform visualiser.** Cool, but not on the "TARS can transcribe"
  critical path. Step 1 + 2 prove the loop; viz is W311+ polish.
- **Voice cloning kit UI.** Brief `docs/VOICE_CLONING_OPERATOR.md`
  covers the operator flow; cockpit surface is a separate wave.
- **`webkitSpeechRecognition` fallback.** Chromium-only, server STT is
  the source of truth. If `/api/voice/transcribe` is down, surface
  "STT unavailable" rather than degrade to a different transport.
- **STT streaming (vs the upload-after-stop pattern).** Streaming
  requires `MediaRecorder` chunks pumped over a WebSocket; the
  upload-after-stop pattern is the cheapest correct loop and is what
  the sidecar accepts today.
- **Per-persona TTS preview button.** Operators can already test by
  typing in chat and getting a reply. A dedicated preview is W311
  polish.

If new scope surfaces during step 2, stop and write a step 3 brief.
Don't expand step 2.

---

## 7. Commit message (suggested)

```
feat(cockpit): W309 step 2 — behavioural coverage + STT + persona picker

Closes the three gaps left by W309 step 1 (PR #187): no behavioural
tests (all 20 runtime tests were static greps), mic permission went
nowhere (no STT upload), and voice persona had no operator UI.

Behaviour:
- voice.ts extended with startRecording / stopRecording / isRecording.
  MediaRecorder picks the best supported mimeType (webm/opus preferred,
  mp4 fallback for WKWebView). stopRecording packs chunks into a
  multipart upload to /api/voice/transcribe; transcript drops into the
  input textarea.
- New api.apiMultipart helper for the multipart endpoint (same
  defensive content-type guards as apiBinary).
- Persona picker added to the status bar — minimal <select> driven by
  voice.getPersonas(), persists choice via window.localStorage
  TARS_VOICE_PERSONA, restores on next setup() if the persona still
  exists server-side.

Tests:
- 5 new static pin-ups in tests/test_cockpit_runtime_contract.py
  (STT endpoint, MediaRecorder ref, picker DOM, localStorage knob,
  e2e suite presence). Total: 11 drift + 25 runtime = 36 green.
- NEW Playwright behavioural smoke in apps/cockpit/tests/e2e/cockpit.spec.ts
  — mocks sidecar (page.route), mocks SSE (streamed response body),
  mocks WebSocket (init script). Asserts: backend badge flips online,
  user message + assistant deltas render correctly, vault CTA has
  noreferrer, persona picker persists choice. Runs in < 10s.
- New make target `make ci-cockpit` runs static + e2e together.
  Not wired into top-level `make ci` yet — kept opt-in until the
  Playwright harness proves stable in CI.

Bundle: ~22.9 KB raw → ~30 KB raw / ~10 KB gzipped (well under the
35 KB rollback cap). Legacy still available via package-cockpit.sh
--legacy.

Strikes STT + persona picker off the W309 brief §6 W310+ queue.
Drawers, council, playbooks, wallet, pairing, meeet bridge, awareness
rendering, recovery — all still queued for W310+.

Co-authored-by: Cursor <cursor@anysphere.com>  # for the W309 step 2 brief
```

---

## 8. Estimated cost

- **Playwright suite (3.1):** 90 min.
- **STT upload (3.2):** 60 min.
- **Persona picker (3.3):** 30 min.
- **Tests (3.4):** 30 min.
- **Docs (3.5):** 20 min.
- **Manual verify (§4):** 15 min.

Total: ~4 hours of careful work. One Cursor session. **Smaller than
step 1** — most of the runtime substrate already exists.

---

## 9. Why this brief is gated on PR #187 merge

Step 2 extends `runtime/voice.ts`, `cockpit-entry.ts`, and the
contract test file — all three are in flight on PR #187. Starting
step 2 before merge guarantees rebase conflict and would force a
re-review of step 1 changes folded into step 2.

Operator action:
1. Merge PR #187 (W309 step 1 + fix-up).
2. Say "go" on step 2.
3. Cursor picks this brief up and ships it in one session.

If the operator wants to defer step 2 entirely — e.g. to ship
v9.1.0 with step-1 functionality and accept the gaps — that's a
valid call. The three gaps are real but not blocking:

- **No behavioural tests** → still ship, but eyeball any future
  runtime changes more carefully.
- **No STT** → operators can still type-and-Enter; mic button is a
  placeholder.
- **No picker UI** → power-users can switch persona via
  `localStorage.setItem('TARS_VOICE_PERSONA', 'jarvis')` + reload.

If those tradeoffs are acceptable, queue this brief for W310 and
move to higher-value waves (council, playbooks, drawers per the
W310+ pile).
