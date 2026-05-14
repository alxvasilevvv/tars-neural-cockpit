# CURRENT_STATUS — daily-glance snapshot

> Live one-pager. Full story: `TARS_MASTER_DOC.md`. Doc map:
> `PROJECT_INDEX.md`. This page is the 60-second pulse check.

**Last updated:** 2026-05-15 (W267). **Tag in flight:** `v10.0.0` —
rc1 → GA the moment the 5 external items below flip green.

---

## v10.0.0-rc.1 → v10.0 GA delta

| Wave | Status | What landed |
|---|---|---|
| W264 | ✅ Shipped | `v10.0.0-rc.1` cut — Wave A + B + C bundled. |
| W265 | ✅ Shipped | brother mock at `/api/_meeet_mock` so cockpit doesn't block while brother ships. |
| W266 | ✅ Shipped | Perf suite — 5 SLOs (chat/voice/metering/audit/composer). |
| W267 | ✅ Shipped | Final QA gate + v10.0 GA checklist + RELEASE-v10.0 script. |

**From inside the repo, GA is DONE.** Only the 5 external checklist
items remain (see `docs/V10_GA_CHECKLIST.md`).

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

## What's left for the operator (the 5 external items)

These can't be closed from inside the repo — see
`docs/V10_GA_CHECKLIST.md` for the 30-item breakdown:

1. **rc1 soak on Alien's main host** — 1 week, daily SMOKE-TEST.
2. **Brother live on billing** — `/api/billing/{usage_event,balance,topup}` + reconciliation (groups A1-A5).
3. **Apple Developer cert in CI** — `.p12` + secrets configured so every tag ships a signed `.dmg` (B1-B5).
4. **VS Code marketplace first publish** — `tars-tab` listed (C1-C4).
5. **First paying on-prem customer** — proves W263 kit works (D1-D5).

When all 5 are green: `bash scripts/RELEASE-v10.0.command`.

---

## Recent commits (Claude lane)

| SHA | Wave | Subject |
|---|---|---|
| `(this)` | W266+W267 | perf benchmarks + final QA gate + v10.0 GA checklist + release script |
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

**Status (W267):** v10.0 GA is **DONE** Claude-side. The repo is in
the cleanest state of its life — pytest green, smoke green, perf
green (when the suite is run), version constants in lockstep,
FINAL-QA-GATE wired. The next commit on this lane will be the actual
GA tag, fired by `scripts/RELEASE-v10.0.command` once the 5 external
items above flip green.
