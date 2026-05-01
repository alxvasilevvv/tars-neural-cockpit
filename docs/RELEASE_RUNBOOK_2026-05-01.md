# Release Runbook — 2026-05-01

This runbook covers the **Cursor lane** changes shipped on 2026-05-01,
across both repos (`tars-neural-cockpit` and `meeet-solana-state-941a6045`),
and what the operator + Lovable + Claude need to do to fully activate
them in production.

> Single source of truth for operator/Claude/Lovable to walk this release
> end-to-end. Linked from `docs/SYNC.md` (handoff row 2026-05-01 08:30).

---

## 1. What shipped

### TARS repo (`tars-neural-cockpit`)

- **Branch `cursor/chat-pickup-2026-05-01`** — handoff docs only.
  - `docs/CHANGELOG_AGENTS.md` — log cross-repo Control Tower work.
  - `docs/AGENT_HANDOFF.md` — entry under "Done (running list)".
  - `docs/SYNC.md` — handoff row 2026-05-01 08:30.
  - `docs/ROADMAP_SHARED.md` — Stage 1 ticked items.
  - `docs/RELEASE_RUNBOOK_2026-05-01.md` (this file).
- **Validation:** `pytest -q` → 686 passed, `npm test` (showcase v3) → 63
  passed, `tsc --noEmit` ok, `npm run build` ok.

### Core repo (`meeet-solana-state-941a6045`)

- **PR #6 — `cursor/navbar-test-realign` (test-only):**
  Rewrites `src/test/navbarItemsE2E.test.tsx` to match the new Navbar
  structure (Explore / Economy / Community / Academy with
  `<button aria-haspopup="menu">` triggers). 18/18 navbar assertions
  green; full suite **332 / 337** (5 skipped).
- **PR #7 — `cursor/control-tower-and-bridge-smoke`:**
  - `COORDINATION.md` (lane ownership + integration contract)
  - `docs/CONTROL_TOWER.md` (release gate + secret policy)
  - `docs/TARS_INTEGRATION_RUNBOOK.md` (TARS_ALLOWED_ORIGINS env)
  - `scripts/smoke_tars_bridge.sh`,
    `scripts/smoke_old_core_connectivity.sh`,
    `scripts/smoke_release_gate.sh`
  - `package.json` → `smoke:tars-bridge`, `smoke:core-connectivity`,
    `gate:control-tower`
  - `supabase/functions/tars-{downloads,ingest}` → origin allowlist via
    `TARS_ALLOWED_ORIGINS` (defense-in-depth on top of API-key auth)
  - `SOFT_SMOKE=1` dev flag (skips ingest write step when key absent)

PR links:

- https://github.com/alxvasilevvv/meeet-solana-state-941a6045/pull/6
- https://github.com/alxvasilevvv/meeet-solana-state-941a6045/pull/7

---

## 2. What I deliberately did NOT ship

These are Lovable-lane / Claude-lane and were dropped to avoid conflicts:

- `src/pages/Deploy.tsx` (hardcoded `MEEET_PRICES` / `-20% off`) — Lovable
  is mid-flight on a USD pricing redesign for the same file.
- `src/pages/Tokenomics.tsx` (Liquidity 5%→15%, APY 25%→30%) — Lovable
  added `src/pages/Token.tsx` with the new canonical tokenomics; old
  `Tokenomics.tsx` will be retired by Lovable, no point in patching it.
- `src/pages/Tars.tsx` FAQ tone-down — same lane as the marketing copy
  redesign; defer to Lovable/Claude.
- `supabase/config.toml` cron schedule deletes — these were unstaged
  local cruft; reverted before any commit. Production cron untouched.

If Lovable/Claude want any of these dropped patches as a starting point,
they're in this repo's local reflog and can be re-applied as a Lovable PR.

---

## 3. Operator action items (in order)

### 3.1. Merge order in `meeet-solana-state-941a6045`

1. **PR #6** (test-only, low-risk). After merge, `main` test gate goes
   from 6 failures → 0.
2. **PR #7** (Control Tower). After merge, `npm run gate:control-tower`
   becomes the canonical pre-release gate.

Either order works; both are independent. #6 first is safer because it
makes the PR #7 gate green on `main` immediately.

### 3.2. Redeploy bridge edge functions

After #7 merges:

```bash
# In meeet-solana-state-941a6045 root
supabase functions deploy tars-downloads --project-ref hhpaukjobskcwkxbgecl
supabase functions deploy tars-ingest    --project-ref hhpaukjobskcwkxbgecl
```

### 3.3. Set Supabase secrets

In project `hhpaukjobskcwkxbgecl` (TARS new Supabase) →
Settings → Edge Functions → Secrets:

| Key                          | Value                                                      | Required? |
| ---------------------------- | ---------------------------------------------------------- | --------- |
| `TARS_ALLOWED_ORIGINS`       | `https://meeet.world,https://tars.meeet.world`             | yes       |
| `TARS_INGEST_API_KEY`        | rotated bearer key (32+ chars, random)                     | yes       |
| `TARS_DOWNLOADS_MANIFEST_URL`| `https://tars.meeet.world/api/product/downloads` (default) | no        |

### 3.4. Mirror `TARS_INGEST_API_KEY` on the TARS side

In `tars-neural-cockpit` deployment env:

```env
MEEET_INGEST_URL=https://hhpaukjobskcwkxbgecl.supabase.co/functions/v1/tars-ingest
MEEET_API_KEY=<same value as TARS_INGEST_API_KEY above>
MEEET_CONTRACT_VERSION=1.0.0
MEEET_SOURCE=tars_desktop
```

(Both Mac/Linux desktop ENV files and any CI env that runs the bridge.)

### 3.5. Verify the bridge end-to-end

From any machine with the rotated key:

```bash
export TARS_INGEST_API_KEY=<rotated key>
cd meeet-solana-state-941a6045
npm run smoke:tars-bridge
```

Expected output:

```
[1/2] tars-downloads health check
[2/2] tars-ingest authenticated write check
OK: TARS bridge smoke passed.
```

Then the full gate:

```bash
npm run gate:control-tower
```

(In production CI: do **not** set `SOFT_SMOKE`; the strict gate must
exercise the authenticated ingest write.)

---

## 4. Coordination notes

### For Claude (cockpit + design lane)

- The Navbar redesign on Lovable side broke `navbarItemsE2E.test.tsx` on
  `main`. PR #6 patches that test against the actual Navbar — no UI code
  changes. If you'd rather the test use `data-testid` attributes (which
  would also need a small Navbar.tsx tweak), open a follow-up PR.
- All other Lovable-lane visual surfaces (Deploy.tsx, Token.tsx,
  Tokenomics.tsx, Tars.tsx) are untouched by this release. If anything
  there needs attention, ping with a SYNC row.

### For Lovable (core lane)

- The two Cursor PRs touch only:
  - new files (`COORDINATION.md`, `docs/CONTROL_TOWER.md`,
    `scripts/smoke_*.sh`)
  - additive npm scripts in `package.json`
  - additive env-driven origin gates in `tars-{downloads,ingest}`
  - test-only realignment in `src/test/navbarItemsE2E.test.tsx`
- The origin-gate pattern (returns 403 for non-allowlisted browser
  Origins) overlaps with the recently shipped
  `_shared/http.ts:resolveCorsHeaders` (which only echoes Origin but
  keeps wildcard CORS otherwise). Both can coexist — happy to unify
  in a follow-up if you prefer one or the other.

### For the operator

- Step 3.1 → 3.5 above is the minimum activation path. Roughly 10 min of
  clicks + one terminal session.
- After 3.5 succeeds, the `gate:control-tower` script becomes the gate
  every release crosses going forward.
- If anything in 3.5 fails, **don't merge any further bridge changes**
  until the failure is understood. This is the whole point of the gate.

---

## 5. Rollback

Each shipped piece is rollback-safe:

- **PR #6** → `git revert <merge-commit>` returns the test file to its
  pre-redesign state (which had 6 known failures matching origin/main
  before the Navbar redesign).
- **PR #7** → `git revert <merge-commit>` removes the smoke scripts,
  npm scripts, docs, and the origin gates from the edge functions. The
  bridge falls back to the prior "API key only" auth model.
- Edge function redeploy can be reverted by re-deploying the previous
  Git ref via `supabase functions deploy --version=<sha>` or by the
  Supabase Dashboard's function history.

No DB migrations were touched. No core schema, no core RLS, no core
Edge Function on `zujrmifaabkletgnpoyw` were touched.

---

## 6. Open follow-ups (parking)

- [ ] CI: wire `npm run gate:control-tower` into a GitHub Actions job
      on `main` push (would need `TARS_INGEST_API_KEY` as a repo secret;
      the gate without `SOFT_SMOKE` would exercise a live ingest write).
- [ ] If Lovable prefers single CORS source-of-truth, switch
      `tars-{downloads,ingest}` to import `resolveCorsHeaders` from
      `_shared/http.ts` and drop the local `parseAllowedOrigins`. This
      removes my 403 gate but unifies the origin policy.
- [ ] If the "Главная" link should reappear in the desktop navbar, that
      change is Lovable lane; the test is structured to pick it up
      automatically (just add a TOP_LEVEL row).
