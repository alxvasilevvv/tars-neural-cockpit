# Cockpit Playwright e2e harness — W309 step 2 prep

> **Status (W310-c, 2026-05-18).** Scaffolded by the parent Cursor
> assistant as **prep work for W309 step 2**, while the project waits
> on PR #187 (W309 step 1) to merge. **The spec file itself is a
> skeleton** with `test.skip()` stubs covering every assertion from
> `docs/handoff/W309_STEP2_BRIEF.md` §3.1. **Helpers, fixtures, and
> config are production-ready.**
>
> When PR #187 lands and step 2 implementation begins, the step-2
> implementer:
>
> 1. Drops the `.skip` markers off the tests they wire up.
> 2. Adds any new fixtures step-2 surfaces (transcribe response shape
>    is already stubbed; persona-picker selectors get wired during
>    impl).
> 3. Runs `pnpm test:e2e` from `apps/cockpit/`
>    (`apps/cockpit/` is a standalone pnpm project, not workspaced
>    under a repo root, so commands run from inside that directory).
>
> No PR #187-runtime imports live in this scaffold — the spec is
> wired to selectors / DOM queries only, so the directory rebases
> cleanly onto any state of `cursor/w309-step1-runtime`.

---

## Why this exists

W309 step 1 (PR #187) restored mic / WS / chat / TTS as the four
MVP behaviours, with **20 static contract tests** that grep source
for the right strings. Claude's PR #187 review explicitly called
out the gap:

> The cheapest behavioural guard you'd actually trust is a
> Playwright smoke against a mock SSE server.

This directory is that guard, prepared **ahead** of step 2 so the
step-2 wave can focus on production code (mediarecorder + STT
upload + persona `<select>`) instead of harness scaffolding.

## Directory layout

```
tests/e2e/
├── README.md                    — this file
├── playwright.config.ts         — config, baseURL, browser pin
├── cockpit.spec.ts              — main spec (skeleton)
├── helpers/
│   ├── mock-sidecar.ts          — page.route() helpers for /api/**
│   ├── mock-sse.ts              — streamed SSE response synthesiser
│   └── mock-ws.ts               — window.WebSocket replacement
└── fixtures/
    ├── voice-personas.json      — canned /api/voice/personas response
    ├── voice-health.json        — canned /api/voice/health response
    ├── vault-status.json        — canned /api/vault/status response
    ├── chat-threads.json        — canned /api/chat/threads response
    ├── chat-sse-deltas.json     — SSE frame definitions for stream tests
    └── voice-transcribe.json    — canned /api/voice/transcribe response
```

## What to run

```bash
cd apps/cockpit

# install Playwright + browsers (one-time)
pnpm install
pnpm test:e2e:install   # runs `playwright install --with-deps chromium`

# run the suite
pnpm test:e2e
```

Target: **< 10s wall-clock** per the brief. CI gate is `make ci-cockpit`
(to be added when step 2 lands — kept off `make ci` until the harness
proves stable per brief §3.1).

## What this scaffold deliberately does NOT cover

Per brief §6 (out of scope for step 2):

- Real `getUserMedia` — bypassed via `context.grantPermissions(['microphone'])`; mic permission tests stay in the static `test_voice_ensure_mic_*` set.
- Waveform visualiser — W311+ polish.
- Voice cloning kit UI — separate brief.
- STT streaming — upload-after-stop is the cheapest correct loop; the harness can be extended for streaming when sidecar supports it.

## Stability budget

Per brief §5 (rollback criteria):

> Playwright spec is flaky in CI (> 1 in 20 fails on a stable PR).
> Better to revert and re-engineer the mock than to ship a flaky guard.

Keep mocks deterministic. No real-time timeouts beyond Playwright's
own. No `page.waitForTimeout(ms)` — wait for selectors / network
events instead.

---

Co-authored-by: Cursor (Sonnet 4.6) — W310-c prep work
