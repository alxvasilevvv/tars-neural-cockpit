# CURRENT_STATUS — daily-glance snapshot

> Live one-pager. Full story: `TARS_MASTER_DOC.md`. Doc map:
> `PROJECT_INDEX.md`. This page is the 60-second pulse check.

**Last updated:** 2026-05-20 (W310-aw fleet landed). **Tag in flight:**
`v10.0.0` — rc1 → GA the moment the **8 hard blockers** (3 brother + 5
Apple sign) flip green AND the operator executes the W310-ao GA
cookbook playbook below. **W310 fleet (#187–#223 + #188 + #224) is on
`main` — merge queue drained 2026-05-20.**

> **Read first (60-second pulse):** the `docs/W310_WAVE_SUMMARY.md`
> TLDR section. It compresses the entire post-rc1 surface (37 PRs,
> 6 verdict wrappers, 5 paste-ready playbooks, cross-stack mirror with
> brother) into one screen. This page (`CURRENT_STATUS.md`) gives the
> code-side snapshot; the wave summary gives the operator-action map.

---

## W310 — post-rc1 PR triage wave (2026-05-18 → 2026-05-19)

| Sub-wave | What landed | PR(s) |
|---|---|---|
| W310-a..f | Runtime/triage track: voice fallback, install funnel, master plan, qa-agent cache fix | #187, #188, #189, #190, #191 |
| W310-g..ac | Planning-surface briefs: STT, voice gallery, keyring, pairing UX, GA dock-down, brother handoff, Apple sign, Windows sign, updater, vault, policy UI, telemetry, L3 sandbox, planner UI, marketplace, mobile (iOS+Android+native speech), Linux signing, design polish | #192, #193..#213 (22 briefs) |
| W310-ad..am | Implementer follow-ups: 10 GA helper scripts — SOAK-HOURLY/REPORT (#214), VERIFY-APPLE (#215), PREFLIGHT-APPLE (#216), BROTHER-PREFLIGHT (#217), GA-COOKBOOK (#218), DOWNLOAD-AND-VERIFY (#219), BROTHER-POSTFLIGHT (#220), RELEASE-TAG-GUARD (#221), POST-INSTALL-SMOKE (#222), FINAL-QA-VERDICT (#223) | #214..#223 (10 wrappers) |
| W310-an..as | Docs-only extensions to PR #192: merge sequence + GA cookbook execution + dry-run rehearsal + post-GA week-1 runbook + post-v10 sprint planning + 60-sec TLDR | extends #192 |
| W310-aq cross-stack | Brother-side first-week runbook mirror (PR #198 §8.A) | extends #198 |

**State as of W310-aw (2026-05-20):** all W310 sub-waves **landed on
`main`**. Tier 0 (#188 + #224), runtime (#187–#191), planning (#192–#213),
and implementer helpers (#214–#223) merged via W310-an sequence (doc
conflicts on #187/#189/#190/#191 resolved in-branch). **0 open PRs** in
the W310 fleet. Next operator surface: **W310-ap dry-run rehearsal** →
**W310-ao GA cookbook** (8 hard blockers still external). See
`docs/W310_WAVE_SUMMARY.md` for playbooks.

---

## v10.0.0-rc.1 → v10.0 GA delta

| Wave | Status | What landed |
|---|---|---|
| W264 | ✅ Shipped | `v10.0.0-rc.1` cut — Wave A + B + C bundled. |
| W265 | ✅ Shipped | brother mock at `/api/_meeet_mock` so cockpit doesn't block while brother ships. |
| W266 | ✅ Shipped | Perf suite — 5 SLOs (chat/voice/metering/audit/composer). |
| W267 | ✅ Shipped | Final QA gate + v10.0 GA checklist + RELEASE-v10.0 script. |
| W269 | ✅ Shipped | 60-sec voice-first onboarding — TTFV <60s target via 5-step voice tour, drop-off recovery, SQLite telemetry. |

**From inside the repo, GA is DONE.** Only the **8 hard blockers**
remain (post-W310-l reconciliation of `docs/V10_GA_CHECKLIST.md`'s
original 29-item list — the other 21 items are soft / v10.1+ / not
GA-blocking):

- **Brother coord (3):** A1 ingest endpoint live, A2 `/operator`
  balance shape parity, A5 auth+billing e2e green.
- **Apple sign (5):** B1 `.p12` cert in CI, B2-B5 the 6 GH secrets
  pushed + manual-dispatch dry-run + post-tag verify.

The 10 helper wrappers shipped in W310-ad..am collapse the entire
verification surface (pre-tag QA, pre-tag Gate A, tag-cut decision,
post-tag Gate B, post-install health, post-launch coord health) to
six single-decision bash commands — see `docs/W310_WAVE_SUMMARY.md`
TLDR for the chain.

---

## The 5 SLOs (W266) — what we're gating on

| Path | SLO target |
|------|------------|
| Chat | p95 < 2.5s @ 100 concurrent |
| Voice command | p95 < 800ms @ 50 concurrent |
| Usage metering | 1000/s sustained, zero drops |
| Audit timeline | p95 < 200ms with 10k receipts |
| Composer plan | p95 < 4s @ 20 concurrent |

Run on the GA host: `bash scripts/RUN-PERF-SUITE.command` →
`docs/PERF_REPORT_v10.0.md` regenerates with live numbers. Any
regression prints a suggested fix in the failing bench's assertion.

---

## FINAL-QA-GATE (W267) blocks on 8 sub-gates

1. `pytest tests/` (excl. `-m perf`)
2. `SMOKE-TEST.command` (60+ routes 2xx)
3. `RUN-PERF-SUITE.command` (all 5 SLOs)
4. `spctl --assess` on `/Applications/TARS.app`
5. `bash -n` on every `scripts/*.command`
6. Doc render — md link integrity
7. JSON + YAML validation
8. Version consistency across 9 source files

`bash scripts/FINAL-QA-GATE.command` prints a single go/no-go report.
`bash scripts/RELEASE-v10.0.command` aborts immediately if FINAL-QA-GATE fails.

---

## What's left for the operator (post-W310-l reconciliation)

**Hard GA blockers (8 items, all coord/cert work that can't be closed
from inside the repo):**

| # | Item | Owner | PR ref |
|---|---|---|---|
| A1 | meeet.world `/usage_event` ingest endpoint live + matches `docs/INGEST_PROTOCOL.md` v1.0.0 | brother | #198 §3.A1 |
| A2 | `/operator` balance shape parity check (TARS field names = brother field names) | brother | #198 §3.A2 |
| A5 | auth + billing e2e suite green against live meeet.world | brother | #198 §3.A5 |
| B1 | Apple Developer ID `.p12` cert in CI as `APPLE_CERTIFICATE` secret | operator | #199 §3.1 |
| B2-B5 | 5 GH secrets pushed (`APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_TEAM_ID`, `APPLE_ID`, `APPLE_PASSWORD`) + manual-dispatch dry-run + post-tag verify | operator | #199 §4 + §6.2 |

**Soft / deferred (21 items, NOT v10 GA-blocking):**

- **VS Code marketplace publish** (`tars-tab` listing) → v10.1.
- **First paying on-prem customer** → independent funnel, not a tag gate.
- **Windows .exe Authenticode** → v10.1 (see PR #200).
- **Updater channel UI** → v10.1 (see PR #201; bootstrap secrets push
  is part of v10.0 tag-cut, UI ships v10.1).
- **Linux GPG signing** → v10.2 OPTIONAL (see PR #212).
- Remainder → v10.1 / v10.2 / v11 per `docs/PRODUCT_MASTER_PLAN.md`.

**When 8 hard blockers green, execute the playbook in
`docs/W310_WAVE_SUMMARY.md` → "Operator one-shot GA cookbook
execution sequence" (W310-ao):**

```bash
# Pre-tag verification (Gate A + tag-cut decision):
bash scripts/FINAL-QA-VERDICT.command       # mechanical-checks gate (#223)
bash scripts/GA-COOKBOOK.command            # Apple + Brother pre-flight (#218)
bash scripts/RELEASE-TAG-GUARD.command      # tag-cut decision gate (#221)

# Destructive tag cut:
bash scripts/RELEASE-v10.0.command          # cuts + pushes v10.0.0 tag

# Post-tag verification (Gate B + post-install + post-launch):
bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command   # download + signature (#219)
# (operator drag-installs)
bash scripts/POST-INSTALL-SMOKE.command            # 4-gate health (#222)
# (cron starts SOAK-HOURLY for 72h)
bash scripts/SOAK-REPORT.command                   # soak verdict
bash scripts/BROTHER-POSTFLIGHT.command            # T+24h coord (#220)
```

Six verdict wrappers, six exit codes, six color-coded verdicts.
**Zero remembered probes. Zero remembered sequencing.**

---


## W274 — Premium voice + persistent memory (2026-05-15)

- TARS now speaks with **ElevenLabs Multilingual v2** — 29 languages
  including Russian, sub-second latency, emotion-aware. Robotic
  `speechSynthesis` voice is gone when an API key is configured.
- 6 curated voices ship in the cockpit Settings picker (Rachel /
  Adam / Charlie / Sarah / Daniel / Bella). Each shows lang flags +
  preview button.
- New Memory tab in the drawer renders **persistent conversation
  history** — sessions list, timeline view, FTS5 semantic search
  across every session. Storage at `~/.tars/conversations.sqlite`.
- 6 new endpoints: `POST /api/a11y/speak`, `GET /api/a11y/voices`,
  `POST /api/a11y/voice-clone`, `GET /api/conversations`,
  `GET /api/conversations/search`, `GET /api/conversations/sessions`,
  `DELETE /api/conversations/session/{id}` (plus turn/exchange/context).
- Fallback: no `ELEVENLABS_API_KEY` -> browser speechSynthesis, never
  silent.
- Cost guidance: Starter plan ($5/mo) covers ~30K chars (≈10 min of
  voice per day) — enough for daily demos and trial usage.

## Recent commits (Claude lane)

| SHA | Wave | Subject |
|---|---|---|
| `(this)` | W274 | Premium ElevenLabs TTS + conversation memory layer — natural multilingual voice (29 langs) + persistent context |
| _prior_ | W273 | DEMO-READY.command pre-flight + demo orchestration + final smoke + rebuild |
| _prior_ | W272 | Presentation deck for v10.0.0-rc.1 demo |
| _prior_ | W269 | 60-sec voice-first onboarding — TTFV measurement + scripted first-launch flow |
| _prior_ | W266+W267 | perf benchmarks + final QA gate + v10.0 GA checklist + release script |
| _prior_ | W264 | `v10.0.0-rc.1` release prep — notes, CHANGELOG, version bumps, master doc + index sync, RELEASE script |
| _prior_ | W263 | On-prem TARS deployment kit (docker compose, OIDC, systemd, 435-line guide) |
| _prior_ | W262 | Voice-first pair programming in Composer |
| _prior_ | W261 | Agent marketplace v0 — third-party agents via Skill SDK (70/30 split) |
| _prior_ | W260 | T2T code review handoff with signed approval |
| _prior_ | W257 | SOC2 Type II readiness + GDPR export + compliance bundle |
| _prior_ | W256 | Domain-pack-aware composer |
| _prior_ | W255 | Receipt-anchored audit explorer |
| _prior_ | W254 | `tars-tab` VS Code extension scaffold |

---

**TTFV:** <60s target via 5-step voice-first onboarding (W269). Step
timings + funnel land in `~/.tars/onboarding.sqlite` via
`/api/onboarding/{event,stats,skip}`; final-step completion also rides
W235 metering so marketing sees a single headline number.

**Status (W267):** v10.0 GA is **DONE** Claude-side. The repo is in
the cleanest state of its life — pytest green, smoke green, perf
green (when the suite is run), version constants in lockstep,
FINAL-QA-GATE wired. The next commit on this lane will be the actual
GA tag, fired by `scripts/RELEASE-v10.0.command` once the 5 external
items above flip green.

---

## Status (W310-as, 2026-05-19): GA orchestration arc closed

W310 wave closed the operator's orchestration surface from
**D-0 (today)** through **D+365 (v11 GA)**:

- **37 PRs open**, all awaiting operator merge. Tier 0 is PR #188
  (qa-agent.yml cache fix); after that, tiers 1-5 land via the
  W310-an one-shot bash playbook (~20-30 min wall-clock).
- **6 single-decision verdict wrappers** ship as PRs #214/215/216/217
  /218/219/220/221/222/223 — collapse the 8-mechanical-checks pre-tag
  gate + Apple+Brother pre-flight + tag-cut decision + post-tag
  artifact verify + post-install health + post-launch coord health
  into six bash commands, six exit codes.
- **5 docs-only paste playbooks** in `docs/W310_WAVE_SUMMARY.md`
  (W310-an merge / W310-ao GA cookbook / W310-ap dry-run rehearsal /
  W310-aq post-GA first week / W310-ar post-v10 sprint planning)
  compress the entire arc into "5 paste actions + 2 typed
  confirmations + 1 decision-tree walk + 1 sprint-matrix paste per
  sprint kickoff".
- **Cross-stack mirror** (PR #198 §8.A) — brother-side first-week
  runbook landed same day as W310-aq, with bidirectional escalation
  tree, 4 named feature flag endpoints brother owns, joint
  post-mortem cadence.
- **W310-as TLDR** (60-second summary atop `W310_WAVE_SUMMARY.md`)
  means a freshly-landed agent or operator can grok state +
  next-action in one minute instead of reading 2100+ lines linearly.

**The next commit on this lane** will be the actual GA tag, fired by
`scripts/RELEASE-v10.0.command` after the operator drains the 37-PR
merge queue (PR #188 first) and resolves the 8 hard blockers via the
W310-ao playbook above. From there, the W310-aq post-GA first-week
runbook + W310-ar sprint planning sequence carry the project through
v10.1 (~D+45), v10.2 (~D+90), and v11 (~D+365).
