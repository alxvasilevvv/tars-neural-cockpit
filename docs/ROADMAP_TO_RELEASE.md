# Roadmap to release — TARS + meeet.world (Cursor lane master plan)

> Owner: Cursor agent (this file). Mirrors live in:
> - `meeet-solana-state-941a6045` (Lovable lane) — pulled into PR commentary.
> - `meeet-browser-agent` — referenced in `AGENTS.md` pointer.
>
> Date: 2026-05-01. Last refresh: see git log on this file.

This document is the single, exhaustive plan to take the entire stack
(`tars.meeet.world` cockpit + `meeet.world` core + automation) from current
mid-flight state to a production-grade release. Every variable, every
button, every link, every flow is accounted for.

It is organised as **Phases → Slices → Acceptance**. Each slice has an
owner (Cursor / Lovable / shared) and a concrete acceptance check.

---

## 0. Current state (snapshot 2026-05-01 15:00 UTC+7)

- Two repos in scope:
  - `meeet-solana-state-941a6045` (the public meeet.world site, Solana state, dashboards, agents) — Lovable-led.
  - `tars-neural-cockpit` / `Jarvis/jarvis` (TARS cockpit, backend, showcase v2/v3, design system, docs) — Cursor-led.
- Live PRs (Cursor):
  - core PR #6 — navbar e2e realignment (MERGEABLE).
  - core PR #7 — Control Tower + bridge hardening + `SOFT_SMOKE` (MERGEABLE).
  - tars PR #31 — handoff docs + release runbook (MERGEABLE).
- Tests: TARS backend 686/686 ✅, showcase v3 63/63 ✅, core 332/337 (PR #6 fixes the 6 pre-existing reds), gate `npm run gate:control-tower` green in `SOFT_SMOKE=1`.
- Languages: default lang switched to **English** (forced via `meeet-lang-v2` localStorage bump). RU still selectable via navbar switcher. Top-3 most-mixed pages translated to clean EN baseline (`Tars`, `Tokenomics` SEO, `Settings`).
- Outstanding hard blockers: none. Outstanding soft blockers: residual RU-only strings on ≈40 secondary pages (catalogued below).

---

## 1. Phase A — i18n parity to English-default (Cursor + Lovable)

Goal: every public-facing surface defaults to English on a fresh visit
and never mixes RU and EN in a single render.

### A.1 — Force English default for new and returning visitors  ✅ DONE

- File: `src/i18n/LanguageContext.tsx`.
- Bumped storage key `meeet-lang` → `meeet-lang-v2`. Legacy `ru` value is
  intentionally not migrated; legacy non-`ru` values still migrate.
- Side effect: every visitor sees English the first time the deployed
  build hits their browser. They can switch back via the navbar.
- Acceptance: open the deployed site in incognito → site is English; flip
  to RU → it persists in `meeet-lang-v2`.

### A.2 — Top-priority public pages — clean EN baseline  ✅ DONE for 3, NEXT for the rest

| Page | State | Owner | Notes |
| --- | --- | --- | --- |
| `src/pages/Tars.tsx` | ✅ done | Cursor | All STATS, FEATURES, MODES, FAQ, RELEASE_NOTES, share buttons, install, version selector localised to EN. |
| `src/pages/Tokenomics.tsx` (SEO) | ✅ done | Cursor | SEO `<title>` and `<description>` switched to EN. Body already uses `{en, ru}` pairs. |
| `src/pages/Settings.tsx` | ✅ done | Cursor | All NOTIF_OPTIONS, toasts, section titles, danger zone, SEO localised to EN. |
| `src/pages/Index.tsx` | ✅ already correct | Lovable | Has `domainLabelsEn` + `lang === "ru"` gates. Only fires Russian when the user actively opts in. |
| `src/pages/Deploy.tsx` | ✅ already correct | Lovable | Uses `{en, ru}` dictionaries everywhere relevant. |
| `src/pages/LiveDashboard.tsx` | 🟡 next | Lovable | 79 cyrillic occurrences. Mostly labels and tooltips. |
| `src/pages/Referrals.tsx` | 🟡 next | Lovable | 69 cyrillic occurrences (RU-only marketing copy). |
| `src/pages/ArenaEnhanced.tsx` | 🟡 next | Lovable | 68 cyrillic. |
| `src/pages/Staking.tsx` | 🟡 next | Lovable | 67 cyrillic. |
| `src/pages/Economy.tsx` | 🟡 next | Lovable | 67 cyrillic. |
| `src/pages/Parliament.tsx`, `Marketplace.tsx`, `Token.tsx`, `Evolution.tsx`, `Discoveries.tsx`, `Quests.tsx`, `World.tsx`, `Activity.tsx`, `BreedingLab.tsx`, `Academy.tsx`, `Consensus.tsx`, `Passport.tsx`, `DeveloperPortal.tsx` and ~20 secondaries | 🟡 next | Lovable | Same pattern: hardcoded RU literals → either move to `LanguageContext` keys or to `{en, ru}` inline pairs. |

Acceptance per page:
1. `rg "[А-Яа-яЁё]" src/pages/<page>.tsx` returns no public-string hit (only comments allowed).
2. With `lang=en` (default), the entire page renders in English.
3. With `lang=ru`, RU is the source of truth (no mixed rendering).
4. Vitest suite still green: `npm run test:e2e:vitest`.

### A.3 — Component sweep

Same exercise across `src/components/` (esp. `AskAINationSection`, `TopicPicker`, `OnboardingBanner`, `KnowledgeGraphExplorer`, `AINationCouncil`, `TreasuryAdminPanel`, `AgentNeuralNetwork`, `RouteSkeleton`, `NavAcademyProgress`, `ErrorBoundary`).

### A.4 — TARS cockpit (Jarvis)

The TARS cockpit (`frontend/`) is already EN-first. Showcase v3 uses
`useT()` hook from `src/lib/i18n` — verify `defaultLang === "en"` and
that no component does `lang === "ru"` fallback.

Acceptance: TARS cockpit and `experiments/neural-showcase-v3/` both
render EN by default in incognito.

### A.5 — Documentation surface (no user-facing impact)

`docs/**` may stay bilingual where it is internal (CHANGELOG, AGENT_HANDOFF). All public-facing markdown (`docs/RELEASE_NOTES_*`, `docs/LAUNCH_*`) must be EN-canonical with optional RU mirrors.

---

## 2. Phase B — QA Agent (Cursor lane)

Goal: a single executable that visits every public route, clicks every
button, follows every link, exercises every form, and validates the
deploy / agent management flow end-to-end. Reports must include:
HTTP status, JS errors, console warnings, broken images, missing alts,
broken anchors, slow LCP, CSP violations, mixed content, accidental
RU-on-EN-page or vice versa.

### B.1 — Architecture (this section is the design doc)

Two-layer split:

**Layer 1 — Static probes (existing TARS qa_agent)**
- Path: `Jarvis/jarvis/scripts/qa_agent/`.
- Tech: Python stdlib only, no deps.
- Scope: DNS, TLS, security headers, sitemap/robots, manifest CORS, SPA route 200, downloads JSON shape, ingest auth/CORS, tokenomics invariants.
- Trigger: `python -m scripts.qa_agent` (cron / GH Actions / manual).
- Already implemented and passing.

**Layer 2 — Browser-driven probes (new)**
- Path: `meeet-solana-state-941a6045/qa-suite/` (new top-level folder).
- Tech: Playwright + TypeScript (Playwright is already a devDep in this repo).
- Scope: every public route, every button, every link, every form, deploy flow with mocked wallet, agent CRUD, language switcher, theme behaviour, toast lifecycle, SPA navigation, broken images, console errors.
- Trigger: `npm run qa:browser` (local), `qa-suite/playwright.config.ts` (CI).

The two layers communicate via a shared **JSON report schema**:

```jsonc
{
  "version": "qa-report/1.0.0",
  "started_at": "...",
  "finished_at": "...",
  "trace_id": "...",
  "probes": [
    {
      "name": "page.deploy.buttons",
      "category": "functional",
      "status": "pass" | "warn" | "fail" | "skip",
      "details": "...",
      "evidence": { "screenshot_path": "...", "console": [...] }
    }
  ],
  "summary": { "pass": 123, "warn": 4, "fail": 0, "skip": 2 }
}
```

The Layer-1 probes already emit a compatible shape; we extend it.

### B.2 — Probes catalogue (Layer 2)

Each probe is a Playwright test file under `qa-suite/probes/`. Naming:
`<area>.<feature>.spec.ts`. Probes:

1. **`routing.discover.spec.ts`** — pulls `/sitemap.xml`, queries every
   route in turn, asserts 200, checks `<title>` is non-empty, checks no
   `Loading…` left after 5s, takes a screenshot.
2. **`navigation.navbar.spec.ts`** — desktop + mobile nav: every
   top-level item, every dropdown item, every CTA. Click → URL changes →
   target page renders.
3. **`navigation.footer.spec.ts`** — every footer link returns 200 (or
   external links return reachable host).
4. **`forms.contact.spec.ts`** — every form on the site: empty-submit
   shows validation, valid submit shows toast, no console errors.
5. **`deploy.flow.mock.spec.ts`** — `/deploy` page: mocks Solana wallet
   adapter (custom Phantom mock), selects each plan, clicks deploy,
   asserts success/error toast and analytics event fire.
6. **`agents.crud.spec.ts`** — `/agents` and `/agent-marketplace`: list,
   open detail, deploy, edit (where allowed), delete (where allowed).
7. **`i18n.parity.spec.ts`** — for each public page, default visit
   renders 0 cyrillic characters in visible body. Switch to RU →
   renders cyrillic. Switch back → no cyrillic remains.
8. **`assets.images.spec.ts`** — every `<img>` returns 200, has `alt`,
   width/height defined.
9. **`assets.console.spec.ts`** — for each page, `page.on('console')`
   collects warnings/errors. Page fails if `console.error` count > 0.
10. **`a11y.axe.spec.ts`** — runs `@axe-core/playwright` on every page,
    fails on `serious` or `critical` violations.
11. **`api.tars-bridge.spec.ts`** — calls `/functions/v1/tars-downloads`
    and a sample protected ingest with API key, asserts CORS + status.
12. **`api.core-rest.spec.ts`** — exercises a curated set of public
    Supabase RPC / view endpoints (read-only).
13. **`perf.lcp.spec.ts`** — collects `LCP` from `PerformanceObserver`
    on each landing route. Warn > 2.5s, fail > 4s.

### B.3 — Implementation plan

| Step | Owner | Deliverable |
| --- | --- | --- |
| 1 | Cursor | Skeleton: `qa-suite/{playwright.config.ts, package.json (scoped), tsconfig.json, README.md}`. |
| 2 | Cursor | Fixture: `qa-suite/fixtures/site.ts` — base URL from env, axe loader, console collector, screenshot helper. |
| 3 | Cursor | Probe 1 (`routing.discover`) + report writer (`qa-suite/lib/report.ts`). |
| 4 | Cursor | Probes 2, 3, 7, 8, 9, 13 (no auth needed). |
| 5 | Cursor + Lovable | Probe 5 (deploy mock) — needs Lovable to expose `data-testid` on plan cards and CTAs. |
| 6 | Cursor + Lovable | Probe 6 (agents) — needs `data-testid` on agent rows. |
| 7 | Cursor | Probe 10 (axe) + probe 11/12 (api). |
| 8 | Cursor | CI workflow: `.github/workflows/qa-suite.yml` runs nightly + on PR labelled `qa`. |

### B.4 — Acceptance

- `npm run qa:browser` from a clean clone goes green in <5 minutes for a
  warm cache.
- A single failing button anywhere on the site produces a Playwright HTML
  report with screenshot + DOM snapshot + console log, pinpointing the
  exact `data-testid`.
- Report schema is stable so Layer-1 probes can be merged into one
  combined dashboard later.

### B.5 — Optional follow-up — autonomous QA agent

Once the Playwright suite stabilises, an autonomous loop wraps it:

```
1. Pull latest main.
2. Build site, start preview server.
3. Run qa:browser → report.json.
4. If fail: open GH issue with report attached + screenshots.
5. If pass: post green badge to release runbook.
6. Repeat every 6h on staging, every 30min on prod.
```

That loop lives in `Jarvis/jarvis/scripts/qa_agent/loop.py` (extending
the existing runner.py), using `gh issue create` + `gh pr comment`.

---

## 3. Phase C — TARS finalisation

Goal: TARS cockpit + showcase + backend + downloads bridge are
production-clean, fully EN, and matched to the published runbook.

### C.1 — Cockpit + showcase
- ✅ `frontend/` already EN.
- 🟡 verify `experiments/neural-showcase-v3/src/lib/i18n.ts` defaults to `en` and supports lang switcher.
- 🟡 ensure all `<SEOHead/>` tags on public TARS routes (`/tars`, `/tars-dashboard`, `/cockpit`) are EN.

### C.2 — Backend
- ✅ Domain packs, awareness streams, council, policy gate, playbooks all green (686/686).
- 🟡 add a `/api/qa/health` endpoint that returns the latest qa-suite report digest (for dashboards).
- 🟡 add `MeeetClient.replay_unpushed()` cron tick to ensure offline events flush.

### C.3 — Downloads bridge
- ✅ `tars-downloads` and `tars-ingest` deployed with origin allowlist + API key.
- 🟡 wire `tars-ingest` into the `awareness.snapshot.completed` event so meeet.world receives a heartbeat per snapshot.

### C.4 — Acceptance
- `make smoke-tars` green.
- `make smoke-core-bridge` green with prod creds.
- `npm run gate:control-tower` green WITHOUT `SOFT_SMOKE`.

---

## 4. Phase D — Release readiness gate

Single command tells you whether the whole system is ready to ship.

```bash
make gate-release
```

Behind the scenes:
1. `pytest -q` (TARS backend, 686/686).
2. `npm test` (TARS showcase v3, 63/63).
3. `npm run test:e2e:vitest` (core repo, 337/337 once PR #6 lands).
4. `npm run build` (core repo).
5. `npm run gate:control-tower` (core repo, full mode, no SOFT_SMOKE).
6. `npm run qa:browser` (qa-suite, all probes green or warn-only).
7. `python -m scripts.qa_agent` (TARS Layer-1 probes).

If any step fails, gate exits non-zero and prints the failing step.
If all green, prints `RELEASE GATE: GREEN  trace_id=…` and writes the
trace to `docs/release-evidence/<trace_id>.json` for audit.

---

## 5. Stage-by-stage delivery sequence (calendar)

Day 0 (today, 2026-05-01):
- ✅ A.1 done (force EN default).
- ✅ A.2 top-3 done (Tars, Tokenomics, Settings).
- ✅ B.1 design doc landed (this file).
- ✅ Phase 0 PRs open and MERGEABLE.

Day 1:
- Lovable merges PR #6 (navbar e2e), then PR #7 (Control Tower).
- Lovable redeploys edge functions with `TARS_INGEST_API_KEY` and `TARS_ALLOWED_ORIGINS`.
- Cursor opens PR for QA-suite skeleton (B.3 step 1) on core repo.

Day 2:
- Cursor lands probes 1, 2, 3, 7, 8, 9, 13.
- Lovable adds `data-testid` to deploy / agent UI per the QA-suite README.

Day 3:
- Cursor lands probes 5, 6, 10, 11, 12.
- First full `npm run qa:browser` against staging.

Day 4:
- Lovable continues i18n sweep on remaining ~40 pages.
- Cursor wires CI workflow + nightly autonomous loop.

Day 5:
- Run `make gate-release`. If green: ship.

---

## 6. Variables and secrets matrix

| Var | Where | Owner | Required for |
| --- | --- | --- | --- |
| `TARS_INGEST_API_KEY` | TARS Supabase project secrets | Lovable | smoke_tars_bridge.sh, ingest auth |
| `TARS_ALLOWED_ORIGINS` | TARS Supabase project secrets | Lovable | edge function origin gate |
| `SOFT_SMOKE` | local dev shells, CI for cursor lane | Cursor | letting `gate:control-tower` skip auth probe locally |
| `MEEET_INGEST_URL` | TARS server env | Cursor | bridge events egress |
| `MEEET_API_KEY` | TARS server env | Cursor | bridge events auth |
| `MEEET_SOURCE` | TARS server env | Cursor | event source tagging |
| `CORE_SUPABASE_URL` / `CORE_SUPABASE_ANON_KEY` | optional, both lanes CI | shared | `smoke_old_core_connectivity.sh` |
| `STAGING_BASE_URL` | qa-suite env | Cursor | playwright suite target |

---

## 7. Roll-back plan

- Anything in PR #6 / #7 / #31 reverts cleanly via `git revert`.
- LanguageContext bump is also reversible via revert; old `meeet-lang`
  values still survive untouched in browser localStorage so a revert
  restores the prior behaviour for legacy users.
- Edge function changes: previous version is in Supabase function
  history — `supabase functions deploy <name> --version <prev>`.

---

## 8. Done definition

The release is "done" when:

1. `make gate-release` is green.
2. All Lovable / Cursor PRs in the milestone are merged.
3. QA-suite report has 0 fails and `<5%` warns over a 24h window.
4. Default-EN parity holds across all public routes (i18n parity probe is green).
5. The runbook in `docs/RELEASE_RUNBOOK_2026-05-01.md` has its checklist
   100% ticked.

This document is the **single source of truth** for "what is left and who
owns it". Update it whenever a slice changes state.
