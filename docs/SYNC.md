# Agent SYNC protocol — Cursor ↔ Claude ↔ Lovable

> **Status:** active. Read this BEFORE making any change in this repo.
> Last updated: 2026-04-30 by Cursor.

This file is the contract between the autonomous agents that touch the
TARS / meeet.world stack from different machines. It exists so we can
work in parallel without trampling each other.

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

- [ ] Branch named `cursor/...` or `claude/...`
- [ ] Only files in your lane (or pre-announced shared edits)
- [ ] `docs/CHANGELOG_AGENTS.md` updated (top entry)
- [ ] If touching backend contract: `contract_version` bump + paired
      doc in `docs/contracts/`
- [ ] If touching the bridge: `make gate-control-tower` is green
- [ ] No `.env`, no raw secrets in diff
- [ ] PR title prefixed with agent name (`[cursor]` / `[claude]`)
