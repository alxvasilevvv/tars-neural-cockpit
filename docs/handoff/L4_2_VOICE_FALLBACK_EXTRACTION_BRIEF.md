# L4.2 voice fallback hardening — extraction brief

> **Author.** Cursor (Sonnet 4.6) — Wave 310-f.
> **Audience.** Whoever opens the replacement PR after PR #183 closes.
> **Status.** Ready — operator-unblocked, no decisions pending.
> **Purpose.** Salvage the genuinely valuable hardening from PR #183
> (per-persona macOS voice fallback diagnostic) while leaving W295's
> `/personas/effective` endpoint on `main` untouched and avoiding the
> regression PR #183 would otherwise reintroduce.

---

## 0. Why this brief exists

PR #183 (`cursor/voice-persona-fallback`, "Phase L4.2 — per-persona
mac_say fallback + voice substitution diagnostic", +777/-31 LoC across
9 files) was opened 2026-05-11. The forensic rebase attempt on
2026-05-17 (W310-c) discovered a **semantic architectural conflict**:
`main` already ships `/api/voice/personas/effective` via W295, and
PR #183 silently overwrites it with a different shape.

Deeper inspection (W310-f, 2026-05-18) found PR #183 also carries
**three regressions** that would land if merged as-is:

1. **Jarvis voice REGRESSION.** PR #183's `personas.py` resets
   `jarvis.elevenlabs_voice_id` from `JBFqnCBsd6RMkjVDRZzb` ("George"
   — warm British baritone) back to `onwK4e9ZLuTAKqWW03F9` ("Daniel"
   — flat narrator). The main branch explicitly comments
   *"replaced Daniel which was flat narrator"*. This is an operator
   subjective-quality regression.
2. **ElevenLabs tuning regression.** PR #183 strips
   `jarvis.elevenlabs_stability=0.22`, `similarity=0.92`, `style=0.78`
   (cinematic butler tuning) back to dataclass defaults. Operator
   notes: *"cinematic delivery is unlocked only via aggressive
   parameter tuning"* — defaults read flat.
3. **Docstring deletion.** PR #183 reduces `PersonaProviderHint`'s
   docstring from ~30 lines of free-tier ElevenLabs operator guidance
   (the stability / similarity / style ranges per persona archetype)
   to a single-line summary. This is institutional knowledge loss.

The endpoint conflict + 3 regressions make a clean cherry-pick
non-trivial. Hence: extract only the safe additive value, leave the
rest behind.

---

## 1. What to extract (safe additive value)

### 1.1. `requested_voice_id` + `substituted` on `SynthesisResult`

`backend/core/voice/engines.py`:

- Add `requested_voice_id: str | None = None` field to the dataclass.
- Add `@property substituted -> bool` (returns False when
  `requested_voice_id is None`; otherwise `self.voice_id != self.requested_voice_id`).
- Extend `to_dict()` to include both fields.
- Update each engine's `synthesise()` return to populate
  `requested_voice_id`:
  - `ElevenLabsEngine`: same as `voice_id` (cloud providers don't
    silently substitute).
  - `OpenAITTSEngine`: same as `voice_id`.
  - `MacSayEngine`: the pre-fallback `requested` voice (e.g. "Alex"
    even when engine falls back to "Daniel").

This is **purely additive** — backwards-compatible default keeps
existing M-wave callers green.

### 1.2. `_pick_fallback_voice` + per-persona alternatives

`backend/core/voice/personas.py`:

- Add `mac_say_voice_alternatives: tuple[str, ...] = ()` field to
  `PersonaProviderHint` (with `merged()` whitelist update + `to_dict()`
  inclusion).
- **DO NOT TOUCH** the rich docstring on `PersonaProviderHint` — main
  has the authoritative version, PR #183 deletes it.
- **DO NOT TOUCH** `_build_default_personas()` `jarvis` definition —
  main's George + cinematic tuning is canonical.

`backend/core/voice/engines.py` MacSayEngine:

- Cherry-pick `_pick_fallback_voice(persona, installed_voices)` static
  method (selects from `persona.provider.mac_say_voice_alternatives`
  first, then falls through to `_VOICE_FALLBACKS_BY_ACCENT`).
- Cherry-pick `_VOICE_FALLBACKS_BY_ACCENT` mapping.
- The `synthesise()` body already needs `requested_voice_id` plumbing
  from §1.1 — folds in naturally.

### 1.3. Tests — fallback unit tests only

`tests/test_voice_persona_alternatives.py` (NEW, +225 LoC):

- Extract **wholesale** — these test `_pick_fallback_voice`
  behaviour at the unit level and are endpoint-shape-independent.

`tests/test_voice_engines.py` (+10/-4 in PR #183):

- Extract the **additive** assertions only (new test cases for
  `requested_voice_id` / `substituted`). The `-4` deletions are
  shape changes for the old `SynthesisResult` test; keep them.

`tests/test_thread_persona_pinning.py` (+6/-0):

- Extract — these are six new assertions about how pinned voices
  flow through pinning, additive only.

### 1.4. (Optional) Augment W295's `/personas/effective` with substitution diagnostic

If the operator finds substitution diagnostic valuable in the cockpit
picker ("→ Daniel (substituted)"), **extend** W295's endpoint rather
than replace it:

```python
# web_extras/routers/voice.py — augment, don't replace
@router.get("/personas/effective")
async def personas_effective_endpoint() -> dict[str, Any]:
    """W295 — pure read-only diagnostics endpoint (kept canonical).
    L4.2 add: include substitution preview for mac_say."""
    personas = list_personas()
    providers_available = await available_engines()
    items: list[dict[str, Any]] = []
    mac_engine = MacSayEngine()
    installed_mac = await mac_engine.installed_voices() if providers_available.get("mac_say") else set()
    for persona in personas:
        eff = await resolve_effective(persona)
        # NEW: substitution preview (additive field, doesn't break W295 shape)
        requested_mac = persona.provider.mac_say_voice
        effective_mac = requested_mac
        if installed_mac and requested_mac and requested_mac not in installed_mac:
            effective_mac = MacSayEngine._pick_fallback_voice(persona, installed_mac)
        items.append({
            ...eff existing keys...,
            "mac_say_substitution": {
                "requested": requested_mac,
                "effective": effective_mac,
                "substituted": requested_mac != effective_mac,
            } if requested_mac else None,
        })
    return {"providers_available": providers_available, "personas": items}
```

This is an **optional §1.4** — only do if cockpit picker actually
needs it. The §1.1–1.3 extraction stands on its own.

---

## 2. What to leave behind (PR #183 regressions / dead weight)

### 2.1. DO NOT touch `web_extras/routers/voice.py` `/personas/effective`

W295's version on main is canonical:

- Uses shared `resolve_effective()` → stays DRY with `/api/voice/speak`.
- Returns full provider/voice info (richer than L4.2's shape).
- Tested by W290 acceptance harness (`scripts/qa_w290_cockpit.sh` Group 9).

L4.2's rewrite drops `resolve_effective` (re-implements probe logic
inline) and produces a less-complete shape. Reject.

### 2.2. DO NOT regress jarvis voice config

Main: `JBFqnCBsd6RMkjVDRZzb` ("George"), stability 0.22, similarity
0.92, style 0.78 — cinematic butler.

PR #183: `onwK4e9ZLuTAKqWW03F9` ("Daniel"), defaults — flat narrator.

Regression. Leave main's values alone.

### 2.3. DO NOT delete `PersonaProviderHint` docstring

Main has ~30 lines of operator tuning guidance (free-tier ElevenLabs
ranges per persona archetype). PR #183 reduces it to one line.
Institutional knowledge — preserve.

### 2.4. DO NOT cherry-pick `tests/test_voice_router.py` wholesale

The +156 LoC test additions assert L4.2's endpoint shape
(`requested.mac_say`, `effective.mac_say`, `substituted` at top
level). These would FAIL against W295's shape. Skip these tests
entirely — the §1.4 augmentation has different assertions to write
fresh.

---

## 3. Proposed PR shape

| Path | Action | Source |
|------|--------|--------|
| `backend/core/voice/engines.py` | +SUBSET (additive only) | Cherry-pick fallback + `requested_voice_id` |
| `backend/core/voice/personas.py` | +ONE FIELD | `mac_say_voice_alternatives` only; preserve rest |
| `tests/test_voice_persona_alternatives.py` | +NEW | Wholesale from PR #183 |
| `tests/test_voice_engines.py` | +DELTA | Additive assertions only |
| `tests/test_thread_persona_pinning.py` | +DELTA | Six new assertions only |
| `web_extras/routers/voice.py` | UNTOUCHED | (or §1.4 augmentation, optional) |
| `docs/CHANGELOG_AGENTS.md` | +ENTRY | Wave 311 entry; cite this brief |
| `docs/CHANGELOG_PUBLIC.md` | (auto-generated by hook) | — |

Expected diff: ~250 LoC adds, 0 deletions, 0 regressions, 0 endpoint
shape changes.

---

## 4. Verification protocol (~10 min)

1. `git checkout main && git pull origin main`
2. `git checkout -b cursor/voice-fallback-extract-clean`
3. Apply §1.1 + §1.2 + §1.3 changes (manually, file by file —
   `git checkout origin/cursor/voice-persona-fallback -- <path>` is
   tempting but pulls regressions; **paste from the brief instead**).
4. Run: `python3 -m pytest tests/test_voice_engines.py tests/test_voice_persona_alternatives.py tests/test_thread_persona_pinning.py tests/test_voice_router.py -v`
   → All green; `test_voice_router.py` assertions should match
   W295's shape unchanged.
5. Run: `python3 -m pytest tests/test_qa_w290_cockpit.py -v`
   → Group 9 ( `/personas/effective` contract) still green.
6. Commit + push + open PR with title:
   `feat(voice): L4.2 fallback hardening — _pick_fallback_voice + requested_voice_id (extracted from #183)`
7. Reference this brief in the PR body.

---

## 5. Closing PR #183

PR #183 should be **closed** (not merged, not rebased) once this
extraction PR opens. Body should reference this brief + the §2
regressions list. The branch (`cursor/voice-persona-fallback`) stays
on the fork as forensic evidence; no force-delete.

---

## 6. Estimated cost

- Cherry-pick + manual fixup (§1): 45 min.
- Test run + adjust (§4 step 4–5): 15 min.
- PR open + write description: 15 min.

**Total: ~1.25 hours.** Smaller than rebasing #183 + reverting
regressions + writing the diagnostic on top.

---

## 7. Audit trail

- **2026-05-11** — PR #183 opened by Cursor on `cursor/voice-persona-fallback`.
- **2026-05-17 (W310-c)** — Cursor parent agent attempted rebase,
  surfaced semantic conflict; filed PR #183 comment with three paths
  (A — pick W295, B — pick L4.2, C — augment W295). Operator did
  not respond.
- **2026-05-18 (W310-f)** — Cursor parent agent diagnosed three
  regressions in PR #183 (Jarvis voice, ElevenLabs tuning, docstring
  deletion). Authored this extraction brief; recommended close-and-
  re-open with the additive-only subset. Operator instructed
  *"делай сам"* — proceeding autonomously.

— end —
