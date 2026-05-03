# Agent SYNC protocol — Cursor ↔ Cursor ↔ Claude ↔ Lovable

> **Status:** active. Read this BEFORE making any change in this repo.
> Last updated: 2026-05-03 by Cursor (B-001 dist guard + CF token ops note).

This file is the contract between the autonomous agents that touch the
TARS / meeet.world stack. It exists so we can work in parallel without
trampling each other — across machines AND across windows.

---

## 1. Repos in scope (canonical)

| Repo                                                         | Owner / agent              | Canonical remote                                                              | Default branch | Notes                                            |
| ------------------------------------------------------------ | -------------------------- | ----------------------------------------------------------------------------- | -------------- | ------------------------------------------------ |
| **TARS** (this repo, `Jarvis/jarvis`)                        | Cursor + Claude (shared)   | `integration` → `https://github.com/alxvasilevvv/tars-neural-cockpit.git`     | `main`         | Local `origin` is dead (404). Use `integration`. |
| **meeet core** (Lovable-managed, old Supabase)               | Claude (via Lovable)       | `https://github.com/alxvasilevvv/meeet-solana-state-941a6045.git`             | `main`         | Cursor must NOT push directly. Lovable owns it.  |
| **meeet-browser-agent-bootstrap** (this Cursor workspace)    | Cursor                     | `https://github.com/alxvasilevvv/meeet-browser-agent-bootstrap.git`           | `cursor/bootstrap-workspace` | Phase-1 lab + sync docs.                |

If a remote breaks (404, auth fail), do **not** silently invent a new
URL — open a SYNC issue and ping the operator.

---

## 2. Hard rules (no-conflict zone)

1. **Never force-push** to `main` on any repo above.
2. **Never amend / rewrite** commits authored by another agent.
3. **Never commit** files staged or modified by another agent unless they
   are in your declared lane (see §3). When in doubt, leave them alone.
4. **Never commit secrets** (`.env`, `*.key`, `*.pem`, raw API keys).
   `.env.example` only.
5. **Never** change cross-project HTTPS contracts without bumping
   `contract_version` AND adding a paired note in `docs/contracts/`.
6. **Never push directly to meeet core repo from Cursor.** Always relay
   changes through the `core-bridge` Edge Function or open a request
   in `docs/SYNC.md` for Claude / Lovable to apply.

---

## 3. Lane ownership (who owns what)

### Cursor lane (this machine)
- Backend: `backend/`, `web_extras/`, `tests/`, `scripts/` (smoke + ops).
- Cockpit functional wiring: `experiments/neural-showcase-v3/src/lib/**`.
- Desktop: `desktop/src-tauri/src/**`, `desktop/scripts/**`.
- Mobile: `mobile/ios/**`, `mobile/android/**`.
- Control Tower: `Makefile` (smoke targets), `scripts/smoke_*.sh`.
- This file (`docs/SYNC.md`) and `docs/ROADMAP_SHARED.md`.

### Claude Code lane (other machine)
- Cockpit visual polish: `experiments/neural-showcase-v3/src/components/**`,
  `src/index.css`, `src/pages/**`, `design-system/**`.
- Brand assets: `experiments/neural-showcase-v3/public/**` (badges,
  OG images, favicons).
- Public docs / launch comms: `docs/RELEASE_NOTES_*.md`,
  `docs/LAUNCH_ANNOUNCEMENTS.md`, `docs/PRIVACY_POLICY.md`,
  `docs/TERMS_OF_SERVICE.md`, `docs/SECURITY.md`,
  `docs/POST_LAUNCH_*.md`, `docs/AUDIT_*.md`,
  `docs/DESIGN_*.md`, `docs/handoff-claude.md`.
- Tauri desktop assets (built dist): `desktop/src-tauri/web/**` (these
  are build artifacts; Cursor will not touch them).

### Shared (require a SYNC note before edit)
- `CLAUDE.md`, `.cursorrules`, `AGENTS.md`
- `docs/AGENT_HANDOFF.md`, `docs/CHANGELOG_AGENTS.md`, `docs/IDEAS.md`
- `docs/PHASE_L_ROADMAP.md`, `docs/ROADMAP_SHARED.md`, this file
- `docs/contracts/**`
- Top-level `Makefile`, `requirements.txt`, root `package.json` (none
  exists today)

If both agents need to touch a shared file in the same window, the
later author **rebases** on top of the earlier author and adds a
`>>> SYNC: who/when/what` comment in `docs/CHANGELOG_AGENTS.md`.

---

## 4. Branch + commit conventions

- **Branch names:**
  - Cursor: `cursor/<topic>` (e.g. `cursor/agent-sync-protocol`)
  - Claude: `claude/<topic>` (e.g. `claude/wave-52-cockpit-polish`)
  - Hotfixes: `hotfix/<topic>` (any agent, must announce in SYNC).
- **Commit messages:** present tense, scope-prefixed.
  - `cursor: control-tower core-bridge e2e smoke`
  - `claude: cockpit v9.x polish wave 51`
  - First line ≤ 72 chars; body explains the *why*.
- **One PR = one lane.** Don't mix Cursor backend changes with Claude
  visual changes in the same branch.

---

## 5. Push / pull workflow

```bash
# Before starting work (any repo, any agent)
git fetch <canonical-remote>
git status              # must be clean
git checkout -b <agent>/<topic> <canonical-remote>/main

# While working
git add <only-your-lane-files>
git commit -m "<agent>: <scope> <what>"

# Before pushing
git fetch <canonical-remote>
git rebase <canonical-remote>/main   # never merge

# Push
git push -u <canonical-remote> <agent>/<topic>
```

The canonical remote in this repo is **`integration`**, not `origin`.
Until `origin` is fixed, every command above must explicitly name
`integration`.

---

## 6. Cross-machine handoff (the actual protocol)

We do not have a live socket between machines. Sync happens through
**three artifacts in the repo**:

1. `docs/AGENT_HANDOFF.md` — long-form state, "what is open right now".
2. `docs/CHANGELOG_AGENTS.md` — append-only log: who / when / scope /
   files. Latest entry on top.
3. `docs/SYNC.md` (this file) — the rules + the table below.

### Handoff table

When an agent finishes a slice, append a row to the table below in the
PR that lands the slice. Old rows stay forever (audit trail).

| Date (UTC)      | From → To       | Branch / PR                                          | Scope summary                                 | Blocks the other agent? |
| --------------- | --------------- | ---------------------------------------------------- | --------------------------------------------- | ----------------------- |
| 2026-04-30 15:50 | Cursor → Claude | `cursor/agent-sync-protocol` (this PR)               | Sync protocol + shared roadmap + bridge smoke | No                      |
| 2026-04-30 16:25 | Cursor → Claude | `cursor/agent-sync-protocol` (same PR, follow-up)    | Open formal request for meeet handoff package + first-pass meeet review (`docs/REQUEST_TO_CLAUDE.md`, `docs/MEEET_PROJECT_REVIEW.md`) | **Yes — Claude action required** to ship `docs/agent-handoff/*` in meeet core repo |
| 2026-04-30 16:45 | Cursor → Claude | `cursor/agent-sync-protocol` (same PR, follow-up)    | Hotfix proposal for meeet `MobileBottomNav` Vitest regression (`docs/MEEET_HOTFIX_NAVBAR_REGRESSION.md`); freeze `core-bridge` contract (`docs/contracts/CORE_BRIDGE.md` + `relay_event.schema.json`); silence false-positive failed runs in TARS `release.yml` / `release-desktop.yml` via explicit `branches-ignore: ['**']` | **Yes — Claude action required** for the navbar Vitest hotfix in meeet core (2 lines, 2 files); contract freeze + workflow fix is informational |
| 2026-04-30 17:20 | Cursor → Operator+Claude | `cursor/release-yml-yaml-fix` + 6 follow-ups (PRs #1–#7) | Real CI root cause: YAML scanner error on `release.yml:139` (inline `run:` with colon in quoted string). Fixed via `run: |` literal block in PR #6. Confirmed live: post-merge pushes to main no longer mint phantom failed runs. | No |
| 2026-05-01 00:25 | Cursor → Operator+Claude | `cursor/tars-meeet-readiness`                        | Full `tars.meeet.world` integration readiness audit + Cloudflare Pages config (`_headers`, `_redirects`, `functions/_middleware.ts`) + GitHub Action deploy + acceptance gates + ops checklist for Operator-Brother (`docs/TARS_MEEET_READINESS.md`, `docs/TARS_MEEET_OPS_TODO.md`). | **Yes** — Operator must wire DNS + Cloudflare secrets (Steps 1–5 in OPS TODO, ~30 min total) before launch. Claude action: `/api/tars/downloads` proxy on meeet-app + `meeet_session` cookie domain bump (already raised on tars-neural-cockpit#8). |
| 2026-05-01 08:30 | Cursor → Lovable+Claude | `meeet-solana-state-941a6045#6` (navbar test realign), `#7` (Control Tower) | Two PRs in meeet core repo. **#6 (navbar test realign):** test-only fix; the recent Navbar redesign (Explore / Economy / Community / Academy with `<button aria-haspopup="menu">` triggers) broke 6/12 e2e assertions on `main`. PR rewrites `src/test/navbarItemsE2E.test.tsx` against the actual structure (332/337 green). **#7 (Control Tower):** adds `COORDINATION.md`, `docs/CONTROL_TOWER.md`, three smoke scripts (`scripts/smoke_*.sh`), three npm scripts (`smoke:tars-bridge`, `smoke:core-connectivity`, `gate:control-tower`), origin allowlist on `tars-{downloads,ingest}` via `TARS_ALLOWED_ORIGINS` env, and `SOFT_SMOKE=1` dev-only flag for the gate. Cross-repo handoff log appended to `docs/CHANGELOG_AGENTS.md` and `docs/AGENT_HANDOFF.md` here. | **Claude/Lovable action:** review and merge #6 first (test-only, low-risk), then #7. After #7 merges + edge functions redeploy, set Supabase secrets `TARS_ALLOWED_ORIGINS=https://meeet.world,https://tars.meeet.world` and `TARS_INGEST_API_KEY=<rotated>` in `hhpaukjobskcwkxbgecl`. UI commits earlier on Cursor's local main (Deploy.tsx hardcoded prices, Tokenomics rebalance) were dropped — Lovable's parallel redesign already covers that surface. |
| 2026-05-01 15:55 | Cursor → Lovable+Claude | `meeet-solana-state-941a6045#8` (default-EN + qa-suite), TARS `docs/ROADMAP_TO_RELEASE.md` | **Master release roadmap published** in TARS at `docs/ROADMAP_TO_RELEASE.md` (Phases A–D: i18n parity, QA-suite, TARS finalisation, release-readiness gate; with slices, owners, acceptance, calendar, secrets matrix, rollback). **Core PR #8** delivers Phase A + the QA-suite skeleton from Phase B: (1) `LanguageContext` bumps `meeet-lang`→`meeet-lang-v2` so every visitor lands on EN by default and legacy `ru` is deliberately not migrated; (2) clean EN baseline on `Tars.tsx` (full), `Tokenomics.tsx` (SEO meta), `Settings.tsx` (notif/profile/danger); (3) new top-level `qa-suite/` with isolated Playwright config and four probes (`routing.discover`, `i18n.parity`, `navigation.navbar`, `assets.console`) writing a `qa-report/1.0.0` JSON shared with TARS Layer-1 in `scripts/qa_agent/`; (4) bundles the navbar e2e fix from #6 so the branch is green on its own. Validation: 332/337 vitest, build green, qa-suite tsconfig clean. | **Lovable action:** review and merge #8 (after #7 if you prefer; either order works — #8 cherry-picks #6's fix). Then continue the EN parity sweep on the remaining ~38 pages catalogued in ROADMAP §A.2 (`LiveDashboard`, `Referrals`, `ArenaEnhanced`, `Staking`, `Economy`, `Parliament`, `Marketplace`, `Token`, `Evolution`, `Discoveries`, etc.). **Claude action:** review the master roadmap and confirm the calendar in §5; align design-system updates to the QA-suite expectations. Cursor will keep extending qa-suite (deploy mock, agent CRUD, axe a11y, perf) once Lovable lands `data-testid`s on the deploy/agent UI per the qa-suite README. |
| 2026-05-03 16:45 | Cursor → Operator+Lovable | meeet-solana `main` (B-001 infra) + TARS `main` (ops doc) | **meeet.world B-001:** Added `netlify.toml` (redirect mirror), GitHub workflow **B-001 dist guard** (post-`vite build` asserts `dist/install.sh`, `dist/_redirects`, redirect strings in `vercel.json` + `netlify.toml`), `DEPLOY.md` v9 operator smoke. **TARS:** `TARS_MEEET_OPS_TODO.md` bullet — rotate `CLOUDFLARE_API_TOKEN` after Secret Scanning / history scrub; never paste literals. | **Yes** — Operator: new CF token → GH secret → Pages workflow; **Lovable:** Publish prod so `meeet.world` `x-deployment-id` advances (legacy URLs still 404 on stale deploy). |

---

## 7. Cross-project bridge (TARS ↔ Lovable Core)

- **TARS-side ingest** (new Supabase, `hhpaukjobskcwkxbgecl`):
  `POST /functions/v1/tars-ingest` (Bearer + Origin allowlist).
- **Core-side bridge** (old Supabase, `zujrmifaabkletgnpoyw`,
  Lovable-deployed): `core-bridge` with three routes:
  - `GET /health` (200, requires `x-bridge-secret`)
  - `GET /token-stats` (200, allowed Origins)
  - `POST /relay-event` (200, schema-validated, relays to `tars-ingest`)
- Smoke test (run before any release): `make smoke-core-bridge` after
  exporting `BRIDGE_SHARED_SECRET`. Full gate: `make gate-control-tower`.
- All changes to either side **must** add the test before the change.

If Claude (via Lovable) needs to evolve the `core-bridge` schema, open
a SYNC note describing:
- new field name
- type / required / default
- whether it bumps `contract_version` (1.0.0 today)

Cursor will then ship the matching `tars-ingest` patch + the smoke
update in a paired PR.

---

## 8. Secrets & rotation

- Real keys live only in:
  - `.env` (per-machine, gitignored)
  - Supabase Dashboard → Project secrets
  - GitHub Actions secrets (for CI)
- If a secret leaks (chat, log, screenshot), **immediately** rotate:
  - `BRIDGE_SHARED_SECRET` (Lovable's `core-bridge`)
  - `TARS_INGEST_API_KEY` (both projects, must match)
  - any leaked Supabase `service_role`
- After rotation, re-run `make smoke-core-bridge` to confirm green.

---

## 9. Conflict resolution

If two agents accidentally touch the same file:

1. The earlier-pushed branch wins by default.
2. The later agent rebases, resolves, and adds `SYNC:` note in
   `docs/CHANGELOG_AGENTS.md`.
3. If conflict is non-trivial (touching the same function), the later
   agent stops, opens a SYNC entry below describing the collision, and
   waits for operator's call.

### Open conflicts queue
*(none)*

---

## 10. Quick checklist for every PR

- [ ] Branch named `cursor/...`, `cursor-b/...`, `claude/...`
- [ ] Only files in your lane (or pre-announced shared edits)
- [ ] `docs/CHANGELOG_AGENTS.md` updated (top entry, with session tag)
- [ ] If touching backend contract: `contract_version` bump + paired
      doc in `docs/contracts/`
- [ ] If touching the bridge: `make gate-control-tower` is green
- [ ] No `.env`, no raw secrets in diff
- [ ] PR title prefixed with agent name (`[cursor]` / `[cursor-b]` /
      `[claude]`)

---

## 11. Two Cursor sessions on the same machine

The operator now keeps **two Cursor windows** open on the same laptop,
both able to edit this repo in parallel. Treat them as **two
independent agents** with the same lane scope as §3 (the "Cursor
lane"), but with the following extra rules so they don't fight over
shared files / branches / ports:

### 11.1 Branch namespace

| Window | Prefix       | Example                       |
| ------ | ------------ | ----------------------------- |
| A (primary) | `cursor/`    | `cursor/launch-cleanup`        |
| B (helper)  | `cursor-b/`  | `cursor-b/cockpit-copy-pass`   |

If you don't know which window you are, **assume B** until the
operator says otherwise; B is the safer default because A is the one
that already touched `main` today.

### 11.2 Local ports (no clashes)

| Surface                 | Window A           | Window B           |
| ----------------------- | ------------------ | ------------------ |
| TARS backend (uvicorn)  | `127.0.0.1:8765`   | `127.0.0.1:8866`   |
| TARS cockpit preview    | `127.0.0.1:5174`   | `127.0.0.1:5184`   |
| meeet.world prod (serve)| `127.0.0.1:8083`   | `127.0.0.1:8084`   |

If a port is occupied, **do not** kill the other process — switch to
your column above. `lsof -nP -iTCP:<port> -sTCP:LISTEN` tells you who
owns it.

### 11.3 File-level mutex (lightweight)

Before editing a shared file (`docs/AGENT_HANDOFF.md`,
`docs/CHANGELOG_AGENTS.md`, `docs/SYNC.md`, `Makefile`, root
`requirements.txt`, `experiments/neural-showcase-v3/package.json`),
prepend a `>>> SYNC LOCK` comment in `docs/CHANGELOG_AGENTS.md`'s
top entry with `cursor` or `cursor-b` and a 5-min TTL. The other
window respects it for that window. The lock is advisory — if 5 min
have elapsed, take it.

### 11.4 Forbidden in window B by default

Window B should **NOT**, without an explicit operator request:

- merge / squash-merge PRs
- close PRs
- force-push existing branches
- delete remote branches
- rotate any secret or `.env`

These are A's responsibilities so the operator has a single source of
authority for "destructive" actions.

### 11.5 Shared CHANGELOG_AGENTS entries

Both windows append to `docs/CHANGELOG_AGENTS.md`. Mark each entry
with the source window:

```
## 2026-05-01 — Cursor [A] · launch-today snapshot
## 2026-05-01 — Cursor [B] · cockpit copy pass
```

If both windows want to edit the file in the same minute, the second
one rebases on the first.

### 11.6 What window B can do solo (safe lane)

- Read & analyze code (Grep / Glob / SemanticSearch).
- Run pytest / vitest / npm scripts.
- Push **new** branches under `cursor-b/...` and open PRs.
- Edit cockpit copy / page wording (lane overlap with Claude is OK
  here — Claude lane wins on visuals).
- Add tests / fixtures / fixtures' data files.
- Update its own `cursor-b/...` branch via `git rebase
  origin/main`.

If unsure — **ping the operator and pause**. The cost of pausing is
seconds; the cost of rewriting another agent's commit is minutes.
