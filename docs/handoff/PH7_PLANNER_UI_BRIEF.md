# PH7 — Phase 7 / L6 cockpit planner UI (`<PlanTimeline />` + `<PlanInbox />`) implementer brief

**Owner:** next L6-lane implementer
**Release target:** v11 (post-Phase-5 trio)
**Scope window:** ~1 week / ~5 PRs
**Estimated LoC:** ~2.1k (incl ~600 LoC tests)
**Status entering brief:** **backend FULLY shipped (~5.1k LoC + 14 test files); brief is PURE COCKPIT UI**

---

## 0. TL;DR for the implementer

This brief is **L6 cockpit-side completion only**. The planner is the
spiritual sibling of the Phase 5 policy UI brief (#203): the whole
backend stack — synthesizer, SQLite store, runner with cooperative
abort, full HTTP surface, SSE event stream, run history reconstructor,
clone/rerun, meeet event emission — is **already on `main`**. The
shipped code is roughly:

| Module | Path | LoC |
| ------ | ---- | --- |
| Plan/PlanStep/PlanStatus types | `backend/core/planner/types.py` | 186 |
| Plan SQLite store | `backend/core/planner/store.py` | 384 |
| Heuristic plan synthesizer | `backend/core/planner/synthesizer.py` | 321 |
| `PlanRunner` + abort registry | `backend/core/planner/runner.py` | 649 |
| Run-history reconstructor | `backend/core/planner/history.py` | 607 |
| `planner` CLI surface | `backend/core/planner/cli.py` | 600 |
| Plan HTTP + SSE router | `web_extras/routers/planner.py` | 904 |
| `PlaybookRunner` (plan executor) | `backend/core/playbooks/runner.py` | 487 |
| Playbook validator | `backend/core/playbooks/validator.py` | 544 |
| Backend tests | `tests/test_planner_*.py` (14 files) | — |

The cockpit currently has **zero** planner UI scaffolding. What the
brief delivers:

1. `/plans` page rendering the plan inbox (proposed/approved/running/
   completed/aborted/rejected filter chips, sortable table, status
   pill, per-row destructive-step icon).
2. `<PlanTimeline />` drawer that opens on row click and renders the
   per-step list with **live progress** via the
   `/api/planner/events` SSE stream.
3. Approve / reject / abort buttons wired to the existing HTTP
   endpoints, with policy mode picker (`autopilot` / `confirm` /
   `dry_run`) matching the runner's resolution surface.
4. "Create plan" affordance in the chat composer that posts a goal to
   `POST /api/planner/plan` and pivots to the drawer.
5. Header pill `[plans: N ▾]` showing the count of `proposed` +
   `running` plans, identical visual treatment to the policy
   confirmations pill from #203.

The brief is **5 mechanical UI steps** with no new backend endpoints
and no new tests outside cockpit-side. It assumes #189 (Playwright
scaffold) and #196 (pairing UX) have landed first so the existing
e2e harness and aside-panel pattern are available, but it can also
land independently — the harness is a soft dep.

---

## 1. Why this brief exists (forensic note)

The L6 contract from `docs/PHASE_L_ROADMAP.md §L6` reads:

```
plan.proposed           {plan_id, steps, est_cost_usd}
plan.step.requested     {plan_id, step_id, dest, args}
plan.step.allowed       {plan_id, step_id, mode}
plan.step.completed     {plan_id, step_id, result_summary, cost_usd}
plan.completed          {plan_id, status, total_cost_usd}
plan.aborted            {plan_id, reason}
```

Every one of these event kinds is **already emitted** by the
`PlanRunner` and persisted to the meeet store (verifiable: `rg
'plan\.(proposed|step|completed|aborted)' web_extras/ backend/core/`).
The runner also already handles cooperative abort via
`PlanRunRegistry` and exposes it through `POST /api/planner/{id}/abort`.
The HTTP router exposes a full SSE stream that fans these events out
to subscribers with `after_id` cursor + `Last-Event-ID` resume.

What's not shipped is **the UI that makes any of this visible to the
operator**. Today a plan can be synthesized via `POST /api/planner/plan`,
approved via `POST /api/planner/{id}/status`, and run via `POST
/api/planner/{id}/run`, but only an operator who curls the API can see
it happen. The cockpit needs to surface this lifecycle in a way that
mirrors the policy inbox (#203) — same visual grammar so an operator
who knows one knows both.

This brief is the cockpit closure.

---

## 2. Target UX

```
┌─────────────────────────────────────────────────────────────────────┐
│ TARS cockpit  …  [vault: 🔒 28:14]  [pending: 7 ⚡]  [plans: 3 ▾]  │ ← header
├──────────────────┬──────────────────────────────────────────────────┤
│ ☐ Inbox  📥      │ 3 plans                            [⊕ New plan]  │
│ ☐ Plans  🧭      │ status: [all▾] [proposed▾]                       │
│ ☐ Threads        │  ┌──────────────────────────────────────────┐    │
│ ──────────────── │  │ ⌖ when    goal                  status   │    │
│ status: running  │  │ 14:23   crm digest weekly       proposed│    │
│ ☐ recent         │  │ 14:21   build → deploy staging  running │    │
│ ☐ all            │  │ 14:18   send Q3 outreach (12)   prop⚠   │ ← red bg if any destructive
│                  │  │ …                                        │    │
│ since: [7d  ▾]   │  └──────────────────────────────────────────┘    │
│                  │                                                   │
│ [ + autopilot    │  ┌─ drawer (opens on row click) ──────────┐     │
│   threshold:     │  │ Plan pln_abc1234                         │    │
│   $20 ✎ ]        │  │ Goal: "build then deploy to staging"     │    │
│                  │  │ Model: heuristic-v1   Trace: tr_xyz      │    │
│                  │  │ ───────────────────────────────────────  │    │
│                  │  │ ✓ step_01  github.repo.snapshot          │    │
│                  │  │ ✓ step_02  github.pr.list                │    │
│                  │  │ ◑ step_03  ci.build.run    (running…)    │    │
│                  │  │ ○ step_04  deploy.staging.push  ⚠ destruct│    │
│                  │  │ ○ step_05  meeet.notify.send             │    │
│                  │  │ ───────────────────────────────────────  │    │
│                  │  │ Cost so far: $0.08   est total: $0.21    │    │
│                  │  │ Policy: [autopilot ▾ ]                   │    │
│                  │  │ [ ✓ Approve ] [ ✗ Reject ] [ ⏸ Abort ]   │    │
│                  │  └─────────────────────────────────────────┘     │
└──────────────────┴──────────────────────────────────────────────────┘
```

UX gestures (all keyboard-first):

| Key | Action |
| --- | ------ |
| `j` / `k` | move row selection up/down |
| `Enter` | open drawer on selected row |
| `a` | approve selected plan |
| `r` | reject selected plan |
| `p` | toggle "running" filter (quick-view in-flight) |
| `n` | open "new plan" composer (focus textarea) |
| `Esc` | close drawer |

Color discipline (reuses cockpit token system — no new colors):

| Status | Pill bg | Text |
| ------ | ------- | ---- |
| `proposed` | `--tars-accent-amber-100` | `--tars-accent-amber-900` |
| `approved` | `--tars-accent-blue-100`  | `--tars-accent-blue-900`  |
| `running`  | `--tars-accent-violet-100`| `--tars-accent-violet-900`|
| `completed`| `--tars-accent-green-100` | `--tars-accent-green-900` |
| `aborted`  | `--tars-accent-orange-100`| `--tars-accent-orange-900`|
| `rejected` | `--tars-fg-tertiary`      | `--tars-bg-canvas`        |

Destructive-step warning uses the same `border-l-2 border-red-500`
treatment as the policy inbox over-threshold tint.

---

## 3. Wire contract (read-only — these are the shipped endpoints)

Every endpoint already exists in `web_extras/routers/planner.py`.
The brief does NOT add or modify any backend route. List included
here so the implementer doesn't have to re-derive from the source.

### 3.1 REST

| Method | Path | Purpose | UI use |
| ------ | ---- | ------- | ------ |
| `POST` | `/api/planner/plan` | synthesize new plan from goal | New-plan composer |
| `GET`  | `/api/planner` | list plans (filters: status, thread_id) | Inbox table |
| `GET`  | `/api/planner/{id}` | one plan envelope | Drawer header |
| `GET`  | `/api/planner/{id}/full` | plan + runs + lifetime usage | Drawer body |
| `GET`  | `/api/planner/{id}/runs` | reconstructed run history | Drawer history tab |
| `GET`  | `/api/planner/_stats` | totals + by_status counts | Header pill |
| `POST` | `/api/planner/{id}/status` | approve / reject | Approve/Reject buttons |
| `POST` | `/api/planner/{id}/run` | execute approved plan | (auto-runs after approve when toggle on) |
| `POST` | `/api/planner/{id}/abort` | cooperative abort | Abort button |
| `POST` | `/api/planner/{id}/clone` | clone as new proposed | "Rerun" menu |
| `POST` | `/api/planner/{id}/rerun` | clone → approve → run in one round-trip | "Rerun" menu |
| `DELETE` | `/api/planner/{id}` | prune | Row menu |

### 3.2 SSE — `GET /api/planner/events`

```
event: plan.proposed
data: {"id": 4711, "ts": 17474..., "kind": "plan.proposed", "plan_id": "pln_abc", "steps": [...], "est_cost_usd": 0.21}

event: planner.synthesis.completed
data: {...}

event: plan.run.started
data: {"id": 4712, "plan_id": "pln_abc", "mode": "autopilot", ...}

event: plan.step.requested
data: {"id": 4713, "plan_id": "pln_abc", "step_id": "step_03", "dest": "ci.build.run", "args": {...}}

event: plan.step.allowed
data: {"id": 4714, ...}

event: plan.step.completed
data: {"id": 4715, "plan_id": "pln_abc", "step_id": "step_03", "result_summary": "...", "cost_usd": 0.03, "took_ms": 1240}

event: plan.completed
data: {"id": 4716, "status": "completed", "total_cost_usd": 0.21}

event: plan.aborted
data: {"id": 4717, "reason": "operator_request"}
```

Cockpit subscribes with `EventSource('/api/planner/events?plan_id=' + id)`
(scoped) on the drawer, and `EventSource('/api/planner/events')`
(global) on the inbox page for the pending-count pill.

Resume on reconnect: pass last-seen `id` via the SSE `Last-Event-ID`
header (auto-handled by `EventSource`) or `?after_id=...` query
parameter; router accepts both with header winning.

---

## 4. Mechanical steps

### Step 1 — `/plans` page entry + hash route (~110 LoC)

**Files (new):**

- `apps/cockpit/src/pages/plans-entry.ts` (40 LoC) — bootstraps the
  `<PlanInbox />` mount and SSE pill connection.
- `apps/cockpit/src/pages/plans-entry.html` (entry template, 30 LoC).

**Files (modified):**

- `apps/cockpit/src/pages/cockpit-entry.ts` — add `/plans` hash route
  + `[plans: N ▾]` header pill mount point + `<PlanInbox />` import
  on demand (~40 LoC delta).

Hash route: `#/plans?status=proposed&since=7d`. Both query params are
optional. Mirrors the existing `#/inbox` route shape from #203.

The header pill mounts unconditionally (every cockpit page sees it);
the inbox component only mounts when the hash matches.

### Step 2 — `planner-client.ts` HTTP + SSE wrapper (~380 LoC)

**Files (new):**

- `apps/cockpit/src/lib/planner-client.ts` (~280 LoC):
  - `PlannerClient` class with one method per REST endpoint listed
    in §3.1.
  - `subscribeEvents({plan_id?, after_id?}, onEvent)` returns an
    `EventSource` wrapper with auto-reconnect (exponential
    backoff capped at 30 s) and `Last-Event-ID` resume.
  - Returns typed `Plan`, `PlanStep`, `PlanRun`, `PlanFull` objects
    matching `backend/core/planner/types.py` shape (manually
    transcribed; the TypeScript types live in the client).
- `apps/cockpit/src/lib/planner-client.spec.ts` (~100 LoC) — Vitest
  unit tests with `msw` stubs.

The client is intentionally framework-free (no React, no Vue —
matches existing cockpit vanilla-TS pattern from #203).

### Step 3 — `<PlanInbox />` + `<PlanDrawer />` components + CSS (~870 LoC)

**Files (new):**

- `apps/cockpit/src/components/plan-inbox.ts` (~310 LoC) — sortable
  table, filter chip bar, keyboard nav (`j/k/Enter/a/r/p/n`),
  "+ New plan" composer modal trigger, status/destructive coloring,
  bulk-approve safety prompt (modeled on #203's
  `confirmBulkOver1k()`).
- `apps/cockpit/src/components/plan-drawer.ts` (~370 LoC) —
  per-step timeline with live SSE-driven progress, cost rollup,
  policy mode picker, approve/reject/abort buttons, "Rerun" menu
  (Clone, Rerun, Reset to proposed).
- `apps/cockpit/src/components/plan-step-row.ts` (~80 LoC) —
  single-row presenter with status icon (`○` pending, `◑` running,
  `✓` completed, `✗` failed, `⏸` aborted), action name, args
  pretty-print, optional `rationale` collapsible.
- `apps/cockpit/src/components/plan-new-modal.ts` (~110 LoC) —
  textarea + "thread context" pre-fill + "synthesize"
  button → posts to `/api/planner/plan` and pivots to drawer.
- `apps/cockpit/src/styles/plans.css` (~200 LoC) — color tokens
  (reuses tokens from `tokens-preview.ts`), drawer slide-in,
  row hover/selected/destructive variants.

No new npm deps. Same icon set as existing cockpit (`feather-icons`
via inline SVG; already loaded).

Performance: a busy inbox of 200 plans must render in <120 ms initial
paint and stream new SSE events without retriggering full re-render
(use `requestAnimationFrame` batching and per-row `data-plan-id`
diffing — same pattern as the policy inbox).

### Step 4 — Header pill `[plans: N ▾]` (~70 LoC)

**Files (new):**

- `apps/cockpit/src/components/plans-pill.ts` (~70 LoC) —
  reads `GET /api/planner/_stats` on mount + every 30 s, plus
  subscribes to global `/api/planner/events` to bump immediately
  on `plan.proposed` / `plan.completed` / `plan.aborted`.
  Click expands a 5-item popover ("Recent: ...") and "View all →
  #/plans" link.

Visual treatment matches `[pending: N ⚡]` from #203 exactly so the
two pills live side-by-side without color clashes.

### Step 5 — Chat-composer "Create plan" affordance + chat→plan link (~250 LoC)

**Files (modified):**

- `apps/cockpit/src/components/chat-pane.ts` — add a "wand"
  icon button next to the send button; on click pre-fills the
  new-plan modal with the **selected text** of the most recent
  assistant message (or the operator's last message if no
  selection). Adds a small "🧭 plan pln_abc" inline badge to
  any chat message whose `thread_id` matched a synthesized plan
  (reads `/api/planner?thread_id=<id>` lazily on chat hydration).
- `apps/cockpit/src/styles/chat.css` — wand button + plan badge.

**Files (new):**

- `apps/cockpit/src/lib/plans-thread-link.ts` (~80 LoC) — caches
  plan→thread mappings client-side to avoid N+1 requests; uses
  `swr`-like stale-while-revalidate semantics on a 60 s TTL.

This affordance is the "make planner discoverable" touch — without
it, operators won't know the planner exists. It's optional UX polish
in the sense that a/b removal still ships a working inbox, but
expected to be in the v11 release notes.

### Step 6 — Playwright e2e + visual regression + a11y (~410 LoC tests)

**Files (new):**

- `tests/e2e/plans/plans-inbox.spec.ts` (~120 LoC):
  - inbox renders fixtures via msw
  - keyboard nav (`j/k/Enter`) selects rows
  - approve/reject buttons post to correct endpoints
  - "+ New plan" → synthesize → drawer opens with new plan
- `tests/e2e/plans/plan-drawer.spec.ts` (~140 LoC):
  - SSE events stream into the drawer (mock with `EventSourcePolyfill`)
  - step status icon transitions on `plan.step.completed`
  - abort button posts to `/abort` and disables further actions
- `tests/e2e/plans/plans-pill.spec.ts` (~70 LoC) — pill count
  updates on `plan.proposed` event.
- `tests/e2e/plans/plans-a11y.spec.ts` (~80 LoC) — Axe scan on
  inbox + drawer (zero violations gate).

Visual regression: PR pipeline snapshots `/plans` at three states
(empty / 7 plans / 1 running with timeline) at viewports 1280×800,
1440×900, 1920×1080. Tolerance 0.1% pixel diff.

A11y: zero Axe violations gate (matches #203 policy).

---

## 5. Test plan summary

| Test type | Files | Count | Pass gate |
| --------- | ----- | ----- | --------- |
| Cockpit unit | `planner-client.spec.ts` | 18 | 18/18 green |
| Playwright e2e | `tests/e2e/plans/*.spec.ts` | 4 files × ~6-10 scenarios = ~32 | 32/32 green |
| Visual regression | snapshots | 9 | 0% drift |
| Axe a11y | inbox + drawer | 2 | 0 violations |
| Backend regression | existing 14 planner test files | unchanged | 14/14 green |

**Smoke test:** operator opens `/plans` with 3 fixture plans, hits
`j` until "build → deploy staging" is selected, hits Enter, sees the
drawer open, hits `a` to approve, observes the timeline step-by-step
progression (each step icon transitions `○ → ◑ → ✓`), watches cost
counter increment, then closes the drawer. Total time from page open
to drawer-closed should be <8 s on a Mac M-series.

---

## 6. Coupling notes

| Other brief | Hard / Soft | Reason |
| ----------- | ----------- | ------ |
| **PH5 vault (#202)** | Soft | Plan persistence is in `planner.sqlite` (NOT `meeet.sqlite`); SQLCipher does not extend to it in v10.2. If v10.3 expands SQLCipher coverage, this brief will need to add an unlock-gate before mounting `<PlanInbox />`. Out of scope here. |
| **PH5 policy UI (#203)** | Hard (visual) | Header pill `[plans: N ▾]` shares header slot with `[pending: N ⚡]`; both pills must coexist without overflow. This brief reuses #203's pill component contract (`PillProps` + `usePillCount`). |
| **PH5 telemetry (#204)** | Soft | Telemetry bucket schema already includes `plan.*` family (verifiable in #204 §3.2); no extra wiring needed here. |
| **PH6 L3 sandbox (#205)** | Soft (forward) | Plans that include a `runtime.run_code` step will route through the sandbox; this brief's drawer auto-routes the per-step output preview through `<ArtifactPanel />` when the step's action is `runtime.run_code` (one-line conditional render). |
| **PH8 marketplace (#206)** | Soft (forward) | Pack-installed events should refresh the "available actions" hint in the new-plan composer; out of scope here (deferred to #206's brief). |
| **PH9 mobile (#207-209)** | None | Mobile companion is read-only on plans for v11; no brief overlap. |

---

## 7. Operator-side checklist (v11 GA)

Add to `docs/V11_GA_CHECKLIST.md` (file does not yet exist; will be
authored alongside the v11 release-engineering brief):

- [ ] **C1.** `/plans` page renders on every cockpit instance (run
      Playwright suite end-to-end).
- [ ] **C2.** Header pill survives 1 h soak with 10 plans/minute
      throughput (no leaked event listeners; observe heap stability).
- [ ] **C3.** Drawer SSE reconnect works after a 30 s network drop
      (simulate via Chrome DevTools "Offline" toggle).
- [ ] **C4.** Approve→run→abort round-trip persists per-step
      `plan.step.completed` events to the meeet store with the right
      thread_id.
- [ ] **C5.** Bulk-approve safety prompt blocks "approve all" when
      the selection includes any destructive step.

---

## 8. Open questions for operator (resolve before merge)

1. **Where does `/plans` live in the global nav?** Recommend
   left-sidebar third entry below "Inbox 📥" and "Threads", new
   "Plans 🧭". Operator to confirm icon + position.
2. **Auto-run after approve?** Recommend new operator setting
   `planner.auto_run_on_approve` default `false`; when `true`,
   `Approve` calls `/status` + `/run` in one click. Same shape as
   the policy inbox's `auto_approve_threshold` (#203).
3. **Plan cost display unit:** USD only or also tokens? Recommend
   USD primary, tokens as drawer tooltip on the cost number.
4. **Synthesizer surface:** v11 ships `heuristic-v1` only (already
   the default). Cloud-LLM voice (`anthropic-v1` / `openai-v1`)
   deferred to v11.1 — when added, the drawer needs a "model: ▾"
   pill in the header. Implementer should leave the slot in markup
   (just hide it for v11).
5. **Empty state:** Recommend illustration + "Synthesize your first
   plan" CTA → opens `<PlanNewModal />`. Design owner to confirm
   if illustration needs to be commissioned or generic vector icon
   from `feather-icons` is acceptable.
6. **Mobile cockpit (read-only):** out of scope for v11; brief
   only addresses desktop cockpit. Confirm OK.
7. **Plan inbox pagination:** for v11, recommend client-side
   filter on the most-recent 200 plans (matches policy inbox
   page-size). Server-side pagination → v11.1 if any user reports
   slowdown.

---

## 9. Effort estimate

| Step | LoC | Hours |
| ---- | --- | ----- |
| 1. Entry + hash route | 110 | 1.5 |
| 2. planner-client + spec | 380 | 5 |
| 3. Inbox + drawer + step row + new modal + CSS | 870 | 14 |
| 4. Header pill | 70 | 1.5 |
| 5. Chat-composer affordance | 250 | 4 |
| 6. Playwright + a11y + visual | 410 | 7 |
| **Total** | **2090** | **33 hrs (~1 week)** |

5 small PRs are recommended (one per step), each independently
mergeable on top of #205 (L3 sandbox brief, for the
ArtifactPanel-in-drawer conditional in step 3). The pill (step 4)
and chat-composer (step 5) can also land in either order and don't
block each other.

---

## 10. Out of scope (explicit non-goals)

- **Cloud-LLM planner synthesizer.** v11 ships `heuristic-v1` only.
  Cloud voices land in v11.1 — separate brief.
- **Plan editing (proposed → modified).** v11 is propose-or-reject
  only. To modify, operator clones and edits the clone — same
  pattern as the policy inbox's "deny + re-confirm". Edit-in-place
  UX is v11.1.
- **Plan templates / saved plans.** Out of scope; existing
  `backend/core/playbooks/` is the template surface. UI for saving
  a plan as a playbook is v11.1.
- **Multi-user plan ownership.** Single-operator semantics in v11;
  multi-user lands when v10's auth surface lands (no current ETA).
- **Server-side pagination.** v11 client-side filter on most-recent
  200 plans; revisit only if a user reports inbox slowness.

---

## 11. Glossary

| Term | Meaning |
| ---- | ------- |
| Plan | A `proposed`/`approved`/`running`/`completed`/`aborted`/`rejected` Plan object — see `backend/core/planner/types.py`. |
| Plan step | Individual unit of work; mirrors `PlaybookStep` 1:1 plus `rationale` and `destructive` flags. |
| Run | One execution attempt of an approved plan. Reconstructed from meeet events (no separate "runs" table). |
| Trace | `trace_id` carried from the plan-synthesis call through every step's policy gate and meeet emission. |
| PlannerSynthesisRequest | Input envelope to `synthesize_plan()` — `goal`, optional `pinned_pack`, optional `thread_id`. |
| Policy gate | The `PolicyMode` resolution at run time (`autopilot` / `confirm` / `dry_run`); destructive steps in `confirm` mode go to the policy inbox (#203). |

---

## 12. Acceptance criteria (merge gate)

- [ ] All 32 Playwright scenarios pass on macOS, Windows, Linux runners.
- [ ] All 18 cockpit unit tests pass.
- [ ] Visual regression snapshots: 0% drift on 9 captured states.
- [ ] Axe a11y scan: 0 violations on `/plans` and drawer.
- [ ] Existing 14 backend planner tests: unchanged & green.
- [ ] Manual smoke (§5) under 8 s.
- [ ] Header pill survives 1 h soak with 10 plans/minute throughput.
- [ ] Drawer SSE reconnects within 5 s after 30 s offline.
- [ ] No new npm deps added.
- [ ] No new backend endpoints added.
- [ ] No backend code modified outside `backend/core/planner/types.py`
      (additive only if needed for serialization deltas; ideally zero
      backend changes).

---

**End of brief.** Next planning briefs queued in the autonomous
orchestration window: PH8 (L7 marketplace), PH9 (L10 mobile companion
apps), PH10 (Claude design polish backlog).
