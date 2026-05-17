# W310 — Post-rc1 PR triage wave · summary

**Owner:** Cursor agent (Claude Opus 4.7) — autonomous orchestration window
**Window:** 2026-05-17 → 2026-05-18
**Lane:** PR hygiene + cross-cutting closeouts on top of `v10.0.0-rc.1`
**Branch home:** `cursor/post-rc1-master-plan` (PR #188), plus per-extraction branches
**Status:** ✅ All sub-waves landed; 12 PRs open awaiting operator merge

---

## Why W310 exists

After `v10.0.0-rc.1` was cut (W264, 2026-05-15) the repository carried
**14 open PRs** that had been stacked through Waves 80-95 — long-running
branches built against a `main` that had since absorbed three large
refactors (W264 release axis bump, OpenTelemetry pin, dynamic
`SUPPORTED_VERSIONS`). Several of them no longer rebased cleanly; a few
introduced regressions; one outright conflicted with an endpoint that
had already shipped on `main`.

W310's mandate: **forensic triage of every open PR**, with a per-PR
decision (rebase / close-and-rewrite / close-only / extract), and a
clean repository state heading into the v10.0.0 GA dock-down.

---

## Sub-wave map

| Sub-wave | Scope | Output |
| -------- | ----- | ------ |
| **W310-a** | Master plan composition — operator decision capture, release-axis archaeology, L5 crypto canon verification | `docs/PRODUCT_MASTER_PLAN.md` (PR #188), `docs/handoff/MCP_REWRITE_BRIEF.md` |
| **W310-b** | M-wave MCP stack closeout — 6 stale stacked PRs reviewed and closed with design-intel preservation comments | PR #176, #177, #178, #179, #180, #184 closed; consolidated rewrite scheduled per `MCP_REWRITE_BRIEF.md` |
| **W310-c** | CI infrastructure diagnosis — root cause of `qa-agent.yml` failures traced to GH Actions workflow-registration cache staleness since 2026-05-13 | Header-comment touch baked into PR #188; follow-up PR planned for other affected workflows |
| **W310-d** | W309 step 2 preparation — Playwright e2e scaffold (7 `test.skip()` scenarios mapped to the W309 step 2 brief), independent of PR #187 | PR #189 (draft); `docs/handoff/W309_STEP2_BRIEF.md` updated |
| **W310-e** | Install funnel v10 sync — close PR #175 (rebase impossible due to deep semantic drift), rewrite clean | PR #190; 4 bugs fixed (3 v10-exposed); 30/30 tests green |
| **W310-f** | L4.2 voice fallback hardening — close PR #183 (4 regressions: Jarvis voice ID, ElevenLabs tuning, docstring deletion, endpoint conflict), extract additive value only | PR #191; 164/164 voice+persona tests green; `docs/handoff/L4_2_VOICE_FALLBACK_EXTRACTION_BRIEF.md` |
| **W310-g** | This document — single-page wave summary so operator can orient before the merge sequence | PR #192; this file |
| **W310-h** | Phase 2 STT streaming + push-to-talk implementer brief (v10.1, ~38 h, 7 PRs) — accelerates the next L4-lane session | PR #193; `docs/handoff/PH2_STT_STREAMING_BRIEF.md` |
| **W310-i** | Phase 2 voice gallery UI implementer brief (v10.1, ~17 h, 4 PRs) — companion to W310-h, smaller-scope warm-up | PR #194; `docs/handoff/PH2_VOICE_GALLERY_BRIEF.md` |
| **W310-j** | Phase 3 cross-platform keyring implementer brief (v10.1, ~23 h, 6 PRs) — extends macOS-only secret storage to Windows Credential Manager + Linux Secret Service | PR #195; `docs/handoff/PH3_KEYRING_BRIEF.md` |
| **W310-k** | Phase 3 cockpit pairing/recovery UX implementer brief (v10.1, ~26 h, 7 PRs) — companion to W310-j; new `<aside class="security">` panel covering 5 L5 flows (recovery seed, add-device QR, devices list, audit timeline, identity rotation) | PR #196; `docs/handoff/PH3_PAIRING_UX_BRIEF.md` |
| **W310-l** | Phase 11 v10.0.0 GA dock-down brief (~6-8 h active + 72 h soak) — V10_GA_CHECKLIST reconciliation post-W310 (8 hard blockers vs 21 deferred), 72 h soak protocol (hourly probes, hard-fail thresholds), tag-cut protocol with per-step rollback gates | PR #197; `docs/handoff/PH11_QA_SWEEP_BRIEF.md` |
| **W310-m** | v10.0.0 brother coord handoff brief (~10-12 h cross-stack) — companion to W310-l; 7 concrete syncs convergence-only (no new endpoints), reclassifies 3 of 6 brother-side A-items out of hard-blocker set, surfaces `ph3-pair-ttl` as v10.2 brother slot | PR #198; `docs/handoff/PH11_BROTHER_HANDOFF_BRIEF.md` |

> **Sub-waves a..f are forensic triage on stacked PRs.** Sub-waves g..m
> are forward-leaning **planning surface** that reduces the briefing
> load on the next implementer session — Phase 2 voice loop + Phase 3
> security closeout for v10.1, plus the full v10.0.0 GA dock-down arc
> (Phase 11, TARS-side methodology + brother-side convergence). The
> two halves can be reviewed independently.

---

## Active PRs (12 open, all awaiting operator merge)

| # | Title | Wave | Status | Merge unblocks |
| - | ----- | ---- | ------ | -------------- |
| **#187** | W309 cockpit runtime step 1 — voice mode + WS + chat + TTS + vault hook-up | W309 | green except known CI cache issue | W309 step 2 implementation |
| **#188** | Post-rc1 master plan + 8 stale-PR closeouts + `qa-agent.yml` cache-fix header touch | W310-a..c | green except known CI cache issue | MCP consolidated rewrite + landing-report + cache fix on other workflows |
| **#189** *(draft)* | W310-d Playwright e2e scaffold for cockpit | W310-d | green except known CI cache issue | step 2 implementer opens to a green suite (just drop `.skip()` markers) |
| **#190** | W310-e install funnel v10 sync — Win/Linux artifacts, `LATEST_TAG`, pre-release filename regex | W310-e | green except known CI cache issue | cross-target updater channel + funnel for Tauri 2 cross-target builds |
| **#191** | W310-f L4.2 voice fallback hardening — additive extract from closed #183 | W310-f | green except known CI cache issue | L4 voice loop GA-ready |
| **#192** | W310-g wave summary (this doc) | W310-g | green except known CI cache issue | n/a — orientation doc, useful any time |
| **#193** | W310-h Phase 2 STT streaming + push-to-talk implementer brief | W310-h | green except known CI cache issue | next L4-lane session can start ph2-stt without spec work |
| **#194** | W310-i Phase 2 voice gallery UI implementer brief | W310-i | green except known CI cache issue | next L4-lane session can start ph2-voice-gallery without spec work |
| **#195** | W310-j Phase 3 cross-platform keyring implementer brief | W310-j | green except known CI cache issue | next L5-lane session can start ph3-keyring without spec work |
| **#196** | W310-k Phase 3 cockpit pairing/recovery UX implementer brief | W310-k | green except known CI cache issue | next L5-lane session can start ph3-pairing-ux without spec work; together with #195 covers the entire v10.1 Phase 3 surface |
| **#197** | W310-l Phase 11 v10.0.0 GA dock-down brief (reconciliation + soak + tag) | W310-l | green except known CI cache issue | gives operator a single-document GA execution script; ph11-qa-sweep is now spec'd end-to-end |
| **#198** | W310-m v10.0.0 brother coord handoff brief (7-sync convergence) | W310-m | green except known CI cache issue | brother lane for v10 GA is now spec'd; together with #197 closes the full v10.0.0 GA dock-down arc on planning surface |

> **Known CI failure (cosmetic, repo-wide).** `TARS B2B E2E suite`,
> `TARS eval suite`, `scan working tree` all fail in 2-3 s on every
> PR cut after 2026-05-13. Root cause is a GH Actions workflow
> registration cache that went stale; PR #188 includes the
> single-character header-comment fix for `qa-agent.yml` and a
> follow-up PR is scheduled to apply the same trick to
> `e2e-suite.yml`, `eval-suite.yml`, `credential-sentinel.yml`,
> `scan-working-tree.yml`. **None of these failures reflect actual
> test results.**

---

## Closed PRs (W310)

### Stale M-wave MCP stack (6 PRs)

Closed in W310-b. All targeted the pre-rc1 cockpit and depended on each
other in a 6-deep stack that no longer rebased. Design intelligence
captured in `docs/handoff/MCP_REWRITE_BRIEF.md`; consolidated rewrite
will follow on a single fresh branch after PR #188 merges.

| # | Rationale |
| - | --------- |
| #176 | Wrong cockpit + stack base no longer rebasable |
| #177 | Stack child of #176; same |
| #178 | Stack child of #177; same |
| #179 | Stack child of #178; same |
| #180 | Stack child of #179; same |
| #184 | Mid-stack repaint; same |

### Algotrade Wave-M (2 PRs)

Closed in W310-a (operator decision D4: out of scope until post-v10 GA).
Re-open candidacy noted in `docs/PRODUCT_MASTER_PLAN.md §3.A`.

| # | Rationale |
| - | --------- |
| #170 | Algotrade E2E suite — out of scope for v10 GA |
| #174 | Algotrade Wave-M continuation — same |

### Other PR triage (W310-b/e/f)

| # | Wave | Outcome | Reason |
| - | ---- | ------- | ------ |
| #175 | W310-e | Close-and-rewrite as #190 | Hardcoded `_DEFAULT_ARTIFACTS` approach obsolete after dynamic `SUPPORTED_VERSIONS` refactor on `main`; 3 newly-discovered v10-exposed bugs found during forensic review |
| #181 | W310-b | Closed | Algotrade demo (same scope as #170/#174) |
| #182 | W310-b | Closed | Frontend targeted outdated `experiments/neural-showcase-v3` cockpit; backend depended on closed M-wave stack — graceful-degradation patterns preserved in `MCP_REWRITE_BRIEF.md §4` |
| #183 | W310-f | Close-and-extract as #191 | 4 regressions (Jarvis voice "George"→default, ElevenLabs cinematic tuning stripped, `PersonaProviderHint` docstring deleted, semantic conflict with already-shipped `/api/voice/personas/effective` endpoint from W295) |

---

## Recommended merge order

**Triage/runtime PRs (#187-#191):**

1. **#188 first** — unlocks the cache-fix follow-up + makes the master plan canonical (it's already referenced by `AGENTS.md` in `meeet-browser-agent`).
2. **#187** — unlocks W309 step 2 implementation.
3. **#189** — can land any time but ideally **after #187** so step 2 implementation opens with a green skipping suite.
4. **#190** — install funnel; landing earlier just means the cross-target funnel works sooner for testing.
5. **#191** — voice fallback hardening; landing earlier just means the L4 voice loop becomes GA-ready sooner.

**Planning-surface PRs (#192-#198):**

These are docs-only and have **no downstream code dependency** — merge
any time, in any order. Optimal time-to-value is to merge them whenever
operator has a 1-minute review window between the runtime merges.

All 12 are **independent** at the file level (no shared paths), so they
can also land in parallel. The order above only reflects which merges
unblock the most downstream work.

---

## Pending W310 follow-ups (post-merge)

- **`ph1-ci-cache-other-workflows`** — after PR #188 lands, apply the same `qa-agent.yml`-style header-comment trick to `e2e-suite.yml`, `eval-suite.yml`, `credential-sentinel.yml`, `scan-working-tree.yml`. **Mix-of-scopes risk** — done as a separate small infra PR, not bundled into anything else.
- **`ph1-mcp-consolidated`** — open `cursor/mcp-rewrite-consolidated` PR per `docs/handoff/MCP_REWRITE_BRIEF.md` after PR #188 merges (master plan needs to be canonical first so the new PR can cite §2.B of it).

Both items are tracked in the active todo list and will be picked up
autonomously once their merge prerequisites are met.

---

## Cross-workspace state

`meeet-browser-agent`'s `AGENTS.md` has been synced through W310 in three
passes:

- **W310-b** — initial #187 + #188 snapshot
- **W310-f** — expanded to full 5-PR fleet (#187-#191) plus known CI cache issue
- **W310-i** — re-expanded to the full 8-PR fleet (#187-#194) including the three
  planning-surface PRs and their per-PR effort estimates
- **W310-j** — added PR #195 (Phase 3 keyring brief) to the planning-surface
  track, lifting the active PR count to 9
- **W310-k** — added PR #196 (Phase 3 pairing/recovery UX brief, companion
  to #195) to the planning-surface track, lifting the active PR count to 10
- **W310-l** — added PR #197 (Phase 11 v10.0.0 GA dock-down brief, the
  release-engineering methodology that bridges existing scripts +
  checklist) to the planning-surface track, lifting the active PR count
  to 11
- **W310-m** — added PR #198 (v10.0.0 brother coord handoff brief,
  companion to W310-l) to the planning-surface track, lifting the
  active PR count to 12. The W310 wave now covers the full v10 → v10.1
  arc on planning surface alone — every implementer + coord question
  for the v10.0.0 GA tag has a spec'd brief.

Pickup pointer for any agent landing in the meeet workspace now lists all
12 active PRs, all closed stacks, and points at this wave summary as the
single-page operator-readable W310 retrospective.

---

## What this wave does NOT touch

- **Production runtime code on `main`** — all sub-waves operate on PR branches.
- **`v10.0.0-rc.1` artifacts** — no installer rebuild required; rc1 still ships as cut.
- **Phase L semantics** — L0-L9 contracts unchanged; #191's L4.2 work is purely additive.
- **Operator decisions** — D1-D4 captured in W310-a and unchanged here.

W310 is **PR-hygiene and forensic-extraction wave only**. v10.0.0 GA
dock-down begins as soon as #187 + #188 (and ideally #189-#191) land on
`main`.
