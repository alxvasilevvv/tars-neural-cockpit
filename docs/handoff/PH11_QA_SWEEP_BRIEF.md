# Phase 11 — v10.0.0 GA dock-down: QA sweep + 72 h soak + tag protocol

**Authoring agent:** Cursor agent (Claude Opus 4.7), W310-l
**Authoring date:** 2026-05-18
**Implementer:** TBD (release session — could be operator-driven with this brief as the script)
**Target release:** `v10.0.0` GA (drop the `-rc.1` suffix)
**Depends on:** W310 wave fully landed (PRs #187-#196 merged), and at least one of the v10 GA `[ ]` checklist items resolved (the Apple .p12 unblock is the only true GA blocker on the Claude/Cursor lane)
**Phase ID in master plan:** `ph11-qa-sweep` (companion: `ph11-brother-handoff`, separate brief)

---

## 1. Why this brief exists

`v10.0.0-rc.1` was cut at W264 (2026-05-15). The repo already ships
everything needed to **execute** a GA tag — `scripts/FINAL-QA-GATE.command`
(8 gates), `scripts/SMOKE-TEST.command` (60+ routes), `scripts/RELEASE-v10.0.command`
(one-shot tag/push/build), `docs/V10_GA_CHECKLIST.md` (30-item go/no-go),
`docs/LAUNCH_PLAYBOOK_v10_GA.md` (T-7 → T+30 sequencing).

**What's missing:** a **forward-looking dock-down brief** that:

1. **Reconciles the v10 GA checklist state after the W310 wave** — which `[ ]` items the W310 PRs unblock, which still need operator action.
2. **Specifies the 72 h soak test methodology** — what runs, what we measure, pass/fail thresholds, escalation criteria. The master plan's `ph11-qa-sweep` literally says "Full QA sweep + soak 72h + tag v10.0.0"; there is no existing doc for the 72 h soak.
3. **Defines the tag-cutting protocol** — sequence of operations from "all 30/30 green" to "GA tag pushed + release notes finalised + announce post drafted" with rollback gates at each step.

This is the methodology brief, not the runbook. The runbook is the
union of the existing `scripts/RELEASE-v10.0.command` + `docs/LAUNCH_PLAYBOOK_v10_GA.md`.
This brief fills the gap **between** them — the dock-down phase that
happens *after* code freeze but *before* tag cut.

---

## 2. Goals / non-goals

### Goals

| ID | Goal | Acceptance |
| -- | ---- | ---------- |
| G1 | Single document operator can hand to a fresh session that says "run this sequence; tag v10.0.0 at the end" | Brief reads top-to-bottom; no required side-reading except the existing scripts it invokes |
| G2 | 72 h soak protocol with explicit pass/fail thresholds | Soak section is self-contained: what runs, what we capture, what counts as a hard fail vs. soft signal |
| G3 | Reconcile current v10 GA checklist against post-W310 reality | Each `[ ]` item in `V10_GA_CHECKLIST.md` annotated with: status after W310, blocker (if any), expected resolution path |
| G4 | Tag-cutting protocol with rollback gates | Operator can stop at any step and revert without leaving the repo in a half-tagged state |
| G5 | Zero net-new code or scripts | All sequencing uses scripts that already exist on `main` |

### Non-goals

- **Brother handoff document.** That's `ph11-brother-handoff` — separate brief.
- **Apple / Windows signing setup.** That's `ph4-apple-sign` / `ph4-windows-sign` — separate briefs. This doc treats them as inputs.
- **Post-GA monitoring playbook.** Already covered by `docs/DISASTER_RECOVERY.md` and `docs/LAUNCH_PLAYBOOK_v10_GA.md §3`. No duplication.
- **Marketing copy.** This is engineering dock-down. Marketing lives in `docs/LAUNCH_PLAYBOOK_v10_GA.md §1`.
- **v10.1 planning.** That's `docs/PRODUCT_MASTER_PLAN.md §4` — orthogonal.

---

## 3. State reconciliation — V10_GA_CHECKLIST after W310

`docs/V10_GA_CHECKLIST.md` has 30 items across 7 categories (A-G).
Status after the W310 wave + planning surface PRs #192-#196:

### Category A — Brother (`api.meeet.world`) — external lane

All 5 items (A1-A5) **untouched by W310**. These are brother-side
endpoints (billing usage event, balance, top-up, reconciliation,
auth). Status: still `[ ]`. Blocker: brother coord — needs the
brother session to confirm endpoints are live. **`ph11-brother-handoff`
brief (separate) will surface the per-endpoint coordination delta.**

### Category B — Apple Developer + macOS distribution

All 5 items (B1-B5) **untouched by W310**. These need real `.p12`
credentials uploaded as CI secrets. Status: still `[ ]`. Blocker:
operator — the .p12 cert acquisition + upload to GitHub Actions
secrets. **`ph4-apple-sign` brief (separate, future autonomous
candidate) will document the unblock sequence.**

### Category C — VS Code marketplace (`tars-tab` — W254)

4 items (C1-C4). **Untouched by W310.** Blocker: operator — `vsce`
publisher account setup. Not a hard GA gate; the master plan lists
this as a v10.0.x patch slot if it slips.

### Category D — On-prem deployment kit (W263)

5 items (D1-D5). **Untouched by W310.** All `[ ]`. Blocker: customer-side
acceptance (D3, D4 specifically need a real on-prem customer).
**Not a hard GA gate** per `docs/PRODUCT_MASTER_PLAN.md §2.1` — on-prem
slips to v10.0.x without blocking the GA tag.

### Category E — Perf + QA gates (Claude lane — done locally)

All 5 items (E1-E5) **were `[x]` at rc.1 cut** (W266-W267). **W310
does not invalidate them.** Status: still `[x]`. **Re-verification
needed as part of the 72 h soak** (§4) — that's normal, since `main`
will have absorbed the 10 W310 PRs by the time soak starts.

### Category F — Compliance + receipts

All 4 items (F1-F4) **were `[x]` at rc.1 cut**. Untouched. Status: `[x]`.

### Category G — Marketing + launch comms

G1 was `[x]` at rc.1. Status: `[x]` for rc.1; **needs version rename
from `v10.0-rc1` → `v10.0` as part of tag cut** (handled by
`scripts/RELEASE-v10.0.command` automatically).

### Reconciled summary

| Category | Items | `[x]` | `[ ]` | Hard GA blocker? |
| -------- | ----: | ----: | ----: | ---------------- |
| A. Brother | 5 | 0 | 5 | **YES** — A1, A2, A5 only |
| B. Apple signing | 5 | 0 | 5 | **YES** — B1-B5 all hard blockers (no signed binary = no GA) |
| C. VS Code | 4 | 0 | 4 | NO (slips to v10.0.x) |
| D. On-prem | 5 | 0 | 5 | NO (slips to v10.0.x) |
| E. Perf + QA | 5 | 5 | 0 | (re-verify in soak) |
| F. Compliance | 4 | 4 | 0 | n/a |
| G. Marketing | 1 | 1 | 0 | n/a (auto-renamed by release script) |
| **Total** | **29** | **10** | **19** | **8 hard blockers** |

**(N.B.** `V10_GA_CHECKLIST.md` shows 30 items in its TOC but only 29
under the section headings. Cross-check during the soak preflight in §4.1 — likely
a doc-only typo.)

So the **true v10 GA gating set** post-W310 is **8 items** (A1, A2, A5 + B1-B5). Everything else is `[x]` already done or `[ ]` deferred to v10.0.x patches.

---

## 4. 72 h soak protocol

**When to start:** After 8 hard blockers (§3) resolve AND all W310 PRs
merge to `main`. The soak runs against `main` at HEAD, not against a
release candidate branch.

**Where to run:** Operator's primary dev workstation (the same host
where `FINAL-QA-GATE.command` is canonical). Optional secondary:
a clean Linux VM (Ubuntu 22.04) to catch cross-platform regressions
that don't surface on macOS.

### 4.1 — Preflight (T-0 to T+0 h)

1. **Confirm clean state:**
   ```bash
   git switch main
   git pull --ff-only
   git status   # must be clean
   ```
2. **Re-run E-category gates** (they were `[x]` at rc.1; need re-verification post-W310):
   ```bash
   bash scripts/FINAL-QA-GATE.command
   ```
   All 8 gates must be green. If any red → stop soak, fix, restart preflight.
3. **Cross-check `V10_GA_CHECKLIST.md` item count** (TOC says 30, section count is 29 — confirm intent).
4. **Snapshot baseline:**
   ```bash
   bash scripts/SMOKE-TEST.command > .soak/baseline-smoke.txt
   bash scripts/RUN-PERF-SUITE.command > .soak/baseline-perf.txt
   pytest --collect-only -q > .soak/baseline-test-count.txt
   ```
   Capture into a fresh `.soak/` directory (gitignored). These are
   the baselines every soak hour-mark compares against.

### 4.2 — Backend soak (T+0 to T+72 h)

Run the backend on `:8765` continuously:

```bash
nohup make backend > .soak/backend.log 2>&1 &
echo $! > .soak/backend.pid
```

Hourly cron (operator's `crontab -e` or `launchd plist`):

```cron
0 * * * *   bash scripts/SOAK-HOURLY.command >> .soak/hourly.log 2>&1
```

`scripts/SOAK-HOURLY.command` does NOT exist yet — **this brief asks
the implementer to create it** as one of the prep steps (§5.A below).
Spec for that script:

- Hits `/api/health`, `/api/pairing/identity`, `/api/voice/health`, `/api/vault/status`
- Hits the QA-Agent route surface (`make qa-agent`-style probes)
- Tail-checks `backend.log` for new ERROR lines since last hour-mark
- Records p50/p95 latency, RSS, fd count, sqlite WAL size
- Appends a one-line JSON record to `.soak/hourly.log`
- Fails if any probe non-2xx for 3 consecutive hours

### 4.3 — Cockpit + desktop soak (continuous)

In parallel with backend:

- Tauri shell open on the operator's primary monitor (`make desktop-dev`)
- Cockpit panel visible (no auto-refresh — natural mouse/keyboard idle behaviour)
- One real-ish conversation per ~8 h (talk to the model, run a chat thread, send a couple of voice utterances if W309 step 2 is merged)

**Why:** Catches memory leaks in the desktop shell, WS reconnect
bugs after sleep/wake, vault re-load after Keychain prompt. These
**don't surface in headless tests.**

### 4.4 — meeet bridge soak (continuous)

`backend/core/meeet/` emits events on every action. During soak:

- `MEEET_LOCAL_LOG=1` so events also land in `meeet_events.jsonl`
- Hourly check: `wc -l` on the local log + `gh api repos/...` to compare against the meeet.world ingest count (drift < 0.5 % per the existing reconciliation script)

### 4.5 — Pass / fail criteria

**Hard fails (abort soak, fix, restart):**

- Any `FINAL-QA-GATE.command` gate goes red during the soak window
- Backend process dies (PID gone from `.soak/backend.pid`)
- ERROR log grows by > 100 lines/hour on average
- p95 latency on `/api/chat/turn` regresses > 20 % from baseline
- RSS grows > 2 GB or fd count > 1024 (indicates leak)
- meeet bridge drift > 0.5 % at any hour-mark (reconciliation script's existing threshold)

**Soft signals (note, don't abort):**

- p50 latency drift < 10 %
- Single-hour ERROR spike that recovers
- Desktop shell sleep/wake reconnect taking > 5 s but eventually succeeding

**Pass:** 72 consecutive hour-marks recorded, all hard-fail conditions
unmet, all 30 (29) GA checklist items green.

### 4.6 — Soak postmortem (T+72 h)

1. `bash scripts/SOAK-REPORT.command > docs/qa/SOAK_v10.0.0.md` (also new — see §5.A).
2. Soak report includes:
   - Hour-by-hour latency + RSS + fd + ERROR-count chart (ASCII or markdown table)
   - Top 5 ERROR signatures (grep + count)
   - meeet bridge drift histogram
   - Final go/no-go: "GA tag authorised" or "GA tag blocked — see fix list"
3. **If GA authorised:** proceed to §5 (tag cut).
4. **If GA blocked:** fix list becomes a `cursor/soak-v10-fix-NN` PR set, then **restart soak from T-0** (don't bandage; soak is binary).

---

## 5. Tag-cutting protocol

Assumes §3 reconciliation + §4 soak both passed.

### 5.A — Preparation PR (one PR, before tag)

Add the two missing helper scripts:

- `scripts/SOAK-HOURLY.command` (spec in §4.2)
- `scripts/SOAK-REPORT.command` (spec in §4.6)

Both are pure helpers — no behaviour change to the existing release
pipeline. Land via a normal PR (not via `RELEASE-v10.0.command`).

### 5.B — Cut the tag (T-0 launch day)

Per `docs/LAUNCH_PLAYBOOK_v10_GA.md §2` step-by-step. Concrete sequence:

1. **Last sanity check:**
   ```bash
   bash scripts/FINAL-QA-GATE.command   # all 8 green
   bash scripts/SMOKE-TEST.command      # all 60+ routes 2xx
   ```
2. **Dry-run the release script:**
   ```bash
   RELEASE_v10_DRY_RUN=1 bash scripts/RELEASE-v10.0.command
   ```
   Verifies version bumps + gates without tagging.
3. **Real cut:**
   ```bash
   bash scripts/RELEASE-v10.0.command
   ```
   Script does: drop `-rc.1` suffix in all 10 version files → `FINAL-QA-GATE` re-run → `git tag v10.0.0` → `git push origin main v10.0.0` → trigger `release-tagged.yml` workflow → attach signed `.dmg` once Apple notary returns → optionally `vsce publish` for the VS Code extension.
4. **Post-tag verification:**
   - GitHub release page shows `v10.0.0` with attached `.dmg`
   - `https://tars.meeet.world/updater/latest.json` returns the new version
   - `https://github.com/alxvasilevvv/tars-neural-cockpit/releases/tag/v10.0.0` 200s

### 5.C — Rollback gates

Each step in §5.B has an explicit rollback:

| Step | If it fails | Rollback |
| ---- | ----------- | -------- |
| 5.B.1 | Any gate red | Don't proceed. Fix, restart from §5.B.1. No state changed. |
| 5.B.2 | Dry-run errors | Read `LAUNCH_PLAYBOOK_v10_GA.md §1` — usually a version-string drift. Fix, restart. No state changed. |
| 5.B.3 | Tag push fails | `git tag -d v10.0.0`; investigate; restart. Local repo only — no remote state. |
| 5.B.3 | CI `release-tagged.yml` fails | `gh release delete v10.0.0`; `git push --delete origin v10.0.0`; fix CI; restart. Remote state cleared. |
| 5.B.4 | Updater JSON missing | Manually re-trigger the relevant workflow (`gh workflow run release-tagged.yml -f tag=v10.0.0`). |

**Once 5.B.4 is fully green, GA is committed.** No public rollback path
beyond a `v10.0.1` patch tag.

### 5.D — Announce sequence (T+0 to T+2 h)

Per `LAUNCH_PLAYBOOK_v10_GA.md §2.5` — out of this brief's scope.
This brief ends at "GA tag live; updater JSON live; .dmg attached".

---

## 6. Acceptance criteria for Phase 11 QA sweep done

- [ ] §3 reconciliation reviewed by operator; per-blocker action assigned
- [ ] 8 hard-blocker GA checklist items closed (A1, A2, A5, B1-B5)
- [ ] `scripts/SOAK-HOURLY.command` + `scripts/SOAK-REPORT.command` shipped (§5.A PR)
- [ ] 72 h soak completed without hitting any hard-fail criterion (§4.5)
- [ ] Soak report saved to `docs/qa/SOAK_v10.0.0.md`
- [ ] `bash scripts/RELEASE-v10.0.command` ran end-to-end and exited 0
- [ ] `v10.0.0` tag visible on https://github.com/alxvasilevvv/tars-neural-cockpit/releases
- [ ] Signed `.dmg` attached to the release
- [ ] `https://tars.meeet.world/updater/latest.json` reports `v10.0.0`

---

## 7. Test plan summary

| Layer | New tests | Modified tests | Coverage |
| ----- | --------- | -------------- | -------- |
| Scripts (SOAK-HOURLY) | `tests/test_soak_hourly.py` (4 cases) | none | probes succeed / fail / log append shape / 3-consecutive-fail abort |
| Scripts (SOAK-REPORT) | `tests/test_soak_report.py` (3 cases) | none | empty soak / one-hour soak / multi-hour soak with one error spike |
| Regression | none | none | existing FINAL-QA-GATE / SMOKE-TEST / pytest suites all unchanged |

**Total: 7 new tests, 0 modified.**

Soak itself is not "tested" — it's the test. The 72 h window with
hard pass/fail criteria IS the gate.

---

## 8. Rollback strategy (for this brief's own deliverable)

| Step | Rollback |
| ---- | -------- |
| §5.A scripts PR | Revert PR. Soak can still run by stitching shell loops, just less ergonomic. |
| Soak in progress | Kill background backend, `rm -rf .soak/`. No persistent state. |
| Tag cut (§5.B) | See §5.C per-step rollback table. |

This brief itself is documentation — no rollback needed for the brief.

---

## 9. Open questions for operator

| # | Question | Default if silent |
| - | -------- | ----------------- |
| Q1 | Run the soak on macOS only, or also on Ubuntu 22.04 VM in parallel? | macOS only for v10.0.0 GA; Linux soak deferred to v10.0.1 (no Linux customer yet per `docs/V10_GA_CHECKLIST.md §D`) |
| Q2 | Should hourly soak probes hit `/api/chat/turn` (real LLM call, cost ~$0.10/h) or only the static health endpoints? | Static health only; one real chat per 8 h is enough to catch end-to-end regressions without burning $7 over 72 h |
| Q3 | If brother (A1, A2, A5) doesn't land in time for GA window, fork the tag with `billing_stub_mode=true`? | No — defer GA by 1 week. Real billing is the whole point of v10. Better to slip than ship a stub. |
| Q4 | If on-prem (D1-D5) doesn't land, document slip publicly or quietly defer? | Quietly defer to v10.0.x in `RELEASE_NOTES_v10.0.md §Known limitations`. Marketing copy still focuses on consumer + SaaS surfaces. |
| Q5 | Soak window calendar slot — weekday or weekend? | Weekend (Fri evening → Mon morning). Lower model usage, fewer cockpit interruptions, easier to spot weekday-only regressions. |

---

## 10. Estimated effort

- §5.A scripts PR (SOAK-HOURLY + SOAK-REPORT): ~4 h, 1 PR, low risk
- Soak execution: 72 h wall-clock, ~2 h operator attention (preflight + hourly spot-checks + postmortem)
- Reconciliation §3 review + operator action on blockers: ~2 h operator time
- Tag cut (§5.B): ~30 min if all gates green

**Total: ~6-8 h active operator/agent time + 72 h passive soak wall-clock.**

This is the smallest brief in the W310 series because most of the
work is in the existing scripts; this doc is mostly the **methodology**
+ **reconciliation** + **pass/fail thresholds** that the existing
scripts don't encode.

---

## 11. Pointers / references

- Existing GA scripts: `scripts/FINAL-QA-GATE.command`, `scripts/SMOKE-TEST.command`, `scripts/RUN-PERF-SUITE.command`, `scripts/RELEASE-v10.0.command`
- Existing GA docs: `docs/V10_GA_CHECKLIST.md`, `docs/LAUNCH_PLAYBOOK_v10_GA.md`, `docs/RELEASE_RUNBOOK_2026-05-01.md`, `docs/QA_AGENT_RUNBOOK.md`
- W310 master plan slot: `docs/PRODUCT_MASTER_PLAN.md` → Phase 11 → `ph11-qa-sweep`
- Companion brief (separate): `ph11-brother-handoff` — TBD, next autonomous candidate
- Wave summary: `docs/W310_WAVE_SUMMARY.md` (will be extended)
- Existing release notes (for tag-rename pattern): `docs/RELEASE_NOTES_v10.0-rc1.md`
- Disaster recovery (post-GA monitoring, out of scope here): `docs/DISASTER_RECOVERY.md`

---

**End of brief.**
