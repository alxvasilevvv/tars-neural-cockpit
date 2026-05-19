# MCP — single-PR consolidated rewrite (close + redo)

> **Author.** Cursor (Sonnet 4.6) parent assistant — W310.
> **Audience.** Cursor implementor lane (or any agent that picks up MCP).
> **Status.** Draft — **gated on operator OK + the 5 closed PRs being formally closed**.
> **Purpose.** Replace the M-wave 5-PR stack (#177→#184, plus #176, #182 if scope aligns) with one consolidated PR that's reviewable end-to-end.

---

## 0. Why close + redo

The original M-wave stack ran:

| PR | Wave | Title | Base | Mergeable? |
|----|------|-------|------|------------|
| #176 | M4 | MCP server (TARS exposes actions to MCP hosts) | main | **CONFLICTING** |
| #177 | M3 | MCP client (drives external MCP servers) | main | **CONFLICTING** |
| #178 | M5 | MCP bridge (external tools as `BridgedPack`) | #177 branch | mergeable into #177 |
| #179 | M5b | `tars mcp` CLI verbs | #178 branch | mergeable into #178 |
| #180 | M6 | MCP pool (`SessionPool`) | #179 branch | mergeable into #179 |
| #184 | M7 | Pool lifecycle (sweeper + `max_concurrency`) | #180 branch | mergeable into #180 |
| #182 | M6-FE | Cockpit bridge panel | main | **CONFLICTING** (depends on #178 surface) |

**Three issues with the current stack.**
1. **#176 + #177 conflict with main** → blocks both lanes from landing.
2. **6 PRs × ~1000-2000 LoC each** = ~10000 LoC across cross-dependent commits — hard to review safely after ~2 weeks of main movement.
3. **Stale base branches** make rebase invasive (cross-cutting changes to `web_extras/app.py` include_router list, `tars/cli/`, shared utilities).

**Decision (operator W310, 2026-05-18):** close all six (and reopen #182 as a follow-up after rewrite), rewrite as one consolidated PR.

---

## 1. Scope of the rewrite

One PR, base `main`, target `main`. Bounded to backend + CLI.

### 1.1 Backend modules
- `backend/core/mcp/client.py` — stdio transport, server registry, primitive ops (M3 from #177)
- `backend/core/mcp/server.py` — TARS-as-MCP-server (M4 from #176)
- `backend/core/mcp/bridge.py` — external MCP tools as `BridgedPack` actions (M5 from #178)
- `backend/core/mcp/pool.py` — `SessionPool` with `max_concurrency` + background sweeper (M6+M7 from #180+#184)
- `backend/core/mcp/__init__.py` — public API

### 1.2 HTTP surface
- `web_extras/routers/mcp.py` — bridge status, pool stats (M6-be from #182 surface, UI deferred)
- Mount in `web_extras/app.py` include_router list

### 1.3 CLI
- `tars/cli/mcp.py` — `tars mcp servers list/add/remove`, `tars mcp bridge bootstrap/list/cache` (M5b from #179)
- Wire into existing `tars` CLI entry-point

### 1.4 Config + docs
- `~/.tars/mcp/servers.json` schema + example
- Operator guide at `docs/MCP_GUIDE.md` (new)

### 1.5 Tests
- `tests/test_mcp_client.py` (in-process MCP echo server)
- `tests/test_mcp_bridge.py` (BridgedPack roundtrip)
- `tests/test_mcp_pool.py` (concurrency, sweeper, eviction)
- `tests/test_mcp_router.py` (HTTP surface)
- `tests/test_mcp_cli.py` (CLI verbs)
- Reuse fixtures from existing tests where possible

---

## 2. NOT in scope (defer to follow-ups)

- Cockpit MCP bridge panel UI (#182) — separate PR after this one, base = main with this PR merged.
- Voice persona fallback L4.2 (#183) — unrelated, rebase separately.
- Install funnel cross-target sync (#175) — unrelated, rebase separately; fix `probe`/qa-agent CI first.
- E2E playbook + deterministic OHLCV (#181) — algotrade scope, rebase separately.

---

## 3. Approach

### 3.1 Branch
`cursor/mcp-rewrite-consolidated` from current `main`.

### 3.2 Build order (commit-by-commit, each independently revertable)
1. `feat(mcp): client (M3) — stdio transport + server registry + primitive ops + tests`
2. `feat(mcp): bridge (M5) — external MCP tools as BridgedPack + tests`
3. `feat(mcp): server (M4) — TARS as MCP server + tests`
4. `feat(mcp): pool (M6+M7) — SessionPool + sweeper + max_concurrency + tests`
5. `feat(mcp): HTTP router (M6-be) + tests`
6. `feat(mcp): tars CLI verbs (M5b) + tests`
7. `docs(mcp): operator guide + servers.json schema`

### 3.3 Review pattern (W309 step 1 lesson)
Before merge, run `gstack-claude review` for independent second opinion. Fix-ups land as a separate commit on the same branch, **not deferred**. Tests grow 1:1 with each finding (see W309 step 1 fix-up commit `545cd4d` for the template — 8 → 20 tests, one new test per Claude finding).

---

## 4. Acceptance criteria

| Criterion | How verified |
|---|---|
| MCP tests green | `pytest tests/test_mcp_*.py -v` |
| Existing tests still green | `pytest tests/ -x` (exclude `-m perf`) |
| HTTP surface live | `curl http://127.0.0.1:8765/api/mcp/bridge/status` returns 200 |
| CLI smoke | `tars mcp servers list` works without crashing |
| No new linter warnings | `ruff check backend/core/mcp/` clean |
| Smoke tests pass | `bash scripts/SMOKE-TEST.command` (the W267 60+ routes test) |
| No regression in FINAL-QA-GATE | `bash scripts/FINAL-QA-GATE.command` green |

---

## 5. Verification protocol (~20 min)

1. Branch off `main` clean.
2. Build commits in order from §3.2.
3. After each commit: `pytest tests/test_mcp_*.py -v` for that slice only.
4. After all commits: full `pytest tests/ -x`.
5. **Manual smoke.** Spawn a real MCP server (e.g. `npx @modelcontextprotocol/server-filesystem /tmp`), register via CLI, call a tool via bridge, verify the call lands.
6. `gstack-claude review`.
7. Apply fix-ups on same branch.
8. Push, open PR, wait for CI. Ignore baseline-red checks: `scan working tree`, `TARS B2B E2E suite (Wave 105)`, `TARS eval suite` — same as W309 step 1.
9. Operator merge.

---

## 6. Rollback criteria

- If §5 manual smoke fails → don't open PR, debug locally first.
- If CI shows real (non-baseline) red → fix or back out.
- If review surfaces structural issue (e.g. wrong public API surface) → redo on a new branch, don't force-push existing PR.

---

## 7. Design intel from the closed PRs

Each of the 5+ closed PRs left useful design choices. **Preserve these in the rewrite — the closed diffs are not garbage, they're the design spec.**

- **#177 (M3 client):** stdio transport works; **chose to NOT support SSE or HTTP MCP transports in v1** (operator can revisit when needed).
- **#178 (M5 bridge):** `BridgedPack` envelope shape **mirrors `DomainPack`** so cockpit treats them identically.
- **#179 (M5b CLI):** `tars mcp` namespace; `servers.json` schema with `name + command + args + env` (NPM scripts as servers work great).
- **#180 (M6 pool):** `SessionPool` reuses live MCP connections; **per-call spawn was 200ms slower** in M6 PR description's benchmark.
- **#184 (M7 lifecycle):** sweeper kills idle sessions after **60s default**; `max_concurrency` prevents fork-bomb when many threads.
- **#176 (M4 server):** TARS exposes its `DomainPack` actions as MCP tools, callable from Anthropic Claude / Cursor / any MCP host.
- **#182 (M6-FE):** bridge status panel design — preserve the layout intent for the follow-up cockpit PR.

---

## 8. References

- `docs/PRODUCT_MASTER_PLAN.md §2.2` — context for why this rewrite is sequenced here
- Closed PRs (read-only intel): #176, #177, #178, #179, #180, #182, #184
- Anthropic MCP spec: <https://modelcontextprotocol.io/>
- `docs/handoff/W309_STEP2_BRIEF.md` — W309 closeout pattern for review + fix-up flow
- `CHANGELOG_AGENTS.md` (top of file) — W309 fix-up commit `545cd4d` as the canonical review-pattern template
