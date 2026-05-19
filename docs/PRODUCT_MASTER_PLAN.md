# PRODUCT_MASTER_PLAN — post-rc1 dock + post-v10 forward roadmap

> **Status:** living plan. Created **W310 (2026-05-18)**.
> **Scope:** synthesises the forward path from `v10.0.0-rc.1` (cut **W264**, 2026-05-15) through GA and into the Phase L closure waves that take us to `v10.1` / `v10.2` / `v11`.
> **Audience:** every agent (Cursor / Claude / Codex / Hermes / Kiro / OpenClaw / Slate), brother, operator.
> **Source-of-truth notes.** `CURRENT_STATUS.md` is the daily one-pager. `TARS_MASTER_DOC.md §1-5` is the North Star + shipped inventory. **This doc is forward-only** — it extends `TARS_MASTER_DOC.md §6` and supersedes piecemeal forward bullets scattered in `docs/AGENT_HANDOFF.md`. Phase L per-phase spec stays in `docs/PHASE_L_ROADMAP.md`.

---

## §1. Where we are (one paragraph)

`v10.0.0-rc.1` is cut and live across cockpit + desktop manifests (W264, 2026-05-15). From inside the repo, v10 GA is **DONE Claude-side** per `CURRENT_STATUS.md`. `v9.1.0` already shipped (W138-158, ~2 weeks ago) and its launch checklist (`docs/AGENT_HANDOFF.md` Wave 81 block) is now historical archive — superseded marker added in the same PR that introduces this doc. What separates us from `bash scripts/RELEASE-v10.0.command`: **5 operator-side external items**. What separates v10 GA from a feature-complete `v11`: Phase L closure (**L3** code execution, **L6** planner, **L7** marketplace, **L10** mobile), L4/L5 polish (STT relay, persistent keyring, pairing UX), Claude design polish backlog (13 items), encrypted vault.

---

## §2. v10 GA: the final push (1-4 weeks)

### 2.1 The 5 external items (operator-only)

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | rc1 soak on operator host (1 week daily smoke) | Operator | `bash scripts/SMOKE-TEST.command` daily; ⩾ 6/7 days green |
| 2 | Brother live on billing (A1-A5) | Brother | 4 endpoints + reconciliation; mock at `/api/_meeet_mock` until live |
| 3 | Apple Dev cert in CI (.p12 + secrets, B1-B5) | Operator | `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` |
| 4 | VS Code marketplace publish (`tars-tab`, C1-C4) | Operator | extension scaffold shipped W254 |
| 5 | First paying on-prem customer (D1-D5) | Operator + ops | kit shipped W263 |

Full breakdown: `docs/V10_GA_CHECKLIST.md`.

### 2.2 Internal docking before GA (this branch + follow-ups)

| Item | Owner | Status |
|---|---|---|
| Merge **PR #188** (this PR — master plan + closures) | Operator | ⬜ ready |
| Merge **PR #187** (W309 step 1) | Operator | ⬜ ready |
| W309 step 2: Playwright + STT + persona picker | Agent (after #187 merge) | brief at `docs/handoff/W309_STEP2_BRIEF.md` |
| HANDOFF L5 §6 line fix (mock→real crypto stale text) | This branch | ✅ in this PR |
| HANDOFF Wave 81 SUPERSEDED marker | This branch | ✅ in this PR |
| HANDOFF Wave 100 audit CORRECTION (`exec/*` not actually file-copied) | This branch | ✅ in this PR |
| Close **M-wave MCP stack** (6 PRs: #176, #177, #178, #179, #180, #184) | This branch + Cursor | ✅ all 6 closed; rewrite brief at `docs/handoff/MCP_REWRITE_BRIEF.md`; impl after #188 merge |
| Close **algotrade Wave-M / W2-W4 stack** (2 PRs: #170, #174) | This branch | ✅ both closed (stack bases #166-#169, #173 already closed); consolidated landing at §3.A |
| Voice persona fallback (#183, standalone) | Cursor (semantic refactor) | **NOT** a clean rebase — W295 (main) and L4.2 (this PR) ship two competing impls of `GET /personas/effective`; needs 30-60min semantic-merge refactor of `resolve_effective()` to be alternatives-aware. See PR #183 comment for 3 paths (A=full refactor, B=additive merge, C=close+defer to §3.1). W310-c verified. |
| Install funnel cross-target (#175, standalone) | Cursor rebase | independent; W310-c traced `probe`/qa-agent CI failure: not a real probe failure — GH Actions workflow registration cache went stale 2026-05-13 (e5f1911 updated path filters but workflow metadata kept May 11 version → every push triggers + dies in 0 sec ignoring path filter). PR #188 carries a header-comment touch to qa-agent.yml that forces re-registration on merge. After PR #188 lands → rebase #175; soft-fail (`QA_AGENT_SOFT_FAIL=1`) should keep workflow green even on probe FAILs. |
| Algotrade E2E playbook (#181, standalone) | Cursor lane | depends on §3.A algotrade closeout landing |
| Cockpit bridge panel (#182, follow-up to MCP rewrite) | Cursor | depends on rewritten MCP stack landing |
| FINAL-QA-GATE pass + version-consistency check | Agent | ⬜ |
| Cockpit polish (Claude lane) for soak surface | Claude lane | partial (13-item backlog, §3.10) |

### 2.3 The cut

`bash scripts/RELEASE-v10.0.command` once §2.1 + §2.2 green. Per `FINAL-QA-GATE` (8 sub-gates documented in `CURRENT_STATUS.md`).

---

## §3. Post-v10 roadmap (v10.1 → v11)

### 3.1 L4 closure (STT relay + full-duplex voice) — **v10.1**

- Faster-whisper STT relay endpoint (sidecar)
- Push-to-talk session semantics (start/stop, partial transcripts)
- Cockpit STT button + transcript wiring (W309 step 2 deliverable; ports to v10.1 after merge)
- Voice gallery UI (latency/token/model per persona)

**Estimate:** 2 weeks (assumes W309 step 2 merged + voice gallery scaffold).

### 3.2 L5 closure (encrypted sync hardening) — **v10.1 / v10.2**

**Important.** Host crypto is **already shipped** (real X25519 + XChaCha20-Poly1305 via PyNaCl — `backend/core/crypto/envelope.py`, `tests/test_pairing_envelope_e2e.py`). `docs/PHASE_L_ROADMAP.md §L5` correct; HANDOFF §6 line was stale — fixed in this PR.

Remaining:
- Persistent host keyring (X25519 secret → OS Keychain / Credential Manager / libsecret)
- Cockpit pairing/recovery UX wiring (use `docs/contracts/L5_PAIRING_DRAFT.md`)
- Mobile begin/accept protocol flows (without full mobile app — protocol layer)
- Pairing audit timeline in cockpit
- `pair_id` TTL on `meeet.world` relay (off-repo coordination)

**Estimate:** 3 weeks (split desktop + meeet bridge).

### 3.3 L9 closure (signed distribution) — **v10.1**

- Apple .dmg signing on real `.p12` (depends on §2.1 #3)
- Windows .exe Authenticode signing
- Pyoxidizer sidecar pinning + OTEL bundling
- Updater channel on real keys
- Linux .deb / AppImage track (optional v10.2)

**Estimate:** 1 week post-cert.

### 3.4 Encrypted vault (security gate) — **v10.2**

`docs/IDEAS.md` flags as "required before … real data". Without this, CRM keys / wallet keys / OAuth tokens sit in plaintext on disk.

- libsodium + OS keystore for at-rest secrets
- CRM / wallet / OAuth tokens migrate behind vault
- Vault open/lock UX in cockpit
- Vault rekey + recovery flow

**Estimate:** 2 weeks.

### 3.5 Policy & governance — **v10.2**

- Policy confirmations UI (inbox on `/api/policy/pending`)
- "Policy mode" badge in cockpit
- Differential telemetry (opt-in)
- Periodic ingest replay (~60s)

**Estimate:** 1 week.

### 3.6 L3 (code execution + artifacts) — **v11**

- Sandboxed `runtime.run_code` (Docker / Firecracker / nsjail)
- ArtifactPanel in cockpit (live preview, source view, export)
- Policy-gated execution (uses §3.5 confirmation UI + §3.4 vault)
- OS matrix (macOS / Linux / Windows sandbox backends)

**Estimate:** 3 weeks. Unlocks Claude.app artifact parity.

### 3.7 L6 (planner loop) — **v11**

- Planner action with voice integration
- PlanTimeline UI in cockpit
- New meeet event kinds (`plan.created`, `plan.step.completed`, `plan.completed`)
- Background execution with checkpoint resume

**Estimate:** 2 weeks.

### 3.8 L7 (marketplace v1) — **v11**

- Pack format + signing (deterministic build)
- Static analysis preflight (`tars pack lint`)
- `GET /api/domains/marketplace` + browsing API
- Marketplace sheet UI in cockpit
- Install / uninstall flow with confirmation UI (uses §3.5)

**Estimate:** 3-4 weeks.

### 3.9 L10 (mobile companions) — **v11**

- iOS app (SwiftUI, consumes L4/L5/L9)
- Android app (Compose)
- Native pairing UX
- Native mobile speech (replaces Web Speech on iOS/Android)
- TestFlight + Play internal track

**Estimate:** 6 weeks (longest, parallelisable with §3.6-3.8).

### 3.10 Claude design polish — **continuous, lane-isolated**

13 items from `docs/AGENT_HANDOFF.md` "Pending — Owned by Claude": GLB brain asset, cockpit micro-interactions, page transitions, landing copy, brand dressing, sound design, AwarenessTicker rev, ChatPane polish, attachment/sources treatment, ⌘K palette + timeline motif, download CTAs, meeet.world embed, pairing flow visual.

Pace: 1-2 items / week. Triage by current-screen importance — items 7, 8, 9 most user-visible.

### 3.A Algotrade closeout (deferred Wave-M / W2-W4 stack) — **v10.2 or v11**

**Context.** The algotrade vertical originally landed across **7 stacked PRs**: #166 paper-exec → #167 workshop-pack → #168 analytics → #169 session-report → #170 council-voices → #173 workshop-debrief → #174 `tars` CLI. All 7 are **closed-not-merged** as of W310 because their stacked-base structure made one-PR-at-a-time landing impossible after ~2 weeks of `main` drift. Wave 100 audit (`docs/AGENT_HANDOFF.md` L4439) file-copied only the *integration test*; the `backend/core/algotrade/exec/` payload itself remained absent from main.

**Scope.** Land the full W2-W4 algotrade payload + the `tars` CLI as **one consolidated rewrite** (mirrors the MCP M-wave pattern at `docs/handoff/MCP_REWRITE_BRIEF.md`):
- `backend/core/algotrade/exec/{base,paper,positions,risk,router,sessions,runtime,analytics,voices}.py`
- `backend/core/algotrade/exec/__init__.py` + `tests/test_algotrade_{paper,risk,voices,...}.py`
- `backend/core/domains/packs/algotrade/exec_actions.py` + manifest / pack.py updates
- `backend/cli/` + `bin/tars` (Wave M2 — operator + workshop power-user surface)
- `docs/ALGOTRADE.md` + `docs/CLI.md`

**Sources of truth (design intel preserved).** Each closed PR's "Design intel preserved" closure comment carries the full design spec. The 7 closed branches still exist on `origin/cursor/algotrade-w*` — their diffs are the implementation reference.

**Open punch list inherited from Wave 100 audit** (still valid):
- Rename exec's `Side.BUY/SELL` → `OrderSide` to avoid collision with backtest's `Side.LONG/SHORT`.
- Add `session_timeseries` action (rolling Sharpe, drawdown curve, trade-PnL histogram) for workshop FE.
- Resolve `from .report import …` duplicate in `exec/__init__.py`.

**Estimate.** 1-2 weeks for a single Cursor agent following the MCP rewrite pattern (most code already exists on the 7 closed branches as design spec; the work is consolidation + conflict resolution + adapter to current `pack.py` envelope).

**Gating.** Defer until after L4/L5/L9 closeout (v10.1) and vault (v10.2). Algotrade is workshop/B2B surface, not a v10 GA gate. **Owner:** Cursor lane, after #188 merge + MCP rewrite shipped.

---

## §4. Lane discipline & orchestration

### 4.1 Agent ownership

- **Agent in this lane (Cursor / Sonnet 4.6 / parent assistant)** — v10 GA dock-down, W309 closeout, M-wave rewrite brief, post-rc1 cleanup. Files: `apps/cockpit/`, `docs/handoff/`, `docs/AGENT_HANDOFF.md`, `tests/test_cockpit_*.py`.
- **Claude (separate lane)** — design polish backlog (§3.10), independent PR reviews via `gstack-claude` (W309 step 1 pattern).
- **Cursor (separate lane, sibling)** — M-wave MCP rewrite (per `docs/handoff/MCP_REWRITE_BRIEF.md`), other backend feature work.
- **Operator (Alien)** — the 5 external items (§2.1), version-axis decisions, merge approvals.
- **Brother (`meeet.world` cloud)** — billing endpoints, marketplace ingest contract, relay `pair_id` TTL.

### 4.2 Gates

Every phase has a clear gate:
- §2.1 #1-5 + §2.2 → §2.3 cut → **v10.0.0** tag.
- §3.1-3.3 → **v10.1** cut.
- §3.4-3.5 → **v10.2** cut.
- §3.6-3.9 → **v11** cut.

### 4.3 Review pattern (worth keeping)

W309 step 1 → `gstack-claude` independent review → fix-up commit on same branch → 1:1 test additions per finding. **Use this pattern for every non-trivial PR.** Git history reads `impl → review → fix-up` as three distinct commits.

### 4.4 Subagent usage

- **Parallel recon** — for scoping work. (This very plan was synthesised from 3 parallel `explore` subagents.)
- **Independent verification** — CI investigation, security audit, contract conformance.
- **Linear feature work** — single agent; subagents add coordination cost without benefit.

---

## §5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Operator blocked on Apple cert (§2.1 #3) for weeks | Soak rc1 on unsigned binary on operator host; `tauri-action` dev path supports it |
| Brother billing endpoints slip (§2.1 #2) | `/api/_meeet_mock` covers cockpit; ship v10 GA unblocked, snap to brother live in v10.0.1 |
| M-wave rewrite (§2.2, by Cursor) churns | Brief is bounded (one PR, ~7-commit sequence); time-box at 1 week or revert to per-PR landing |
| Phase L work expands scope mid-sprint | Hard rule: any item not in this plan goes to `docs/IDEAS.md`, not the active sprint |
| Doc drift between this plan + TARS_MASTER_DOC + AGENT_HANDOFF | Update all three on every phase close; rule: TARS_MASTER_DOC = north star (slow-moving), this doc = forward execution (per-wave), HANDOFF = chronological log (append-only) |
| v9.1.0 / v10 release-axis confusion (root cause of W310 spin-up) | `CURRENT_STATUS.md` is canonical for active version; HANDOFF historical blocks marked SUPERSEDED |

---

## §6. References

- `TARS_MASTER_DOC.md` — single source of truth (architecture, shipped inventory)
- `CURRENT_STATUS.md` — daily one-pager (rc1 → GA delta + 5 external items)
- `docs/PHASE_L_ROADMAP.md` — Phase L per-phase spec
- `docs/V10_GA_CHECKLIST.md` — 30-item breakdown of the 5 external items
- `docs/IDEAS.md` — long-tail unshipped items (this plan synthesises the HIGH-impact subset)
- `docs/AGENT_HANDOFF.md` — chronological work log
- `docs/handoff/W309_STEP2_BRIEF.md` — next cockpit work (Playwright + STT + persona picker)
- `docs/handoff/MCP_REWRITE_BRIEF.md` — M-wave consolidated rewrite (created in this PR)
- `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` — §2.1 #3 details
- `docs/V9_1_0_LAUNCH_PLAN.md` — historical (v9.1.0 shipped W138)

---

## §7. Change log of this plan

| Date | Wave | Author | Change |
|---|---|---|---|
| 2026-05-18 | W310 | Cursor (Sonnet 4.6 parent assistant) | Initial synthesis. Compiled from 3 parallel recon subagents (Phase L roadmap, 13-PR triage, IDEAS+tech debt) + 2 verification subagents (L5 crypto canon, v10 release-axis archaeology). Operator decisions captured: **D1 = v10 GA direct** (v9.1.0 already shipped W138; v9_then_v10 obsolete), **D3 = W309 step 2 go-now** after PR #187 merge, **D4 = close M-wave stack + consolidated rewrite**, **save = all_three** (this file + TARS_MASTER §6 pointer + HANDOFF SYNC sync). |
| 2026-05-18 | W310-b | Cursor (Sonnet 4.6 parent assistant) | **Algotrade closeout** (operator directive "выстрой правильную структуру"). Closed PRs #170 (W3-PR3 council voices) + #174 (Wave M2 `tars` CLI) — both stale stacked PRs whose base chain (#166-#169, #173) was already closed. Added new **§3.A Algotrade closeout** as deferred v10.2/v11 consolidated rewrite. Updated §2.2 PR triage table with definitive per-PR state for all remaining open PRs (#175, #181, #182, #183). Added HANDOFF Wave 100 audit CORRECTION marker (the W2/W3 `exec/*` payload was *not* actually file-copied into main, contrary to the audit's claim — only the integration test was). Synced `meeet-browser-agent/AGENTS.md` to point at this plan for cross-workspace agent pickup. |
| 2026-05-18 | W310-c | Cursor (Sonnet 4.6 parent assistant) | **Independent-PR cleanup pass.** Attempted PR #183 rebase: surfaced **semantic** conflict (W295 vs L4.2 ship two competing `GET /personas/effective` impls — needs ~30-60min `resolve_effective()` refactor, not a textual merge). Filed [PR #183 comment](https://github.com/alxvasilevvv/tars-neural-cockpit/pull/183#issuecomment-4472299281) with 3 paths (A=full refactor, B=additive merge, C=close+defer to §3.1). Rebase aborted cleanly (no force-push). Diagnosed **PR #175 `probe` CI failure** root cause: not a real probe failure — GH Actions workflow registration cache went stale on 2026-05-13 when `e5f1911` updated `qa-agent.yml` path filters but workflow metadata kept the May 11 version. Symptom: every push triggers qa-agent (ignoring path filter) and dies in 0 sec with "workflow file issue". Fix: header-comment touch in `.github/workflows/qa-agent.yml` to force re-registration on next merge to main. Both #183 and #175 rows in §2.2 updated with full diagnosis. |
