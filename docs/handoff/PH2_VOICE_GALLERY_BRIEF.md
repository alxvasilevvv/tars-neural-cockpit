# Phase 2 — Voice gallery UI (v10.1, companion to STT brief)

**Authoring agent:** Cursor agent (Claude Opus 4.7), W310-i (continuation)
**Authoring date:** 2026-05-18
**Implementer:** TBD (next L4-lane Cursor/Claude session)
**Target release:** `v10.1.0` (post-GA polish window)
**Depends on:** v10.0.0 GA tag (no hard dep on Phase 2 STT brief — can land in parallel)
**Phase ID in master plan:** `ph2-voice-gallery` (companion to `ph2-stt` in `PH2_STT_STREAMING_BRIEF.md`)

---

## 1. Why this brief exists

After v10.0.0 GA, operators have 6 default personas configured (`jarvis`,
`stark`, `hal9000`, `glados`, `tars`, `operator`), but the cockpit
currently provides **no UI for**:

1. **Auditioning voices** — operator can't preview what each persona
   sounds like without changing the active thread's persona and
   sending a message.
2. **Comparing per-voice cost / latency** — `voice.tts` events are
   captured but never surfaced. Operator has no signal on which voice
   is fastest or cheapest for their workload.
3. **Changing the default persona** — `default_persona_id` is
   hardcoded to `"jarvis"` in `/api/voice/personas` (line 65 of
   `web_extras/routers/voice.py`). Switching default requires a code
   change.

Phase 2 voice gallery (`ph2-voice-gallery`) adds a cockpit panel that
surfaces all three, leveraging existing telemetry instead of
introducing new event kinds.

This is **smaller-scope and lower-risk than the STT brief** — pure
read of existing data + one new write endpoint + a cockpit panel.
Suitable as a warm-up Phase 2 task.

---

## 2. Goals / non-goals

### Goals

| ID | Goal | Acceptance |
| -- | ---- | ---------- |
| G1 | Audition each persona with one click | Voice gallery panel shows all 6 personas; clicking "Play preview" emits audio within 1.5 s on M1 (warm cache) |
| G2 | Per-persona metrics surface | Each card shows p50 latency, p95 latency, total TTS cost (last 7 d), call count, last-used-at |
| G3 | Change default persona at runtime | Selecting a persona in the gallery persists as the new `default_persona_id`; new threads created after the change use it |
| G4 | No new telemetry | Aggregation reads existing `voice.tts` + `usage.tokens` events; zero new event kinds |
| G5 | No audio bloat | Preview audio is generated on-demand AND cached (per-persona) so the same preview file is reused across all operator visits |

### Non-goals

- **A/B testing two voices on the same text simultaneously.** Defer to v10.2 if requested; not in the master plan slot.
- **Per-persona TTS tuning knobs** (stability / similarity / style sliders for ElevenLabs personas). Defer to v10.2 — operator can still tune via persona definition files.
- **Voice cloning UI.** Out of scope; cloning is creator-side, not operator-side.
- **Mobile gallery.** Phase 9 owns mobile companion UI.

---

## 3. Current state baseline

### What already exists (lean on this)

- `GET /api/voice/personas` — returns full persona list (lines 59-68 of `web_extras/routers/voice.py`).
- `GET /api/voice/personas/effective` — returns per-persona resolved provider / voice / fallback chain (line 70).
- `POST /api/voice/speak` — synthesizes text → audio with chosen persona (line 269).
- `voice.tts` event payload emitted on every synthesis (line 314 of `backend/core/voice/synthesis.py`):
  ```python
  {
    "persona": target.id,
    "provider": result.provider,
    "voice_id": result.voice_id,
    "mime": result.mime,
    "bytes_total": result.bytes_total,
    "chars": len(text),
    "duration_estimate_ms": result.duration_estimate_ms,
    "latency_ms": round(elapsed_ms, 3),
    "route": current_route(),
    "trace_id": trace_id,
    "cost_usd": cost_usd,
    "fallbacks_tried": [...],
    "fallback_reasons": {...},
  }
  ```
- `usage.tokens` event with `model="voice/<provider>"` for cost rollups.
- `MeeetStore.list_events(kind="voice.tts", since=..., limit=...)` — query historical events.
- `default_persona_id="jarvis"` returned in `/api/voice/personas` response (line 65 of voice.py) — needs to become dynamic, sourced from a small settings table.

### What's missing (this brief adds)

- Preview generation + cache.
- Aggregation endpoint that turns `voice.tts` events into per-persona stats.
- Settings write endpoint for `default_persona_id`.
- Cockpit panel.

---

## 4. API contracts

### 4.1 `GET /api/voice/gallery/preview/{persona_id}` (NEW)

Returns the cached preview audio for a persona, generating it lazily
on first request and caching it on disk thereafter.

**Response 200:**

- Body: raw audio bytes
- Headers: `Content-Type: audio/mpeg|wav`, `X-Tars-Preview-Cached: true|false`, `X-Tars-Persona-Id: <id>`

**Response 404:** Unknown persona ID.

**Response 503:** No engine available to synthesise; envelope `{ok:false, error:"no_tts_backend"}`.

**Preview text:** Fixed phrase per persona's locale. English default:
`"Hello, I'm <Persona Name>. I'll be your voice for this session."`
Russian: `"Здравствуйте, я <Persona Name>. Я буду вашим голосом."`
Locale picked from `persona.locale` field.

**Cache location:** `${APP_DATA_DIR}/voice_previews/<persona_id>__<voice_id>__<provider>.mp3`
(filename includes provider so cache invalidates automatically when the
operator's chain changes, e.g. ElevenLabs key removed → mac_say
fallback gets a new cache slot).

### 4.2 `GET /api/voice/gallery/metrics` (NEW)

Aggregate per-persona stats from existing `voice.tts` events.

**Query params:**
- `window_hours: int = 168` (default 7 d)
- `personas: str | None = None` (CSV; default all)

**Response 200:**

```json
{
  "ok": true,
  "window_hours": 168,
  "as_of": "2026-05-18T14:23:00Z",
  "personas": [
    {
      "id": "jarvis",
      "name": "Jarvis",
      "call_count": 142,
      "latency_p50_ms": 320,
      "latency_p95_ms": 980,
      "total_cost_usd": 0.187,
      "providers_used": {"elevenlabs": 138, "mac_say": 4},
      "last_used_at": "2026-05-18T13:55:12Z",
      "fallback_rate": 0.028
    },
    ...
  ]
}
```

Empty personas (no events in window) appear with `call_count: 0` and
all metric fields `null`.

### 4.3 `POST /api/voice/gallery/default` (NEW)

Set the default persona ID for newly-created threads.

**Request body:** `{ "persona_id": "stark" }`
**Response 200:** `{ ok: true, default_persona_id: "stark", previous: "jarvis" }`
**Response 422:** Unknown persona ID.

**Persistence:** Single-row settings table `voice_gallery_settings`
(SQLite) with columns `(key TEXT PRIMARY KEY, value TEXT)`. Upsert
key `default_persona_id`.

### 4.4 Update to existing `GET /api/voice/personas`

`default_persona_id` field now reads from settings table (falls back
to hardcoded `"jarvis"` if no row exists). **No breaking change** — same
field name, same shape.

---

## 5. Implementation steps (mechanical)

### Step 1 — Settings table + dynamic default persona

**Branch:** `cursor/ph2-vg-step1-settings`
**Files:**
- `backend/core/voice/gallery_settings.py` (NEW) — thin SQLite kv store:
  ```python
  def get_default_persona_id() -> str: ...
  def set_default_persona_id(persona_id: str) -> str: ...  # returns previous
  ```
- `web_extras/routers/voice.py` — change line 65 to call `gallery_settings.get_default_persona_id()` with fallback to `"jarvis"`.
- `web_extras/routers/voice.py` — add `POST /api/voice/gallery/default` endpoint.

**Tests:**
- `tests/test_voice_gallery_settings.py` (NEW) — 6 cases: get-before-set returns jarvis; set + get roundtrip; set unknown persona returns 422; concurrent writes safe; settings table created on first call; reset_store clears.

**Acceptance:**
- `/api/voice/personas` echoes whatever was last POSTed to `/default`.
- All existing voice tests still pass (no breaking change).

---

### Step 2 — Metrics aggregation endpoint

**Branch:** `cursor/ph2-vg-step2-metrics`
**Files:**
- `backend/core/voice/gallery_metrics.py` (NEW) — pure-Python aggregation:
  ```python
  async def aggregate_per_persona(*, window_hours: int, personas: list[str] | None) -> list[dict]:
      since = time.time() - window_hours * 3600
      events = await get_store().list_events(kind="voice.tts", since=since, limit=10000)
      # Group by persona, compute count, p50, p95, sum(cost_usd), providers_used,
      # last_used_at, fallback_rate (calls with non-empty fallbacks_tried / total).
      ...
  ```
- `web_extras/routers/voice.py` — add `GET /api/voice/gallery/metrics`.

**Tests:**
- `tests/test_voice_gallery_metrics.py` (NEW) — 10 cases:
  - Empty window → all personas with `call_count: 0`
  - Single event → p50 == p95 == that event's latency
  - 100 events → p50/p95 within tolerance of expected
  - Mixed providers per persona → `providers_used` counts correct
  - Events with `fallbacks_tried` non-empty → `fallback_rate` correct
  - `personas` filter excludes others
  - `window_hours=1` excludes 2 h old events
  - Persona present in `list_personas()` but no events → `call_count: 0`, metrics `null`
  - Persona in events but removed from definitions → still appears as `"id": "<unknown>"` with `name: null`
  - Concurrent calls return consistent snapshots

**Acceptance:**
- p50/p95 math verified with synthetic data.
- 10K-event window completes in < 200 ms on M1 (10K is a generous cap — typical operator weekly volume is <500).

---

### Step 3 — Preview cache + endpoint

**Branch:** `cursor/ph2-vg-step3-preview`
**Files:**
- `backend/core/voice/gallery_preview.py` (NEW):
  ```python
  PREVIEW_PHRASES = {
      "en": "Hello, I'm {name}. I'll be your voice for this session.",
      "ru": "Здравствуйте, я {name}. Я буду вашим голосом.",
      # ... add more as personas add locales
  }

  async def get_or_generate_preview(persona_id: str) -> tuple[bytes, str, bool]:
      # Returns (audio_bytes, mime, cached_hit)
      ...
  ```
- `web_extras/routers/voice.py` — add `GET /api/voice/gallery/preview/{persona_id}`. Uses `synthesize(...)` from existing `synthesis.py` for generation.
- `backend/core/voice/gallery_preview.py` — cache eviction on persona change is automatic via filename containing provider + voice_id; stale files just orphan harmlessly (clean-up script optional, not required for correctness).

**Tests:**
- `tests/test_voice_gallery_preview.py` (NEW) — 8 cases:
  - First call generates + writes to disk + returns `X-Tars-Preview-Cached: false`
  - Second call returns `X-Tars-Preview-Cached: true` and matches first byte-for-byte
  - Unknown persona → 404
  - All engines unavailable → 503 with `no_tts_backend`
  - Persona's voice changed → new cache slot, both files coexist
  - Locale dispatch picks right phrase template
  - Cache dir created on first call if missing
  - Filesystem error during write → still returns audio (best-effort cache)

**Acceptance:**
- Second-call latency < 50 ms (cache hit).

---

### Step 4 — Cockpit Voice Gallery panel

**Branch:** `cursor/ph2-vg-step4-cockpit`
**Files:**
- `apps/cockpit/src/pages/voice-gallery.html` (NEW) — markup-first, matches the cockpit pattern. Grid of persona cards.
- `apps/cockpit/src/pages/voice-gallery-entry.ts` (NEW) — tiny TS module:
  - Fetch `/api/voice/personas` + `/api/voice/personas/effective` + `/api/voice/gallery/metrics` in parallel on mount
  - Render cards: persona name, character description, effective provider + voice, metrics row (latency p50/p95, calls, $)
  - "Play preview" button → fetch `/api/voice/gallery/preview/{id}` → `new Audio(URL.createObjectURL(blob)).play()`
  - "Set as default" button → POST `/api/voice/gallery/default` → toast confirmation
  - Window-hours selector (1 h / 24 h / 7 d / 30 d) → refetch metrics
- `apps/cockpit/src/styles/voice-gallery.css` (NEW) — grid layout, uses existing design tokens (`--type-label`, `--color-surface-elevated`, etc.)
- Cockpit nav: add "Voice gallery" entry pointing to `/voice-gallery.html` (existing routing pattern, not React).

**Tests:**
- `apps/cockpit/tests/e2e/voice_gallery.spec.ts` (NEW Playwright) — 5 scenarios:
  - Page loads, 6 personas rendered
  - Play preview triggers audio (assert `<audio>` element appended, `play()` called)
  - Set as default updates persona card with "default" badge, hits backend
  - Window selector switches metrics fetch
  - Empty metrics state (no events yet) shows "No usage data yet"

**Acceptance:**
- Manual ops verification: navigate to voice gallery, hear each of 6 personas.
- Default switch persists across cockpit reloads.

---

## 6. Acceptance criteria (Phase 2 voice gallery done = all of these)

- [ ] 6 personas auditionable in < 2 clicks from any cockpit page
- [ ] Per-persona metrics card shows real numbers from `voice.tts` event history
- [ ] Default persona is changeable at runtime and persists
- [ ] No new event kinds introduced (only reads existing telemetry + writes settings row)
- [ ] Preview cache hits return in < 50 ms
- [ ] No regression in existing voice tests
- [ ] Playwright e2e covers all 5 user flows

---

## 7. Test plan summary

| Layer | New tests | Modified tests | Coverage target |
| ----- | --------- | -------------- | --------------- |
| Unit (settings kv) | `test_voice_gallery_settings.py` (6 cases) | none | get/set/unknown/concurrent |
| Unit (metrics agg) | `test_voice_gallery_metrics.py` (10 cases) | none | percentile math, filters, edge cases |
| Unit (preview cache) | `test_voice_gallery_preview.py` (8 cases) | none | generate/cache/locale/errors |
| Integration | `test_voice_gallery_endpoints.py` (existing-style FastAPI client) (12 cases) | none | full contract per §4 |
| Regression | none | `test_voice_personas_effective.py`, `test_voice_synthesis.py` | unchanged |
| E2E (cockpit) | `voice_gallery.spec.ts` (5 scenarios) | none | full user flow |

---

## 8. Rollback strategy

| Step | Rollback |
| ---- | -------- |
| 1 | Revert PR. Hardcoded `"jarvis"` default returns. |
| 2 | Revert PR. Metrics endpoint disappears; no other consumers. |
| 3 | Revert PR. Preview endpoint disappears; cache dir orphans harmlessly. |
| 4 | Revert PR OR hide nav entry; backend endpoints remain accessible but no UI. |

Every step is independently revertable — no cross-step coupling.

---

## 9. Open questions for operator (resolve before step 1 starts)

| # | Question | Default if operator silent |
| - | -------- | -------------------------- |
| Q1 | Should preview phrase be operator-customisable, or are the en/ru templates fine? | Hardcoded templates in v10.1, customisable in v10.2 |
| Q2 | Default metrics window — 7 d feels right; objection? | 7 d (168 h) |
| Q3 | Should setting a new default persona retroactively re-pin existing threads, or apply only to new threads? | New threads only; existing threads keep their pinned persona |
| Q4 | Cache size cap? Each preview ≈ 50 KB; 6 personas × 3 providers = 18 files = ~1 MB. Unbounded acceptable? | Unbounded acceptable for v10.1 (revisit if file count balloons) |
| Q5 | Show fallback_rate as a colour signal (green < 5%, yellow 5-15%, red > 15%) or as a plain number? | Plain number for v10.1; colour-coding is design-system work for v10.2 |

If operator doesn't override within the first step's PR, defaults stick.

---

## 10. Estimated effort

- Step 1 (settings + dynamic default): ~3 h, 1 PR, low risk
- Step 2 (metrics aggregation): ~4 h, 1 PR, low risk
- Step 3 (preview cache): ~4 h, 1 PR, low risk
- Step 4 (cockpit panel): ~6 h, 1 PR, medium risk (UI work, design tokens)

**Total:** ~17 h, 4 PRs, distributable across 4 days at one-step-per-day cadence.

Significantly less risky than the Phase 2 STT brief — pure read-side
work plus one settings row plus one UI panel, no new protocol, no
audio decoding, no warm-cache singleton.

---

## 11. Pointers / references

- Companion brief: `docs/handoff/PH2_STT_STREAMING_BRIEF.md` — Phase 2 STT half. Can land in parallel; no shared files.
- Existing voice.tts payload reference: `backend/core/voice/synthesis.py:314-356`
- Existing personas list/effective endpoints: `web_extras/routers/voice.py:59-126`
- Existing telemetry store API: `backend/core/meeet/store.py:324-362` (`list_events`)
- Master plan slot: `docs/PRODUCT_MASTER_PLAN.md` — Phase 2 (`ph2-voice-gallery`)
- Wave summary that scheduled this work: `docs/W310_WAVE_SUMMARY.md`

---

**End of brief.**
