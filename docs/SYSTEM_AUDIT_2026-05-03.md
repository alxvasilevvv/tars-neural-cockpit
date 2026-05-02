# TARS — system audit 2026-05-03

Closeout audit after the multi-PR operator-surface batch (PR #136
through PR #144). Two days after `SYSTEM_AUDIT_2026-05-02.md` (which
opened 9 critical bugs and 12 high-severity gaps).

> **Status conventions**: ✅ pass · ⚠️ partial / known gap ·
> ❌ broken / bug found · ⏭️ deferred (out of autonomous scope)

## TL;DR

- **All 9 critical bugs from 2026-05-02 are closed** (the last
  one — duplicate `reembed` route — landed today as PR #143).
- **All 12 high-severity gaps from 2026-05-02 are closed** or
  documented + scheduled.
- The backend test suite (**2315 passed, 1 skipped, 2 xfailed**)
  is fully green and discovers all 161 modules. The 40 modules
  that were silently failing collection on `main` since PR #60
  (the `attachments/index.py` syntax breakage) are restored as of
  PR #141.
- The cockpit vitest suite (**328 passed**, 22 files) is fully
  green; +162 cases land with this batch.
- Five new operator surfaces shipped: `/cockpit/traces`,
  `/cockpit/policy`, `/cockpit/council`, `/cockpit/awareness`,
  and a `⌘.` / `Ctrl+.` operator command palette.
- Image vision routing now reaches Anthropic / OpenAI voices
  natively (PR #142), not just the OCR fallback.
- The cockpit `/changelog` chunk is **63% smaller** (PR #144)
  via a new public-changelog generator.
- Three remaining items are explicitly **out of autonomous
  scope** (live cloud creds, Apple / Windows code signing,
  Stripe live billing) — documented with the missing inputs.

## Bugs closed since 2026-05-02 audit

| # | From 2026-05-02 audit | PR | Status |
|---|---|---|---|
| Bug #1 | `attachments/index.py` syntax (40 test modules silently broken) | **#141** | ✅ closed |
| Bug #2 | Duplicate `POST /api/chat/attachments/{id}/reembed` route | **#143** | ✅ closed |
| Bug #3 | Image attachments dropped from cloud voice payloads | **#142** | ✅ closed |
| Bug #4 | `/changelog` chunk dwarfs the cockpit shell (188 KB gzip) | **#144** | ✅ closed |
| Bug #5 | No operator inbox for pending policy confirmations | **#137** | ✅ closed |
| Bug #6 | Council deliberation can't be debugged from the cockpit | **#138** | ✅ closed |
| Bug #7 | Awareness sources can be listed but not snapshotted from UI | **#140** | ✅ closed |
| Bug #8 | Trace events visible only via curl on `/api/meeet/events` | **#136** | ✅ closed |
| Bug #9 | No keyboard fast-path to actions / playbooks / awareness | **#139** | ✅ closed |

## Test gate at audit time

```text
backend (pytest .): 2315 passed, 1 skipped, 2 xfailed in 142.71s
cockpit (pnpm test): 328 passed in 22 files / 1.14s
cockpit (pnpm build): 0 errors; Changelog chunk 216 KB (was 560 KB)
gate-control-tower local subset:
  - cockpit-tsc                ✓
  - cockpit-test               ✓
  - planner-smoke              ✓
  - playbooks-validate-all     ✓ (every playbook validated, 0 err / 0 warn)
gate-control-tower cloud subset:
  - smoke-core-bridge          ⏭️ requires BRIDGE_SHARED_SECRET
```

## Background loops sanity check

All seven `web_extras/app.py` lifespan loops verified wired and
opt-in via env interval (`0` disables, never crashes the host):

| Loop | Env knob | Default | Purpose |
|---|---|---|---|
| `_replay_loop` | `MEEET_REPLAY_INTERVAL_S` | 30s | Flushes meeet event store to ingest |
| `autopilot_loop` | `TARS_AUTOPILOT_INTERVAL_S` | 60s | Drives agent reasoning loop |
| `_trace_summary_loop` | `TRACE_SUMMARY_INTERVAL_S` | 300s | Rolls up trace stats |
| `_message_embed_loop` | `MESSAGE_EMBED_INTERVAL_S` | 60s | Backfills missing embeddings |
| `_saved_search_poll_loop` | `SAVED_SEARCH_POLL_INTERVAL_S` | 600s | Polls saved alerts |
| `_memory_purge_loop` | `MEMORY_PURGE_INTERVAL_S` | 3600s | Evicts stale memory rows |
| `_policy_expire_loop` | `POLICY_EXPIRE_INTERVAL_S` | 60s | Expires pending policy tokens |

Each loop runs inside its own `trace_scope` and emits at least
`*.invoked` / `*.completed` events, so failures show up in
`/cockpit/traces` immediately rather than silently.

## What's still pending (and why)

### Out of autonomous scope (need operator input)

- **Live cloud-bridge smoke** (`make smoke-core-bridge`,
  `meeet ingest replay`): needs `BRIDGE_SHARED_SECRET`,
  `MEEET_INGEST_URL`, `MEEET_API_KEY`. CI workflow exists at
  `.github/workflows/tars-meeet-synthetic-monitor.yml` and runs
  on a schedule against the real ingest with operator-set
  secrets.
- **Desktop installer signing** (Apple Developer ID,
  Apple notary, Windows Authenticode): workflow exists at
  `.github/workflows/release-desktop-tagged.yml` and produces
  unsigned `.dmg`, `.deb`, `.exe` for all four targets right
  now. It already shells `latest.json` for the in-app updater
  channel (Bug #9 from previous audit). To go signed, set
  `TAURI_SIGNING_PRIVATE_KEY` +
  `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` repo secrets.
- **Live Stripe billing / consumption-limit end-to-end**:
  `/api/usage` rollups, `/api/entitlements` enforcement, and
  the `usage.tokens` event flow are pinned by 47 unit tests
  and 11 integration tests; the live path needs an operator
  with a Stripe test card and the test webhook configured at
  the dashboard.
- **Live LLM voice tests** against Anthropic Claude / OpenAI
  gpt-4o (multimodal): voices ship behind `vault` keys; round-trip
  tested with mocked HTTP, not real APIs.

### Documented, scheduled

- **Phase L9 desktop polish** (pyoxidizer migration, smaller
  binaries, faster cold start): pyinstaller works today, ships
  ~140 MB onefile bundles. Pyoxidizer trade-off (smaller / faster
  but per-target Rust matrix complexity) is captured in
  `docs/PHASE_L_ROADMAP.md` §L9.
- **iOS / Android companion apps** (Phase L roadmap): scaffold
  exists in `mobile/` but feature flags off by default; needs a
  separate batch.

## Operator-surface coverage

The `experiments/neural-showcase-v3/src/pages/Cockpit.tsx`
navigation now exposes:

| Surface | Route | Backend | Status |
|---|---|---|---|
| Overview | `/cockpit` | `/api/domains/manifest` | ✅ |
| Planner | `/cockpit/planner` | `/api/playbooks/*` | ✅ |
| Policy inbox | `/cockpit/policy` | `/api/policy/{pending,recent,confirm,cancel}` | ✅ shipped today (#137) |
| Trace viewer | `/cockpit/traces` | `/api/meeet/{traces,events}` | ✅ shipped today (#136) |
| Council debug | `/cockpit/council` | `/api/council/deliberate` | ✅ shipped today (#138) |
| Awareness explorer | `/cockpit/awareness` | `/api/domains/{slug}/awareness/{id}/snapshot` | ✅ shipped today (#140) |
| Operator palette | `⌘.` / `Ctrl+.` (anywhere) | indexes everything above | ✅ shipped today (#139) |
| Usage / billing | `/cockpit/usage` | `/api/usage` | ✅ pre-existing |
| Vault / keys | `/cockpit/vault` | `/api/vault/status` | ✅ pre-existing |

## Bundle audit (PR #144 result)

| Chunk | Raw | Gzip | Lazy? | Notes |
|---|---|---|---|---|
| `index` | 305 KB | 103 KB | – | Entry shell + framework |
| `Landing` | 308 KB | 86 KB | ✓ | Marketing route |
| `Cockpit` | 197 KB | 49 KB | ✓ | All operator routes |
| `Changelog` | **216 KB** | **69 KB** | ✓ | **Was 560 / 188 KB before #144** |
| `react-vendor` | 142 KB | 46 KB | – | React 18 + ReactDOM |
| `ui` | 90 KB | 28 KB | ✓ | shadcn helpers |
| `three-vendor` | 492 KB | 124 KB | ✓ | R3F-only, lazy on landing |
| `react-spline` | 2 MB | 580 KB | ✓ | Lazy via IntersectionObserver, never loaded for cockpit users |
| `physics` | 2 MB | 723 KB | ✓ | Spline runtime, same as above |

The two heaviest chunks (`react-spline` + `physics`, ~1.3 MB
gzip combined) are downloaded only when the user actually scrolls
the landing-page MeetTars 3D scene into view. Cockpit users never
pay this cost.

## Files written / changed this session

- `experiments/neural-showcase-v3/src/pages/{Traces,Policy,Council,Awareness}.tsx` (4 new pages)
- `experiments/neural-showcase-v3/src/components/OperatorPalette.tsx` (new, 312 lines)
- `experiments/neural-showcase-v3/src/lib/{traceFmt,palette,councilFmt,policyFmt,awarenessFmt}.ts` (5 new pure helpers + matching `*.test.ts`)
- `experiments/neural-showcase-v3/src/pages/Changelog.tsx` (now imports `CHANGELOG_PUBLIC.md`)
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` (+162 RU/EN keys for the new surfaces)
- `experiments/neural-showcase-v3/src/App.tsx` + `Cockpit.tsx` (route registration + nav)
- `experiments/neural-showcase-v3/package.json` (predev / prebuild hooks, `changelog:check`)
- `backend/core/chat/{multimodal,voices,orchestrator}.py` (multimodal image plumbing)
- `backend/core/attachments/index.py` (PR #141 — restored 4 mangled methods)
- `web_extras/routers/chat.py` (PR #143 — unified duplicate reembed route)
- `scripts/generate_public_changelog.py` (new — bundle trim generator)
- `docs/CHANGELOG_PUBLIC.md` (new — generated)
- `docs/CHANGELOG_AGENTS.md`, `docs/IDEAS.md`, `docs/AGENT_HANDOFF.md`,
  `docs/SYSTEM_AUDIT_2026-05-03.md` (this file)
- `tests/test_chat_multimodal.py`, `tests/test_chat_voices_multimodal.py` (new — 48 cases)

PRs landed: **#136, #137, #138, #139, #140, #141, #142, #143, #144** (9 PRs).

## Verdict

The system is **battle-ready for autonomous operation** within
the local-first scope (no live cloud creds, no signed installers,
no live billing). Every operator-side workflow that the previous
audit flagged as "blind from UI" now has a dedicated cockpit
surface and the keyboard fast-path. The test gate is fully green
for the first time since PR #60 broke `attachments/index.py`. The
remaining gaps (cloud creds, code signing, Stripe live) are all
operator-input bound and are documented above with the exact
missing inputs.
