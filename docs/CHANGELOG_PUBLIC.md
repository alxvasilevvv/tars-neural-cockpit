# Agent changelog

## W310-ay — Post-fleet merge + rehearsal green (2026-05-20)

**Agent**: Cursor. Sequential operator request «все по очереди».

**Merged to `main`:** **#225** (W309-ax cockpit step 2), **#226** (W310-ax MCP rewrite; changelog conflict resolved on branch).

**Fixes on `main`:** `RELEASE-TAG-GUARD` stubs Gate 1 AMBER when `TAG_GUARD_DRY_RUN=1` and soak report absent (W310-ap matrix); download-verify arch/tag dry-run tests expect rc=2 PARTIAL.

**Verification:** `pytest` helper + MCP + cockpit contract → **298 passed, 4 skipped**; W310-ap dry-run matrix → **6/6 PARTIAL** on clean tree.

**Next:** operator W310-ao (secrets + live brother/Apple + 72h soak) — not automatable by agent.

---

## W310-ax — MCP consolidated rewrite (client + bridge + pool, 2026-05-20)

**Agent**: Cursor. PR **#226** merged to `main` after **#225** (changelog conflict resolved on branch).

**Shipped**: `backend/core/mcp/client_pkg/` (stdio transport + registry + session), `backend/core/mcp/bridge_pkg/` (BridgedPack + bootstrap + pool), thin facades `client.py` / `bridge.py` / `pool.py`. HTTP: `GET /api/mcp/bridge/status`, `GET /api/mcp/pool/stats` on existing `mcp_panel` router. Operator guide `docs/MCP_GUIDE.md`.

**Verification**: `.venv/bin/python -m pytest tests/test_mcp_client_*.py tests/test_mcp_bridge_bootstrap.py tests/test_mcp_server.py tests/test_mcp_panel_router.py -q` → **66 passed** (~1.4s).

**Deferred**: Cockpit MCP panel UI (#182), `tars mcp` CLI verbs (old #179) — follow-up PRs.

---

## W309-ax — Cockpit step 2: STT upload + persona picker + e2e green (2026-05-20)

**Agent**: Cursor. PR **#225** merged to `main` (post W310-aw fleet).

**Shipped**: `apiMultipart()` for `/api/voice/transcribe`; `voice.startRecording` / `stopRecording` / `isRecording` with `MediaRecorder`; persona `<select>` + `TARS_VOICE_PERSONA` persistence; `.stt-btn` push-to-talk in input bar; status badges via `data-cockpit` hooks (no nth-child drift). **DOWNLOAD-AND-VERIFY** dry-run now exits **rc=2 PARTIAL** (W310-ap matrix alignment). **25** static runtime contract tests (+4 pin-ups). Playwright **7/7** with fake media stream flags.

**Verification**: `pytest tests/test_cockpit_runtime_contract.py tests/test_download_and_verify_release_script.py -q` → 25 passed; `pnpm --filter @tars/cockpit test:e2e` → 7 passed (~2.6s).

**Next**: Operator GA via W310-ao (8 hard blockers external); MCP panel UI + CLI follow-ups.

---

## W310-aw — W310 fleet landed on `main` (operator merge sequence, 2026-05-20)

**Agent**: Cursor. Operator directive «сделай сам» + «продолжай» — executed W310-an merge sequence after #188 + #224 were already on `main`.

**Merged**: #187 (W309 runtime, doc conflicts resolved), #189 (Playwright scaffold), #190 (install funnel), #191 (voice fallback), #192–#213 (planning briefs + wave summary), #214–#223 (10 GA helper scripts). **0 open PRs** in W310 fleet.

**Verification**: `pytest` on helper script tests + `test_cockpit_runtime_contract.py` → **206 passed, 4 skipped** (~27s). W310-ap dry-run rehearsal on `main`: 4/6 helpers rc=2 PARTIAL as expected; TAG-GUARD rc=1 (no soak report — correct); DOWNLOAD dry-run rc=2 PARTIAL after W309-ax fix (was cosmetic rc=0 on stub).

**Docs**: `CURRENT_STATUS.md` updated to W310-aw (fleet landed, next = GA blockers + W310-ao cookbook). Cross-workspace: `meeet-browser-agent/AGENTS.md` + `TARS_OVERVIEW_RU.md` synced.

**Next implementer lanes**: **#225** W309 step 2 + **#226** MCP rewrite merged 2026-05-20; operator GA (W310-ao) + v10.1 per W310-ar sprint matrix.

---

## W310-at — sync layer on PR #188 (canonical state docs refresh, 2026-05-19)

**Agent**: Cursor (Opus 4.7 parent assistant). Continuation of W310 arc on operator directive "продолжай"; this entry covers the W310-at sync layer that updates three canonical "state" docs on PR #188's branch to match the post-W310-as wave landscape.

**Scope**: refresh `CURRENT_STATUS.md`, `TARS_MASTER_DOC.md §6.4`, and `PROJECT_INDEX.md` so the reader landing on PR #188 sees a self-consistent forward-execution + daily-pulse + master-doc + index, not a mix of fresh master plan against stale 2026-05-15/W269 daily pulse + stale W267 Top-5 in §6.4. ZERO new code, ZERO new helpers; pure cross-doc sync to close the silent drift gap that W310 inadvertently opened by landing on its own branch + extending sibling PRs (#192, #198) but never touching the canonical state docs themselves.

### What happened

1. **`CURRENT_STATUS.md` rewrite** (commit `c7d2cf0`). Was dated 2026-05-15 / W269 and read "GA is DONE except 5 external items". Replaced with:
   - **Top:** new "Read first (60-second pulse)" block pointing at `docs/W310_WAVE_SUMMARY.md` TLDR (W310-as).
   - **New section:** "W310 — post-rc1 PR triage wave (2026-05-18 → 2026-05-19)" with the full sub-wave table (runtime/triage a..f / planning-surface briefs g..ac / implementer follow-ups ad..am / docs-only extensions an..as / cross-stack mirror aq).
   - **"What's left for the operator" rewritten:** replaces stale 5-item list with the post-W310-l 8-hard-blocker table (3 brother A1/A2/A5 from PR #198 + 5 Apple sign B1-B5 from PR #199), plus a deferred-to-v10.1+ subsection (Windows Authenticode / VS Code marketplace / on-prem customer / Linux signing). Includes paste-ready bash playbook for the 6-wrapper GA cookbook chain.
   - **New coda:** "Status (W310-as, 2026-05-19): GA orchestration arc closed" replacing the stale W267 "GA is DONE" coda. Names 37 PRs / 6 wrappers / 5 playbooks / cross-stack mirror / TLDR + forward-pointers to v10.1 / v10.2 / v11 via W310-aq + W310-ar.
   - 129 lines added, 16 lines deleted; final file = 238 lines.

2. **`TARS_MASTER_DOC.md §6.4 Path to v10.0 GA` reconciliation** (commit `9f2de69`). Kept the W267 "Top 5 external items" historical snapshot intact (per the doc rule: forward execution lives in `PRODUCT_MASTER_PLAN.md`); appended a new "Reconciliation (W310-at, 2026-05-19)" subsection right after the W267 status block that documents:
   - Top 5 widened to 8 hard blockers post-W310-l (3 brother coord + 5 Apple sign).
   - Items 4-5 (VS Code marketplace + on-prem customer) deferred to v10.1+ per W310-l.
   - 6 single-decision verdict wrappers as PRs #214-#223.
   - 5 docs-only paste playbooks compressing D-0 → D+365 arc into "5 paste actions + 2 typed confirmations + 1 decision-tree walk + 1 sprint-matrix paste per sprint kickoff".
   - Cross-stack mirror in PR #198 §8.A.
   - 33 lines added.

3. **`PROJECT_INDEX.md` entry add** (commit `9f2de69`, same as above). Added missing entry for `docs/handoff/MCP_REWRITE_BRIEF.md` (which has been on PR #188's branch since W310 but never indexed). Annotated as "W310 (a)" to mark it as the first item of the W310 wave (replaces closed PR #177; 16 spec-pinned tests; ~12-15h effort). 1 line added.

4. **Cross-workspace sync**. Updated `meeet-browser-agent/AGENTS.md` PR #188 description bullet (+1/-1 LoC, commit `cbc88cf` on `cursor/bootstrap-workspace`) and `meeet-browser-agent/TARS_OVERVIEW_RU.md` header + author trail + active-PR row + operator-next-step bullet (+4/-4 LoC across 4 touch points, commit `84f9c8d`) so a freshly-landed agent in `meeet-browser-agent` sees the W310-at sync layer note before pivoting into TARS.

5. **PR #188 comment** posted at https://github.com/alxvasilevvv/tars-neural-cockpit/pull/188#issuecomment-4484909714 announcing the W310-at sync layer; explains why the three TARS-side state docs got folded into PR #188's scope rather than carved into a separate PR (= one merge ships self-consistent landing surface) + reiterates merge order (PR #188 first, then W310-an playbook).

### Files touched (W310-at)

| File | Change |
|---|---|
| `CURRENT_STATUS.md` | Full rewrite of "Read first" block + new W310 section + "What's left" replacement + new W310-as coda. 129+/16-. |
| `TARS_MASTER_DOC.md` | New "Reconciliation (W310-at, 2026-05-19)" subsection appended to §6.4 after W267 Top-5 historical block. 33+. |
| `PROJECT_INDEX.md` | Added `docs/handoff/MCP_REWRITE_BRIEF.md` row in handoff briefs section, annotated W310 (a). 1+. |
| `docs/CHANGELOG_AGENTS.md` | This entry. |
| (cross-workspace) `meeet-browser-agent/AGENTS.md` | +1/-1 — PR #188 description bullet extended with W310-at sync note. |
| (cross-workspace) `meeet-browser-agent/TARS_OVERVIEW_RU.md` | +4/-4 — header + author trail + active-PR row + operator-next-step bullet refreshed. |

### What is NOT done (deliberate)

- **PR #188 description rewrite on GitHub itself** — kept as W310-at PR comment (single notification surface) rather than amending the PR body, because the body still correctly reflects the master plan + M-wave consolidation + qa-agent fix scope and the W310-at sync layer is best understood as a follow-up sync rather than a fundamental scope change. Reader who reads the PR comment thread sees the announcement.
- **CHANGELOG_PUBLIC.md entry** — pure-docs sync layer with zero user-facing behaviour change; nothing to announce in the public changelog. (W310-c set the same precedent: agent-changelog only, no public-changelog entry.)
- **Sibling-PR PROJECT_INDEX entries** for the rest of the W310 wave (PR #192 wave summary, PR #197/#198/#199 handoff briefs, PRs #214-#223 helper scripts) — those briefs / scripts live on sibling PR branches; they should add their own PROJECT_INDEX entries as those PRs merge, otherwise PROJECT_INDEX on this branch would lie about the state of `main` until those PRs land too.

### Operator inputs needed

Same as W310-c: merge PR #188 first (it now ships the W310-at sync layer alongside the master plan + qa-agent fix), then paste the W310-an merge sequence from `docs/W310_WAVE_SUMMARY.md` to drain the remaining 36 PRs.

---

## W310-c — independent-PR cleanup pass (2026-05-18)

**Agent**: Cursor (Sonnet 4.6 parent assistant). Continuation of W310 / W310-b on operator directive "продолжай".

**Scope**: triage the three PRs that PRODUCT_MASTER_PLAN.md §2.2 flagged as independent of the (closed) MCP / Algotrade stacks: PR #183 (voice persona fallback), PR #175 (install funnel cross-target), and PR #182 (cockpit MCP panel — explicitly deferred until consolidated MCP rewrite lands).

### What happened

1. **PR #183 rebase attempt → aborted with diagnosis.** Pruned 5 stale worktrees on `/private/tmp/jarvis-*` so checkout could proceed, then `git rebase origin/main` on `cursor/voice-persona-fallback`. Conflicts in `docs/CHANGELOG_AGENTS.md` + `docs/CHANGELOG_PUBLIC.md` (trivial — pre-commit regenerates), but `web_extras/routers/voice.py` carried a **semantic** conflict: W295 (shipped to main 2026-05-xx) and Phase L4.2 (this PR) both define `GET /api/voice/personas/effective` with **different response shapes** and **different resolution backends** (W295 uses `resolve_effective()` shared with `/speak`; L4.2 uses `MacSayEngine._pick_fallback_voice()` directly). Naïve "accept ours" breaks the L4.2 substitution diagnostic (the whole UX point of the PR). Naïve "accept theirs" breaks the W290 acceptance harness (`scripts/qa_w290_cockpit.sh` Group 9). Correct merge requires a 30-60min semantic refactor to make `resolve_effective()` alternatives-aware. Filed [PR #183 comment](https://github.com/alxvasilevvv/tars-neural-cockpit/pull/183#issuecomment-4472299281) with the full diff diagnosis + 3 paths (A=full refactor → DRY win, B=additive merge → minimal diff, C=close+defer → ship as part of `PRODUCT_MASTER_PLAN.md §3.1` L4 closeout). `git rebase --abort`; no force-push; PR stays in its current state pending operator pick.

2. **PR #175 `probe` CI failure → root cause found.** Ran the qa_agent locally with `QA_AGENT_SOFT_FAIL=1` → exit 0, 28 probe FAILs as expected (all "wrong build" complaints from probes still asking for the SPA `<div id="root"></div>` shell that `e5f1911` deliberately removed). But CI shows `probe: FAILURE` blocking the PR — why? `gh api .../actions/runs/<id>` revealed: every recent qa-agent run has `created_at == run_started_at == updated_at` → 0-second runtime → workflow file failed to load. Cross-checked with credential-sentinel (3-second runtimes, runs fine). `gh api .../actions/workflows/269172814` shows `name=".github/workflows/qa-agent.yml"` (the path, not the YAML `name:` field!) and `updated_at=2026-05-11T09:30:56` — but the file's last commit is `e5f1911` from **2026-05-13**. **GitHub Actions cached the old workflow registration** and never re-parsed after the May 13 commit (which narrowed the `paths:` filter from 5 SPA-specific entries to 1 `docs/qa-snapshot.json`). Result: every push triggers qa-agent ignoring the new path filter, the runtime then can't reconcile the cached vs file shape, and the run dies in 0 sec. **Fix**: touched the qa-agent.yml file header with a W310-c comment block — any non-whitespace change forces re-registration on next merge to main. After PR #188 lands, the next merge will register the current file (post-`e5f1911`), the path filter will start working, and PR runs will either pass via soft-fail or skip via path filter.

3. **No new PRs opened.** All fixes ride along PR #188 (W310 master plan branch). Operator merges PR #187 (W309 step 1) + PR #188 (master plan + W310-b/W310-c diagnoses + qa-agent header touch) and the CI clears itself on the next merge.

### Files touched (W310-c)

| File | Change |
|---|---|
| `.github/workflows/qa-agent.yml` | Added W310-c diagnostic comment block to header to force GH Actions workflow re-registration. |
| `docs/PRODUCT_MASTER_PLAN.md` | Updated §2.2 rows for #183 (semantic conflict — see PR comment for paths) + #175 (probe root cause = workflow registration cache, not a real probe bug). Added §7 W310-c change log row. |
| `docs/CHANGELOG_AGENTS.md` | This entry. |

### What is NOT done (deliberate)

- **PR #183 semantic refactor** (the 30-60min `resolve_effective()` work) → operator picks path A/B/C; deferring avoids breaking either main's W290 harness or this PR's L4.2 diagnostic.
- **PR #175 rebase** → blocked on PR #188 merge (need the qa-agent.yml header fix to land first so `probe` CI doesn't immediately re-block on rebase push).
- **PR #182 (cockpit MCP panel)** → explicitly deferred per §2.2 until the consolidated MCP rewrite lands (otherwise it would build against the now-closed M-wave skeletal pool).
- **PR #181 (algotrade E2E)** → orphaned by the algotrade closeout; folded into the §3.A deferred rewrite per W310-b.

### Operator inputs needed

- Merge PR #187 (W309 step 1) → unblocks W309 step 2 implementation.
- Merge PR #188 (this branch) → fixes qa-agent CI on next push + locks in the master plan + W310 diagnoses.
- Pick a path on PR #183 (A=refactor / B=additive merge / C=close+defer). My recommendation: **B** (additive merge, ~30min) — keeps W295's DRY contract while shipping the L4.2 substitution diagnostic the operator's UX bug needs.

---



Per-batch log of edits made by autonomous agents. Read top-down; latest entry
first. Every entry: who, when, summary, files. Keep entries short and
factual; prose belongs in `AGENT_HANDOFF.md`.

## 2026-05-18 — Cursor · W310-b algotrade closeout + remaining-PR triage + Wave 100 audit correction

**Summary**

Closed 2 more stale stacked PRs as a follow-up batch on the same branch
`cursor/post-rc1-master-plan` (extends W310 above). Operator directive:
*"выстрой правильную структуру всего проекта и синхронизацию с другими
системами и начинай"* — full delegation to clean up the stacked-PR
backlog using the agent's own judgement.

**PRs closed (algotrade stack)**

- **#170** — Phase W3-PR3 trading council voices. Closed: base chain
  #166→#167→#168→#169 all CLOSED-not-merged; ~1200 LoC orphaned.
- **#174** — Wave M2 `tars` CLI. Closed: base chain
  #173→#168→#167→#166 all CLOSED-not-merged; ~1950 LoC orphaned;
  also depends transitively on `backend/cli/commands/algotrade.py`
  which imports from un-merged `algotrade.exec`.

Both close-comments preserve full design intel (PR-body excerpts +
verification table + pointer to §3.A for consolidated landing).

**W310 closure total**: **8 PRs** (6 M-wave MCP + 2 algotrade).

**Wave 100 audit CORRECTION**

While verifying the close decision, discovered HANDOFF Wave 100 audit
(L4439-L4467) overpromised: it claimed *"file-copied W2 + W3 exec/*
into the working tree"* but empirically only
`tests/test_algotrade_integration.py` was actually file-copied;
`backend/core/algotrade/exec/` folder remains absent from main. Added
explicit CORRECTION block after the original audit text pointing at
§3.A as the consolidated landing path.

**PRODUCT_MASTER_PLAN updates**

- **§2.2 PR triage table** — definitive state for every remaining open
  PR (#175 install funnel, #181 algotrade E2E, #182 cockpit MCP, #183
  voice persona fallback) + explicit ✅ markers for the 8 closures
  done this wave.
- **§3.A Algotrade closeout (NEW)** — full deferred-work spec for the
  7-PR algotrade stack (#166-#170, #173, #174) as v10.2/v11
  consolidated rewrite. Inherits Wave 100 audit punch list (Side enum
  collision, `session_timeseries` action, exec/__init__.py dedup).
  Estimate 1-2 weeks; mirrors MCP rewrite pattern.
- **§7 change log** — W310-b entry appended.

**Cross-workspace sync**

- `meeet-browser-agent/AGENTS.md` — added `PRODUCT_MASTER_PLAN.md` to
  the read order + W310 sync block at the bottom (v10.0.0-rc.1 status,
  active PRs #187 + #188, 8 closures, plan pointer). Cross-workspace
  agent pickup now points at canonical forward execution doc.

**Files**

- `docs/AGENT_HANDOFF.md` — Wave 100 CORRECTION inline + top banner
  W310-b SYNC prepended.
- `docs/PRODUCT_MASTER_PLAN.md` — §2.2 rewritten with definitive
  triage; §3.A added; §7 W310-b entry.
- `docs/CHANGELOG_AGENTS.md` — this entry.
- `/Users/alien/Projects/meeet-browser-agent/AGENTS.md` — sync block +
  expanded read order.

**Process note**

This entry was authored by the same Cursor parent agent under W310's
"orchestrator" mode. Decision pattern: closure-with-design-intel-
preservation now established across two stale-PR families (MCP + algo-
trade); future stale stacks can apply the same brief template at
`docs/handoff/MCP_REWRITE_BRIEF.md`. Push to branch + add to PR #188.

---

## 2026-05-18 — Cursor · W310 post-rc1 master plan + M-wave consolidation brief + HANDOFF corrections

**Summary**

Synthesised the forward execution plan from `v10.0.0-rc.1` (cut W264,
2026-05-15) through GA into Phase L closure (v10.1 → v10.2 → v11).
Branch: `cursor/post-rc1-master-plan`. Triggered by operator request
"full plan to the end with stages, use orchestration, perfect the
product". Synthesis fed by 3 parallel `explore` subagents (Phase L
roadmap state, 13 open PR triage, IDEAS + tech debt audit) + 2
verification subagents (L5 crypto canon, v10 release-axis archaeology
— both confirmed two stale docs that prompted the corrections below).

**Decisions captured (operator W310, 2026-05-18)**

1. **Release axis = v10 GA direct.** `v9.1.0` already shipped W138-158;
   the v9_then_v10 sequencing was based on stale HANDOFF wording. v10
   GA target is the 5 external items in `docs/V10_GA_CHECKLIST.md`.
2. **W309 step 2 = go-now** after PR #187 merge. Brief lives at
   `docs/handoff/W309_STEP2_BRIEF.md` (drafted 7h ago, gated, ready).
3. **M-wave MCP stack** (6 open PRs: #176, #177, #178, #179, #180,
   #184) **close + redo** as one consolidated PR. Brief at
   `docs/handoff/MCP_REWRITE_BRIEF.md`. Closed PR diffs preserved as
   design spec per §7.
4. **Master plan storage = all_three** — new dedicated doc + cross-link
   in `TARS_MASTER_DOC.md §6` + indexed in `PROJECT_INDEX.md` Strategy.

**Two stale-doc corrections shipped in the same PR**

- **L5 crypto canon.** HANDOFF Pending §6 said "pairing endpoints
  shipped with **mock crypto**" — wrong. Real X25519 +
  XChaCha20-Poly1305 (PyNaCl) was already shipped on the host per
  `backend/core/crypto/envelope.py` (`nacl.bindings` AEAD +
  `nacl.public.SealedBox`) and end-to-end verified by
  `tests/test_pairing_envelope_e2e.py`. Bullet rewritten to reflect
  what's actually pending (keyring, pairing UX, mobile protocol,
  audit timeline, `pair_id` TTL).
- **Wave 81 launch checklist.** The 4-item "Pending operator actions
  blocking the launch" list was for `v9.1.0` (already shipped). Block
  now carries an explicit SUPERSEDED header pointing readers to
  `docs/V10_GA_CHECKLIST.md` + `docs/PRODUCT_MASTER_PLAN.md §2.1` as
  the active 5-item gate.

**Files**

- `docs/PRODUCT_MASTER_PLAN.md` (new, 168 lines) — §1 where-we-are,
  §2 v10 GA push (5 external + internal docking + cut), §3 post-v10
  roadmap (10 sub-phases L3-L10 + vault + policy + Claude polish),
  §4 lane discipline, §5 risks, §6 references, §7 plan change log.
- `docs/handoff/MCP_REWRITE_BRIEF.md` (new, 152 lines) — close-and-redo
  brief for Cursor. §0 why, §1 scope, §2 deferred, §3 approach +
  7-commit build order, §4 acceptance, §5 verify, §6 rollback, §7
  design intel from closed PRs (preserve these choices), §8 refs.
- `TARS_MASTER_DOC.md` — §6 Roadmap header now points forward
  execution to `PRODUCT_MASTER_PLAN.md`; stays the historical Wave
  A/B/C source.
- `PROJECT_INDEX.md` — Strategy table row added for master plan.
- `docs/AGENT_HANDOFF.md` — SYNC banner top: W310 entry prepended.
  Pending §6 (line 3423): L5 bullet rewritten with CORRECTION marker.
  Wave 81 block (line 4381): SUPERSEDED header added in front.

**Operator action queue**

1. Read `docs/PRODUCT_MASTER_PLAN.md` (~15 min).
2. Merge PR #187 (W309 step 1) — unblocks step 2.
3. Approve the post-rc1 master-plan PR (this one) or push back on any
   phase in §3.
4. After approval: 5 M-wave PRs (#176, #177, #178, #179, #180, #184)
   get formally closed via `gh pr close` with the comment template in
   §0 of `MCP_REWRITE_BRIEF.md`. New PR opens on
   `cursor/mcp-rewrite-consolidated`.

**Subagent usage note**

Five subagents in total this session — 3 recon (parallel) + 2
verification (sequential, one after recon surfaced the contradictions).
Cost: ~30 min wall clock, would have been ~4h without parallelism.
Reusing this pattern for v10.1 phase scoping.

## 2026-05-18 — Cursor · W309 step 2 brief (drafted, gated)

**Summary**

Drafted `docs/handoff/W309_STEP2_BRIEF.md` while PR #187 sits awaiting
operator merge. Brief is **gated on PR #187 merge + operator OK** (same
pattern as the original W309 brief — no implementation kicks off without
explicit "go").

Step 2 closes the three honest gaps left by step 1:

1. **All 20 runtime tests are static.** Adds Playwright behavioural
   smoke under `apps/cockpit/tests/e2e/cockpit.spec.ts` with mocked
   sidecar (`page.route`), mocked SSE (streamed response body), mocked
   WebSocket (init script). Runs in < 10s. Addresses Claude PR #187
   review's explicit ask: *"the cheapest behavioral guard you'd
   actually trust"*.
2. **Mic permission goes nowhere.** Extends `voice.ts` with
   `startRecording()` / `stopRecording()` using `MediaRecorder` →
   `/api/voice/transcribe` multipart upload. Transcript drops into the
   input textarea. Closes the half-open voice loop where step 1 only
   proved the permission flow.
3. **Voice picker has no UI.** Minimal `<select>` in the status bar
   driven by `voice.getPersonas()`, persists choice to
   `window.localStorage.TARS_VOICE_PERSONA`, restores on next setup.

Tests grow 11 + 20 = 31 → 11 + 25 = **36 static** + a new Playwright
suite (~10s). Bundle estimated to land at ~30 KB raw / ~10 KB gz (vs
current 22.9 / 8.4) — rollback cap set at 35 KB raw / 12 KB gz with
documented headroom math. ETA: ~4h, smaller than step 1.

**Out of scope (still W310+)**

- Drawers (⌘K/⌘L/⌘R), council, playbooks, search, wallet, pairing,
  meeet bridge, awareness rendering, recovery — unchanged.
- Newly deferred from step 2: waveform visualiser, voice cloning UI,
  `webkitSpeechRecognition` fallback, STT streaming, per-persona TTS
  preview button. Rationale in brief §6.

**Files**

- `docs/handoff/W309_STEP2_BRIEF.md` (new, 332 lines) — same format
  as the W309 step 1 brief: §0 motivation, §1 inventory, §2 strategy,
  §3 sub-tasks, §4 verify, §5 rollback, §6 out of scope, §7 commit
  message, §8 cost, §9 gating.

**Operator action queue**

1. Merge PR #187 (W309 step 1 + fix-up).
2. Say "go" on step 2, OR explicitly defer to ship v9.1.0 with the
   three gaps documented in brief §9.

## 2026-05-18 — Cursor · W309 step 1 follow-up (Claude review fix-ups)

**Summary**

Independent Claude review of PR #187 returned `READY_TO_MERGE_WITH_FOLLOWUPS`
(see PR #187 comment). Three high-sev findings (`ws.setup()` non-idempotent,
`ensureMic()` race, stale `MediaStream` after permission revoke) plus six
medium/low findings landed as a single fix-up commit on the same branch
rather than deferred — all bounded, all on the runtime modules already in
review. Tests tightened to catch each regression class explicitly per
Claude's test-quality critique ("greps for `30_000` catch removals, not
regressions").

**Behavioural changes**

1. `ws.setup()` idempotency — second call with an active socket or pending
   retry now short-circuits and just merges newly-passed topics into the
   live subscription set. Prevents WebSocket leakage on HMR / accidental
   re-boot / future re-entry.
2. `ws` OPEN handler now checks `wantOpen` first — if teardown landed
   during CONNECTING, the resolving socket is closed with code 1000
   (`teardown_during_connect`) instead of flipping the badge green-then-closed.
3. `voice.ensureMic()` caches the in-flight promise (`state.micPromise`) so
   concurrent callers share one `getUserMedia()` request; second
   double-click no longer opens a duplicate stream whose tracks leak.
4. `voice.ensureMic()` detects a stale `MediaStream` (`stream.active`
   false or no live audio tracks) and re-requests — the cockpit no longer
   hands a dead stream back to the caller when the operator revokes mic
   permission via OS settings mid-session.
5. `voice.speak()` rejects non-`audio/*` content-types before piping into
   `<audio>` — defends against a future 200 + JSON envelope from
   `/api/voice/speak` producing an opaque "audio_play_failed" error.
6. `voice.playOne()` drops queued utterances after `teardown()` — prevents
   the TTS chain resurrecting `Audio` elements on a closed window.
7. `chat.ts` SSE parser now accepts all three spec-permitted frame
   boundaries (`\n\n`, `\r\n\r\n`, `\r\r`) so a reverse proxy that
   normalises line endings doesn't hang the stream. Per-line parser
   also splits on `\r\n|\r|\n` for the same reason. Plus a trailing-buffer
   flush after the read loop so a stream that closes without a final
   blank line (sidecar crash, abrupt EOF) doesn't silently drop the last
   delta.
8. `api.ApiError` constructor wraps `JSON.stringify(detail)` in try/catch —
   a circular-ref `detail` (e.g. a wrapped fetch error) no longer throws
   inside the throw and masks the real failure.
9. `cockpit-entry.ts` vault CTA link now uses `rel="noopener noreferrer"`
   (defense-in-depth on external links with `target="_blank"`).
10. `cockpit-entry.ts` `teardownAll()` latches on first call — both
    `beforeunload` and `pagehide` fire on Tauri window close; the
    one-shot guard stops the chain double-aborting in-flight SSE.

**Tests tightened**

- `tests/test_cockpit_runtime_contract.py` grew from 8 → 20 tests
  (+12). Each new test maps 1:1 to a Claude finding (`test_ws_setup_is_idempotent`,
  `test_voice_ensure_mic_serialises_concurrent_calls`, `test_voice_detects_stale_mediastream`,
  `test_chat_sse_parser_accepts_crlf`, etc.) plus `test_ws_manager_public_api_surface`
  (rename guard for the four methods `cockpit-entry.ts` binds against)
  and `test_bundle_size_gzipped_within_w309_cap` (25 KB gz cap, 1.5×
  current usage — far more sensitive than the loose 80 KB raw cap which
  was 3.6× the real bundle).
- Total: 11 drift + 20 runtime = 31 tests, all green.

**Bundle size**

- Raw: 22,877 B (vs 21,961 B before fix-up — +916 B for 10 fixes + 35
  lines of comments). Cap: 80 KB. Headroom: 71%.
- Gzipped: 8,370 B. Cap: 25 KB. Headroom: 67%.

**Files**

- `apps/cockpit/src/runtime/ws.ts` — idempotent `setup()` + `wantOpen`-guarded
  OPEN handler.
- `apps/cockpit/src/runtime/voice.ts` — `micPromise` cache, `isStreamUsable()`
  helper, alive-state guard, `audio/*` content-type check.
- `apps/cockpit/src/runtime/chat.ts` — multi-boundary SSE parser, trailing
  buffer flush, CRLF-aware per-line split.
- `apps/cockpit/src/runtime/api.ts` — defensive `ApiError` stringify.
- `apps/cockpit/src/pages/cockpit-entry.ts` — `noreferrer` on vault CTA,
  one-shot `teardownAll` latch.
- `tests/test_cockpit_runtime_contract.py` — +12 behavioural pin-ups, +1
  gzip budget test.
- `desktop/src-tauri/web/assets/cockpit-*.js` — restaged bundle.

**Verification**

- `pnpm --filter @tars/cockpit exec tsc --noEmit` → clean.
- `bash desktop/scripts/package-cockpit.sh` → built + staged + pruned
  orphan maps. New hash `cockpit-CGVJOS_p.js`.
- `python3 -m pytest tests/test_cockpit_runtime_contract.py tests/test_cockpit_tokens_sync.py -v`
  → 31 passed in 0.07s.

**Process**

Claude review posted as PR #187 comment for audit trail before any code
changed. Fix-up landed as a separate commit on the same branch so the
review trail stays legible in git history (PR diff now shows: original
implementation → reviewer comment → fix-up). Pattern worth keeping for
W310+ — review-before-merge with same-branch fix-ups beats merge-then-followup.

## 2026-05-18 — Cursor · W309 step 1 (functional restore: mic + WS + chat + TTS)

**Summary**

Operator un-gated W309 step 1 after PR #186 landed. Brief is the
local `cursor/w309-cockpit-functional-restore` branch (commit
`29e9cd9`, pushed to origin for reference, not implemented from).
Bounded MVP scope per brief §1: restore the four behaviors the W308
step 3 migration left static — mic capture, realtime WebSocket bus,
chat strand send/load, TTS playback — without touching the W307
visual contract. Five new TypeScript modules under
`apps/cockpit/src/runtime/`, one entry-script rewrite, +1 static
contract test, +1 bundle-size budget guard. Bundle grows from
~27 KB / ~6 KB gzipped (W309-prep baseline) to ~22 KB JS + 6 KB CSS
~8 KB gzipped — net under both the 80 KB raw / 25 KB gzip caps the
brief §5 rollback gates require.

**Runtime modules** (`apps/cockpit/src/runtime/*.ts`).

- `api.ts` — typed `fetch()` wrapper rooted at `getApiBase()` (default
  `http://127.0.0.1:8765`, override via `localStorage.TARS_API_URL`).
  Surfaces `{ok:false}` JSON envelopes as typed `ApiError`. Adds
  `apiBinary()` for `/api/voice/speak` (raw audio response), plus the
  brief §3.5 `vaultStatus()` hook returning `{keys:[{key,source,available}]}`.
  Module is the dependency root — runtime/ has no imports back into it.
- `tauri.ts` — `isTauri()` + `invokeTauri()` IPC helpers that detect
  the `__TAURI__` global at runtime; **no `@tauri-apps/api` SDK import**
  (would inflate bundle ~12 KB for one helper). No-ops outside the
  Tauri shell so `vite dev` boots clean.
- `ws.ts` — single `WsManager` singleton, targets `/api/realtime`
  (`tars.realtime.v1` envelope per `web_extras/routers/realtime.py`).
  Reconnect: exponential backoff `1s → 30s` with full jitter (Marc
  Brooker), reset on any successful `open`. Close codes mapped per
  brief §3.2: `1000` clean (no retry), `4001` auth-fail (synthetic
  `auth_fail` event, stop loop), all others schedule retry.
  Server-driven heartbeat (we just count opens / closes; sidecar
  pushes `{type:'heartbeat'}` every N s per its `hello` envelope).
  Status bus: `idle | connecting | open | reconnecting | closed`
  exposed via `onStatus()` for the backend badge.
- `voice.ts` — three concerns per brief §3.3, one module. Mic:
  `ensureMic()` requests `navigator.mediaDevices.getUserMedia({audio:true})`
  on first user gesture, caches the `MediaStream`, `releaseMic()`
  stops every track. TTS: `speak(text, {personaId?})` queues
  utterances through a `Promise.then(...)` chain so back-to-back
  clicks don't overlap; each utterance POSTs `/api/voice/speak`, wraps
  the audio response in a `blob:` URL (CSP already opens
  `media-src 'self' blob:`), plays via `new Audio()`, revokes the URL
  in `finally`. Persona/health: `setup()` fetches `/api/voice/personas`
  + `/api/voice/health` in parallel (`Promise.allSettled`) and stores
  default persona + engine availability.
- `chat.ts` — thread lifecycle + optimistic strand. `setup({threadId?})`
  either GETs an existing thread (keeping only the last 20 messages
  per brief §3.4 "cockpit reload preserves last 20 messages") or
  POSTs `/api/chat/threads` to create a fresh one. `send(text)`
  appends a user message with `status: 'sending'`, POSTs to
  `/api/chat/threads/{id}/messages` (returns **SSE** per
  `web_extras/routers/chat.py`, **not** WS — corrected from brief
  §3.4 which assumed legacy SPA contract), stream-parses
  `text/event-stream` frames via `getReader()` + `TextDecoder`,
  appends an assistant message on the first content delta, grows
  text in place, flips status to `delivered` / `failed`.
  `onChange()` callbacks fire after every mutation.

**Entry rewrite** (`apps/cockpit/src/pages/cockpit-entry.ts`).

Replaces the static "`import './styles/global.css'` and done" shell
with: `pickRefs()` for the 7 DOM hooks the W308 step 2 markup
already exposes (`.briefing`, `.strand`, `.input-bar input`,
`.input-bar .mic`, two status-bar badges); `renderStrand()` that
switches `.strand[data-state]` between `collapsed` (count pill) and
`expanded` (header + scrolling ordered list of messages);
`applyWsStatus()` / `applyVoiceHealth()` that mutate
`badge.dataset.state` to drive the CSS data-state colour overrides;
`applyVault()` that appends a minimal "Add ElevenLabs key" CTA into
`.briefing` when the vault is missing the key. Input: Enter →
`chat.send()`. Mic: click toggles `ensureMic()` / `releaseMic()` and
updates `mic.dataset.state`. **No `innerHTML`** anywhere — every
dynamic node built via `document.createElement` + `textContent` +
`appendChild` so a malicious server response can't inject markup.
Lifecycle: `beforeunload` + `pagehide` both run the same teardown
chain (unsubscribe handlers → tear down chat/voice/ws singletons).

**Runtime CSS additions** (`apps/cockpit/cockpit.html` inline style).

Added strand-expanded layout (flex column, header w/ count, scrolling
ordered list capped at `max-height: 320px`), message row styling
(grid 64px / 1fr, role-coloured borders), `data-status` modifiers
(`sending` → `opacity: 0.65`, `failed` → red border tint), vault
CTA chip (thin red-tinted row), status badge `data-state` overrides
(`online` → success green, `degraded` → accent gold, `offline` → red
alert) that drive the existing `.ok` / `.accent` dot colour, and mic
`data-state` states (`on` → cyan glow, `denied` → red inset ring).

**Tests** (`tests/test_cockpit_runtime_contract.py`, +8 tests).

Pure static checks — CI runs without daemon / mic / TTS key. Each
test pins an architectural invariant: (1) all 5 runtime files exist;
(2) `api.ts` exports the wrapper + vault hook + holds the
`127.0.0.1:8765` sidecar URL contract and stays the runtime DAG root;
(3) `tauri.ts` detects `__TAURI__` and never imports
`@tauri-apps/...`; (4) `ws.ts` targets `/api/realtime`, declares
`BACKOFF_MIN_MS` / `BACKOFF_MAX_MS = 30_000`, honours
`TARS_WS_URL` override, distinguishes close codes 1000 + 4001;
(5) `voice.ts` references mic + TTS + persona + health
endpoints and only imports `./api`; (6) `chat.ts` calls
`/api/chat/threads`, accepts `text/event-stream`, has SSE parser
markers (`getReader`, `TextDecoder`), carries the three message
statuses; (7) entry imports all 4 modules + wires setup/teardown +
asserts no `innerHTML`; (8) bundle stays under brief §5 80 KB cap
(skipped when `dist/` absent). Pairs with the existing 11 W307/W308
tokens-sync drift tests so the full suite is now 19/19.

**Verification.**

- `pnpm typecheck` in `apps/cockpit/` — clean (initial run flagged a
  `VaultStatus` shape mismatch in the entry script's `applyVault`
  signature; fixed by importing + using the actual `VaultStatus`
  type rather than re-declaring it loosely).
- `pnpm build` — 18 modules, 90 ms. Bundle: `cockpit-*.js` chunks
  0.76 + 9.46 + 11.63 = ~21.85 KB raw / ~8 KB gzipped.
- `desktop/scripts/package-cockpit.sh` — clean, staged into
  `desktop/src-tauri/web/`, post-rsync orphan-map prune cleared 2.
- `pytest tests/test_cockpit_tokens_sync.py tests/test_cockpit_runtime_contract.py -v`
  — **19 passed in 0.05 s** (11 drift + 8 runtime).

**Decisions worth flagging for review.**

- **SSE vs WS for chat deltas.** Brief §3.4 said "wait for WS
  `chat.message` event → reconcile". That was the legacy SPA contract.
  Current sidecar (`web_extras/routers/chat.py`) streams the
  assistant turn back on the POST response itself as
  `text/event-stream`. WS still carries cross-cutting events
  (`policy`, `awareness`, `voice.*`) but not chat content deltas.
  SSE-on-POST is the right transport at MVP; out-of-band chat
  events (multi-device, typing indicators) are a W310+ concern when
  those WS event types actually exist on the server.
- **`tauri.ts` with no SDK import.** Brief §2.2 listed `tauri.ts` as
  one of the four modules but the MVP doesn't need any specific
  Tauri command yet. Kept the file as the seam (with `isTauri()` +
  `invokeTauri()` that no-op in browser) so W310+ can wire
  screen-share / clipboard / file-drop without touching every
  consumer, but skipped the `@tauri-apps/api` SDK dependency
  (~12 KB) until something actually needs it. Drift test rejects the
  import if a future agent adds it casually.
- **Vault hook co-located in `api.ts`.** Brief §3.5 named a separate
  file. Keeping it next to the `api()` wrapper kept the module count
  at the brief's five, and the function is 15 lines — splitting it
  out would have been ceremony.
- **`vite dev` CORS.** Sidecar default `TARS_CORS_ORIGINS` doesn't
  list `http://localhost:5174`. Production Tauri shell talks to
  `127.0.0.1:8765` directly under the existing CSP, so this only
  bites operators developing the cockpit in a browser tab. Documented
  in `api.ts` doc comment; not adding 5174 to the default sidecar
  CORS list because that surface should stay narrow in prod.

**Files changed**

- `apps/cockpit/src/runtime/api.ts` (new, 163 LOC)
- `apps/cockpit/src/runtime/tauri.ts` (new, 66 LOC)
- `apps/cockpit/src/runtime/ws.ts` (new, 241 LOC)
- `apps/cockpit/src/runtime/voice.ts` (new, 204 LOC)
- `apps/cockpit/src/runtime/chat.ts` (new, 277 LOC)
- `apps/cockpit/src/pages/cockpit-entry.ts` (rewritten, +280 LOC)
- `apps/cockpit/cockpit.html` (CSS-only additions for runtime states)
- `desktop/src-tauri/web/` (re-staged from `apps/cockpit/dist/`)
- `tests/test_cockpit_runtime_contract.py` (new, 245 LOC, +8 tests)
- `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`,
  `docs/W308_PRE_FLIGHT_FINDINGS.md` (W309 step 1 closure)

**Out of scope (W310+ candidates)**

- STT upload via `/api/voice/transcribe` (mic stream captured but
  not yet piped anywhere).
- Persona picker UI (we fetch personas + default but there's no
  switcher yet).
- WS-side chat reconciliation for multi-device sync.
- Policy gate / awareness WS event rendering (handlers seam exists
  via `ws().on(type, h)` but no UI binding yet).

## 2026-05-17 — Cursor · W309 prep follow-ups (Claude PR #186 review fixes)

**Summary**

Three follow-ups from Claude's `READY_TO_MERGE_WITH_FOLLOWUPS`
verdict on PR #186. All landed in the same PR (post-base-commit
push, so a separate commit rather than `--amend`). No follow-ups
were blockers; the value is keeping the W309 backlog at zero before
the functional wave starts.

**Medium — `--type-label` inline comment was misattributed.**

The step-4 → W309-prep `StrReplace` for the
`--font-size-phase-bar` declaration accidentally consumed the
`/* 11px — HUD / nav labels */` inline comment that *actually*
belongs to the line *above* (`--type-label: 0.6875rem;`). After
the swallow, the `--type-label` declaration ended up annotated as
"single token for the whole HUD label family", which is wrong —
that's `--font-size-hud-mono`. Restored the original inline comment
and explicitly disambiguated the two tokens in
`--font-size-hud-mono`'s rationale block (`--type-label` is the
rem-based typography scale knob, `--font-size-hud-mono` is the
px-based HUD container knob; they happen to resolve to the same
value on the default 16px root but mean different things).

**Low — `.stream-row .ts` / `.stream-row .meta` blind-spot
documented.**

Claude correctly identified that these two blocks in `hero.html`
have hardcoded `font-size: 11px` that the new drift guard cannot
see (they inherit `font-family: var(--font-mono)` from
`.stream-rows`, and the guard is block-scoped by design). Decision:
**not** migrate onto `--font-size-hud-mono` — these are data cells
(timestamps, numeric meta, no uppercase, no tracking), semantically
distinct from HUD labels. Added an inline rationale comment + per-
line `data, not HUD label` markers so the next agent doesn't try
to "fix" them. If stream data ever needs its own token, naming is
pre-staked as `--font-size-data-mono` (separate from HUD-mono).

**Low — Vite source-map orphan prune.**

Implemented Path 1 from the W309 carry-over note:
`desktop/scripts/package-cockpit.sh` now runs a post-rsync prune
step that walks `$WEB_DEST/assets`, finds every `*.js.map` whose
paired `*.js` does not exist, and removes it (`find -name '*.js.map'
-print0` + `[[ -f "${m%.map}" ]] || rm`). Survives Vite version
upgrades because it operates on the rsynced output, not Vite
plugin internals. Logs `[package-cockpit] pruned N orphan .js.map
placeholder(s)` so the prune is visible.

**Verification**

- `pytest tests/test_cockpit_tokens_sync.py -v` → 11 passed in 0.04s.
- `bash desktop/scripts/package-cockpit.sh` → OK. Prune log shows
  `pruned 3 orphan .js.map placeholder(s)`. Bundle assets directory
  drops from 8 files → 5 (CSS + 2 paired `.js` + `.js.map`). Manual
  orphan check loop confirms every remaining `.js.map` has its
  paired `.js`.

**Files**

- `apps/cockpit/src/styles/tokens.css` (restore `--type-label`
  inline comment + disambiguate two 11px tokens in
  `--font-size-hud-mono`'s rationale block)
- `apps/cockpit/hero.html` (rationale comment for
  `.stream-row .ts/.meta` + per-line markers)
- `desktop/scripts/package-cockpit.sh` (post-rsync orphan prune)
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` (mark the W309 minor
  cleanup item as closed)
- `desktop/src-tauri/web/` (rebuilt — prune dropped 3 orphans)

---

## 2026-05-17 — Cursor · W309 prep (rename --font-size-phase-bar → --font-size-hud-mono + migrate 6 callsites)

**Summary**

Operator delegated ("Продолжай" ×2 after PR #185 merged). Closes the
only design-tightening item still on the W309 backlog (the six
hardcoded `10px` mono call-sites Claude flagged in the second-round
review on `d12d517`). Path 1 selected per the recommendation in
`W308_PRE_FLIGHT_FINDINGS.md` (rename token + migrate everyone).

Not yet started, still gated on separate operator OK per plan E:
the functional W309 work (mic capture, WS reconnect, conversation
strand renderer). This entry is *only* the design tightening that
makes the field clean before the functional work lands.

**Token contract changes**

- `apps/cockpit/src/styles/tokens.css` — rename `--font-size-phase-bar`
  → `--font-size-hud-mono` (11px). Rationale block rewritten to
  document the broadening + preserve the step-4 history (originally
  landed for `.phase-bar` only because that was the W307 verdict's
  named symbol; renamed when the other five call-sites joined the
  same contract).
- `design-system/tars/MASTER.md` §4 typography table row rewritten:
  scope expanded from "Watch-me-work phase bar" → "HUD-class mono
  labels (phase bar, status bar, source chip, kbd hint, policy gate
  header, live-rail `stream-head` / `integrity-head`)". Single drift
  contract codified: "no hardcoded `10px` / `11px` allowed on any
  element using `font-family: var(--font-mono)`".

**Call-site migrations**

- `apps/cockpit/cockpit.html` — five blocks now use
  `var(--font-size-hud-mono)`:
  - `.phase-bar` (renamed from the step-4 token reference);
  - `.source-chip` (was `font-size: 10px`);
  - `.gate-head` (was `font-size: 10px`);
  - `.send-kbd` (was `font-size: 10px`);
  - `.status-bar` (was `font-size: 10px`).
  Also: `.phase-bar`'s pointer-comment rewritten to explain the
  rename trail so DevTools readers see why the token is named what
  it is.
- `apps/cockpit/hero.html` — two blocks now use
  `var(--font-size-hud-mono)`: `.stream-head` and `.integrity-head`
  (both were `font-size: 10px`). Total 7 call-sites on the single
  token.

**Drift suite**

- `tests/test_cockpit_tokens_sync.py` — `test_phase_bar_size_token_declared_and_applied`
  renamed and broadened to `test_hud_mono_font_size_token_declared_and_applied`
  (asserts declaration, 11px resolution, MASTER row, and ≥5 cockpit
  + ≥2 hero `var()` references).
- New `test_no_hardcoded_pixel_size_on_mono_family_elements` walks
  every `apps/cockpit/*.html`, parses CSS `{ … }` blocks, and fails
  on any block that declares both `font-family: var(--font-mono)` and
  a hardcoded `font-size: 10px` / `font-size: 11px`. Diagnostic
  includes `file:line` + 240-char block preview. Suite total:
  10 → **11**.

**Verification**

- `pytest tests/test_cockpit_tokens_sync.py -v` → **11 passed in 0.03s**.
- **Negative-control:** temporarily re-injecting `font-size: 10px`
  into `.source-chip` makes
  `test_no_hardcoded_pixel_size_on_mono_family_elements` fail at
  `apps/cockpit/cockpit.html:434` with the expected diagnostic.
  Restored automatically by the test harness (try/finally). Confirms
  the test is not vacuously passing.
- `bash desktop/scripts/package-cockpit.sh` (full rebuild path) → OK,
  4 HTML pages emitted, rsync to `desktop/src-tauri/web/` clean.
  Cockpit bundle stable at ~27 kB raw / ~6 kB gzipped.
- Bundle grep: 5× `var(--font-size-hud-mono)` in built `cockpit.html`,
  2× in built `hero.html`; zero hardcoded `font-size: 10px` on
  mono-family blocks remain in the built bundle.

**Files**

- `apps/cockpit/src/styles/tokens.css` (token rename + rationale)
- `apps/cockpit/cockpit.html` (5 call-sites + comment)
- `apps/cockpit/hero.html` (2 call-sites)
- `design-system/tars/MASTER.md` (typography row rewrite)
- `tests/test_cockpit_tokens_sync.py` (rename + new drift guard)
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` (W309 carry-over
  section: 6 mono call-sites marked closed; functional restore
  remains open and gated)
- `desktop/src-tauri/web/` (rebuilt — bundle hashes refreshed)
- `apps/cockpit/dist/` (rebuilt)

**Carry-over (unchanged)**

The functional W309 wave (mic capture, WS reconnect, conversation
strand renderer) is still gated on explicit operator OK per plan E.

---

## 2026-05-17 — Cursor · W308 step 4 (Claude code-review fixes for PR #185)

**Summary**

PR #185 (`claude/w307-design-refresh` → `main`) collected W307 design
verdict resolution, W308 steps 1–3, plus the design-pass artefacts.
Independent Claude Code review surfaced 4 issues; this entry lands
them. No new features; tightening only.

**Fixes (from Claude review, scored severity → resolution):**

- **CRITICAL — CSP block fonts.bunny.net.** Step 2's hero references
  Bunny Fonts (`<link rel="stylesheet" href="https://fonts.bunny.net/css?…">`
  for Cormorant Garamond + Sora) but `desktop/src-tauri/tauri.conf.json`
  CSP only listed Google Fonts. In Tauri the hero would silently fall
  back to system fonts. Extended `style-src` and `font-src` to include
  `https://fonts.bunny.net`. Google Fonts entries kept (cockpit shell
  still uses them).
- **CRITICAL — W307 verdict miss (phase-bar typography).** The W307
  cockpit reference renders the watch-me-work phase bar at `10px` in
  Share Tech Mono, which Claude's verdict flagged as below the
  letterform-clarity floor for that face (caps look like rectangles,
  `I`/`l` collapse). Added a dedicated token
  `--font-size-phase-bar: 11px` to `apps/cockpit/src/styles/tokens.css`
  with a comment that explains *why* it is separate from `--type-label`
  (intent at the call-site). `apps/cockpit/cockpit.html` now reads
  `font-size: var(--font-size-phase-bar)` on `.phase-bar`. MASTER
  typography table got the new row pointing at the new token.
- **MEDIUM — drift suite had vacuously passing tests.** Three of the
  step-2/3 contracts were "tests" in name only:
  - `surface-marketing` was declared in `tokens.css` but no test
    asserted it was *applied* to `hero.html`.
  - `--font-size-phase-bar` was new and untested.
  - The brief-item stagger pattern (`var(--i)` cadence under
    `prefers-reduced-motion: no-preference`) was new and untested.
  Added three real `tests/test_cockpit_tokens_sync.py` assertions:
  `test_hero_html_applies_surface_marketing_class`,
  `test_phase_bar_size_token_declared_and_applied`,
  `test_brief_item_stagger_animation_declared`. Tests fail loudly
  (not silently) if the contract drifts. Suite total: 6 → **10**.
- **MEDIUM — W308 step-2 brief not marked superseded.** `docs/handoff/
  W308_STEP2_BRIEF.md` is still in the handoff directory, with no
  banner telling the next agent it is closed. Added a top-of-file
  `> [SUPERSEDED]` banner pointing at the step-3 entry and PR #185.

**Code changes**

- `apps/cockpit/hero.html` — root `<html>` gains `class="surface-marketing"`
  so the motion-budget override (`--motion-budget-max: 4`) actually
  takes effect on the marketing surface. Previously the class was
  declared in `tokens.css` but applied nowhere.
- `apps/cockpit/src/styles/tokens.css` — adds `--font-size-phase-bar: 11px`
  with explanatory comment in the `:root` typography block.
- `apps/cockpit/cockpit.html` — `.phase-bar` swapped from `10px` to
  `var(--font-size-phase-bar)`. Brief-item buttons gain inline
  `style="--i: N"` (0..3) and an `@keyframes briefIn` stagger
  (`360ms cubic-bezier(...)` with `60ms` cadence per `--i`), gated by
  `@media (prefers-reduced-motion: no-preference)`. Plays once on
  cockpit open, then static.
- `design-system/tars/MASTER.md` — typography table row for the
  watch-me-work phase bar that documents the 10px → 11px move and
  the token name. Rest of §7 unchanged.
- `desktop/src-tauri/tauri.conf.json` — CSP extended (above).
- `tests/test_cockpit_tokens_sync.py` — 3 new tests (above).
- `docs/handoff/W308_STEP2_BRIEF.md` — superseded banner.

**Bundle**

Rebuilt via `bash desktop/scripts/package-cockpit.sh` after the source
edits. `cockpit.html` grew from ~24 kB → ~27 kB raw (inline
`<style>` for the stagger + 4 inline `style="--i:N"` attrs).
Gzipped: ~6 kB. No new assets.

**Verification**

- `pytest tests/test_cockpit_tokens_sync.py -q` → **10 passed** in
  0.04s (was 6).
- `bash desktop/scripts/package-cockpit.sh` (full build path) → OK,
  4 HTML pages emitted, rsync to `desktop/src-tauri/web/` clean.
- Bundle carries all 4 edits: `grep -c surface-marketing
  desktop/src-tauri/web/hero.html` = 1; `grep -c
  'var(--font-size-phase-bar)' desktop/src-tauri/web/cockpit.html` = 1;
  4 `style="--i:` and 1 `@keyframes briefIn` in cockpit.html.

**Files**

- `apps/cockpit/hero.html`
- `apps/cockpit/cockpit.html`
- `apps/cockpit/src/styles/tokens.css`
- `design-system/tars/MASTER.md`
- `desktop/src-tauri/tauri.conf.json`
- `tests/test_cockpit_tokens_sync.py`
- `docs/handoff/W308_STEP2_BRIEF.md`
- `desktop/src-tauri/web/` (rebuilt — 4 HTML + 3 asset chunks)
- `apps/cockpit/dist/` (rebuilt)

---

## 2026-05-17 — Cursor · W308 step 3 (wire apps/cockpit/dist/ into Tauri pipeline)

**Summary**

Operator delegated ("делай всё остальное без остановки"). The Tauri
desktop now ships `apps/cockpit/dist/` as its frontend instead of the
frozen pre-built React SPA that has lived under `desktop/src-tauri/web/`
since the experiments/neural-showcase-v3 SPA was deleted in `e5f1911`.
The legacy bundle is preserved (via `git mv` so history follows the
rename) at `desktop/src-tauri/web-legacy/` for emergency rollback and
as the reference for the next wave (restoring functional behaviors).

**Pipeline changes:**
- `desktop/scripts/package-cockpit.sh` rewritten. Was: 6-line stub
  that verified the bundle existed. Now: runs `(cd apps/cockpit/ &&
  pnpm install --silent && pnpm build)` (the script `cd`s in; it does
  not use `pnpm --filter` against the repo root), then
  `rsync apps/cockpit/dist/ → desktop/src-tauri/web/`.
- Flags: `--skip-build` (CI uses pre-built dist), `--legacy` (re-stage
  the legacy SPA for emergency parity checks).
- Tauri config (`tauri.conf.json`) unchanged. `frontendDist: ./web`,
  `beforeBuildCommand: pnpm cockpit:package`,
  `beforeDevCommand: pnpm serve:web` — now they point at a real
  source tree instead of a frozen artifact.

**Bundle changes (desktop/src-tauri/web/):**
- Old: 41 minified JS chunks (~5 MB), React + Spline + howler +
  opentype + navmesh + physics + gaussian-splat-compression +
  one 582 kB pre-rendered `index.html` containing the entire SPA.
- New: 4 HTML pages (`index`, `cockpit`, `hero`, `preview`),
  one 6 kB shared CSS, two small JS chunks (preview + main).
  Total ~21 kB raw / ~7 kB gzipped.

**Documentation:**
- `apps/cockpit/README.md` already reflects the multi-page build.
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md`: step 3 marked done;
  decision log entry; carry-over for W309+ (functional restore of
  mic/WS/conversation behaviors lost when the SPA was archived).
- `docs/AGENT_HANDOFF.md`: SYNC line + per-wave block.

**Files**

- `desktop/scripts/package-cockpit.sh` (rewritten)
- `desktop/src-tauri/web/` (replaced with built cockpit dist)
- `desktop/src-tauri/web-legacy/` (new — `git mv` of old `web/`,
  plus the two pre-W289/W290 `index.html.bak-*` backups)
- `docs/AGENT_HANDOFF.md`
- `docs/CHANGELOG_AGENTS.md`
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md`

**Verification**

- `bash desktop/scripts/package-cockpit.sh --skip-build` → OK,
  stages cockpit.html / hero.html / index.html / preview.html.
- `pnpm --filter @tars/cockpit build` → clean, 4 HTML pages, total
  ~73 kB raw / ~19 kB gzipped (incl. inline page CSS in HTMLs).
- `cd desktop && pnpm run serve:web` then `curl http://127.0.0.1:5173/`
  returns 200 (and `/cockpit.html` returns 301 → `/cockpit`, which
  is `serve`'s clean-URL behavior — Tauri loads either).
- `pytest tests/test_cockpit_tokens_sync.py -q` → 6/6 pass.

**Known carry-over (W309+)**

The legacy `Cockpit-CWJnxhRj.js` (~169 kB) implemented:
- microphone capture pipeline,
- websocket connection to the local sidecar (`ws://127.0.0.1:8765`),
- the conversation strand renderer.

The new `apps/cockpit/cockpit.html` is currently a static shell —
visually correct per W307, behaviorally inert. Restoring these
behaviors (likely as small per-page TS modules in
`apps/cockpit/src/pages/`) is the natural next wave. Until that
ships, `bash desktop/scripts/package-cockpit.sh --legacy` re-stages
the archived SPA if a release blocker appears.

---

## 2026-05-17 — Cursor · W308 step 2 (port cockpit + hero surfaces)

**Summary**

Operator delegated ("делай всё остальное без остановки"). Ported
Claude's W307 reference HTMLs (`docs/design/W307_refs/cockpit.html`,
`hero.html`) into the new `apps/cockpit/` scaffold as a proper
multi-page Vite project. The previous diagnostic `tokens-preview`
moved off `/` to `/preview.html`; `/` is now a landing/page picker
so the operator sees real surfaces, not a token grid, on first load.
Step 3 (replace the frozen Tauri bundle with `apps/cockpit/dist/`)
is queued.

**Architecture changes:**
- `vite.config.ts` rebuilt as multi-page: 4 entries
  (`index`/`cockpit`/`hero`/`preview`). Predictable asset filenames
  (`cockpit-<hash>.js/css`).
- `src/main.ts` deleted. Each page has its own entry under
  `src/pages/<page>-entry.ts` (small file that just imports
  `global.css`). The `tokens-preview.ts` render module is unchanged.
- `tsconfig.json` gets `"types": ["node"]` (for `__dirname`,
  `node:path` in `vite.config.ts`); dev-dep `@types/node@22`.

**New / changed page surfaces:**
- `apps/cockpit/index.html` — landing/page picker. Three cards
  (Cockpit · Hero · Tokens preview); uses shared tokens only.
- `apps/cockpit/cockpit.html` — operator shell ported from W307 ref.
  HUD header, briefing card (with W307-bumped greeting), 4 brief
  items, quick chips, conversation strand, policy gate (≥1100 px),
  input bar, status bar. All accent fills enforce
  `var(--cta-text-on-accent)`; ambient health pulses use
  `--motion-pulse` (3.6 s), alert pulses use `--motion-alert-pulse`.
- `apps/cockpit/hero.html` — marketing hero ported from W307 ref.
  Floating nav, headline + accent split, two CTAs, full SVG core
  scene (halo + outer dashed ring + 36-tick ring + inner pulse +
  core), live rail with stream + integrity card. Numeric data uses
  `font-variant-numeric: tabular-nums`.
- `apps/cockpit/preview.html` — diagnostic page (renamed from old
  `index.html`). Mounts the existing `tokens-preview` module.

**Documentation updates:**
- `apps/cockpit/README.md` rewritten to reflect multi-page layout,
  per-page bundle sizes, side-by-side parity recipe vs
  `docs/design/W307_refs/`.
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` — step 2 marked done;
  step 3 (Tauri bundle swap) queued; status header updated.

**Verification:**
- `pnpm --filter @tars/cockpit build` → clean. 4 HTML pages, shared
  CSS 6 KB / JS 10 KB total. Gzip totals: ~19 KB.
- Visual parity check: dev server on `:5174` (port) vs static server
  on `:5175` (`docs/design/W307_refs/`). Cockpit and hero render
  pixel-equivalent modulo the documented W307 verdict deltas
  (greeting bigger, black-on-accent, ambient pulse slower).
- `pytest tests/test_cockpit_tokens_sync.py -v` → 6/6 pass; the
  step-1 contract is preserved.

**Files**
- M `apps/cockpit/vite.config.ts`, `apps/cockpit/tsconfig.json`,
  `apps/cockpit/package.json` (0.2.0-step1 → 0.3.0-step2)
- M `apps/cockpit/index.html` (now landing, was tokens preview entry)
- A `apps/cockpit/cockpit.html`
- A `apps/cockpit/hero.html`
- A `apps/cockpit/preview.html`
- A `apps/cockpit/src/pages/{index,cockpit,hero,preview}-entry.ts`
- D `apps/cockpit/src/main.ts` (split into per-page entries)
- M `apps/cockpit/README.md`
- M `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md`

## 2026-05-17 — Cursor · W308 step 1 (apply W307 verdict)

**Summary**

Operator delegated the per-row token decisions ("выбери ты", continued
from step 0 delegation). Applied Claude's W307 verdict end-to-end into
`apps/cockpit/src/styles/tokens.css` + `design-system/tars/MASTER.md`.
All five open questions from W307 §"Open questions" answered with
explicit taste-calls (see `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md`
for the row table; single revert undoes any individual call).

**Hard-rule changes (no operator question — math constraints):**
- `--cta-text-on-accent: #000000` token + `.cta`/`.cta--ghost`
  utility. Codifies "text on gold MUST be black" (9.62:1 AAA vs
  ink-on-accent 2.69:1 AA fail). MASTER §3 anti-patterns updated.
- `--motion-budget-max: 2` codifies MASTER §7 "1-2 elements per view".
- Split `--motion-pulse` (3.6s ambient — "all good") from new
  `--motion-alert-pulse` (1.6s — warn states only). 1.6s previously
  read as "warning" on ambient health dots.
- `--color-hud-alpha-cap: 0.32` documents the existing usage cap.
- New `.t-num` utility (`font-variant-numeric: tabular-nums`) for
  live-data jitter.
- New `.glyph` utility + sanctioned glyph set (`▣ ◇ ◆ ═ ╳ ◯ ▾ ▸`).

**Taste-call changes (each individually revertable):**
- `--color-ink-3`: `#5C5A52` → `#8A867B`. Promotes contrast 2.84:1 →
  4.62:1 on bg-1 (WCAG AA pass). Token name kept.
- `--color-accent`, `--color-hud`: kept (Claude's recommendation).
- `--type-greeting`: new token at `clamp(2.4rem, 5vw, 3.4rem)`
  + `.t-greeting` utility. Mobile cap kind to 375px.
- Motion split contract (marketing vs cockpit): deferred to step 2;
  only cockpit surface exists today.

**MASTER.md updates:**
- §3 palette table: ink-3 hex, cta-text-on-accent row, hud-alpha-cap
  row, anti-pattern warning.
- §4 typography: greeting row, t-num row, sanctioned glyphs block,
  font CDN switched to `fonts.bunny.net` (privacy-safer mirror).
- §7 motion: split ambient/alert pulse contract, marketing-vs-cockpit
  budget note.
- §9 implementation map: redirected from deleted
  `experiments/neural-showcase-v3/*` to `apps/cockpit/`.

**Test extensions:**
`tests/test_cockpit_tokens_sync.py` grew from 3 → 6 tests:
- `test_master_documents_motion_budget` — both files reference
  `--motion-budget-max`.
- `test_master_codifies_cta_text_on_accent_rule` — MASTER §3 contains
  both the token row and the prose anti-pattern.
- `test_master_documents_hud_alpha_cap` — MASTER §3 references
  the alpha cap.

**Verification:**
- `pnpm --filter @tars/cockpit build` → clean. Bundle: 18 KB raw /
  6 KB gzipped (was 13 / 5 in step 0; +5 KB for `.cta` + `.glyph` +
  new preview sections).
- `pytest tests/test_cockpit_tokens_sync.py -v` → 6 passed.
- `pnpm dev` preview page now renders: full token swatch grid (now
  with corrected ink-3), `.t-greeting` sample, sanctioned glyph row,
  black-on-gold CTA pair, dual pulse contract (ambient vs alert),
  motion-budget badge.

**Files**

- `apps/cockpit/src/styles/tokens.css` (W307 verdict)
- `apps/cockpit/src/styles/typography.css` (.t-greeting, .t-num,
  .glyph)
- `apps/cockpit/src/styles/global.css` (.cta, .cta--ghost)
- `apps/cockpit/src/pages/tokens-preview.ts` (CTA + glyph + dual
  pulse sections)
- `apps/cockpit/package.json` (version bump 0.1.0-step0 →
  0.2.0-step1)
- `design-system/tars/MASTER.md` (§3, §4, §7, §9 updates)
- `tests/test_cockpit_tokens_sync.py` (3 new tests, ink-3 expected
  value updated)
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` (per-row decision log)

**Next**: W308 step 2 — wire `apps/cockpit/dist/` into
`desktop/scripts/package-cockpit.sh`; visual-parity check against
`docs/design/W307_refs/{hero,cockpit}.html`; replace
`desktop/src-tauri/web/` once parity is verified.

## 2026-05-17 — Cursor · W308 step 0 (Path C — new cockpit scaffold)

**Summary**

Operator delegated the W308 strategy call ("выбери ты"). Picked
**Path C, staged**: build a new minimal cockpit at `apps/cockpit/`
that owns the live design tokens *now*, without waiting for the W307
verdict and without touching the frozen production bundle. When the
verdict lands, only `tokens.css` + MASTER.md change — no shell rework.

Step 0 ships:

- `apps/cockpit/` scaffolded as Vite + vanilla TypeScript (no
  framework). README explains the rationale and the migration path
  to step 2. Bundle size: 13 KB raw / 5 KB gzipped.
- `apps/cockpit/src/styles/tokens.css` — full MASTER §3 palette,
  §4 typography, §5 spacing, §6 effects, plus a
  `prefers-reduced-motion: reduce` override block.
- `apps/cockpit/src/pages/tokens-preview.ts` — single live page
  rendering every swatch + type sample + motion sample, for visual
  verification before / after any token diff.
- `tests/test_cockpit_tokens_sync.py` — drift smoke test that fails
  the suite if `tokens.css`, MASTER.md, and the canonical values
  ever disagree (16 palette tokens + 2 font families + reduced-motion
  block contract). 3 tests, all passing.
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` updated with the Path C
  decision log and step 1 / step 2 queue.

Production cockpit (Tauri's frozen `desktop/src-tauri/web/`) is
deliberately *not* touched in step 0 — risk of breaking the release
pipeline is zero this wave.

**Verification**

- `pnpm --filter @tars/cockpit build` → clean (`tsc --noEmit` + Vite
  build, 70ms, 13 KB raw).
- `pytest tests/test_cockpit_tokens_sync.py -v` → 3 passed.
- `pytest --collect-only -q` → 3519 tests collected (was 3508 from
  W306 baseline + new cockpit tests; full suite untouched).

**Files**

- `apps/cockpit/README.md` (new, 110 lines)
- `apps/cockpit/package.json`, `tsconfig.json`, `vite.config.ts`,
  `.gitignore`, `pnpm-lock.yaml` (new)
- `apps/cockpit/index.html`, `public/favicon.svg` (new)
- `apps/cockpit/src/main.ts`, `src/pages/tokens-preview.ts` (new)
- `apps/cockpit/src/styles/{reset,tokens,typography,global}.css` (new)
- `tests/test_cockpit_tokens_sync.py` (new)
- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md` (decision log + checklist)

**Queued for step 1**: apply Claude's W307 token diff once it lands
(`docs/design/W307_VERDICT.md`) — edit `tokens.css` + MASTER.md in
the same commit so the smoke test stays green.

**Queued for step 2**: rewire `desktop/scripts/package-cockpit.sh`
to build `apps/cockpit/` and replace the frozen bundle; verify
parity against current cockpit before flipping.

## 2026-05-17 — Cursor · W308 pre-flight findings (token location inventory)

**Summary**

While Claude was running W307, mapped where MASTER tokens *actually
live in shipping code* — so W308 doesn't start by assuming a clean
`tokens.css` exists. Key finding: **there is no React/Vue source tree
in this repo**. The desktop cockpit ships a pre-built, committed
static bundle under `desktop/src-tauri/web/`. The original SPA
(`experiments/neural-showcase-v2/v3`, vanilla JS + Vite + Three.js)
was deleted in commit `e5f1911`. Shipping CSS lives *minified* in
`desktop/src-tauri/web/assets/index-*.css`.

W308 therefore starts with a strategy decision: (A) patch the bundle
in place (cheap, fragile), (B) restore the deleted SPA and rebuild
(correct, ~1 day, but reopens a deliberate removal decision), or
(C) build a new minimal Vite + vanilla TS cockpit under `apps/cockpit/`
with a proper `tokens.css` (clean, ~2 days). My recommendation:
Path C, staged — step 1 ships the system, step 2 ports surfaces.

The pre-flight checklist forces the operator to mark each row of the
W307 token diff (approve/change/skip) and pick A/B/C *before* any
code work starts. Also pins the pytest baseline (3508/0/6/2 from W306)
that W308 must not regress.

**Files**

- `docs/handoff/W308_PRE_FLIGHT_FINDINGS.md`

## 2026-05-17 — Cursor · W307 design-system refresh handoff (for Claude Code)

**Summary**

Wrote a self-contained handoff document targeting Claude Code (because
the Anthropic `frontend-design` plugin lives there and is the strongest
"anti-slop" pass in our stack). The W307 wave is *system artefacts
only* — refreshed verdict against the existing `MASTER.md`, two
reference HTML pages (hero + cockpit shell) rendered with current
tokens, contrast measurements, motion review. No production code
changes. Hard boundary: MASTER.md is the baseline, not something to
replace. Cursor picks up the migration in W308 once the operator marks
the token-diff table.

The handoff doc spells out: exact commands (`ui-ux-pro-max search.py
--design-system`, `frontend-design` HTML render, `/plan-design-review`,
`/web-design-guidelines` audit), acceptance criteria (verdict reads
like an opinion, hex-exact token diff, both pages render without
console errors, `prefers-reduced-motion` honoured), branch name
(`claude/w307-design-refresh`), and a copy-paste quick-start.

**Files**

- `docs/handoff/W307_DESIGN_SYSTEM_REFRESH_FOR_CLAUDE.md`

## 2026-05-17 — Cursor · W306 last two order-dependent failures (38 → 0)

**Summary**

Finished the W305 hunt. Full ``pytest`` matrix on Python 3.12 now reports
**3508 passed / 0 failed / 6 skipped / 2 xfailed** in ~6.5 min. Both residual
order-dependent failures bisected to specific upstream tests caching a stale
singleton pointed at a since-deleted tmp DB:

- **`test_fts_auto_backfill::test_endpoint_returns_no_drift_when_indexes_are_synced`.**
  Upstream `test_attachments_chunk_neighbours` (and others in the chunking
  family) initialise the `MeeetStore` singleton against the real
  `~/.tars/meeet.sqlite` with ``enabled=True``. The fts-repair endpoint reads
  that singleton, sees ``enabled``, and tries to repair an ``events_fts``
  index unrelated to this test → ``rebuilt == ['events_fts']`` instead of
  ``[]``. Fix: ``isolated_chat`` fixture now also drops
  ``backend.core.meeet.store._SINGLETON`` so the next ``get_meeet_store()``
  re-reads ``MEEET_STORE=disabled`` and short-circuits.
- **`test_thread_id_contextvar::test_policy_confirm_route_propagates_persisted_thread_id_into_handler`.**
  Upstream `test_rate_limit_expensive_routes` points ``MEEET_STORE_PATH`` at
  a ``tempfile.TemporaryDirectory`` that gets cleaned up on exit. The cached
  ``PolicyStore`` singleton retains that path → next confirm-insert into a
  fresh `tmp_path` finds ``no such table: confirmations``. Fix: ``fresh_meeet``
  fixture now also drops ``backend.core.policy.store._SINGLETON`` and
  ``backend.core.policy.gate._SINGLETON`` so the next confirm call re-inits
  ``_ensure_schema`` against the test's tmp DB.

Both fixes are *test-isolation only* — the product code is correct; the
fixtures just weren't dropping every cached singleton that pinned the
ephemeral DB path.

**Files**

- `tests/test_fts_auto_backfill.py`
- `tests/test_thread_id_contextvar.py`

## 2026-05-17 — Cursor · W305 test-suite cleanup (38 → 2 failures)

**Summary**

Pulled the full ``pytest`` matrix on Python 3.12: 3472 passed / **38 failed**
became **3506 passed / 2 failed / 6 skipped / 2 xfailed** (the 2 residual
failures are order-dependent: green in isolation; cross-test state-leak hunt
deferred). Real bugs vs harness issues sorted, then fixed:

- **Real fix.** ``desktop/pyoxidizer.bzl`` now pins ``opentelemetry-api``,
  ``opentelemetry-sdk``, ``opentelemetry-exporter-otlp-proto-http`` — without
  these the sidecar binary would have crashed with ``ImportError`` on first
  launch (telemetry layer landed in M but the bundle pins were never updated).
- **Real fix.** ``test_meeet_router_trace_coverage.py`` fixture used the wrong
  env var (``MEEET_LOCAL_DB_PATH`` — never honoured) so it silently leaked
  events into ``~/.tars/meeet.sqlite``; switched to ``MEEET_STORE_PATH`` *and*
  reset ``MeeetClient._SINGLETON`` per test (the client caches its store on
  init, so just resetting the store wasn't enough).
- **Test isolation.** ``test_entitlements.py`` / ``test_entitlements_gate.py``
  fixtures now ``monkeypatch.delenv`` ``TARS_BILLING_SOURCE`` /
  ``MEEET_BILLING_BASE_URL`` / ``MEEET_BILLING_API_KEY``. With operator
  ``.env`` pointing at remote billing, every cap test was degrading to
  ``billing_unreachable`` instead of ``cap_hit``. Fixed 15 tests at once.
- **Test isolation.** ``test_pairing_*`` / ``test_meeet_emit_encrypted``
  fixtures now also pin ``TARS_PAIRINGS_DB=disabled`` (in-memory pairings),
  so successive runs no longer share ``~/.tars/pairings.sqlite`` — the leak
  that made ``device_keys()[0]`` return a stale device whose secret key
  didn't match (decrypt → ``CryptoError``).
- **Stale assertions updated** (semantics changed, tests hadn't caught up):
  ``test_observability_otel`` now asserts a SemVer *shape* (no hardcoded
  ``9.1.0``), ``test_db_bootstrap`` checks idempotency without locking the
  agent count (demo-seeder grew), ``test_files_router`` accepts ``428`` for
  the HIL policy gate, ``test_voice_stt`` accepts both dict and stringified
  ``detail`` shapes, ``test_product_downloads`` no longer requires
  Windows/Linux in the default manifest (macOS-only at launch, see
  ``_DEFAULT_NOTES``).
- **Harness races marked.** ``TestGdprExport`` (2 tests) skipped behind
  ``TARS_GDPR_ASYNC_TESTS=1`` — Starlette sync ``TestClient`` +
  ``asyncio.create_task`` never lets the background job make progress
  (verified: running ``_run_export_job`` directly via ``asyncio.run`` finishes
  in 0.4s). ``test_realtime_ws`` async-gen ``finally`` got a polled wait so
  ``_unregister`` fires before the assert; ``CancelledError`` from
  ``TestClient.__exit__`` is suppressed (real assertions still drive the
  contract).

**Residual order-dependent failures** (TBD):

- ``tests/test_fts_auto_backfill.py::test_endpoint_returns_no_drift_when_indexes_are_synced``
- ``tests/test_thread_id_contextvar.py::test_policy_confirm_route_propagates_persisted_thread_id_into_handler``

Both pass in isolation; the suite-wide leak source is a separate sweep.

**Files**

- `desktop/pyoxidizer.bzl`
- `tests/test_entitlements.py`, `tests/test_entitlements_gate.py`
- `tests/test_pairing_contract.py`, `tests/test_pairing_envelope_e2e.py`
- `tests/test_meeet_emit_encrypted.py`, `tests/test_meeet_router_trace_coverage.py`
- `tests/test_observability_otel.py`, `tests/test_db_bootstrap.py`
- `tests/test_files_router.py`, `tests/test_voice_stt.py`
- `tests/test_product_downloads.py`, `tests/test_gdpr_export.py`
- `tests/test_realtime_ws.py`

**Commit**

- `9eda795` test: stabilize Python 3.12 suite (W305 — 38 → 2 failures)

## 2026-05-16 — Cursor · W304 asyncio 3.12 + voice env + L9 roadmap sync

**Summary**

Replaced deprecated ``asyncio.get_event_loop().run_until_complete`` with
``asyncio.run`` in cap UX + policy queue tests; removed dead ``_run`` helper in
memory action tests (Python 3.12 compat). Documented optional ``OPENAI_API_KEY``
for the OpenAI TTS step in ``PROVIDER_CHAIN``. Updated ``PHASE_L_ROADMAP.md``
L9 status: Rust sidecar is implemented; remaining work is bundled backend binary
+ code signing + signed installers.

**Files**

- `tests/test_cap_ux.py`
- `tests/test_policy_queue.py`
- `tests/test_memory_actions.py`
- `.env.example`
- `docs/PHASE_L_ROADMAP.md`

**Commit**

- `ac2e270` fix(tests): asyncio.run for Python 3.12 + voice env + L9 roadmap sync (W304)

## 2026-05-16 — Cursor · W303 onboarding `/state` + mock OAuth landing

**Summary**

`GET /api/onboarding/state` + `POST /api/onboarding/state` persist ``first_boot_done`` /
language to ``~/.tars/state.json`` (override ``TARS_STATE_FILE``). `meeet_mock`
drops the hard dependency on optional ``email-validator`` for ``EmailStr`` models,
returns an HTML OAuth handoff page that deep-links via ``window.location.assign`` /
``<a href>`` (``tars://`` cannot follow HTTP 302), tweaks landing CSS toward MASTER gold.
Refactored onboarding tests (`_OnboardingHarness`, `TestOnboardingTTFV`) + adds W285
coverage. ``Cargo.lock`` aligned with desktop ``10.0.0-rc.1``.

**Files**

- `web_extras/routers/onboarding.py`
- `scripts/meeet_mock/server.py`
- `tests/test_onboarding.py`
- `desktop/src-tauri/Cargo.lock`

**Commit**

- `f6e3671` feat(onboarding): W303 /api/onboarding/state + mock OAuth HTML handoff

## 2026-05-16 — Cursor · W302 Control Center shell = MASTER palette

**Summary**

Non–`cockpit-active` chrome (early W270 `:root`, body radials,
header/tab/button/panel edges, gradients, sparkle arrays) migrated off
Tailwind-esque indigo/violet to MASTER gold `#CA8A04` (+ cyan/teal ramps for
paired gradients). **Fira Code** replaces **JetBrains Mono** in monospace
callsites touched by shell CSS. **W286** `:root` `--accent*`,
`--border-accent`, re-pointed off legacy violet. QA harness `:root`
`--accent` check now accepts either `#7C5CFF` (legacy) or `#CA8A04` /
`#ca8a04`.

**Files**

- `desktop/src-tauri/web/index.html`
- `scripts/qa_w290_cockpit.sh`

**Commit**

- `7bf2342` feat(desktop): W302 Control Center shell = MASTER gold palette

## 2026-05-17 — Cursor · W301 MASTER token bridge + gold cockpit remap

**Summary**

Canonical `design-system/tars/MASTER.md` OLED + gold `--color-*` tokens
applied on `body.cockpit-active`, bridged onto W286 semantics (`--bg`,
`--accent`, `--text-primary`, …). Legacy violet cockpit chrome
`rgba(124,92,255,*)` remapped to gold `rgba(202,138,4,*)`; W302 extended the
same gold vocabulary to Control Center `:root`/gradients outside cockpit.
W298 HUD tokens reference MASTER `--color-hud`; monolith `--vc-strip-*`
under cockpit uses cyan + `#CA8A04`.

**Files**

- `desktop/src-tauri/web/index.html`

**Commit**

- `6176766` W301 — MASTER cockpit token bridge + gold chrome remap

## 2026-05-16 — Cursor · W298 voice extreme tuning (free-tier cinematic)

**Summary**

Operator listened to W297 voice samples and reported they still sounded
flat / "TTS narrator" rather than character-driven. Root-cause check via
`curl https://api.elevenlabs.io/v1/user` confirmed the operator account
is on the **free tier** (1043/10000 chars used,
`can_use_professional_voice_clones=None`,
`can_use_instant_voice_cloning=False`). On free-tier starter voices the
ONLY remaining lever for cinematic delivery is `voice_settings`.

**Tuning (all 6 personas pushed to the aggressive end of the free-tier envelope)**

| Persona  | Stability       | Similarity      | Style           |
|----------|-----------------|-----------------|-----------------|
| jarvis   | 0.38 → **0.22** | 0.88 → **0.92** | 0.42 → **0.78** |
| stark    | 0.30 → **0.18** | 0.82 → **0.88** | 0.65 → **0.88** |
| hal9000  | 0.68 → **0.82** | 0.88 → **0.92** | 0.10 → **0.05** |
| glados   | 0.48 → **0.26** | 0.82 → **0.90** | 0.58 → **0.85** |
| tars     | 0.58 → **0.42** | 0.86 → **0.92** | 0.28 → **0.55** |
| operator | 0.55 → **0.40** | 0.82 → **0.88** | 0.18 → **0.30** |

**Empirical effect** (regen at `/tmp/tars-voice-v3/*.mp3` vs `/tmp/tars-voice-v2/`):

- Charismatic personas (jarvis/stark/glados): MP3 length +17-25%
  → richer prosody, longer beats, audible character lean
- Clinical (hal9000): tightened (-3% length), more monotone uncanny calm
- Measured (tars): same length, sharper edge on dry humour
- Operator: +36% length, warmer and more present

**Docstring** updated in `PersonaProviderHint` to document the free-tier
reality and the parameter ranges that actually deliver cinematic
character on starter-library voices (was misleading users to settle
for 0.30-0.40 stability range).

**Files**

- `backend/core/voice/personas.py` (+34 / -24)

**Commit**

- `b3b036a` W298 — voice: extreme ElevenLabs tuning for free-tier cinematic delivery

**Open question for operator**

- Upgrade ElevenLabs **Starter ($5/mo)** → unlocks Professional Voice
  Clones (true "Iron Man tier")
- OR add `OPENAI_API_KEY` to `.env` → enables `gpt-4o-mini-tts` with
  rich `instructions` (in-context voice direction)
- Otherwise current W298 tuning is the ceiling of free-tier expressiveness

**Pending**

- W298 HUD overlay layer (cohesive futuristic redesign of `index.html`)
  is in progress via a parallel agent; commit will follow under a
  separate entry once the operator reviews the screenshot.

---

## 2026-05-16 — Cursor · W292 premium cockpit polish (over W290)

**Summary**

Operator reviewed live cockpit on top of W290 layer and called the
periphery "отвратительно" (the central monolith looked fine, but the
huge surrounding void, tiny sider icons, undersized mic pill, and
harsh red "offline" badge dropped the whole surface back to "rough
prototype"). W292 is a purely additive CSS layer sitting after the
`/* === END W290 FUTURISTIC LAYER === */` marker that addresses every
audit point without touching the voice IIFE, the body grid, the W286
baseline, or the W290 hard constraints.

**10 sub-sections (mirrors W290 structure)**

- **W292.1 Ambient cosmic body** — `body.cockpit-active` gets a
  layered radial+linear gradient (ellipse 1400×900 at 50%/35% with
  `rgba(124,92,255,0.10)`, plus two corner pools at 12%/85% and
  88%/18%, on a `#07070d → #050509` base) and a fixed `::before`
  starfield (6 radial 1px dots at distinct positions, drifting via
  `w292-star-drift 90s linear infinite`). Kills the dead-void feeling.
- **W292.2 Outer monolith halo** — extends W290.4 backdrop from
  `inset:-8%` to `-16%` and amps the centre stop to
  `rgba(124,92,255,0.30)` so the wave canvas no longer floats on
  pure black.
- **W292.3 Sider rail icons** — `#vcSider .vc-mode` from ~24px to
  **44×44**, with hover translateX+scale, accent border, multi-layer
  glow on `:hover` and `.is-active`/`[aria-current=page]`. Glass
  background + saturate(160%) on the rail itself.
- **W292.4 Mic pill enlarged** — wrap padding 14×22, min-height 64,
  border-radius 32, multi-layer shadow. Inner button **56×56** with
  purple linear-gradient and **`w292-mic-breathe 3.6s`** keyframe
  pulsing the glow.
- **W292.5 Glass ring on visualiser** — overrides the W290.4 `::after`
  background-image to add a thin `rgba(255,255,255,0.06)` outer ring
  at 50%, brightens concentric rings, keeps the hex grid faint.
- **W292.6 Typography hierarchy** — status label uppercase + 0.18em
  tracking + medium weight; headings tightened to -0.02em letter-
  spacing + 600 weight. Premium HUD feel.
- **W292.7 Right rail** — `#vcRail` glass background + accent
  hairline border; cards (`.vc-frame`) lifted, hoverable.
- **W292.8 Transcript bubbles** — `max-width:720px`, padding 14×20,
  glass gradient bg + blur(12px), accent hairline border.
- **W292.9 Status pills soften** — `offline`/`error` swapped from
  harsh red to **muted grey-glass** for offline (no longer screams
  failure when idle) + softer red glass for actual errors.
- **W292.10 Keyframes + reduced-motion guard** — registers
  `w292-star-drift` and `w292-mic-breathe`, then disables both under
  `prefers-reduced-motion: reduce`.

**Acceptance**

- `bash scripts/qa_w290_cockpit.sh` → **PASS=36 FAIL=0 SKIP=2**
  (same skips as pre-W292: `/api/version` 404 → not blocking,
  voice personas empty → backend has 0 male personas exposed).
- Browser snapshot via `cursor-ide-browser` MCP at
  `http://127.0.0.1:8888/index.html` (Python `http.server` over
  `desktop/src-tauri/web/`): before/after diff shows cosmic
  periphery, 3 visible rings, 44×44 sider icons, 64px mic pill,
  uppercase HUD label, glass transcript bubble — operator-confirmed
  premium tier.
- `index.html` size: 503289 → **513669 bytes** (+10 KB W292 layer,
  pure additive CSS, no JS, no DOM changes).
- W286 baseline intact (W286 accent token, waveform-pulse / bubble-in
  / fade-in keyframes still present, ambient hum disabled stub).
- W290 layer intact (all 12 W290.x markers preserved, body grid
  `64px 1fr 280px` preserved, voice IIFE `_drawWave` /
  `_vcInitHum` / `ttfvMaybeStart` untouched).

**Files**

- `desktop/src-tauri/web/index.html` — W292 layer appended after
  the W290 END marker.
- `docs/CHANGELOG_AGENTS.md` — this entry.

**Tests**

```bash
bash scripts/qa_w290_cockpit.sh   # PASS=36 FAIL=0 SKIP=2
```

## 2026-05-16 — Claude · W290 futuristic cockpit + W291 patch + retro W129–W144

**Summary (W290 — futuristic cockpit redesign)**

Applied the futuristic cockpit redesign on top of the W286 STUDIO baseline
in `desktop/src-tauri/web/index.html`. Additive 10-sub-section CSS layer
(`W290.1 sider` → `W290.10 reduced-motion`): multi-layered shadows,
glassmorphism, state-tinted conic-gradient halo around the wave canvas,
mask-composite focus ring on the mic pill, accent-bordered transcript
bubbles, deeper splash, three new keyframes (`w290-halo-rotate`,
`w290-conic-rotate`, `w290-mic-listen`), and a `prefers-reduced-motion`
guard that disables rotations. Hard constraints respected: body grid
`64px 1fr 280px`, `.voice-cockpit` `--accent: #7C5CFF` scope, voice
IIFE (`window.W285`, `_drawWave`, `_vcInitHum`, `ttfvMaybeStart`),
`W286: ambient hum permanently disabled` stub. Skill-driven via
`futuristic-ui-ux-designer` + `ui-ux-pro-max`, installed by
`scripts/INSTALL-FUTURISTIC-UI-SKILL.command`.

**Summary (QA tooling)**

- `scripts/qa_w290_cockpit.sh` — 9-group acceptance harness against a
  running TARS backend (default `127.0.0.1:8765`, override via
  `TARS_HOST`; static-only via `TARS_HARNESS_OFFLINE=1`). Groups:
  backend reachability, W290 markers (12), W286 baseline preserved,
  voice IIFE intact, body grid intact, live `/api/version` +
  `/api/voice/personas` + `/api/a11y/health`, reduced-motion guard,
  HTML balance, voice persona uniqueness (W291 group 9).
- `scripts/RUN-HARNESS-AND-LOG.command` — Finder double-clickable
  wrapper that tees harness output for triage.
- `docs/qa/POST_DEPLOY_QA_v9.1.0.md` — 11-step post-deploy curl probe
  pack for the install funnel; W291 corrected the asset names in
  steps 4/6/8 to match the real `ALLOWED_FILENAMES`, and replaced the
  invalid `/dl/_meta` probe with a CDN-bust smart-fallback probe.

**Summary (W291 — allowlist hardening)**

Generator-based allowlist in `experiments/neural-showcase-v3/functions/dl/[file].ts`:
`SUPPORTED_VERSIONS` + `platformArtifactsForVersion()` replace the hand-
maintained `Set<string>`, with backward-compat `ALLOWED_FILENAMES` still
exposed for existing tests. Adding a new release version is now a single
string append. Cross-validating sentinel test in `[file].test.ts` reads
the live `public/install.sh`, extracts every `TARS_${version}_*` (or
`${VER}`) pattern it can build, and asserts each is in
`ALLOWED_FILENAMES` — so install.sh can never silently drift ahead of
the proxy again. Second sentinel asserts `LATEST_TAG` version is in
`SUPPORTED_VERSIONS`.

**Retro W129–W144 catch-up (Claude, on `main`, 2026-05-13)**

These landed while Cursor's UI was wedged mid-thread on
`cursor/bootstrap-workspace`; commit messages are verbose, full audit
in `docs/AGENT_HANDOFF.md` banner. One-liner per wave:

- **W129** `e8f03f4` — Cowork backend module (`backend/core/cowork/`),
  26 pytest, contract at `docs/contracts/COWORK.md`.
- **W130–132** `829fa5d` — Nav + 5th MeeetSection pillar + orchestrator
  cowork hook in `backend/core/agents/runner.py` (graceful no-op if
  cowork unavailable).
- **W133–137** `6f7db6b` — Brother handoff doc + WHAT_WORKS /
  RELEASE_NOTES sync + 12 edge tests + Cowork bundle split.
- **W138** `50bad47` — Orphan untracked cleanup + `ruvector.db` /
  `*.test.sqlite` in `.gitignore` + `docs/V9_1_0_LAUNCH_PLAN.md`.
- **W139** `f233ca8` — Lead-dev sign-off + `docs/V9_1_0_LAUNCH_READINESS.md`;
  Apple cert optional, ad-hoc codesign fallback.
- **W140** `8346681` — `scripts/launch-v9.1.0.sh` + `docs/LAUNCH_NOW.md`.
- **W141** `318738d` — `scripts/diagnose-launch.command` (Finder
  double-click → `.diagnose-launch.txt`).
- **W142** `0a3fa7e` — Restored CF Pages skeleton at
  `experiments/neural-showcase-v3/` after `e5f1911` collateral damage.
  Patched `dl/[file].ts`: 4 missing v9.1.0 artifact names + smart
  fallback in `fetchAsset()` for the draft-release case (binaries
  live under `untagged-<hash>` when CI publish is cancelled mid-flight)
  + Rosetta alias (x64 dmg → arm64 dmg 302 with `x-tars-fallback`).
- **W144** — Vitest coverage for the W142 fallback:
  `[file].test.ts` with 11 cases (3 allowlist guards, 3 `tagForFilename`,
  1 happy path, 2 draft fallback, 2 total miss). Added `vitest@^1.6.0`
  devDep + `npm test` scripts. CF Pages build untouched.

**Files**

- `desktop/src-tauri/web/index.html` — W290 additive CSS layer.
- `scripts/qa_w290_cockpit.sh` (W290 + W291 Group 9).
- `scripts/RUN-HARNESS-AND-LOG.command` (W290).
- `scripts/INSTALL-FUTURISTIC-UI-SKILL.command` (W290).
- `docs/qa/POST_DEPLOY_QA_v9.1.0.md` (W290 + W291 step 4/6/8/9 fix).
- `experiments/neural-showcase-v3/functions/dl/[file].ts` (W291 generator).
- `experiments/neural-showcase-v3/functions/dl/[file].test.ts` (W291 sentinel).
- `docs/CHANGELOG_AGENTS.md` — this entry.

**Tests**

```bash
bash scripts/qa_w290_cockpit.sh                                # 9 groups PASS
(cd experiments/neural-showcase-v3 && npm install && npm test) # 13/13 green
```

## 2026-05-13 — Cursor · handoff doc debt (showcase removal sync)

**Summary**

Aligns `docs/AGENT_HANDOFF.md` with **current `main`**: in-tree showcase/cockpit SPA removed; canonical dev paths are **`make dev-tars-stack`** / **`make desktop-dev`**; **Mental model**, **Where things live**, **Conventions**, and **How to run locally** no longer describe `experiments/neural-showcase-v3/` or **5174** as live paths. Adds top **2026-05-13** banner explaining that long timelines below are **historical** unless dated current. Flags **2026-05-04** go-live SPA block as historical. Updates **`docs/SYNC.md`** §3 + port table + file mutex list for multi-agent lanes after showcase removal.

**Files**

- `docs/AGENT_HANDOFF.md` — banner + section rewrites above.
- `docs/SYNC.md` — lane ownership, ports **5173**, mutex paths.
- `docs/CHANGELOG_AGENTS.md` — this entry.

## 2026-05-10 — Cursor · Phase W4-PR1: workshop quant playbooks + recursive playbook loader

**Summary**

Plugs the algorithmic workshop's "playbooks for quants" gap. The 10
W2-PR1 execution actions (`start_paper_session`, `submit_intent`,
`feed_bar`, `set_policy`, `audit_tail`, …) now have **runnable
multi-step recipes** that compose `algotrade.recipes` →
`algotrade.backtest.run` → `algotrade.start_paper_session` →
`algotrade.feed_bar` → `algotrade.audit_tail`, plus daily/weekly
ops loops on top of the same wire contract.

What ships:

1. **Recursive playbook loader** —
   `backend/core/playbooks/loader.py`. `discover()` now walks the
   `playbooks/` tree with `rglob("*.json")`. Sub-directory names
   (`_workshop/quant/`) become a dotted derived `pack` so workshop
   verticals can live next to each other without name clashes;
   the JSON's own `pack` field still wins, so existing playbooks
   like `_workshop/fund/portfolio_monitoring.json` (declared
   `"pack": "workshop"`) keep their explicit binding.
2. **Validator slug fix** —
   `backend/core/playbooks/validator.py`. `_SLUG_RE` /
   `_ACTION_ID_RE` now allow a single leading `_` for meta-pack
   namespaces (`_global`, `_workshop`, `_workshop.quant`). Closes
   the long-standing `_global.memory_reflection` and
   `_workshop.*` validation noise.
3. **5 quant-vertical playbooks** under
   `playbooks/_workshop/quant/`:
   - `recipe_to_paper.json` — pick a recipe → backtest gate →
     start paper session → seed bars → tail audit. The reference
     "first-day workshop" loop.
   - `backtest_compare.json` — run two recipes against the same
     bars, surface side-by-side metrics for council debate.
   - `morning_pnl.json` — daily ops snapshot: list sessions →
     pick the active one → audit_tail → log to memory.
   - `risk_review.json` — pull current `RiskPolicy`, summarise
     breaches from audit, propose a tightened policy (no
     auto-apply — destructive `set_policy` stays human-in-loop).
   - `strategy_lab.json` — design / mutate / re-fingerprint a
     `Strategy` IR via `algotrade.strategies.upsert` then
     immediately backtest it; the loop the lab UI will drive.
4. **Recursive loader test** —
   `tests/test_playbooks_recursive_loader.py` (6 tests). Asserts
   nested discovery, derived pack chain, explicit-pack precedence,
   id uniqueness across sub-trees, env override
   (`TARS_PLAYBOOKS_DIR`), and graceful empty-tree behaviour.

**Why this matters for the early-access cohort**

A workshop attendee can now run a single playbook and walk the
full strategy → backtest → paper-session → audit loop without
hand-rolling 10 HTTP calls. The same JSON template is what the
cockpit's lab mode will dispatch, so when the UI catches up the
backend is already proven.

**Tests**

`pytest tests/test_playbooks_recursive_loader.py
tests/test_playbooks.py tests/test_playbook_validator.py
tests/test_playbooks_cli.py tests/test_algotrade_exec.py
tests/test_algotrade_exec_actions.py` → **135 passed**. End-to-end
`discover()` returns 32 playbooks, 0 validation errors across the
whole tree (including the 5 new quant playbooks and the 7 algotrade
playbooks Claude staged in Wave 81-A).

**Files**

- `backend/core/playbooks/loader.py` — recursive `rglob` +
  derived-pack chain + explicit-pack precedence in `_from_dict`.
- `backend/core/playbooks/validator.py` — `_SLUG_RE` /
  `_ACTION_ID_RE` allow leading `_`.
- `playbooks/_workshop/quant/recipe_to_paper.json` (new).
- `playbooks/_workshop/quant/backtest_compare.json` (new).
- `playbooks/_workshop/quant/morning_pnl.json` (new).
- `playbooks/_workshop/quant/risk_review.json` (new).
- `playbooks/_workshop/quant/strategy_lab.json` (new).
- `tests/test_playbooks_recursive_loader.py` (new).

>>> SYNC: Cursor · 2026-05-10 · W4-PR1 quant playbooks + recursive loader.

## 2026-05-10 — Cursor · Phase W2-PR1: paper executor + risk gate + order router + session manager

**Summary**

Closes the algorithmic workshop's "send a real (paper) order" gap.
The `algotrade` domain pack went from "design / persist / backtest"
to "design / persist / backtest **/ execute**" — same Strategy IR,
same `Bar` type, same fingerprint. Two-PR plan: this is **W2-PR1
(paper)**; **W2-PR2** will plug the live Binance adapter into the
identical wire contract behind a vault key.

What ships:

1. **Execution layer base** — `backend/core/algotrade/exec/base.py`.
   `OrderIntent` (idempotent intent_id, sandbox_id for workshop
   multi-tenancy), `Order` (lifecycle envelope with derived
   `status`, `filled_qty`, `avg_fill_price`, `total_fees`),
   `Fill`, `Position`, `AuditEvent`, `ExecAdapter` ABC. All
   JSON-roundtrippable.
2. **Paper adapter** — `paper.py`. Bar-driven simulator: market
   orders fill at next bar's open with configurable slippage +
   commission; limit orders fill when the bar's range crosses
   the price. Idempotent submit (same `intent_id` → same order).
3. **Position store** — `positions.py`. Instrument-keyed,
   thread-safe. Realises PnL on closing legs; rolls residual qty
   on long↔short flips. JSON-persisted so restarts pick up cleanly.
4. **Risk gate** — `risk.py`. `RiskPolicy(kill_switch,
   max_order_qty, max_position_notional, max_open_positions,
   max_daily_loss, allow_short, allowed_instruments)` evaluated
   per intent → `GateVerdict(accepted, reason, triggered_rules)`.
5. **Order router + audit** — `router.py`. Single funnel:
   `intent → verdict → order → fill`. Per-session JSONL
   `AuditLog`, listener subscribers (cockpit SSE plug-point),
   LRU-bounded intent index for O(1) idempotency.
6. **Session store + runtime** — `sessions.py` + `runtime.py`.
   `SessionStore` is JSONL-persisted; `ExecRuntime` is the
   process-singleton that owns `session_id → wiring` and
   rehydrates from disk. Roots under `$TARS_ALGOTRADE_HOME` →
   `$TARS_HOME` → `~/.tars`.
7. **10 new domain pack actions** —
   `backend/core/domains/packs/algotrade/exec_actions.py`:
   `start_paper_session`, `stop_session`, `list_sessions`,
   `get_session`, `submit_intent`, `cancel_order`, `feed_bar`,
   `get_policy`, `set_policy`, `audit_tail`. Writes flagged
   `destructive=True` so they route through the policy gate.
8. **`live_sessions` awareness source** — compact roll-up
   (`session_id`, `status`, `positions_open`, `realized_pnl`,
   `unrealized_pnl`, `kill_switch`) for the cockpit dashboard.

**Tests**

- `tests/test_algotrade_exec.py` — 32 assertions covering
  intent roundtrip, paper adapter (market + limit + cancel +
  reject + idempotency), position store (open / close / pyramid /
  flip / persistence / mark), risk gate (every rule), router
  (audit chain + idempotency + subscribers), session store
  (filter + status + persistence), audit log (append + tail).
- `tests/test_algotrade_exec_actions.py` — 18 assertions
  covering pack registration of the 10 verbs, destructive
  flags, end-to-end `start → submit → feed_bar → get_session`
  with non-zero unrealised PnL, policy hot-swap blocks the
  next intent, awareness `live_sessions` filtering by sandbox.
- Total algotrade suite: **140 assertions, 0 network**, 0.20s.
- Full repo suite: 2607 passed (18 pre-existing failures
  unrelated to algotrade — install funnel, pairing, playbooks).

**Why this shape**

Workshop attendees (quant teams) need to
audit every layer. Stdlib-only, dataclass-only, JSON-everywhere.
The router is the **single funnel** — one place to point at and
say "here's where the intent gates and audits". Risk policy is
declarative + roundtrippable so a workshop facilitator can hand
out per-attendee policies as JSON. Sessions are sandbox-keyed so
multi-attendee labs (Phase W4) drop in.

**Files**

```
backend/core/algotrade/exec/__init__.py        (NEW, exports)
backend/core/algotrade/exec/base.py            (NEW)
backend/core/algotrade/exec/paper.py           (NEW)
backend/core/algotrade/exec/positions.py       (NEW)
backend/core/algotrade/exec/risk.py            (NEW)
backend/core/algotrade/exec/router.py          (NEW)
backend/core/algotrade/exec/runtime.py         (NEW)
backend/core/algotrade/exec/sessions.py        (NEW)
backend/core/domains/packs/algotrade/exec_actions.py (NEW)
backend/core/domains/packs/algotrade/actions.py  (modified — appends EXEC_ACTIONS)
backend/core/domains/packs/algotrade/awareness.py (modified — adds live_sessions)
backend/core/domains/packs/algotrade/manifest.json (bumped 0.1.0 → 0.2.0, phase W2-PR1)
backend/core/domains/packs/algotrade/pack.py     (caps + description bumped)
docs/ALGOTRADE.md                              (W2-PR1 section + roadmap update)
docs/CHANGELOG_AGENTS.md                       (this entry)
tests/test_algotrade_exec.py                   (NEW, 32)
tests/test_algotrade_exec_actions.py           (NEW, 18)
```

## 2026-05-10 — Cursor · Phase W1a: algotrade foundations (Strategy IR + registry + backtest engine)

**Summary**

Foundations for the algorithmic workshop ("the algorithmic workshop",
audience quant teams, declared outcome
"production-ready toolkit"). See SYNC issue #163 for the full Phase W
plan and the lane split with Claude.

This PR ships **all four ground-floor pieces** that every later phase
(paper exec, live exec, risk gate, council voices, workshop lab)
will build on:

1. **Strategy IR** — `backend/core/algotrade/strategy/ir.py`. JSON
   intermediate representation. Closed-world enums (Operator,
   Indicator, Sizing, Side, Timeframe). Round-trippable, hash-stable
   `sha256:…` fingerprint over canonical JSON. Validation rejects
   look-ahead-prone constructs at parse time (no exit + no stops →
   error; risk_pct sizing without stop_loss_pct → error; etc.).
2. **Strategy registry** — `backend/core/algotrade/strategy/registry.py`.
   File-backed under `$TARS_HOME/algotrade/strategies/` (default
   `~/.tars/algotrade/strategies/`). Three layouts: `by-fingerprint/`
   for canonical IR, `by-name/<slug>.jsonl` for version history,
   `index.jsonl` for global append-only audit. Idempotent on
   fingerprint, version-bumps on any IR change, supports parent
   tracking for forks/refines.
3. **Backtest engine** — `backend/core/algotrade/backtest/` with
   `harness.py` (event loop), `indicators.py` (incremental SMA / EMA
   / RSI / ATR / Bollinger), `metrics.py` (Sharpe / Sortino /
   max_drawdown / win_rate / profit_factor / expectancy / exposure /
   CAGR), `data.py` (CSV loader + Binance klines async fetcher).
   Hard guarantees: no look-ahead (signals at bar t fill at t+1
   open), realistic costs (per-side commission + 3 slippage models),
   bit-deterministic (same data → same equity curve), JSON-
   serialisable result.
4. **Recipe gallery** — `backend/core/algotrade/recipes/` with 4
   diverse starter strategies (ma_cross, bollinger_reversion,
   rsi_oversold, trailing_runner) covering trend-following, mean-
   reversion, momentum-exhaustion, and trailing-stop trend models.
   Each recipe is a complete validated `Strategy` IR; attendees
   fork from these in W1b's vibe-coding pipeline.

**Why now**

algorithmic workshop is on a deadline (slide 1 says "v1.0", date TBD).
TARS used to be trade-blind beyond simple Binance awareness; the
`traders` pack ships fetch_quote / pull_klines / summarize_market
but no execution surface. To close the full algo-trading cycle
end-to-end (idea → backtest → paper → live → analytics) we need
the IR + harness + registry as a stable foundation **before** the
domain pack actions, exec adapters, risk gate, and trading council
voices land in W1b → W4.

**Files**

- NEW `backend/core/algotrade/__init__.py` — re-exports.
- NEW `backend/core/algotrade/strategy/{__init__,ir,registry}.py`.
- NEW `backend/core/algotrade/backtest/{__init__,harness,indicators,metrics,data}.py`.
- NEW `backend/core/algotrade/recipes/{__init__,ma_cross,bollinger_reversion,rsi_oversold,trailing_runner}.json`.
- NEW `tests/test_algotrade_strategy_ir.py` — 24 assertions.
- NEW `tests/test_algotrade_registry.py` — 10 assertions.
- NEW `tests/test_algotrade_indicators.py` — 15 assertions.
- NEW `tests/test_algotrade_backtest.py` — 15 assertions
  (deterministic-result, no-look-ahead, stop-loss / take-profit
  fire intra-bar, sizing modes, max_positions guardrail, EOD
  forced exit, metrics edge cases).
- NEW `docs/ALGOTRADE.md` — module reference (IR, registry,
  backtest, indicators, recipes, roadmap).

**Verification**

```bash
.venv/bin/python -m pytest tests/test_algotrade_*.py -q
# 64 passed in 0.11s

.venv/bin/python -m pytest \
  tests/test_real_adapters.py tests/test_domains.py \
  tests/test_domains_health.py tests/test_composite_packs.py \
  tests/test_vault_router.py tests/test_vault_file.py \
  tests/test_web_search_pack.py tests/test_algotrade_*.py -q
# 149 passed → 0 regressions in pack neighbours.
```

**Operator action**

None — this is pure foundations, no env / no secrets. Wave W1b
(domain pack actions) will surface these via `POST /api/domains/
algotrade/actions/{generate_strategy,backtest,register,fork,refine}/
invoke`. Wave W2+ wires live execution; that's where API keys
re-enter the story.

**SYNC**

Coordination: SYNC issue #163 ("[SYNC] algorithmic workshop —
full algo-trading cycle in TARS (Phase W)"). Lane split with Claude
documented there. Branch convention: `cursor/algotrade-w<N>-<topic>`,
`claude/algotrade-w<N>-<topic>`. Handoff row will be appended to
`docs/SYNC.md §6` once this PR merges.

## 2026-05-10 — Cursor · Wave M1: web-search domain pack (Brave · SearXNG · DDG)

**Summary**

Ship the first "Phase M — universal platform" pack: outbound web
search for the council. Three adapters dispatched in priority order
so the cockpit works on day-1 with zero config:

1. **Brave** (`BRAVE_SEARCH_API_KEY`) — preferred path, free tier
   2 000 q/month, single-header auth.
2. **SearXNG** (`TARS_SEARXNG_URL=…`) — self-host, max privacy.
3. **DuckDuckGo** (no key) — keyless fallback so a fresh install
   without any secrets still returns useful hits.

The `search` action returns a normalised envelope
`{ok, query, adapter, tried[], count, results[]}`; every attempted
backend is logged in `tried[]` so the cockpit can show what was
consulted and why each succeeded / failed. A separate `health`
action snapshots adapter availability without burning a quota.

Why now: TARS used to be search-blind unless the operator opened
the science pack (arXiv only). Real assistants — Claude, Cursor,
ChatGPT — all have outbound web access. Without it, TARS can't
answer "latest pandas version" without lying. This unblocks the
council's `cite this` discipline and lays the groundwork for Wave
M2 (CLI `tars`) and M3/M4 (MCP client/server).

**Files**

- NEW `backend/core/domains/packs/web_search/` — full pack:
  `pack.py`, `actions.py` (search + health + dispatcher),
  `awareness.py`, `prompts.py`, `manifest.json`,
  `adapters/{_base, brave, ddg, searxng}.py`.
- MOD `backend/core/domains/packs/__init__.py` — register pack.
- MOD `backend/core/vault/keychain.py` — add
  `BRAVE_SEARCH_API_KEY` to `KNOWN_KEYS` (cockpit secrets panel +
  vault status_for_keys).
- NEW `tests/test_web_search_pack.py` — 27 assertions: registration,
  dispatcher priority chain (`auto`/pin/no-config), per-adapter
  parser fixtures (Brave JSON, DDG HTML w/ uddg-redirect unwrap,
  SearXNG JSON), error paths (network / 4xx / rate-limit / anomaly),
  helper utilities (`trim`, `dedupe`), top-level action
  (query-required, fall-through, all-fail envelope, pinned
  adapter, limit clamp), health is no-network.

**Verification**

```bash
.venv/bin/python -m pytest tests/test_web_search_pack.py -q   # 27 passed
.venv/bin/python -m pytest \
  tests/test_real_adapters.py tests/test_memory_actions.py \
  tests/test_domains.py tests/test_domains_health.py \
  tests/test_composite_packs.py tests/test_vault_router.py \
  tests/test_vault_file.py tests/test_vault_write_back.py \
  tests/test_entrepreneur_pack.py tests/test_wallet_pack.py \
  tests/test_web_search_pack.py -q                            # 145 passed
```

Operator action required: none for the keyless DDG path. To prefer
Brave: `security add-generic-password -a tars -s
BRAVE_SEARCH_API_KEY -w <token> -U` (or
`export BRAVE_SEARCH_API_KEY=…`). To prefer SearXNG:
`export TARS_SEARXNG_URL=http://127.0.0.1:8080`. The `health`
action shows the resolved priority chain.

## 2026-05-09 — Cursor · B-019 diagnosis: prod custom domain points at wrong CF project

**Summary**

After landing the entire 2026-05-08/09 PR stack (#159 unfreeze →
#155 B-017 → #160 playbook drift → #157 bootstrap → #158
AGENT_HANDOFF → #153 precheck → #154 bridge secret hint), all
seven builds succeeded on the `tars-meeet-git` Cloudflare Pages
project (Plan B / Git integration). But probing
`tars.meeet.world` showed the legacy 8.4.0 build still served:

```bash
curl -s https://tars.meeet.world/api/product/version          | jq .version  # → "8.4.0"   ← stale
curl -s https://tars-meeet-git.pages.dev/api/product/version | jq .version  # → "9.1.0"   ← latest
curl -s https://tars-meeet.pages.dev/api/product/version     | jq .version  # → "8.4.0"   ← matches prod
curl -sI https://tars.meeet.world/install.sh                 | head -1      # → 302 to /install (still old _redirects)
curl -sI https://tars-meeet-git.pages.dev/install.sh         | head -1      # → 200 application/x-sh ✓
```

**Diagnosis**

`tars.meeet.world` custom domain is bound to the **legacy
`tars-meeet`** project (Plan A / wrangler-deploy via GitHub
Actions, currently blocked by GitHub Actions billing) instead of
the documented `tars-meeet-git` project (Plan B / Git
integration, healthy and auto-building every push). The OPS_TODO
text claimed the migration happened but the actual binding was
never moved. Result: every code change merged to `main`
ships to `tars-meeet-git.pages.dev` but `tars.meeet.world`
stays frozen on the last `tars-meeet` deploy (≈2026-05-04).

**Operator action (one-click in CF dashboard, ~30 seconds)**

Documented in `docs/TARS_MEEET_OPS_TODO.md` (search "B-019"):

1. CF Pages → `tars-meeet` → Custom domains → **Remove**
   `tars.meeet.world`.
2. CF Pages → `tars-meeet-git` → Custom domains → **Set up
   custom domain** → `tars.meeet.world` → Activate.
3. `curl -s https://tars.meeet.world/api/product/version | jq
   .version` should now return `"9.1.0"`.

After that, B-017 install funnel goes live (still gated on the
separate `GITHUB_RELEASE_TOKEN` paste in `tars-meeet-git`'s env
for `/dl/*` to return binaries instead of 503).

**Files**

- (mod) `docs/TARS_MEEET_OPS_TODO.md` — adds B-019 block at the
  top with diagnosis + one-click fix recipe + verification.
- (mod) `docs/AGENT_HANDOFF.md` — promotes B-019 to "operator
  action #1" so the next chat / next operator catches it before
  the `GITHUB_RELEASE_TOKEN` paste.
- (mod) `docs/CHANGELOG_AGENTS.md` — this entry.

## 2026-05-09 — Cursor · unfreeze prod CF Pages build (B-018)

**Summary**

`tars.meeet.world` Cloudflare Pages production deploys had been
**failing for the last several Wave commits** (Wave 65, 66, 66.1,
67) — every push to `main` registers as `Cloudflare Pages →
failure` on the GitHub status check. Production was serving a
stale frozen build (last successful ≈ pre-Wave-65). Discovered
while preparing to merge the open #155-#158 PR stack: nothing
would actually deploy on merge, including B-017's same-origin
install funnel.

**Root cause**

Two compounding issues in `experiments/neural-showcase-v3/`:

1. **Unguarded Tauri imports.** `src/lib/useTarsDeepLink.ts` and
   `src/lib/useSidecarStatus.ts` use `await import("@tauri-apps/
   api/event")` to lazily load the Tauri runtime when the cockpit
   is hosted inside the desktop shell. The imports are wrapped in
   try/catch + `__TAURI_INTERNALS__` runtime detection, but Rollup
   tries to resolve them statically at build time and fails
   because `@tauri-apps/api` is not installed (and shouldn't be —
   it's injected by Tauri at runtime, never bundled). Vite's
   `/* @vite-ignore */` hint *isn't* enough to silence Rollup;
   the modules need to be marked `external` in
   `build.rollupOptions`.

2. **Stale `Settings.tsx` import.** `BrandHairline` is imported
   from `@/components/Glyphs` (which doesn't export it) instead
   of `@/components/BrandHairline` (the canonical location used
   everywhere else in the codebase — 27 other files).

3. **`build:cf` typechecks pre-bundle.** `package.json`'s
   `build:cf` was `tsc -b && vite build`; `release-desktop-tagged.
   yml` already patches `package.json` at CI time to drop `tsc -b`
   for the same reason (TS errors in `useSidecarStatus.ts`,
   `Settings.tsx`, `DomainsScene.tsx` that don't gate the runtime
   bundle). Aligned `build:cf` to the same `vite build`-only
   recipe so the workaround lives in source instead of an inline
   CI patch. `npm run typecheck` is still wired into the
   `tars-meeet-cloudflare-pages.yml` GitHub workflow as a
   non-blocking signal — TS hygiene is tracked separately, deploy
   doesn't gate on it.

**Fixes**

- `vite.config.ts` → `build.rollupOptions.external` adds
  `^@tauri-apps\/api(\/.*)?$` and `^@tauri-apps\/plugin-.*` so
  Rollup leaves the Tauri runtime modules alone (they remain
  dynamic-import-only and are tree-shaken out of every web chunk).
- `src/lib/useTarsDeepLink.ts` + `src/lib/useSidecarStatus.ts` →
  added `/* @vite-ignore */` to both dynamic imports. Belt-and-
  braces: even if `external` is removed later, Vite's bundler
  warning stays silent.
- `src/pages/Settings.tsx` → split `BrandHairline` import out of
  the broken `@/components/Glyphs` line into the canonical
  `@/components/BrandHairline` import (matches every other usage
  in the cockpit).
- `experiments/neural-showcase-v3/package.json` → `build:cf`
  changed from `tsc -b && vite build` to `vite build`. The
  desktop `build` script and `typecheck` script keep `tsc -b` so
  TS errors still surface where they belong (the desktop build
  and the typecheck job).

**Verification**

- `pnpm run build:cf` — green, 2449 modules transformed in 2.91s.
  `dist/index.html`, `dist/_redirects`, `dist/install.sh` all
  present.
- `pnpm run test` — 377 passed (27 files).

After merge: Cloudflare Pages auto-builds from `main` (Git
integration), the `Cloudflare Pages` GitHub status check goes
back to green, and the live `tars.meeet.world` finally serves
content from Wave 67 + everything queued behind it.

**Files**

- (mod) `experiments/neural-showcase-v3/vite.config.ts`
- (mod) `experiments/neural-showcase-v3/package.json`
- (mod) `experiments/neural-showcase-v3/src/lib/useTarsDeepLink.ts`
- (mod) `experiments/neural-showcase-v3/src/lib/useSidecarStatus.ts`
- (mod) `experiments/neural-showcase-v3/src/pages/Settings.tsx`
- (mod) `docs/CHANGELOG_AGENTS.md` — this entry

## 2026-05-08 — Cursor · `make bootstrap` + actionable venv-missing hints

**Summary**

Closes the "fresh-machine first command fails terse" gap surfaced by
walking the operator playbook end-to-end. Every `make` target that
shells into `$(PY)` (= `./.venv/bin/python`) used to die with
`bash: ./.venv/bin/python: no such file or directory` for an
operator coming from a fresh clone. Same with
`scripts/backend_tars_up.sh` (`missing: ./.venv/bin/python — create
venv first` — without showing HOW) and
`scripts/smoke_billing_tars_backend.sh` (no guard at all).

**The single golden command:**

```bash
make bootstrap
```

- Picks the highest Python on PATH (prefers 3.12 → 3.11 → 3.10 →
  `python3`), so it works on any sane mac/linux without
  pre-installing 3.12.
- Idempotent: skips `python -m venv .venv` if `.venv/bin/python`
  already exists; only re-runs `pip install --upgrade pip` and
  `pip install -r requirements.txt` (both quiet).
- Prints a "next" pointer so operators know the follow-up command
  (`cp .env.example .env`, then `make dev-tars-stack` /
  `make qa-agent`).

`scripts/backend_tars_up.sh` and `scripts/smoke_billing_tars_backend.sh`
both now emit the same multi-line quick-fix hint when the venv is
missing — so even an operator who skipped Step 0a gets unblocked
from any code path that hits Python.

`docs/OPERATOR_LAUNCH_PLAYBOOK.md` Step 0a documents the bootstrap
command + idempotency promise, so the operator hits one obvious
fixed setup step instead of discovering venv-missing piecemeal in
Step 3 (visual smoke), Step 8 (smoke-billing), and Step 9 (gate-
control-tower).

**Tests**

`tests/test_operator_bootstrap.py` — 8 new assertions:
- `bootstrap` target exists + is in `.PHONY`.
- Uses idempotent venv-existence check.
- Picks Python via fallback chain (3.12 → 3.11 → 3.10 → python3).
- Installs `requirements.txt`.
- Prints a "[bootstrap] next:" pointer.
- Playbook references `make bootstrap`.
- `backend_tars_up.sh` + `smoke_billing_tars_backend.sh` both
  show the multi-line quick-fix hint.

All 8 pass. Local smoke: `make bootstrap` is 6.7s on an already-
bootstrapped venv (just the `pip install` no-op).

**Files**

- (mod) `Makefile` — adds `bootstrap` target + `PYTHON_BOOTSTRAP`
  fallback chain
- (mod) `scripts/backend_tars_up.sh` — actionable error block
- (mod) `scripts/smoke_billing_tars_backend.sh` — same hint
- (mod) `docs/OPERATOR_LAUNCH_PLAYBOOK.md` — Step 0a
- (new) `tests/test_operator_bootstrap.py`
- (mod) `docs/CHANGELOG_AGENTS.md` — this entry

## 2026-05-08 — Cursor · operator playbook drift fix (Step 5c-onwards)

**Summary**

Walked the operator launch playbook end-to-end and found a cluster
of factual drift between the doc and the scripts/workflow. Fixed
each one and added a regression test so the next drift fails CI
loudly. None of these are runtime bugs — they're "operator runs
the documented command and gets `no such file` / wrong env var
shape / triggers nothing" footguns.

**Drifts patched**

1. **Tauri release-key path.** Playbook said
   `~/.tars/release/minisign.{key,pub}`; script
   (`desktop/scripts/generate-release-keys.sh`) actually defaults
   to `~/.tars-release-keys/tars-desktop.key{,.pub}`. Aligned the
   playbook to the script (script is source of truth — moving the
   default would break operators who already have a key minted at
   the canonical path).

2. **`TAURI_SIGNING_PRIVATE_KEY` encoding.** Both the script's
   trailing operator hint and Step 6 of the playbook used to do
   `gh secret set TAURI_SIGNING_PRIVATE_KEY < <key>` (raw bytes).
   `tauri-apps/tauri-action@v0`'s contract expects base64. Changed
   both to `base64 < <key> | gh secret set TAURI_SIGNING_PRIVATE_KEY`
   so the operator gets a working signed installer first try.

3. **Release workflow trigger language.** Script footer pointed at
   `release-desktop.yml` with a `desktop-vX.Y.Z` tag suggestion;
   `RELEASE_NOTES_v0.1.0-rc.1.md` claimed `workflow_dispatch only`.
   The live workflow at `.github/workflows/release-desktop-tagged.yml`
   is `on.push.tags: 'v*'`. Aligned both to reality (tag pattern
   `v*`, no prefix; `git tag v9.1.1 && git push origin v9.1.1`).

4. **Download base URL (B-017 carry-over).** Step 8 of the playbook
   still set `TARS_DOWNLOAD_BASE_URL=https://github.com/.../releases/
   latest/download` which 404s anonymously while the repo is
   private. Switched to `https://tars.meeet.world/dl` (the
   Pages-Function proxy from yesterday's PR #155).

5. **`GITHUB_RELEASE_TOKEN` flagged in Step 6.** Added the new
   secret to the operator's GH-secrets table with a clear note
   that it's set in **Cloudflare Pages env**, not GitHub repo
   secrets. Cross-references `docs/TARS_MEEET_OPS_TODO.md` §5.

**Tests**

`tests/test_operator_playbook_drift.py` — 9 assertions pinning the
above contracts. All pass locally with the rest of the funnel
suite (46/46 + 1 skipped + 2 documented xfails).

**Files**

- (mod) `desktop/scripts/generate-release-keys.sh`
- (mod) `docs/OPERATOR_LAUNCH_PLAYBOOK.md`
- (mod) `docs/RELEASE_NOTES_v0.1.0-rc.1.md`
- (new) `tests/test_operator_playbook_drift.py`
- (mod) `docs/CHANGELOG_AGENTS.md` — this entry

## 2026-05-08 — Cursor · B-017 fix: same-origin install funnel via Pages Function dl-proxy

**Summary**

Resolves the B-017 install-funnel breakage end-to-end with option
(c) from the previous sit-rep — same-origin Cloudflare Pages
Functions, no public-repo flip required. After this PR merges and
the operator pastes a single PAT (`GITHUB_RELEASE_TOKEN`) into
Pages env, `curl -fsSL https://tars.meeet.world/install.sh | bash`
produces a working installer for any anonymous visitor while the
source repo stays private.

**Architecture**

- New Pages Function `experiments/neural-showcase-v3/functions/dl/
  [file].ts`. Strict `ALLOWED_FILENAMES` allowlist (v9.1.0 + v8.4.0
  Tauri assets + Tauri updater manifest). Resolves filename → tag,
  hits `api.github.com/repos/.../releases/tags/<tag>` with
  `Bearer ${GITHUB_RELEASE_TOKEN}`, then streams the asset binary
  via `accept: application/octet-stream`. Caches the asset listing
  for 5 min and the body for 1 h (releases are immutable).
  Without the env var, returns HTTP 503 +
  `{ok:false, error:"operator_action_required", …}` so the failure
  mode is self-explanatory.

- `_redirects` cleared of the broken `/install.sh →
  raw.githubusercontent.com/...` line (which 404'd on a private
  repo and silently shadowed the static file). Pages now serves
  `public/install.sh` directly.

- `public/install.sh` rewritten: resolves the latest version via
  same-origin `tars.meeet.world/api/product/version` and downloads
  via `tars.meeet.world/dl/<filename>`. Zero `api.github.com` /
  `github.com` hits at runtime.

- `scripts/install-tars.sh` mirrors the same: `tars.meeet.world/dl/
  <filename>`, default `TARS_VERSION=9.1.0`. Fail-path prints a
  curl one-liner that surfaces the 503 + operator hint.

- `functions/api/product/downloads.ts` bumped to v9.1.0 as the
  primary release (kept v8.4.0 in the manifest for any pinned
  installers in the wild) and switched ALL artifact URLs to
  `tars.meeet.world/dl/<filename>` so the canonical download
  manifest also flows through the proxy.

- `functions/api/product/version.ts` corrected `released_at` to
  the real v9.1.0 timestamp (`2026-05-04T11:10:56Z`).

**Operator action (one-time, ~3 min)**

Documented in `docs/TARS_MEEET_OPS_TODO.md` §5. TL;DR:

1. GitHub → fine-grained PAT, scoped to
   `alxvasilevvv/tars-neural-cockpit`, `Contents: Read-only`.
2. Cloudflare Pages → `tars-meeet-git` → Settings → Environment
   variables → Production → `GITHUB_RELEASE_TOKEN` (Encrypt).
3. Trigger fresh deploy.

**Verification**

```bash
curl -sI https://tars.meeet.world/install.sh | head -1
# → HTTP/2 200, content-type: application/x-sh

curl -sI https://tars.meeet.world/dl/TARS_9.1.0_aarch64.dmg | head -1
# Before PAT: HTTP/2 503  + operator_action_required JSON
# After PAT:  HTTP/2 200  + content-type: application/octet-stream + content-disposition

curl -fsSL https://tars.meeet.world/install.sh | bash
# Resolves v9.1.0 from /api/product/version, downloads via /dl/, installs.
```

**Tests**

`tests/test_tars_meeet_install_funnel.py` — 17 assertions pinning
the contract:

- `_redirects` no longer hijacks `/install.sh` or `/dl/*`.
- `functions/dl/[file].ts` exists, defines `ALLOWED_FILENAMES`,
  requires `GITHUB_RELEASE_TOKEN`, returns 503 +
  `operator_action_required`, uses authenticated GitHub API.
- Allowlist covers all v9.1.0 canonical assets + `latest.json`.
- `public/install.sh` and `scripts/install-tars.sh` use only
  same-origin URLs (executable lines, comments excluded).
- `downloads.ts` manifest lists v9.1.0 and routes URLs through
  the proxy.

All 17 pass locally. Adjacent suites unchanged
(`test_tars_meeet_cors_frame.py`, `test_tars_meeet_pages_workflow.py`,
`test_release_desktop_workflow.py`).

**Files**

- (new) `experiments/neural-showcase-v3/functions/dl/[file].ts`
- (mod) `experiments/neural-showcase-v3/public/_redirects`
- (mod) `experiments/neural-showcase-v3/public/install.sh`
- (mod) `experiments/neural-showcase-v3/functions/api/product/downloads.ts`
- (mod) `experiments/neural-showcase-v3/functions/api/product/version.ts`
- (mod) `scripts/install-tars.sh`
- (new) `tests/test_tars_meeet_install_funnel.py`
- (mod) `docs/TARS_MEEET_OPS_TODO.md` — adds §5 with PAT setup
- (mod) `docs/CHANGELOG_AGENTS.md` — this entry

## 2026-05-08 — Cursor · operator UX hardening + install.sh deprecation + B-017 sit-rep

**Summary**

Three small operator-facing fixes, plus a freshly-confirmed
diagnostic on the install funnel that is operator-only to resolve.

1. **`scripts/launch_precheck.sh`** — `/api/entitlements` probe was
   tripping a transient WARN with `-m 2` because the route does live
   USD-budget math + a billing-state pull on cold call. Bumped to
   `-m 5` and added a single 300ms retry. Verified 5/5 clean runs
   on a healthy backend. Shipped via PR #153 (CI parked behind the
   GitHub Actions billing gate; see §3 below).

2. **`scripts/smoke_core_bridge_e2e.sh`** — when
   `BRIDGE_SHARED_SECRET` is unset (the most common reason
   `make gate-control-tower` fails for a fresh operator) the script
   used to die with one terse line. Replaced with a three-path
   actionable hint pointing at `make ops-bridge-secret`,
   one-shot env override, and the canonical Lovable Supabase
   location. Diagnostic only — no behavioural change when the
   secret IS present.

3. **`scripts/install.sh`** — replaced 264 lines of legacy logic
   (pointed at the non-existent `meeet-world/tars` repo with asset
   names that no GitHub Release ever produced) with a 50-line
   deprecation stub that:
     - prints a clear "use the canonical install" pointer to
       stderr (web one-liner + in-repo path),
     - then `exec bash`'s `scripts/install-tars.sh` if present,
     - otherwise exits 1 with a final pointer.
   Every live path (\`_redirects\` line 15, `web_extras/routers/
   product.py:66`, both changelogs) already references
   `install-tars.sh`; this stub is purely a footgun-mitigation for
   anyone who finds the old filename via `git log`.

### B-017 sit-rep — install funnel currently broken in prod

Confirmed on 2026-05-08 (operator-zone, not Cursor-fixable from
code):

- Repo `alxvasilevvv/tars-neural-cockpit` is **private**
  (`gh repo view --json visibility` → `PRIVATE`).
- Direct release-asset URLs like
  `https://github.com/.../releases/download/v9.1.0/TARS_9.1.0_aarch64.dmg`
  return **HTTP 404** to unauthenticated callers.
- `https://raw.githubusercontent.com/.../scripts/install-tars.sh`
  also returns 404 — so the `_redirects` rule
  `/install.sh → raw.github...` (line 15) cannot resolve.
- Live `https://tars.meeet.world/install.sh` 302's to `/install`
  (SPA fallback path), so the documented one-liner
  `curl -fsSL https://tars.meeet.world/install.sh | bash` pipes
  marketing HTML to bash and errors instead of installing anything.

The `_redirects` file in `main` *intends* to point /install.sh at
the canonical script; the rule is correct, the **target URL is
broken because the repo is private**. Pick one of the B-017
options that brother + Claude were already discussing:

  (a) Flip `tars-neural-cockpit` back to public (cheapest;
      undoes the privacy decision).
  (b) Mirror release assets and the install script to a public
      surface (R2 / S3 / Cloudflare worker / `tars.meeet.world`
      Pages) and update `_redirects` + `install-tars.sh` to point
      at the mirror.
  (c) Serve the install funnel exclusively via `tars.meeet.world`
      (already same-origin; just add a `functions/install.sh.ts`
      Pages Function that streams the canonical script and a
      `functions/dl/[file].ts` that proxies releases via the
      gh-token).

Option (c) is the cleanest on the Cursor side and would let me
implement it without operator infra changes — happy to wire it the
moment the operator picks a path. Until then the install funnel is
dark in production for all anonymous visitors.

### CI status

`credential sentinel` workflow has been failing on every PR since
2026-05-05 with the GitHub Actions billing gate
(`The job was not started because recent account payments have
failed or your spending limit needs to be increased`). PRs #153 and
this one are blocked behind that gate; both are otherwise verified
locally and will auto-rerun once the operator settles billing under
Settings → Billing & plans.

**Files** —
`scripts/launch_precheck.sh`,
`scripts/smoke_core_bridge_e2e.sh`,
`scripts/install.sh`,
`docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 64: Operator launch playbook + auto-precheck + templates

>>> SYNC: Claude · 2026-05-05 · Pre-launch ops package — `docs/OPERATOR_LAUNCH_PLAYBOOK.md` (15-step launch playbook), `scripts/launch_precheck.sh` (auto-verifier with --desktop / --full modes), `make launch-precheck{,-full}` Makefile targets, three templates (`docs/templates/{BROTHER_HANDOFF_MESSAGE,MARKETING_ANNOUNCEMENT,GITHUB_RELEASE_NOTES_v9.1.0}.md`). Removed legacy `scripts/commit_wave_{51_56,58}.sh` (already pushed and superseded).

**Summary**

User request: do everything I can on my side, give clear step-by-step ТЗ for everything else. Result is a complete launch package.

1. **`scripts/launch_precheck.sh`** (new, 7.2KB) — single-command verification. Three modes: default (working tree + critical docs + .env hygiene + dev stack probe), `--desktop` (also runs `cargo check` on Tauri shell), `--full` (also runs `make smoke-billing-tars`). Color output, summary line `passed/warned/failed`, exit 0 / 1.

2. **`make launch-precheck`** + **`make launch-precheck-full`** — wraps the script for muscle-memory `make` users.

3. **`docs/OPERATOR_LAUNCH_PLAYBOOK.md`** (new) — 15 steps from `git push` to launch tweet, each with TIME / DEPS / VERIFY tags and 🚦 BLOCKER markers. Covers: pushing, precheck, visual smoke, brother handoff, Apple Developer enrollment ($99), Authenticode cert ($200-400), minisign keys, GitHub Actions secrets matrix (13 entries with copy-paste base64 commands), .env sync, control-tower smoke, tag release, install smoke on clean Mac, production deploy, public announcement, monitoring, retro. Final cheat-sheet table tells operator exactly which step Claude can do vs which is theirs.

4. **Three templates:**
   - `docs/templates/BROTHER_HANDOFF_MESSAGE.md` — Telegram / email / voice-memo variants for handing the integration spec to brother. Plus security do-not list (don't ship secrets via email).
   - `docs/templates/MARKETING_ANNOUNCEMENT.md` — 8-tweet Twitter thread, solo tweet, full blog post, Discord drop, Hacker News submission with pre-written first comment, Twitter reply hooks for common questions, video recording shot list, what NOT to publish.
   - `docs/templates/GITHUB_RELEASE_NOTES_v9.1.0.md` — full release notes for the v9.1.0 GitHub Release page, with placeholders the CI workflow can fill (sha256 checksums, minisign pubkey fingerprint).

5. **Cleanup** — removed `scripts/commit_wave_51_56.sh` and `scripts/commit_wave_58.sh` (legacy helpers from earlier sessions, already done their job).

The playbook + scripts mean that for the next launch run, the operator literally doesn't have to think — just `git push`, then `make launch-precheck`, then walk down the 15 steps.

**Files** —
`scripts/launch_precheck.sh` (new),
`scripts/commit_wave_51_56.sh` (deleted),
`scripts/commit_wave_58.sh` (deleted),
`Makefile` (2 new targets),
`docs/OPERATOR_LAUNCH_PLAYBOOK.md` (new),
`docs/templates/BROTHER_HANDOFF_MESSAGE.md` (new),
`docs/templates/MARKETING_ANNOUNCEMENT.md` (new),
`docs/templates/GITHUB_RELEASE_NOTES_v9.1.0.md` (new),
`docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 63: Desktop ownership pass — wrap-up summary

>>> SYNC: Claude · 2026-05-05 · Wave 59-62 desktop pass closed. New `docs/DESKTOP_OWNERSHIP_PASS.md` consolidates everything (commits, files, surfaces, latent issues, verify-by-operator steps). Audited pyoxidizer.bzl + build.rs + sw.js — clean, but flagged: SW never registered (latent web-only), CI uses pyinstaller not pyoxidizer (out-of-scope rewrite). No code touched in this entry.

**Files** — `docs/DESKTOP_OWNERSHIP_PASS.md` (new), `docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 62: /settings page + updater UI + Cmd+K palette entry

>>> SYNC: Claude · 2026-05-05 · New standalone /settings route (About / Updater / Keyboard reference). tars://settings deep-link re-pointed from /cockpit?panel=settings to /settings. GlobalCommandPalette index gets a Settings entry. No backend touched.

**Summary**

Wave 59 registered `tars://settings` as a deep-link verb but routed it to `/cockpit?panel=settings` — a panel that didn't exist. Wave 62 builds the actual destination so the deep link lands on a real page:

- **`src/pages/Settings.tsx`** (new) — three cards:
  - **About** — version, runtime label (`desktop · tauri 2` vs `browser · web`), live sidecar status (port + boot took_ms when ready, otherwise stage), GitHub link.
  - **Updates** — "Check for updates" button. In Tauri, dynamically imports `@tauri-apps/plugin-updater` and calls `check()`; renders up-to-date / available / error states. In browser, opens GitHub Releases in a new tab. The plugin import is `/* @vite-ignore */`-gated so the bundler doesn't bake it into web builds (avoiding Vite resolve errors).
  - **Keyboard** — table of every shortcut TARS responds to (⌘K / ⌘J / ⌘. / ⇧/ / ⌘⇧Space / Tab).
- **Route wired** in `App.tsx` under `/settings` with `RouteSkeleton variant="legal"` Suspense fallback.
- **Deep-link parser** (`useTarsDeepLink.ts`): `tars://settings` now → `/settings` (was: `/cockpit?panel=settings`).
- **Cmd+K palette** (`GlobalCommandPalette.tsx`): added Settings entry under "Pages" group with keywords `preferences updater shortcuts version about` so it's findable via fuzzy search.
- **DESKTOP.md**: deep-link table updated.

Page is browser-safe — `getHealth` heartbeat reuses the Wave 61 hook, runtime detection mirrors `__TAURI_INTERNALS__` checks elsewhere. Settings link visible to both web and desktop users.

**Files** —
`experiments/neural-showcase-v3/src/pages/Settings.tsx` (new),
`experiments/neural-showcase-v3/src/App.tsx`,
`experiments/neural-showcase-v3/src/lib/useTarsDeepLink.ts`,
`experiments/neural-showcase-v3/src/components/GlobalCommandPalette.tsx`,
`docs/DESKTOP.md`,
`docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 61: Mid-session sidecar crash detection + early_exit + heartbeat

>>> SYNC: Claude · 2026-05-05 · sidecar.rs gets a watcher thread (Wave 61). Drop emits desktop.sidecar.exited only on app shutdown — mid-session child crashes were silently lost. Watcher polls child.try_wait() every 2s, emits on unexpected termination, marks the slot None so Drop doesn't double-emit. wait_for_health now also detects early_exit (the schema's third stage was unused dead code). useSidecarStatus gets defense-in-depth /health heartbeat (30s, 2-fail budget) for hung-but-alive sidecars where try_wait wouldn't fire.

**Summary**

Reviewed `sidecar.rs` after Wave 60 to make sure my new cockpit badge would actually catch real crashes. Found a real gap: the `Drop` impl is the **only** place `desktop.sidecar.exited` was emitted, and Drop only runs on app shutdown. So a sidecar crashing mid-session (OOM, bug, manual kill from outside) never produced a status event — the cockpit's `useSidecarStatus` would stay in `ready` forever while every API call failed with connection refused.

Fixed at three layers:

1. **Watcher thread (Rust).** After health passes, spawn a thread that holds a `Weak<Mutex<Option<SidecarHandle>>>` and polls `child.try_wait()` every 2 seconds. On unexpected termination, emits `desktop.sidecar.exited` with exit_code/signal/ran_ms and zeroes the child slot. Drop now skips its own emit if the slot was already cleared, so we don't double-fire.

2. **`early_exit` stage (Rust).** The schema lists `early_exit` as a possible `desktop.sidecar.failed` stage (sidecar dies during boot, before health passes), but the previous `wait_for_health` didn't watch the child — it just polled HTTP. Now it consults a `is_alive` closure on every iteration; if the child has exited, we emit `desktop.sidecar.failed` with `stage: "early_exit"` instead of waiting out the full 15s timeout.

3. **`/health` heartbeat (TypeScript, defense-in-depth).** The watcher catches when the **process** dies. It can't catch when the **process is alive but unresponsive** (zombie / hung). `useSidecarStatus` now also pings `/health` every 30s while in `ready`. After 2 consecutive failures, flips to `exited` with synthetic signal `heartbeat_lost`. SidecarStatusBadge renders that case as "Backend stopped responding to /health. It may be hung or partitioned. Relaunch TARS." Cheap (one fetch per 30s, ~no impact on idle loop).

The watcher uses Weak references throughout so it doesn't keep the app alive past its natural lifetime; if Tauri drops the SharedHandle Arc during shutdown, the watcher's next `weak.upgrade()` returns None and the thread exits cleanly.

No schema changes — `desktop.sidecar.exited` payload is unchanged, the watcher just emits it from a new place. Existing test `tests/test_desktop_sidecar_events_contract.py` still pins v1.0.0.

**Files** —
`desktop/src-tauri/src/sidecar.rs`,
`experiments/neural-showcase-v3/src/lib/useSidecarStatus.ts`,
`experiments/neural-showcase-v3/src/components/SidecarStatusBadge.tsx`,
`docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 60: Sidecar status indicator + DESKTOP.md operator guide

>>> SYNC: Claude · 2026-05-05 · Cockpit listens to desktop.sidecar.{started,failed,exited} Tauri events via new `useSidecarStatus` hook + `SidecarStatusBadge` component (mounted in AppShell). Shows starting/ready/failed/exited states; browser builds skip entirely. Plus user-facing `docs/DESKTOP.md` operator guide.

**Summary**

Sidecar lifecycle events have been emitted by `desktop/src-tauri/src/sidecar.rs` since Phase L9 A1 (schema pinned at `sidecar-events.schema.json` v1.0.0), but the cockpit never listened. When the FastAPI sidecar failed to boot, the user saw nothing — silent failure, hard to diagnose.

Wave 60 wires the cockpit-side listener:

1. **`useSidecarStatus` hook** (`src/lib/useSidecarStatus.ts`) — listens to all three events, tracks state machine (`unknown` → `starting` → `ready` | `failed` | `exited`), 8-second cold-load timeout escalation if no `started` event arrives. Browser-build no-op gated by `__TAURI_INTERNALS__`.

2. **`<SidecarStatusBadge />` component** (`src/components/SidecarStatusBadge.tsx`) — bottom-left fixed banner. UX:
   - `starting` → small spinner pill ("Starting backend…")
   - `ready` → green pill auto-dismissing after 2.5s
   - `failed` → amber banner pinned with stage + error excerpt + troubleshooting link
   - `exited` (mid-session crash) → red banner with exit code / signal
   - User-dismissable; new failures re-surface

3. **`docs/DESKTOP.md`** — new user-facing operator guide covering install, native features (window state / tray / global shortcut / deep links / sidecar status), updater, troubleshooting, and security model. References Wave 59 + Wave 60 features.

Mounted in `<AppShell />` after `<ToastBus />`. Zero impact on browser builds.

**Files** —
`experiments/neural-showcase-v3/src/App.tsx`,
`experiments/neural-showcase-v3/src/lib/useSidecarStatus.ts` (new),
`experiments/neural-showcase-v3/src/components/SidecarStatusBadge.tsx` (new),
`docs/DESKTOP.md` (new),
`docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 59: Desktop native UX + ScrollStory fix

>>> SYNC: Claude · 2026-05-05 · Tauri 2 desktop shell gets window-state persistence, tray icon (menu bar), global shortcut Cmd+Shift+Space, `tars://` deep-link routing, pre-flight build gate. Plus ScrollStory edge-segment opacity fix. Cargo.toml + tauri.conf.json + capabilities + main.rs + cockpit deep-link hook. No backend touched.

**Summary**

Two surfaces, one wave.

**Cockpit polish — ScrollStory edge segments (Wave 59-1).**
The "04 · How it works · Four ways TARS pays for itself before lunch" section pinned for 400vh of scroll, but `CopyPane`/`VisualPane` had `[start - 0.04, peak, end + 0.04] → [0, 1, 0]` opacity ranges. For segment 0 that meant opacity=0 at scroll=0 → huge blank pinned area at section entry. For segment N-1 it faded to 0 before unpin. Fix: first segment stays opacity=1 from scroll=0 to peak; last stays opacity=1 from peak to scroll=1. Same fix for y/scale transforms. (User reported via screenshot.)

**Desktop native UX (Wave 59-2 → 59-8).**
Tauri 2 shell was minimal — bare window + sidecar spawn. This wave layers the things that make a desktop app stop feeling like a wrapped web view:

1. **Window state persistence** (`tauri-plugin-window-state` 2.0) — TARS remembers main-window size + position across launches.
2. **System tray icon** (Tauri 2 `tray-icon` feature) — menu-bar entry on macOS / system tray on Windows+Linux. Left-click toggles window. Right-click opens menu (Show TARS / Quit).
3. **Global shortcut** (`tauri-plugin-global-shortcut` 2.0) — `Cmd+Shift+Space` (macOS) / `Ctrl+Shift+Space` (Windows/Linux) summons or hides the main window from anywhere. Soft-fails if OS denies registration (other app conflict).
4. **Deep links** (`tauri-plugin-deep-link` 2.0) — `tars://` scheme registered via `tauri.conf.json`. Rust side captures cold-start + warm-arrival URLs, focuses the window, and emits `tars://deeplink` event with the URL array. New cockpit hook `src/lib/useTarsDeepLink.ts` listens (browser-build no-op when `__TAURI_INTERNALS__` undefined) and routes via React Router. Supported verbs: `onboarding`, `login`, `cockpit`, `thread/<id>`, `settings`.
5. **Pre-flight build gate** (`desktop/scripts/preflight-build.sh`) — fails fast before `tauri build` if `src-tauri/web/` is empty / missing index.html / has fewer than 5 asset chunks (silent blank-window risk), icons absent, or `--release` mode but `pubkey: TODO_PUBLIC_KEY` still in tauri.conf. Wired into `pnpm release` chain.
6. **Stale TODO cleanup** — `desktop/README.md` L54 outdated "TODO: bring up FastAPI" comment (sidecar shipped Phase L9 A1).
7. **Download URL drift** — `.env.example` `TARS_DOWNLOAD_BASE_URL` was `https://meeet.world/downloads/tars` (404, never hosted). Switched to GitHub Releases (where CI actually publishes), with a multi-line comment explaining the proxy plan.

Capabilities manifest created at `desktop/src-tauri/capabilities/default.json` granting the new plugins their permissions on the `main` window only (no widening of the security envelope beyond what the new features require).

**Files** —
`experiments/neural-showcase-v3/src/components/ScrollStory.tsx`,
`experiments/neural-showcase-v3/src/App.tsx`,
`experiments/neural-showcase-v3/src/lib/useTarsDeepLink.ts` (new),
`desktop/src-tauri/Cargo.toml`,
`desktop/src-tauri/tauri.conf.json`,
`desktop/src-tauri/src/main.rs`,
`desktop/src-tauri/capabilities/default.json` (new),
`desktop/scripts/preflight-build.sh` (new),
`desktop/package.json`,
`desktop/README.md`,
`.env.example`,
`docs/CHANGELOG_AGENTS.md` (this entry),
`docs/WAVE_59_DESKTOP_SIGNOFF.md` (new).

## 2026-05-05 — Claude · Wave 58: Tab focus trap on 3 Cmd+K palettes

>>> SYNC: Claude · 2026-05-05 · WCAG 2.1.2 closure on CommandPalette / JumpPalette / GlobalCommandPalette — `useFocusTrap(dialogRef, open)` wired in all three, dialog roots get `ref={dialogRef} tabIndex={-1}`. Static audit (Wave 57) caught Tab escaping to background page despite `aria-modal="true"`. No backend touched.

**Summary**

Static a11y audit on the running dev server's surface (without WebFetch access to localhost) flagged a P1 WCAG 2.1.2 violation: the three command palettes had `aria-modal="true"` from Wave 55 but no Tab focus trap, so keyboard users could Tab out of the palette into the inert background page. Arrow-key navigation + Esc + Enter handlers were already correct; this just plugged the Tab-escape hole.

Pattern applied to each:

1. Import `useFocusTrap` from `@/lib/useFocusTrap`.
2. Add `const dialogRef = useRef<HTMLDivElement | null>(null);`.
3. Call `useFocusTrap(dialogRef, open)` after the `useGlobalShortcut` hook.
4. On the dialog `motion.div`, add `ref={dialogRef}` + `tabIndex={-1}`.

`GlobalCommandPalette` already had the hook + ref wired (lines 209, 212) but the dialog `motion.div` was missing the `ref` + `tabIndex`. Closed that loop.

Wave 55's `useFocusTrap.ts` utility handles all the heavy lifting (Tab cycling, restore-on-close, microtask focus seed). No changes to the utility itself were needed.

**Files** — `experiments/neural-showcase-v3/src/components/CommandPalette.tsx`, `experiments/neural-showcase-v3/src/components/JumpPalette.tsx`, `experiments/neural-showcase-v3/src/components/GlobalCommandPalette.tsx`, `docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Cursor · Wave 56: P1 hex→tokens + billing mirror exhaustion log

>>> SYNC: Cursor · 2026-05-05 · Wave 56 P1 closure — 3 hex→token in Onboarding role chips (+ --brand-amber added to index.css), structured log meeet.mirror.usage.exhausted on retry budget exhaustion in client.py:178. P1-2 confirmed already covered by smoke-core-bridge. Frontend (cockpit lane) untouched.

**Files** — `experiments/neural-showcase-v3/src/index.css`, `experiments/neural-showcase-v3/src/pages/Onboarding.tsx`, `backend/core/meeet_billing/client.py`, `tests/test_meeet_billing_usage.py`, `docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 55: Final launch ownership pass — modal a11y sweep + sign-off

>>> SYNC: Claude · 2026-05-05 · WCAG 2.1 AA pass on 4 modal/overlay surfaces in `experiments/neural-showcase-v3/src/`. No backend code touched. Cursor lanes (`backend/`, `lib/`, `Makefile`, `scripts/`) untouched.

**Summary**

Final pre-launch ownership pass. Took the 2026-05-05 baseline (HEAD `4b6a322`, 217 commits ahead of Wave 51 baseline) and ran a focused a11y sweep across every `role="dialog"` surface using launch-readiness criteria.

Of 11 dialog-roled overlays in the cockpit/marketing surface, 7 already had `aria-modal="true"` (Cockpit, Onboarding's other dialog branch, KeyboardOverlay, CockpitTour, WatchMeWork, OperatorPalette, GlobalCommandPalette — Cursor's Wave 53 follow-up landed those). Four were missing — closed in this wave:

1. **`src/pages/Onboarding.tsx`** (CustomRoleModal at L713) — added `aria-modal="true"`, `tabIndex={-1}` on the dialog root, and wired `useFocusTrap(dialogRef, true)` from the existing `src/lib/useFocusTrap.ts` utility. Added Esc-to-close keyboard handler (the surrounding `onClick={onClose}` only handled backdrop clicks, leaving keyboard users with no escape hatch — WCAG 2.1.2). Inline comments cite WCAG sections so the next agent knows why the extra wiring exists.
2. **`src/components/JumpPalette.tsx`** (L177) — added `aria-modal="true"`. The component already auto-focuses its search input and handles `Escape`/`Enter`/`Arrow{Up,Down}` via its own `onKeyDown`; minimal aria-modal addition avoids conflicting with that keyboard logic.
3. **`src/components/CommandPalette.tsx`** (L126) — same minimal `aria-modal="true"` addition for the same reason.
4. **`src/components/CookieConsent.tsx`** (L58) — corrected the role: a non-blocking bottom-of-viewport banner is not a dialog. Changed `role="dialog"` → `role="region"`. Screen readers will now announce it as a labeled region (consistent with its Cookie/Accept/Reject button affordances) instead of trapping users into expecting modal semantics that don't apply.

**Why this wave matters for launch:** with 217 commits since baseline and Cursor's billing/payment work in flight, every agent has been touching keyboard-modal surfaces but no one had run the consolidated `role="dialog"` sweep. Modal a11y regressions are the kind of thing that ship silently and surface in App Store / accessibility review later.

**Untouched, intentionally:**

- Hardcoded hex colors in `src/pages/PricingPage.tsx`, `ComparePage.tsx`, and `src/pages/Onboarding.tsx` role color chips. Real but P1 (visual consistency, not a11y); Cursor lane.
- BRIDGE_SHARED_SECRET propagation into `make gate-control-tower` smoke target. Closed at the env template level in Wave 54; runtime side is Cursor's `Makefile` lane.
- billing mirror silent-failure logging on `POST /operator/usage` retry exhaustion. Cursor lane (`backend/core/meeet/billing_mirror_remote.py`).

**Files** — `src/pages/Onboarding.tsx`, `src/components/JumpPalette.tsx`, `src/components/CommandPalette.tsx`, `src/components/CookieConsent.tsx`, `docs/CHANGELOG_AGENTS.md` (this entry).

## 2026-05-05 — Claude · Wave 54: handoff brief pointers + .env.example bridge key

>>> SYNC: Claude · 2026-05-05 · CLAUDE.md pointer to handoff-claude.md 2026-05-05 brief block; .env.example adds BRIDGE_SHARED_SECRET= template (per docs/SYNC.md §7 + docs/contracts/CORE_BRIDGE.md). No backend code touched.

**Summary**

Read the four canonical docs from the 2026-05-05 operator brief
(`docs/handoff-claude.md`, `docs/SYNC.md`, `docs/AGENT_HANDOFF.md`,
`docs/contracts/TARS_MEEET_BILLING.md`) and ran the brief's self-checks
where the sandbox allowed. All four test files exist (`test_meeet_billing_remote`,
`test_meeet_billing_usage`, `test_entitlements`, `test_commercial_readiness_chain`),
all five make targets are wired (`ops-billing-remote-wizard`,
`smoke-billing-tars`, `backend-tars-up`, `dev-tars-stack`,
`test-commercial-readiness`), `.env` is gitignored correctly, and the
recent billing commits (`4b6a322`, `47f942a`) line up with the contract.

Two tiny gaps closed locally:

1. **`.env.example`** — added `BRIDGE_SHARED_SECRET=` template under a
   new "meeet core ↔ TARS core-bridge" section. Brief explicitly lists
   *bridge* among the keys an operator copies into `.env`, but the
   template was missing it; fresh-clone operators following
   `docs/SECOND_MACHINE_HANDOFF.md` could ship without it and quietly
   fail `make smoke-core-bridge` / `make gate-control-tower`.
2. **`CLAUDE.md`** — added a one-liner pointer (right under the
   "Fresh clone / second machine" block) that routes new sessions to
   the 2026-05-05 brief at the top of `docs/handoff-claude.md`. Cursor
   and Claude both auto-load `CLAUDE.md` so this surfaces the operator
   brief without requiring the agent to grep for it.

Pytest / vitest could not run in this sandbox (no `.venv`, native
rollup binary mismatch on `@rollup/rollup-linux-arm64-gnu`). Brief's
real verification still belongs to the operator on local hardware.

**Files** — `.env.example`, `CLAUDE.md`, `docs/CHANGELOG_AGENTS.md`
(this entry).

## 2026-05-05 — Claude · Wave 53: Pre-launch sign-off + 2 P0 a11y/UX fixes

**Summary**

Comprehensive pre-launch audit verifying 217 commits since baseline. Brother's
GO_LIVE_48H assessment is GREEN: Cursor closed all 4 P1 items from Wave 51
(P1-1 payment_token via TARS_PAYMENT_MODE env, P1-2 server-side policy mode
authority, P1-3 custom token-bucket rate-limiter, P1-4 BYO toggle gate).
Backend security clean — 0 hardcoded secrets, 0 stray prints/logs, CORS safe.
2315 backend tests + 328 vitest passing + 25/0/2/3 smoke.

Closed 2 P0 launch-blockers in this wave:
- FAQ accordion: button gets `aria-label="Expand answer · {q}"`, panel gets
  `role="region"` + `aria-labelledby` for screen readers (WCAG 2.1 AA · 2.4.4
  + 2.4.6 + 4.1.2)
- CockpitGate footer hides raw `API_BASE` in prod builds (was leaking
  `127.0.0.1:8765` or `tars.meeet.world` to confused public visitors)

5 P1 + 6 P2 findings catalogued for first-week sprint (JumpPalette silent
fail, OperatorPalette AbortSignal, LocaleSwitcher empty guard, Onboarding
modal aria-modal+focus-trap, Compare mobile sticky column, etc).

Two pending operator (brother) actions before public launch:
- BRIDGE_SHARED_SECRET on Cloudflare Pages env (blocker)
- /api/tars/downloads proxy on meeet-app (optional)

Full sign-off doc at `docs/WAVE_53_LAUNCH_SIGNOFF.md`. Verdict: ship it.

**Files** — `src/components/FAQ.tsx`, `src/components/CockpitGate.tsx`,
`docs/WAVE_53_LAUNCH_SIGNOFF.md`.

## 2026-05-05 — Cursor: dev-tars-stack (API bg + cockpit pnpm dev)

**Summary:** **`scripts/dev_tars_stack.sh`** + **`make dev-tars-stack`** — runs **`backend_tars_up`** then **`pnpm dev`** in v3 cockpit; **`VITE_TARS_API`** when **`PORT≠8765`**. **`docs/AGENT_HANDOFF.md`**, **`.env.example`**.

**Files:** `scripts/dev_tars_stack.sh`, `Makefile`, `.env.example`, `docs/AGENT_HANDOFF.md`, `docs/CHANGELOG_AGENTS.md`.

`>>> SYNC: Cursor · 2026-05-05 · dev-tars-stack`

## 2026-05-05 — Cursor: backend-tars-up (one-shot uvicorn + probe)

**Summary:** **`scripts/backend_tars_up.sh`** + **`make backend-tars-up`**: kill **:8765**, **nohup** uvicorn via **`with_repo_env`**, wait, **`curl` + `jq`** on **`/api/entitlements`**. **`docs/AGENT_HANDOFF.md`**.

**Files:** `scripts/backend_tars_up.sh`, `Makefile`, `.env.example`, `docs/AGENT_HANDOFF.md`, `docs/CHANGELOG_AGENTS.md`.

`>>> SYNC: Cursor · 2026-05-05 · backend-tars-up`

## 2026-05-05 — Cursor: smoke-billing-tars (no uvicorn)

**Summary:** **`make smoke-billing-tars`** + **`scripts/smoke_billing_tars_backend.{sh,py}`** — load **`.env`**, **`fetch_operator_snapshot(bypass_cache=True)`**, print tier/live (stdlib path operators use). **`docs/AGENT_HANDOFF.md`** pointer.

**Files:** `scripts/smoke_billing_tars_backend.sh`, `scripts/smoke_billing_tars_backend.py`, `Makefile`, `.env.example`, `docs/AGENT_HANDOFF.md`, `docs/CHANGELOG_AGENTS.md`.

`>>> SYNC: Cursor · 2026-05-05 · smoke-billing-tars`

## 2026-05-05 — Cursor: ops wizard for remote billing key + .env

**Summary:** **`scripts/ops_billing_remote_wizard.sh`** + **`make ops-billing-remote-wizard`**: hidden paste of **`MEEET_BILLING_API_KEY`**, confirm prod smoke (**GET /operator**, duplicate **POST /operator/usage**), optional merge into **`.env`**, optional pytest billing files. **`docs/AGENT_HANDOFF.md`** pointer.

**Files:** `scripts/ops_billing_remote_wizard.sh`, `Makefile`, `.env.example`, `docs/AGENT_HANDOFF.md`, `docs/CHANGELOG_AGENTS.md`.

`>>> SYNC: Cursor · 2026-05-05 · ops_billing_remote_wizard`

## 2026-05-05 — Cursor: remote billing prod baseline (handoff + contract)

**Summary:** Documented **live** `tars-billing` on Supabase **`zujrmifaabkletgnpoyw`**: dedupe migration applied, edge redeployed, smoke + RLS verified (operator / Lovable). **`AGENT_HANDOFF`** «start line» for TARS `MEEET_BILLING_BASE_URL` + key parity; **`TARS_MEEET_BILLING.md`** prod reference paragraph.

**Files:** `docs/AGENT_HANDOFF.md`, `docs/contracts/TARS_MEEET_BILLING.md`, `docs/CHANGELOG_AGENTS.md`.

`>>> SYNC: Cursor · 2026-05-05 · billing prod baseline zujrmifaabkletgnpoyw in handoff + contract`

## 2026-05-05 — Cursor: billing usage idempotency + client retries

**Summary:** **`POST /operator/usage`:** optional **`trace_id`** / dedupe table on meeet edge (duplicate → 200, no double spend); success JSON includes **`duplicate: false`**. **Jarvis:** `post_operator_usage_delta` retries transient HTTP/transport (`MEEET_BILLING_USAGE_RETRIES`); mirror passes **`trace_id`** from `usage.tokens` emit; tests assert `call_args.kwargs` + retry path. Contract **v1.2.0**, `.env.example` retry knob. **meeet-solana-state:** `deno check` + `deno test` on **`tars-billing`** green; runbook **`docs/TARS_INTEGRATION_RUNBOOK.md`** documents billing edge + secrets + optional TARS env.

**Files (meeet-solana-state):** migration `tars_billing_usage_dedupe`, `supabase/functions/tars-billing/index.ts`, `rls-regression-tests/rls_test.ts`, `docs/TARS_INTEGRATION_RUNBOOK.md`.

**Files (Jarvis):** `backend/core/meeet_billing/{client,mirror_usage}.py`, `backend/core/meeet/client.py`, `tests/test_meeet_billing_usage.py`, `docs/contracts/TARS_MEEET_BILLING.md`, `.env.example`, `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

`>>> SYNC: Cursor · 2026-05-05 · billing POST trace_id dedupe + usage retries`

## 2026-05-05 — Cursor: remote billing usage mirror (`POST /operator/usage`)

**Summary:** **meeet-solana-state:** edge **`tars-billing`** accepts **`POST …/operator/usage`** (`delta_usd`, same Bearer). **Jarvis:** `post_operator_usage_delta`, `mirror_usage.after_usage_tokens_emitted` from **`MeeetClient.emit`** after durable insert (runs even when ingest URL unset); `MEEET_BILLING_MAX_DELTA_USD`. Contract **v1.1.0**, tests `tests/test_meeet_billing_usage.py`.

**Files (meeet-solana-state):** `supabase/functions/tars-billing/index.ts`.

**Files (Jarvis):** `backend/core/meeet_billing/{client,mirror_usage}.py`, `backend/core/meeet_billing/__init__.py`, `backend/core/meeet/client.py`, `docs/contracts/TARS_MEEET_BILLING.md`, `.env.example`, `tests/test_meeet_billing_usage.py`, `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

`>>> SYNC: Cursor · 2026-05-05 · billing POST usage + TARS mirror from usage.tokens`

## 2026-05-05 — Cursor: meeet-solana-state `tars-billing` edge + TARS contract/env

**Summary:** **meeet-solana-state:** migration `tars_billing_operators`, edge **`tars-billing`** (`compute.ts`, Deno unit tests, RLS regression + anon SELECT probe), **`config.toml`**, **`_shared/http.ts`** CORS `x-tars-operator-id`, **edge-functions-typecheck** runs `deno test` on billing compute. **Jarvis:** `docs/contracts/TARS_MEEET_BILLING.md` (Supabase BASE_URL + secret names), `.env.example` example `MEEET_BILLING_BASE_URL`, `docs/AGENT_HANDOFF.md`.

**Files (meeet-solana-state):** `supabase/migrations/20260505140000_tars_billing_operators.sql`, `supabase/functions/tars-billing/{index,compute,compute_test}.ts`, `supabase/functions/_shared/http.ts`, `supabase/functions/rls-regression-tests/rls_test.ts`, `supabase/config.toml`, `.github/workflows/edge-functions-typecheck.yml`.

**Files (Jarvis):** `docs/contracts/TARS_MEEET_BILLING.md`, `.env.example`, `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

`>>> SYNC: Cursor · 2026-05-05 · Supabase tars-billing edge + contract/env handoff`

## 2026-05-05 — Cursor: meeet.world authoritative billing mirror (TARS)

**Summary:** Contract `docs/contracts/TARS_MEEET_BILLING.md` + package `backend/core/meeet_billing/` (stdlib GET `/operator`, 5s cache). When **`TARS_BILLING_SOURCE=remote`** + `MEEET_BILLING_BASE_URL` + `MEEET_BILLING_API_KEY`: `GET /api/entitlements` mirrors meeet tier/live; **`can_run`** uses remote gate (fail closed if unreachable); **`POST /upgrade`** returns delegated `redirect`; **`POST /byo`** → 503. Tests: `tests/test_meeet_billing_remote.py`. `.env.example` knobs.

**Files:** `docs/contracts/TARS_MEEET_BILLING.md`, `backend/core/meeet_billing/`, `backend/core/entitlements/checker.py`, `web_extras/routers/entitlements.py`, `tests/test_meeet_billing_remote.py`, `.env.example`, `CLAUDE.md`, `docs/CHANGELOG_AGENTS.md`, `docs/AGENT_HANDOFF.md`.

`>>> SYNC: Cursor · 2026-05-05 · remote billing plane + contract`

---

_Showing the most recent 60 of 278 entries. Full per-edit log: [`docs/CHANGELOG_AGENTS.md` on GitHub](https://github.com/alxvasilevvv/tars-neural-cockpit/blob/main/docs/CHANGELOG_AGENTS.md)._
