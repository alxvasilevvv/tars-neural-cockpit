# TARS — Master plan v9.1.1 → v10.0

> Compiled 2026-05-13 by Claude after orchestrated audit (3 parallel
> agents: reality audit, meeet.world integration map, product
> roadmap). All three reports linked at the bottom — this is the
> synthesized single-source-of-truth.

---

## TL;DR

Three sub-plans live in three sibling files. This document **points** at
them and **orders** what happens next. If you only read one thing, read
the "Next 7 days" section below.

| Sub-plan | File | Length |
| --- | --- | --- |
| Honest reality of v9.1.0 | [`REALITY_AUDIT_2026-05-13.md`](REALITY_AUDIT_2026-05-13.md) | 291 lines |
| meeet.world integration map | [`MEEET_INTEGRATION_MAP.md`](MEEET_INTEGRATION_MAP.md) | 490 lines |
| Product roadmap v9.1.1 → v10.0 | [`MASTER_ROADMAP_v9.1_to_v10.0.md`](MASTER_ROADMAP_v9.1_to_v10.0.md) | 393 lines |

---

## Where we are honestly (2026-05-13)

**Shipping today:** 3 subsystems fully end-to-end (receipts ledger,
compliance export, workshop FE shell), 9 partial, 2 stub, 2 missing
despite docs. The Reality Audit found three sharp discrepancies that
this plan corrects.

**Integration with meeet.world:** Only **one** channel is fully live
both ways — `core-bridge → tars-ingest`. Twelve other channels are
partial / stub / missing.

**Honest pitch (the only one we can use until shipped):**
> "Local-first, receipt-anchored personal AI workspace with OAuth
> bridges, audit-grade export, and a council of playbook-driven agents.
> macOS desktop-only. Not multi-tenant, not a SaaS, not continuously
> running, not a real fine-tuned AI Clone, not multiplayer yet."

If marketing copy in any channel claims more than that — fix the copy,
not the claim. (See "Honesty floor" in the roadmap doc.)

---

## North Star (6 months out)

> TARS is the local-first operator console for AI agents on Mac. It's
> what you reach for when you want to run agents on YOUR machine, see
> what they did, replay it with cryptographic proof, and pay $MEEET
> instead of OpenAI bills. The wedge is local execution + multi-model
> dissent + visible audit trail. Everything else (Cowork, Marketplace,
> Workshop suite) compounds that wedge — they're not separate products.

---

## Next 7 days — concrete, ordered, with owners

| # | Task | Owner | Time | Status |
| - | ---- | ----- | ---- | ------ |
| 1 | Push current main (8 commits W139-W147) | **You** | 30 sec | `tars-ops` → 2 — Push |
| 2 | Verify `/dl/` proxy + Intel Mac Rosetta fallback works | **Claude** (auto via tars-ops Verify) | 2 min | Wait 3 min after push, then `tars-ops` → 3 — Verify |
| 3 | Apple Developer cert export → 6 GitHub Secrets | **You** (~15 min) | 15 min | `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` step-by-step. Can also send to brother's Cursor. |
| 4 | Brother wires `/api/cowork/*` 10 routes | **Brother** | ~30 min | `docs/handoff/COWORK_WIRING_FOR_CURSOR.md` is paste-ready FastAPI. |
| 5 | Fix WHAT_WORKS.md honesty drift (2 rows) | **Claude** (this commit) | done | iMessage stub row + Background daemon row corrected below |
| 6 | Re-run Apple-signed CI release → v9.1.1 tag | **You** via `tars-ops` → 5 — Tag release | 5 min | After secrets land |
| 7 | First public marketing push (HN) | **You** | 30 min | `docs/launch/HN.v9.1.0.md` (Claude wrote it; you read + post) |

---

## What I (Claude) do autonomously over next 30 days

In order, by impact:

1. **Wire Cowork HTTP routes to FastAPI inside this repo** — even if brother's core-bridge doesn't pick them up, having the routes in our codebase means the operator can run them locally via `make backend-tars-up`. This converts the Cowork module from "library only" to "callable today". Wave 148.
2. **MCP server bridge** — the audit found `backend/core/mcp/` doesn't exist; task #17 + #85 are dishonestly marked done. I'll either build it or strike those tasks. Wave 149.
3. **AI Clone v0.1 → v0.2 (style learning persistence)** — current local-only is a retention risk for paying users. Sync style hint to meeet via webhook so account migration preserves it. Wave 150.
4. **Background TARS as real daemon** — currently three lifespan loops dying with FastAPI. Promote to real `launchd` plist on macOS with restart-on-crash. Wave 151.
5. **Operator onboarding flow** — new user runs `install.sh`, gets TARS, then what? Today: blank wall. v9.2 needs a 60-second guided onboarding that:
   - Detects which connector OAuth credentials are accessible (Google / Slack / GitHub)
   - Sets up first agent (default = "morning briefing")
   - Surfaces one playbook completion in first session
6. **Intel Mac dmg native build** — Rosetta fallback (W146) is a stopgap. Real fix: GitHub Actions release matrix with `macos-13` runner (Intel) when billing allows.
7. **Cowork frontend re-port for Tauri** — the W129/W132 UI was deleted with the SPA. Re-port the 3 pages (list, session, handoff accept) into `desktop/src-tauri/web/` for native desktop use. This goes hand-in-hand with brother's `/api/cowork/*` routes.

Each of these = its own Wave commit, AGENT_HANDOFF.md updated, tests green.

---

## What you (operator) do over next 30 days

Three categories — only the first is on critical path.

**🟥 Required for v9.1.1 launch:**
1. Run `tars-ops` → 2 — Push (whenever you finish reading this)
2. Apple Developer cert (15 min, browser flow, can delegate to brother's Cursor)
3. After v9.1.1 tag → push HN post

**🟧 Strongly desired (operator-only access):**
4. Cloudflare → `tars-meeet-git` env → paste `GITHUB_RELEASE_TOKEN` (clears the install funnel 503 fallback)
5. Register Google Cloud OAuth client + Slack app → put `GOOGLE_CLIENT_ID/SECRET` and `SLACK_CLIENT_ID/SECRET` into Cloudflare env (so connectors work for users without their own apps)
6. Set up Solana mainnet keypair + fund it ~1 SOL → enable `TARS_RECEIPT_ANCHOR_ENABLED=1` (turns the audit anchor claim from "off by default" to "live")

**🟨 Nice-to-have:**
7. SmartScreen reputation submission for Windows installer (preemptively, before first 50 Windows users hit "More info → Run anyway")
8. App Store Connect entry for future TARS distribution channels

---

## What brother does (meeet.world side)

Detailed in [`MEEET_INTEGRATION_MAP.md`](MEEET_INTEGRATION_MAP.md) §4.
TL;DR — 13 edge functions in P0/P1/P2 order:

**P0 (unblocks v9.1.1):**
- `tars-billing` Supabase function (mirror operator tier + spend)
- `/api/cowork/*` 10 routes via `docs/handoff/COWORK_WIRING_FOR_CURSOR.md`
- Magic-link auth token mint

**P1 (unblocks v9.2):**
- OAuth bridge for Google / Slack / GitHub (so users don't register their own apps)
- $MEEET balance reader → SPL on Solana
- Solana receipt anchor relayer (so operator key isn't required)

**P2 (unblocks v9.3 multi-tenant):**
- Workspace fence enforcement at gateway
- Tenant-scoped webhook delivery
- Marketplace payout rails

---

## Killer experiments worth 1-2 weeks each

From the product roadmap. Pick one for v9.2:

| Experiment | Hypothesis | Test |
| --- | --- | --- |
| Browser extension | TARS as Chrome extension that opens contextual agents on the current page | Show HN once + reach 1k installs in week 1 |
| Voice-first mode | Wake-word + dictation as primary input, not chat | A/B test in cockpit: which mode users keep using on day 7 |
| On-device fine-tune per pack | Tiny LoRA per playbook on user's data | Quality vs cloud baseline on standard prompts |
| MCP marketplace inside Claude Desktop | TARS marketplace listings exposed via MCP | Anthropic Discovery surface, real users |
| BYO-LLM wizard | 60-second setup for Ollama / LM Studio | Drop-off rate vs current setup |

---

## Pivots to AVOID

Burned by these in past Waves — don't relitigate:
- Don't add more agents (v7.1 had 8, current has 3 — fewer is better)
- Don't add 3D / neural visualizations (deleted in Wave 71)
- Don't add i18n until 1000 users (deleted Wave 36)
- Don't compete with Claude Desktop on chat UI (use it for what it's good at, differentiate on operator tooling)
- Don't compete with Cursor on code editing
- Don't ship a web SaaS (the local-first wedge is the moat)
- Don't add named-customer branding to marketing
- Don't add Quests / gamification to cockpit (deleted Wave 71)

---

## Honesty floor — what we will NOT claim until shipped

From the roadmap doc. Until each row is honestly true:

| Bad claim | True state today |
| --- | ---------------- |
| "Multiplayer agent sessions" | Backend module ships; UI is v9.1.1 |
| "Audit-anchored on Solana" | Code real, off-by-default, needs operator keypair |
| "Marketplace for skills" | Browse + install + ratings ship; payouts v9.3, third-party publish v9.2 |
| "Multi-tenant SaaS" | Single-operator; v9.2 initial, v10.0 full |
| "Real AI Clone" | v0.1 style hint heuristic; real fine-tune v9.2 |
| "Notarized installer" | Ad-hoc codesign; install.sh handles xattr |
| "Background daemon" | Lifespan loops in FastAPI process; real launchd plist v9.2 |
| "MCP server bridge" | Doesn't exist (tasks #17, #85 dishonestly marked done) |

---

## How this plan evolves

This is a **living document**. After every major Wave, I'll update:
- North Star refinement (if competitive landscape shifts)
- Next 7 days list (always 7 days forward)
- What I do autonomously / What operator does / What brother does

Operator can update via `tars-ops` → 6 — Cursor sync (appends a
SYNC marker to AGENT_HANDOFF so the next chat picks it up).

---

## Three honesty fixes shipped with this plan

The Reality Audit caught three drifts. Two are doc-only; one is a
strike-through of incorrectly-completed historic tasks:

1. **WHAT_WORKS.md row "iMessage bridge — Mac-only stub"** —
   `backend/core/notifications/imessage.py` does not exist. Even the
   stub is fictional. Strike through, move to NOT IMPLEMENTED.

2. **WHAT_WORKS.md row "Background TARS daemon"** —
   `backend/core/background/` directory does not exist. The "daemon"
   is three lifespan loops in `web_extras/app.py` that die with the
   FastAPI process. Strike through, move to NOT IMPLEMENTED with a
   "v9.2 real launchd plist" target.

3. **Tasks #17 (MCP-сервер мост) and #85 (MCP server reference) in
   the historic task log** — marked complete, code path absent.
   Document this drift; will fix in Wave 149 by actually building
   the bridge OR explicitly striking the tasks.

Sources cited inline. The audit reports are linked at the top of
this doc — anyone questioning these conclusions should read them.

---

## Bottom line

**TARS v9.1.0 is launched and honestly does what its honesty floor
says it does.** That's a serious accomplishment.

The roadmap above takes it from "launched" to "the local-first
operator console people reach for" within 6 months. The single
highest-leverage thing in the next 7 days is **Cowork HTTP routes
landing** — without them the multiplayer claim cannot ripen. The
single highest-leverage thing for brand health is **Apple cert** —
without it every new user sees a Gatekeeper warning.

Everything else can slip. Those two cannot.
