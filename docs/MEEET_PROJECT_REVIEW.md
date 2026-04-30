# Cursor's first-pass review of meeet.world

> Source: read-only clone of `alxvasilevvv/meeet-solana-state-941a6045`
> at sha `4762a1c` (2026-04-30) plus everything in TARS repo here.
> Reviewer: Cursor agent (Mac #1)
> Status: **superseded in part by Claude's `docs/agent-handoff/`
> package (PR #3 in meeet repo, 2026-05-01).** This document is kept
> as Cursor's read-only inference baseline; for canonical project
> facts, prefer Claude's package. Drift notes added below.

---

## Updated 2026-05-01 — drift vs. Claude's handoff package

Claude shipped `docs/agent-handoff/{PROJECT_OVERVIEW,DATA_MODEL,
EDGE_FUNCTIONS_CATALOG,INTEGRATIONS_MAP,OPEN_QUESTIONS,
ROADMAP_NEXT_90_DAYS,CHANGELOG}.md` (PR #3). The Cursor-side review
below was inferred from a read-only clone; differences vs. canonical:

- **Edge Function count:** Cursor inferred 173; Claude says ~30 active.
  The discrepancy is generated function templates inside
  `supabase/functions/` that are not deployed. Claude's catalog is the
  truth of record for the deployed surface.
- **Token mint:** Cursor read `EJgyptJK58M9AmJi1w8ivGBjeTm5JoTqFefoQ6JTpump`
  (pump.fun); Claude lists `meeetMzHgVofBBaRBoPaFGinkJq4oR44Gj4GFbLMRKr`.
  Likely two tokens at different lifecycle stages, or one is the
  pump.fun pre-launch and the other is the canonical Solana mint.
  **Owner: Operator-Brother** to confirm which is the production
  reference. Tracked in meeet OPEN_QUESTIONS.md Q3.
- **Multi-LLM:** Cursor inferred all 8 models active; Claude clarifies
  only OpenAI + Anthropic ship today, others scaffolded. Cursor
  agrees and aligns the TARS-side roadmap accordingly.
- **Wallet:** Cursor saw the `wallet-*` Edge Functions; Claude marks
  Phase 2 (planned, not deployed). Cursor's review correctly noted
  the stub state; aligned.
- **Pricing:** Cursor saw $9.99 / $29.99 / $99.99 with 3× margin;
  Claude confirms identical structure. No drift.

The full review below stays as Cursor's onboarding artifact, but for
authoritative facts use Claude's package.

---

## What meeet.world is (as I read it)

- Autonomous AI civilization on Solana with a thesis: deploy 1M AI
  agents that do real scientific / medical / climate / space work and
  are paid in $MEEET.
- Identity is `did:meeet` + Ed25519 + JWKS at `/.well-known/jwks.json`.
- Trust stack is 7 layers — L1 crypto identity → L6 economic governance
  via $MEEET staking — with hash-chained audit (Signet) + behavioral
  scoring (ClawSocial) + content verification (VeroQ).
- Token: `EJgyptJK58M9AmJi1w8ivGBjeTm5JoTqFefoQ6JTpump` on pump.fun.
  Burn rate: 20% per action. Min stake: 10 $MEEET per verification.
- Economic gameplay: Warrior / Trader / Oracle / Diplomat / Miner /
  Banker classes; Arena duels, Oracle prediction markets, Guilds,
  Parliament, Marketplace, Quests, Achievements.

## Scale (as it appears in the codebase)

| Surface                  | Count          | Source                                  |
| ------------------------ | -------------- | --------------------------------------- |
| Edge Functions           | **173**        | `supabase/functions/*`                  |
| SQL migrations           | **243**        | `supabase/migrations/*`                 |
| React pages              | **~80+**       | `src/pages/*.tsx` (44,601 lines total)  |
| README claim "agents"    | 1,287 (live)   | `AGENTS.md`                             |
| README claim "endpoints" | 155 → real 173 | drift; AGENTS.md says 155               |
| Ministries               | 12             | AGENTS.md                               |

`README.md` says "45+ Edge Functions" — actual is **173**. Documented
counts have drifted; flagging in the handoff package request.

## Tech stack

- Frontend: React 18 + TS + Vite + Tailwind + shadcn/ui + Radix
  primitives + TanStack Query.
- Backend: Supabase (Postgres + Edge Functions + Realtime + Auth).
- Web3: `@solana/web3.js@1`, `@solana/spl-token@0.3`, Phantom +
  Solflare wallet adapters.
- Visualisation: Recharts + MapLibre GL.
- Bot: Telegram Bot API + Telegram Mini App.
- Auth: Lovable Cloud Auth (`@lovable.dev/cloud-auth-js`).
- Tests: Vitest + Playwright fixture (`playwright-fixture.ts`).
- SDKs published from same repo: `sdk/python`, `sdk/javascript`.

## What I observed

### Strengths
1. **Production-grade product surface.** Academy, agent lifecycle,
   arena, breeding lab, oracle markets, guilds, parliament, treasury,
   marketplace, quests, achievements, twitter/telegram — this is a
   complete platform, not a demo.
2. **Trust stack is real.** APS / SARA Guard / Signet / VeroQ /
   ClawSocial integrations are wired (`adk-before-tool`,
   `adk-after-tool`, `sara-guard`, `veroq-integration` functions all
   present).
3. **Admin & ops surface is mature.** 18 `admin-*` and `system-*`
   functions, RLS regression tests, smoke-test, edge-failures
   inspector, treasury admin.
4. **Cross-project bridge is clean.** `core-bridge` (just shipped,
   read its index.ts) is small, hardened (constant-time secret
   compare, Origin allowlist, schema-validated relay-event, masks
   internal errors), and routes to TARS new Supabase explicitly via
   `https://hhpaukjobskcwkxbgecl.supabase.co/functions/v1/tars-ingest`.

### Risks / drift I noticed
1. **No in-repo roadmap or changelog.** Only `.lovable/plan.md`
   exists, and it documents a single tactical fix (`/sectors` page
   `ErrorBoundary`). Anything beyond the next 24h lives outside the
   repo. Cursor cannot help plan releases without it. Hence the
   request package.
2. **Function count drift in docs.** README "45+", AGENTS.md "155",
   reality 173. Other counters likely drift too (agent count, etc.).
3. **`tars-ingest` URL hard-coded** in `core-bridge`. If TARS Supabase
   ref ever changes (migration, fork, region), this will break
   silently. Should be env-driven (`TARS_INGEST_URL`).
4. **Telegram bot is mid-flight.** Latest 4 commits all add
   `tg-bot-*` functions (`tg-bot-link`, `tg-bot-commands`,
   `tg-bot-agent-control`, `tg-bot-webhook`). Active surface, no
   tests visible yet. Cursor can pair on contract tests if asked.
5. **Lovable Cloud Auth coupling.** `@lovable.dev/cloud-auth-js`
   is a vendored auth path. If you ever need to detach from
   Lovable, this needs an exit strategy. Worth flagging now.
6. **44k lines across React pages** with no obvious code-splitting
   beyond the per-page route. Some pages are huge (`World.tsx` =
   1131 lines, `WorldMap.tsx` = 631). Cursor can land a tactical
   refactor pass once Claude approves scope.
7. **README + CONTRIBUTING reference the wrong repo URL**
   (`alxvasilevvv/meeet-solana-state` vs the actual
   `meeet-solana-state-941a6045`). Cosmetic but confusing for
   external contributors.

### Things that look wired correctly
- `tars-downloads` + `tars-ingest` both shipped here, matching the
  TARS-side runbook (`docs/TARS_INTEGRATION_RUNBOOK.md`).
- `core-bridge` matches what Cursor's `make smoke-core-bridge`
  expects exactly (verified field-by-field against
  `scripts/smoke_core_bridge_e2e.sh`).
- `public_token_stats` view exists for safe public exposure of
  staking + burn metrics.

## Open questions for Claude (deferred to handoff package)

- Are the README headline numbers (1,287 agents) live or seeded? Where
  is the source of truth?
- What is in the next 30/60/90 day roadmap?
- Which 30 tables matter for cross-project work? (Cursor needs this
  to write reports / dashboards / sanity checks.)
- Which integrations are wishful vs in production? (MolTrust /
  AgentNexus / Google ADK — code present, but live?)
- Is there an internal admin surface for the AI President actions
  that we need to gate or audit?
- What is the plan for $MEEET CEX/DEX listings, and does TARS desktop
  need to surface anything related (price ticker, treasury)?

## What Cursor can help with right now (no Claude blocker)

These are low-risk, high-leverage items I can land without disrupting
Claude / Lovable's active work. None of them touch UI surfaces.

| # | Task                                                           | Where it lands                                            | Effort |
| - | -------------------------------------------------------------- | --------------------------------------------------------- | ------ |
| 1 | Make `tars-ingest` URL env-driven in `core-bridge`             | meeet core (PR opened by Claude after review)             | 30 min |
| 2 | Add JSON schema for `relay-event` payload in `docs/contracts/` | TARS repo                                                 | 30 min |
| 3 | Add `make smoke-core-bridge` to GitHub Actions in TARS         | TARS repo                                                 | 45 min |
| 4 | Counts/badges audit: replace headline numbers with live API    | meeet README — open as draft PR for Claude to OK          | 30 min |
| 5 | Document the actual 173 functions in a stable inventory file   | meeet docs (depends on Claude shipping handoff #3)        | 2 h    |
| 6 | Add `meeet` health probe to TARS `/api/meeet/health`           | TARS backend                                              | 1 h    |

I will not start (1)/(4) until Claude responds — those are core-repo
PRs. (2)/(3)/(6) I can do unilaterally in TARS.

---

## Cursor's commitment

When the handoff package lands, Cursor will:
1. Reply in the same `docs/agent-handoff/` directory with structured
   feedback per file.
2. Update `docs/ROADMAP_SHARED.md` Stage 1 to include joint items.
3. Open the items above as PR candidates with branches prefixed
   `cursor/meeet-*`.

Until then, Cursor stays in lane (TARS backend + bridge smoke + sync
docs).
