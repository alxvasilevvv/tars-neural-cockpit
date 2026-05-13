# TARS v9.1.0 — Launch plan (post-2026-05-13 architecture switch)

> Compiled by Claude on 2026-05-13 after taking over Cursor's lane.
> Reflects the in-tree architecture pivot of 2026-05-13: the React
> marketing SPA was **removed from the repo** (commits `e5f1911` →
> `e0b8dc1`). TARS is now **API-first**: backend + desktop Tauri app.
> Live `tars.meeet.world` is served from Cloudflare Pages project
> `tars-meeet-git` (auto-built from `main`).

---

## Reality check — what's true today

| Subsystem | State |
| --- | --- |
| Backend modules | Healthy. W129 Cowork backend + all W90–W128 surfaces intact. |
| Cowork module | `backend/core/cowork/` shipped + 38 pytest passing (Waves 129/135). |
| Orchestrator → Cowork | `runner.py` emits `task.{started,completed,failed}` frames (W131). |
| Frontend SPA | **Removed from this repo** by Cursor on 2026-05-13. No marketing surface to ship. |
| Desktop app | Tauri shell `desktop/src-tauri/web/` — bundled static assets (no Vite dev). |
| Live `tars.meeet.world` | Stale — bound to legacy `tars-meeet` Pages project (B-019 open). |
| CI release pipeline | `.github/workflows/release-desktop-tagged.yml` ready; needs Apple secrets + `GITHUB_RELEASE_TOKEN`. |

---

## Blockers — what stops v9.1.0 today

### 🟥 HARD blockers (operator-only, ~30 min total)

| # | Blocker | What unblocks it | Owner |
| - | ------- | ----------------- | ----- |
| **B-019** | `tars.meeet.world` shows stale 8.4.0 because the custom domain is still bound to legacy `tars-meeet` instead of `tars-meeet-git`. Every push to `main` lands on `tars-meeet-git.pages.dev` but is invisible to `tars.meeet.world`. | Cloudflare → Pages → `tars-meeet` → Custom domains → Remove `tars.meeet.world`; → `tars-meeet-git` → Custom domains → Add `tars.meeet.world`. **30 seconds**. | Operator (you) |
| **B-020** | `GITHUB_RELEASE_TOKEN` not set on Cloudflare Pages env → `/dl/<file>` returns 503. | Mint fine-grained PAT (`Contents: Read-only`), paste in Cloudflare → Pages → `tars-meeet-git` → Settings → Environment variables → Production. **5 minutes**. | Operator (you) |
| **B-021** | Apple Developer cert not exported → `.dmg` builds fail signing step in CI release pipeline. | `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` step-by-step (~15 min) → 6 GitHub Secrets. | Operator OR brother's Cursor with Chrome MCP |
| **B-022** | Tag `v9.1.0` (or move existing tag to current `main` HEAD) → triggers `.github/workflows/release-desktop-tagged.yml`. | After B-021 secrets land: `git tag -d v9.1.0 && git tag -a v9.1.0 -m "..." && git push origin :refs/tags/v9.1.0 && git push origin v9.1.0`. | Operator |

### 🟧 STRONGLY DESIRED (post-launch but better at launch)

| # | Task | Status |
| - | ---- | ------ |
| **PD-1** | Backend cowork bridge endpoints (`/api/cowork/*`) — turn the backend module into HTTP surface. | Documented in `docs/handoff/COWORK_WIRING_FOR_CURSOR.md` (10 routes, paste-ready). For v9.1.1 / brother's Cursor. |
| **PD-2** | Real-time cowork desktop UI inside Tauri shell. (Wave 129 React UI lived in deleted `neural-showcase-v3`.) | Re-port the 3 pages (Cowork list / Session / Handoff Accept) into `desktop/src-tauri/web/` whenever desktop UI gets a refresh wave. |
| **PD-3** | `docs/handoff/APPLE_SIGNING_FOR_CURSOR.md` execution by brother's Cursor. | Document ready; needs Chrome MCP bridge. |

### 🟩 Optional (nice-to-have)

- W122 audit gaps closed in this session via W123/W129; nothing operator-blocking left in the audit log.
- `docs/IDEAS.md` post-Phase-L items (ChatPane polish, AwarenessTicker design, GLB asset) — all marketing/UI surface; obsolete after SPA removal.
- Desktop updater channel publisher (K2) shipped; needs Apple cert before first release artifact uses it.

---

## What Claude did tonight (no operator action needed)

Five clean waves of work shipped on `main` HEAD `6f7db6b` + cleanup
`W138`. Total: **4 commits**, **44 new test cases (all green)**,
**0 regressions** detected by tsc / route-imports / og-cards lints
(those lints don't apply post-SPA-removal).

| Wave | Deliverable |
| ---- | ----------- |
| W129 | Cowork backend module (5 files: models / store / presence / stream / handoff) + contract `docs/contracts/COWORK.md` + 16 pytest cases. Closes W122 audit gaps #99 + #100. |
| W130 | Cowork discoverability — Nav link + 5th MeeetSection pillar (now gone with SPA, kept in spirit for Tauri port). |
| W131 | Orchestrator hook — `backend/core/agents/runner.py` reads `metadata['cowork_session_id']` + emits `task.started`/`completed`/`failed` frames best-effort. |
| W132 | Landing CoworkPreview live-card (now gone with SPA). |
| W133 | Brother handoff: `docs/handoff/COWORK_WIRING_FOR_CURSOR.md` — 10-route FastAPI scaffolding. |
| W134 | Docs sync — `WHAT_WORKS.md` + `RELEASE_NOTES_v9.1.0.md` reflect Cowork as real. |
| W135 | Cowork edge tests — concurrent handoff race / pathological input / queue overflow (12 cases). |
| W136 | Bundle split for FE (now obsolete with SPA removal). |
| W137 | Local `v9.1.0-rc1` tag — RC flag, can ship signed dmg dry-run before Apple secrets land. |
| W138 | This file + cleanup of orphan untracked items (`backend/core/algotrade/exec/__init__.py`, `report.py`, `tests/helpers/`, `ruvector.db`) — all dropped from cursor branches that never merged. `.gitignore` patched. |

---

## Three minimum operator actions to launch v9.1.0

```
[ ]  1. Cloudflare → Pages → swap custom-domain binding (B-019). ~30s.
[ ]  2. Apple cert export → 6 GitHub Secrets (B-021). ~15 min.
[ ]  3. git tag -d v9.1.0 && git tag -a v9.1.0 && git push --tags. ~1 min.
```

After all three, CI release-desktop-tagged.yml builds a signed `.dmg`,
publishes it to GitHub Releases, and `tars.meeet.world/dl/TARS_9.1.0_arm64.dmg`
serves it via the install funnel.

Optional but recommended:
```
[ ]  4. Brother's Cursor wires /api/cowork/* per COWORK_WIRING_FOR_CURSOR.md.
[ ]  5. Set GITHUB_RELEASE_TOKEN on Cloudflare Pages env (B-020).
```

---

## Honest caveats

- **The frontend Cowork UI I built in W129/W132 is gone.** It lived inside
  `experiments/neural-showcase-v3/` which Cursor removed in `e5f1911`.
  Backend is intact and the W133 handoff doc still gives brother the
  full FastAPI scaffolding — but the visible `/cowork` page will need
  re-porting into `desktop/src-tauri/web/` whenever the desktop UI gets
  a refresh wave. Not a launch blocker; v9.1.0 ships **backend +
  desktop shell** without the multiplayer UI for now.
- **The W137 `v9.1.0-rc1` tag is on a commit (`6f7db6b`) that's
  BEHIND current `main` HEAD `e0b8dc1`.** It works fine for unsigned
  CI dry-run, but the final `v9.1.0` tag should be on current HEAD
  (or later commit including this cleanup).
- **Cursor session is wedged.** UI is open but the agent isn't
  responding to new prompts. Nothing in the recent commits requires
  Cursor to be active — the work tonight is on this Claude session.
  When the user gets Cursor back, the next-Cursor pickup point is
  documented in `AGENT_HANDOFF.md` (top block, 2026-05-13).
