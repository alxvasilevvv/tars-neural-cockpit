# Phase 2 — STT streaming relay + push-to-talk (v10.1)

**Authoring agent:** Cursor agent (Claude Opus 4.7), W310-g (continuation)
**Authoring date:** 2026-05-18
**Implementer:** TBD (next L4-lane Cursor/Claude session)
**Target release:** `v10.1.0` (post-GA polish window)
**Depends on:** W309 step 2 merged on `main` (mic capture + multipart `/api/voice/transcribe` flow established in cockpit)
**Blocked by:** PR #187 → W309 step 2 implementation → this brief
**Phase ID in master plan:** `ph2-stt` (also see `ph2-voice-gallery`, separate brief)

---

## 1. Why this brief exists

W309 step 2 lands a working voice loop: hold-to-talk → record blob →
multipart POST `/api/voice/transcribe` → wait for full transcript →
send to chat. **That flow works**, but it has two operator-visible
problems on real hardware:

1. **Perceived latency.** Operator releases the mic, then waits for
   the full audio to upload AND the full whisper inference to
   complete before seeing any text. On a 30 s utterance with OpenAI
   Whisper this is typically 3-5 s of silent dead time.
2. **Cloud spend on offline-capable workloads.** The default chain
   (`whisper.cpp → openai → faster-whisper`) means when neither
   whisper.cpp binary nor a faster-whisper model is configured —
   which is **the default after a fresh install** — every utterance
   hits OpenAI. v10 is positioned as local-first; the default voice
   loop should be local too.

Phase 2 fixes both:

- **Streaming protocol** — WebSocket `/api/voice/stt/stream` with
  partial-transcript events so the operator sees text within ~200 ms
  of the first phoneme, not after full inference completes.
- **faster-whisper as primary local engine** with a **warm model
  cache** so cold-load latency (currently 1-3 s per request) drops
  to ~0 ms after first warm-up.
- **Push-to-talk semantics** with three modes: hold-to-talk (current),
  toggle-to-talk (operator-configurable hotkey), and VAD endpointing
  (auto-stop when silence detected for N ms).

---

## 2. Goals / non-goals

### Goals

| ID | Goal | Acceptance |
| -- | ---- | ---------- |
| G1 | Partial transcripts visible during utterance | TTFT (time-to-first-text) ≤ 400 ms p50, ≤ 800 ms p95 on stock 16-core M1 with `faster-whisper-medium` |
| G2 | Final transcript latency improvement | End-to-final ≤ 1.2× audio duration p50 (was: ~2.5× on OpenAI Whisper for short utterances) |
| G3 | Local-first by default for fresh installs | `faster-whisper-base` shipped or auto-downloaded post-install; cloud chain only if explicitly configured |
| G4 | Push-to-talk hotkey | Operator can bind hotkey via cockpit settings; works while focus is anywhere in cockpit |
| G5 | VAD endpointing (optional) | Toggle in cockpit; auto-stop after 800 ms silence (configurable 300-2000 ms) |
| G6 | Backwards-compat | Existing `POST /api/voice/transcribe` keeps working byte-for-byte; clients that haven't migrated to WS still work |

### Non-goals

- **Diarisation / speaker separation.** Whisper doesn't do it natively. Punt to Phase 6+ if ever.
- **Real-time translation.** Whisper has a `translate` task but we're not exposing it in v10.1; Phase 2 is monolingual-output only.
- **Cloud-streaming providers** (e.g. AssemblyAI realtime, Deepgram WebSocket). Local-first focus. If we later expose them, they go through the same WS contract behind a `provider` selector.
- **Mobile** — iOS/Android push-to-talk lives in Phase 9 (`ph9-native-speech`).

---

## 3. Current state baseline (as of `v10.0.0-rc.1`)

### Backend

- `backend/core/voice/transcribe.py` — single-shot `transcribe_bytes(audio: bytes, ...)` (lines 332-439).
  - Engine fallback chain: `whisper.cpp → OpenAI Whisper → faster-whisper`.
  - **faster-whisper is last in the chain** — only used when env-configured AND `whisper.cpp` binary is missing AND no OpenAI key.
  - **No model warming** — `WhisperModel(model_path, device="auto", compute_type="auto")` is constructed on every request (line 311).
  - Stdlib-only OpenAI path (manual multipart, `urllib`).
- `web_extras/routers/voice.py:transcribe_endpoint` — accepts multipart `audio` field, returns full JSON envelope after inference completes.
- `web_extras/routers/voice.py:health_endpoint` — `is_configured()` reports which provider would be used.

### Cockpit

- After W309 step 2: hold-to-talk button → `MediaRecorder` blob → `fetch('/api/voice/transcribe', {method:'POST', body: form})` → render text in chat input.
- No WebSocket for STT yet (WS is already used for chat/TTS events per W309 step 1; we'll add a second WS endpoint for STT).

### Deps

- `requirements.txt` only declares `fastapi==0.136.1`. **`faster-whisper` is not pinned** — current code uses `importlib.import_module("faster_whisper")` with try/except. For Phase 2 we'll **add it as a hard dep** so local-first is the default.

---

## 4. Target architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Cockpit (apps/cockpit/src/pages/cockpit-entry.ts + voice/)      │
│                                                                  │
│  ┌──────────────┐    ┌──────────────────┐   ┌──────────────────┐ │
│  │ Hotkey mgr   │───▶│ MicCapture       │──▶│ STTStreamClient  │ │
│  │ (hold/toggle)│    │ (MediaRecorder + │   │ (WebSocket)      │ │
│  └──────────────┘    │  AudioWorklet)   │   └────────┬─────────┘ │
│                      └──────────────────┘            │           │
│                                                       ▼          │
│                                            ┌──────────────────┐  │
│                                            │ TranscriptBuffer │  │
│                                            │ (partial→final)  │  │
│                                            └────────┬─────────┘  │
└─────────────────────────────────────────────────────│────────────┘
                                                     │ WS frames
                  ┌──────────────────────────────────▼──────────────┐
                  │ web_extras/routers/voice_stt_ws.py              │
                  │   POST /api/voice/stt/stream (WebSocket upgrade)│
                  └──────────────────────────────────┬──────────────┘
                                                     │
                  ┌──────────────────────────────────▼──────────────┐
                  │ backend/core/voice/stt_stream.py                │
                  │   StreamingTranscriber (chunked + warm model)   │
                  │   ├─ FasterWhisperWarm (singleton + lock)       │
                  │   ├─ WhisperCppPipe (stdin/stdout streaming)    │
                  │   └─ OpenAIWhisperBatched (fallback, batches)   │
                  └─────────────────────────────────────────────────┘
```

### Component roles

| Component | Responsibility | New file or modify? |
| --------- | -------------- | ------------------- |
| `Hotkey mgr` | Keyboard hotkey binding; emits start/stop events | NEW `apps/cockpit/src/voice/hotkey.ts` |
| `MicCapture` | `getUserMedia` + `MediaRecorder` slice streaming (250 ms chunks) | NEW `apps/cockpit/src/voice/mic_capture.ts` |
| `STTStreamClient` | WS lifecycle, framing, reconnect | NEW `apps/cockpit/src/voice/stt_stream_client.ts` |
| `TranscriptBuffer` | Merge partial events into final transcript with stable prefix | NEW `apps/cockpit/src/voice/transcript_buffer.ts` |
| `voice_stt_ws.py` | WS endpoint, frame routing, auth | NEW `web_extras/routers/voice_stt_ws.py` |
| `stt_stream.py` | StreamingTranscriber orchestrator | NEW `backend/core/voice/stt_stream.py` |
| `transcribe.py` | Keep `transcribe_bytes` for back-compat REST | MODIFY (no breaking changes) |

---

## 5. API contracts

### 5.1 New WebSocket endpoint

**Path:** `WS /api/voice/stt/stream`
**Subprotocol:** `tars.stt.v1`
**Auth:** Same as `/api/voice/transcribe` — pass `X-Tars-Session-Id` as a connection header.

#### Client→server frames

All frames JSON-encoded as text frames OR raw binary frames per type:

| Frame | Direction | Encoding | Shape |
| ----- | --------- | -------- | ----- |
| `start` | C→S | text JSON | `{type:"start", language?:string, model?:string, vad?:{enabled:bool, silence_ms:int}, mime:"audio/webm;codecs=opus"}` |
| `audio_chunk` | C→S | binary | raw Opus/WebM container chunk from `MediaRecorder` |
| `stop` | C→S | text JSON | `{type:"stop", reason:"hotkey_release"\|"vad_silence"\|"user_cancel"}` |
| `ping` | C→S | text JSON | `{type:"ping"}` — keep-alive every 15 s |

#### Server→client frames

| Frame | Direction | Encoding | Shape |
| ----- | --------- | -------- | ----- |
| `ready` | S→C | text JSON | `{type:"ready", session_id:string, provider:"faster_whisper"\|"whisper_cpp"\|"openai_whisper", model:string}` |
| `partial` | S→C | text JSON | `{type:"partial", text:string, stable_prefix_len:int, started_ms:int, elapsed_ms:int}` |
| `final` | S→C | text JSON | `{type:"final", text:string, language:string, duration_ms:int, elapsed_ms:int, model:string, provider:string, segments_count:int}` |
| `error` | S→C | text JSON | `{type:"error", code:string, message:string, retriable:bool}` |
| `pong` | S→C | text JSON | `{type:"pong"}` |

#### Lifecycle

```
C: WS upgrade with X-Tars-Session-Id
S: → ready {provider, model}
C: → start {language:"ru", vad:{enabled:true, silence_ms:800}}
C: → audio_chunk (binary, 250 ms)
S: → partial {text:"привет ка", stable_prefix_len:0, elapsed_ms:230}
C: → audio_chunk (binary, 250 ms)
S: → partial {text:"привет какой", stable_prefix_len:7, elapsed_ms:480}
C: → audio_chunk (binary, 250 ms)
S: → partial {text:"привет какой сегодня день", stable_prefix_len:13, elapsed_ms:730}
C: → stop {reason:"vad_silence"}
S: → final {text:"Привет, какой сегодня день?", language:"ru", duration_ms:2300, elapsed_ms:1980, ...}
S: close 1000
```

**`stable_prefix_len`** is critical for the cockpit's `TranscriptBuffer`:
characters `[0, stable_prefix_len)` of `text` are guaranteed to be
final across subsequent `partial` frames. Everything after is allowed
to mutate as the model gets more context.

### 5.2 REST endpoint (back-compat, unchanged)

`POST /api/voice/transcribe` — keep exactly as-is. Returns 200 with
full envelope OR 503 `no_stt_backend` OR 413 `audio_too_large`. No
new fields, no new query params. Old clients (`/scripts/qa_*.sh`,
`test_voice_stt.py`) keep working.

### 5.3 Health endpoint update

`GET /api/voice/health` adds **one** field under `stt`:

```diff
 "stt": {
   "configured": true,
   "provider": "faster_whisper",
   "model": "base",
   "local_path": "/Users/.../models/faster-whisper-base",
   "whisper_cpp_bin": null,
+  "streaming_supported": true
 }
```

`streaming_supported` is true iff the chosen provider can chunk-feed
(faster-whisper: yes, whisper.cpp: yes via stdin pipe, openai: no —
falls back to batched final-only emission).

---

## 6. Implementation steps (mechanical)

Each step is independently mergeable. Land in order; each step has its
own PR.

### Step 1 — Hard-pin faster-whisper + warm model singleton

**Branch:** `cursor/ph2-stt-step1-warm-model`
**Files:**
- `requirements.txt` — add `faster-whisper>=1.1.0,<2.0.0` and `ctranslate2>=4.5.0,<5.0.0`.
- `backend/core/voice/stt_stream.py` (NEW) — module with:

  ```python
  class FasterWhisperWarm:
      _instance: WhisperModel | None = None
      _lock = asyncio.Lock()
      _model_path: str | None = None

      @classmethod
      async def get(cls, model_path: str) -> WhisperModel:
          async with cls._lock:
              if cls._instance is None or cls._model_path != model_path:
                  cls._instance = await asyncio.to_thread(
                      WhisperModel, model_path,
                      device="auto", compute_type="auto",
                  )
                  cls._model_path = model_path
              return cls._instance

      @classmethod
      async def evict(cls) -> None:
          async with cls._lock:
              cls._instance = None
              cls._model_path = None
  ```

- `backend/core/voice/transcribe.py` — refactor `_run_faster_whisper` to use `FasterWhisperWarm.get(...)` instead of instantiating per request. **No public API change.**

**Tests:**
- `tests/test_stt_warm_model.py` (NEW) — assert that two consecutive calls share the model instance (mock `WhisperModel` and count construction).
- `tests/test_voice_stt.py` — must still pass.

**Acceptance:**
- 2nd faster-whisper call cold-load delta ≤ 50 ms (test by recording two `time.perf_counter()` deltas on a mocked model).

---

### Step 2 — `StreamingTranscriber` class + WS endpoint scaffold

**Branch:** `cursor/ph2-stt-step2-ws-scaffold`
**Files:**
- `backend/core/voice/stt_stream.py` — add `StreamingTranscriber` orchestrator with `feed_chunk(bytes)` and `finalize()` methods. For step 2 it can buffer everything and only emit a single `final` at `finalize()` — no real streaming yet, just wire the contract.
- `web_extras/routers/voice_stt_ws.py` (NEW) — FastAPI WS endpoint implementing the framing contract from §5.1. Subprotocol negotiation, auth header check, frame router.
- `web_extras/app.py` — register the new router.

**Tests:**
- `tests/test_voice_stt_ws.py` (NEW) — use `httpx.AsyncClient` + `websockets` (FastAPI test client supports WS). Cover:
  - Subprotocol mismatch → close 1002
  - Missing `X-Tars-Session-Id` → close 1008
  - Happy path: `start` → 3× `audio_chunk` → `stop` → expect 1× `ready`, 1× `final`, close 1000
  - `start` with unsupported `mime` → `error` frame with `code:"unsupported_mime"`, retriable:false

**Acceptance:**
- 30 tests min, all passing.
- Contract documented in `docs/api/voice_stt_stream.md` (NEW, auto-generated stub OK).

---

### Step 3 — Real chunked transcription (faster-whisper streaming)

**Branch:** `cursor/ph2-stt-step3-real-streaming`
**Files:**
- `backend/core/voice/stt_stream.py` — `StreamingTranscriber.feed_chunk` now decodes incremental WebM chunks (use `pyav` or `soundfile` + `aiortc.codecs` — pick whichever has the smaller install footprint; preference: `soundfile` if it can handle WebM/Opus, else `pyav`).
  - Accumulate PCM frames into a rolling window.
  - After every N ms of new audio (default 500 ms), run `WhisperModel.transcribe` on the window with `beam_size=1, condition_on_previous_text=False, vad_filter=False`.
  - Compute `stable_prefix_len` by diffing previous partial with new partial — longest common prefix length.
  - Emit `partial` frame via the WS callback.
- `requirements.txt` — add audio decoder dep (`soundfile>=0.12.1` or `av>=12.0.0`).

**Tests:**
- `tests/test_stt_streaming_transcriber.py` (NEW) — feed a 5 s test WAV (commit a small WAV fixture under `tests/fixtures/voice/`) in 250 ms chunks, assert at least 3 `partial` frames before `final`.
- TTFT regression: assert first `partial` emitted within 600 ms of first chunk on mock-fast-transcribe (real perf is hardware-dependent; the test asserts the orchestration latency only).

**Acceptance:**
- Real human speech test on M1: TTFT ≤ 400 ms p50 (manual ops verification, not CI gate).

---

### Step 4 — VAD endpointing

**Branch:** `cursor/ph2-stt-step4-vad`
**Files:**
- `backend/core/voice/stt_stream.py` — integrate `webrtcvad` (~30 KB pure-Python wrapper around WebRTC's VAD). After every chunk, check if last 800 ms (configurable) was silence; if yes AND `vad.enabled` AND not at start, trigger auto-`finalize()` and emit `final`.
- `requirements.txt` — add `webrtcvad>=2.0.10`.

**Tests:**
- `tests/test_stt_vad.py` (NEW) — feed silence-padded test audio, assert auto-finalize fires at expected boundary.

**Acceptance:**
- VAD disabled: existing tests unchanged.
- VAD enabled + 1 s of silence after 2 s of speech: `final` arrives within 800-1200 ms of silence start.

---

### Step 5 — Cockpit WS client

**Branch:** `cursor/ph2-stt-step5-cockpit-client`
**Files:**
- `apps/cockpit/src/voice/mic_capture.ts` (NEW) — `MediaRecorder` with `timeslice=250` calling a callback per chunk.
- `apps/cockpit/src/voice/stt_stream_client.ts` (NEW) — WS lifecycle, frame parsing, exposed as event-emitter (`onPartial`, `onFinal`, `onError`).
- `apps/cockpit/src/voice/transcript_buffer.ts` (NEW) — merges partials respecting `stable_prefix_len`, exposes `current_text()`.
- `apps/cockpit/src/voice/hotkey.ts` (NEW) — bind configurable hotkey (default `Space` for hold-to-talk, `Cmd+Shift+M` for toggle).
- `apps/cockpit/src/pages/cockpit-entry.ts` — wire mic button to `STTStreamClient` instead of (or alongside) the W309-step-2 fetch-after-stop path. **Feature-gated** by `window.__TARS_STT_STREAMING__` (boolean, defaults to `true` in dev, `false` in prod until canary period over).

**Tests:**
- `apps/cockpit/tests/e2e/stt_streaming.spec.ts` (NEW Playwright test) — mock WS server, send canned frames, assert UI updates correctly.

**Acceptance:**
- Manual ops verification: hold space, speak, see live transcript appearing word-by-word.
- Toggle hotkey works.
- Reconnect on transient disconnect (≤ 3 retries with exponential backoff).

---

### Step 6 — Local-first installer hook + auto-download

**Branch:** `cursor/ph2-stt-step6-local-first`
**Files:**
- `apps-tauri/src-tauri/src/sidecar.rs` — on first launch, if no `WHISPER_LOCAL_PATH` is set, prompt operator (modal) to download `faster-whisper-base` (~140 MB) into `${APP_DATA_DIR}/models/faster-whisper-base/`. Use HF hub mirror or our own R2 mirror.
- `backend/core/voice/stt_stream.py` — extend default chain: if `WHISPER_LOCAL_PATH` resolves AND `faster_whisper` importable → use faster-whisper FIRST (currently it's #3). Old chain order preserved for back-compat in `transcribe.py` REST path; WS path uses new order.
- `backend/core/voice/transcribe.py` — add `prefer_local: bool = False` param to `transcribe_bytes`; default keeps old behaviour, WS path passes `True`.

**Tests:**
- `tests/test_stt_local_first.py` (NEW) — assert `transcribe_bytes(..., prefer_local=True)` picks faster-whisper over OpenAI when both configured.
- Manual: fresh install on a clean macOS profile → modal appears → click install → speak → local transcription works without OpenAI key.

**Acceptance:**
- Default install transcribes locally with no API keys.
- Existing OpenAI-only workflows unchanged (`prefer_local=False` default for legacy REST).

---

### Step 7 — Cut feature flag + flip on by default

**Branch:** `cursor/ph2-stt-step7-flag-flip`

After 1 week of canary on `window.__TARS_STT_STREAMING__=true` in dev
+ early adopters, flip prod default to `true`. Remove flag on the
release after that. Keep REST endpoint for two further releases as a
safety net.

---

## 7. Acceptance criteria (Phase 2 done = all of these)

- [ ] WS endpoint passes contract tests (30+ in `test_voice_stt_ws.py`).
- [ ] TTFT ≤ 400 ms p50 / ≤ 800 ms p95 measured on stock M1 with `faster-whisper-base`.
- [ ] End-to-final ≤ 1.2× audio duration p50 on 5-30 s utterances.
- [ ] Local-first works after fresh install with no API keys (no OpenAI calls in network log).
- [ ] Hold-to-talk + toggle-to-talk + VAD endpointing all selectable in cockpit.
- [ ] Reconnect works (kill backend, restart, cockpit re-establishes WS within 5 s).
- [ ] Back-compat: existing `POST /api/voice/transcribe` test suite passes unchanged.
- [ ] `is_configured()` correctly reports `streaming_supported: true|false` per provider.
- [ ] Operator can pick provider explicitly via `start` frame's `model` field (e.g. `"openai-whisper-1"` forces cloud).

---

## 8. Test plan summary

| Layer | New tests | Modified tests | Coverage target |
| ----- | --------- | -------------- | --------------- |
| Unit (faster-whisper warm) | `test_stt_warm_model.py` (5 cases) | none | warm-cache hit / miss / evict |
| Unit (streaming transcriber) | `test_stt_streaming_transcriber.py` (8 cases) | none | feed_chunk lifecycle, stable_prefix_len |
| Unit (VAD) | `test_stt_vad.py` (6 cases) | none | enable / disable / threshold sweep |
| Unit (local-first picker) | `test_stt_local_first.py` (4 cases) | none | prefer_local true/false × all engines configured |
| Integration (WS) | `test_voice_stt_ws.py` (30+ cases) | none | full §5.1 contract |
| Regression | none | `test_voice_stt.py` (must still pass) | REST back-compat |
| E2E (cockpit) | `stt_streaming.spec.ts` | `cockpit.spec.ts` (drop `.skip` on STT scenarios) | hold-to-talk, toggle, VAD |

---

## 9. Rollback strategy

Each step's PR ships behind a feature flag where possible:

| Step | Flag | Default | Rollback |
| ---- | ---- | ------- | -------- |
| 1 | none | always on | revert PR; warm cache is purely an optimisation, no contract change |
| 2 | none | endpoint exists but cockpit doesn't call it | leave dormant |
| 3 | none | real streaming behind endpoint | revert to step 2 behaviour (final-only) |
| 4 | `vad.enabled` per-request | client opt-in | client stops sending `vad.enabled:true` |
| 5 | `window.__TARS_STT_STREAMING__` | true in dev, false in prod | set to false; cockpit falls back to W309 step 2 fetch |
| 6 | `prefer_local` param + auto-download modal | modal can be dismissed → falls back to old chain | dismiss modal; old behaviour returns |
| 7 | flag removal | n/a | revert |

---

## 10. Open questions for operator (resolve before step 1 starts)

| # | Question | Default if operator silent |
| - | -------- | -------------------------- |
| Q1 | Which faster-whisper model to ship by default? `base` (~140 MB, fast) vs `medium` (~1.5 GB, accurate)? | `base` (right balance for v10.1 polish window) |
| Q2 | Host the model on our R2 mirror or pull from HF hub? | HF hub for v10.1, R2 mirror as v10.2 follow-up |
| Q3 | VAD library: `webrtcvad` (lightweight C wrapper) vs `silero-vad` (Torch, ~50 MB)? | `webrtcvad` (smaller footprint, no Torch dep) |
| Q4 | Auto-download modal copy + UX — design owner? | Defer to design system MASTER.md; implement with current button/modal patterns |
| Q5 | Should toggle hotkey be customisable in v10.1 or hardcoded? | Hardcoded for v10.1, customisation in v10.2 |

If operator doesn't override within the first step's PR, the defaults above stick.

---

## 11. Pointers / references

- Current single-shot baseline: `backend/core/voice/transcribe.py` (§3 above)
- WS pattern reference (existing): cockpit chat WS in W309 step 1 — same auth header model, same JSON-text-frame style
- Master plan slot: `docs/PRODUCT_MASTER_PLAN.md` — Phase 2 (`ph2-stt`)
- Companion brief (separate scope): `docs/handoff/PH2_VOICE_GALLERY_BRIEF.md` (TODO — separate brief for `ph2-voice-gallery`, not part of Phase 2 STT)
- Wave summary that scheduled this work: `docs/W310_WAVE_SUMMARY.md`

---

## 12. Estimated effort

- Step 1 (warm model): ~3 h, 1 PR, low risk
- Step 2 (WS scaffold): ~6 h, 1 PR, medium risk (new WS contract)
- Step 3 (real streaming): ~10 h, 1 PR, high risk (audio decoding edge cases)
- Step 4 (VAD): ~4 h, 1 PR, low risk
- Step 5 (cockpit client): ~8 h, 1 PR, medium risk
- Step 6 (local-first + auto-download): ~6 h, 1 PR, medium risk (Tauri sidecar work)
- Step 7 (flag flip): ~1 h, 1 PR, trivial

**Total:** ~38 h, 7 PRs, distributable across 2 weeks at one-step-per-day cadence.

---

**End of brief.**
