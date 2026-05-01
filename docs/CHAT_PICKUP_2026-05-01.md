# Chat pickup — 2026-05-01 15:09 UTC+7

> **Why this file exists:** the Cursor multi-root workspace migration
> (`move_agent_to_root`) cannot move the active chat session — internal
> Cursor blob ref from turn 92 is missing. Operator chose to open the
> existing workspace `~/Projects/tars-meeet.code-workspace` and
> continue in a fresh chat there. This file is the one-shot handoff.

## First five things to do in the new chat

1. Read `docs/AGENT_HANDOFF.md` (existing canonical pointer).
2. Read **the latest 5 entries** of `docs/CHANGELOG_AGENTS.md` (the
   four 2026-05-01 entries cover everything below).
3. Read this file (`docs/CHAT_PICKUP_2026-05-01.md`) — that's where
   you are now.
4. Read TARS#8 issue thread on GitHub:
   `gh issue view 8 --repo alxvasilevvv/tars-neural-cockpit --comments`.
   Pay attention to the last two Cursor sit-rep comments
   (`#issuecomment-4358343858` and `#issuecomment-4358364061`).
5. `make qa-agent` once to confirm the live state matches what's in
   §"Live state" below.

## Active git remote (was just cleaned up)

```
origin  https://github.com/alxvasilevvv/tars-neural-cockpit.git  ← single canonical
```

The previous session removed the dead `Alvasilev12/tars` remote that
was sitting under the name `origin`, and dropped the duplicate
`integration` alias. There is also one synthetic branch
`origin/cursor/bootstrap-workspace` (off `main`, no commits) created
to satisfy Cursor's workspace migration handshake — leave it or
delete with `git push origin --delete cursor/bootstrap-workspace`,
nothing depends on it.

## Live state (verified at 14:42 UTC+7)

QA Agent against `https://tars.meeet.world/` returned **YELLOW with 2
WARN, 0 FAIL, 3 SKIP**:

```
WARN  schema.sitemap        meeet.world sitemap missing tars.meeet.world entries (Lovable lane)
WARN  api.client_error      schema OK but BRIDGE_SHARED_SECRET not pasted yet (operator)
SKIP  api.core_bridge_health        BRIDGE_SHARED_SECRET not provided
SKIP  api.relay_roundtrip           BRIDGE_SHARED_SECRET not provided
```

Everything in Cursor's lane is green. Two operator-only gates remain:

- **`make ops-bridge-secret`** — paste `BRIDGE_SHARED_SECRET` once;
  flips the 3 SKIP + 1 WARN to PASS in one shot.
- **`tars-admin` Cloudflare token rotation** — old token leaked into
  git history before scrubbing; rotate at Cloudflare → My Profile →
  API Tokens, then update GitHub Actions secrets.

## What just shipped (all merged today)

| PR | Branch | Summary |
|----|--------|---------|
| #28 | `cursor/cors-frame-ancestors` | CSP `frame-ancestors 'self' https://meeet.world` + CORS allowlist on `/api/product/*` (TARS#8 task 3b enabler + 5). |
| #29 | `cursor/unified-telemetry-spec` | `docs/contracts/UNIFIED_TELEMETRY.md` drop-in spec (TARS#8 task 3a). |
| #27 | (earlier today) | Desktop `v0.1.0-rc.1` release notes corrected from tag-push to `workflow_dispatch`. |
| #26 | (earlier) | TARS CHANGELOG sit-rep entry covering cross-repo phase1-lab work. |
| #25 | (earlier) | SPA-200 regression suite + credential sentinel + ops one-shot. |
| #24 | (earlier) | Pytest contract aligned to `release-desktop-tagged.yml`. |
| #23 | (earlier) | Pages SPA HTTP 200 fix + desktop version triad. |

In `meeet-browser-agent` (sister repo): phase1-lab `lab-ask` was
hardened — provider call layer extracted to `models.ts` with 16 Deno
tests, integrated into pytest via `tests/test_lab_ask_deno.py`, new
`pyproject.toml` and `Makefile`.

## What's still open

### Cursor lane — autonomous, can start any time
1. **Lighten current PR-babysitting load** — there are no open PRs
   right now, so this is idle.
2. **Synthetic monitor SLO refinement** — if any of the WARN-grade
   probes have flapped overnight, tune thresholds in
   `scripts/qa_agent/probes.py`.
3. ~~**Receipt-Ledger bridge spec stub**~~ — **shipped** (PR #36,
   2026-05-01 22:15 UTC+7) at `docs/contracts/RECEIPT_LEDGER.md`
   (DRAFT v0.1). Mirrors Claude's `TarsReceipt` interface from
   TARS#8. Producer side (Lovable / meeet.world Edge Functions) is
   the next blocker.
4. ~~**TARS pricing tier feature gates skeleton**~~ — **shipped**
   (same PR #36) at `experiments/neural-showcase-v3/src/lib/tier.ts`
   with `TIER_GATES`, `useTier()`, `resolveTierFromReceipts`,
   `tierAllows`, plus 23-case `tier.test.ts`. Producer URL read
   from `VITE_TARS_TIER_URL` — `null` today; one-line flip when
   Lovable lands `/functions/v1/tars-tier`.

### Cursor lane — needs Claude/Lovable input first
- **Rate-limit SLA** for `/api/product/*` — token-bucket numbers.
- **Receipt-Ledger consumer shape** — exact fields meeet.world wants.
- **Tier → feature gate map** — which cockpit features unlock at
  Pro / Business / Lifetime.

These three are the open questions in the **last sit-rep on TARS#8**
(comment `#issuecomment-4358364061`); reply there to unblock.

### Claude / Lovable lane — pending on their side
- Task 1a/b/c — payment + agent + staking.
- Task 2 — 5 production-ready test agents.
- Task 3a — meeet half of `unified_funnel` (Cursor shipped the spec
  in PR #29).
- Task 3b — meeet.world side iframe at `/cockpit` (Cursor unblocked
  CSP in PR #28).
- Task 4 — meeet.world pricing tiers backend.
- Task 5 — Supabase secrets, RLS audit, sitemap canonical-flip.

## Tooling cheat-sheet

```bash
# Run the full pytest suite (Jarvis side)
PYTHONPATH=. .venv/bin/python -m pytest -q tests

# Run the QA agent locally against prod
make qa-agent

# Run cockpit type-check + 63-case vitest
cd experiments/neural-showcase-v3 && npm run typecheck && npm test

# Operator one-shot: paste BRIDGE_SHARED_SECRET into Pages env + GH secrets
./scripts/ops_set_bridge_shared_secret.sh
# (or: make ops-bridge-secret)

# Open a PR
gh pr create --repo alxvasilevvv/tars-neural-cockpit --base main --head <branch> --title ... --body ...
```

## How to find the previous chat's full history

The transcript JSONL lives at:
`/Users/alien/.cursor/projects/Users-alien-Projects-meeet-browser-agent/agent-transcripts/06d9857f-a106-41c1-ba32-53855a0cf9f8/06d9857f-a106-41c1-ba32-53855a0cf9f8.jsonl`

Search it for keywords (PR numbers, file names, error strings) rather
than reading top-to-bottom — it's huge.
