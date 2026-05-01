# TARS × meeet.world — shared roadmap

> Read with `docs/SYNC.md`. This is the single board both Cursor and
> Claude work from. Operator owns the order; agents own the lanes.
>
> Last refreshed: 2026-04-30 by Cursor.

---

## Anchor reality (today)

- **TARS host stack** (this repo): backend feature-complete through
  Phase M (Wallets + Agents + Roles + Vision). 671 pytest + 56 vitest
  + 18 swift green at the time of writing. See `docs/AGENT_HANDOFF.md`
  for the long-form state.
- **TARS Supabase (new):** `hhpaukjobskcwkxbgecl`. Holds
  `tars-downloads`, `tars-ingest`, `tars_event_ingest`. Allowlist:
  `https://meeet.world`, `https://tars.meeet.world`.
- **Core Supabase (Lovable, old):** `zujrmifaabkletgnpoyw`. Holds the
  full meeet.world product DB + the freshly-deployed `core-bridge`
  Edge Function (`/health`, `/token-stats`, `/relay-event`).
- **End-to-end bridge** between the two is live and verified:
  `make smoke-core-bridge` passes (PASS, persisted=true).

---

## Lane split (matches `docs/SYNC.md` §3)

```
+----------------- CURSOR ----------------+    +---------------- CLAUDE ----------------+
| backend / web_extras / tests            |    | landing & cockpit visuals              |
| desktop sidecar / mobile pairing        |    | brand assets (badges, OG, favicons)    |
| control tower (smoke, gate, bridges)    |    | public docs / launch comms             |
| sync protocol + shared roadmap          |    | tauri build dist (artifacts)           |
+-----------------------------------------+    +----------------------------------------+
            \                                                /
             \                                              /
              v                                            v
              +--------------- LOVABLE -------------------+
              | meeet.world frontend + old Supabase       |
              | core-bridge Edge Function                 |
              +-------------------------------------------+
```

---

## Stages (sequenced, one card = one PR-sized slice)

Legend: `[ ]` open · `[~]` in progress · `[x]` done · `[CU]` Cursor ·
`[CL]` Claude · `[LV]` Lovable.

### Stage 0 — Foundation (DONE)
- [x] [CU] `core-bridge` end-to-end smoke (`scripts/smoke_core_bridge_e2e.sh`)
- [x] [CU] `make gate-control-tower` (cockpit-tsc + vitest + bridge smoke)
- [x] [LV] `core-bridge` deployed in old Supabase
- [x] [CU] `docs/SYNC.md` + `docs/ROADMAP_SHARED.md`

### Stage 1 — Sync hardening (this week)
- [ ] [CU] Push `cursor/agent-sync-protocol` to integration, open PR
- [ ] [CL] Read SYNC.md, append handoff row, ack on next push
- [ ] [CU] Add a `make smoke-core-bridge` step to CI (Github Actions)
- [ ] [CU] Rotate exposed secrets (`BRIDGE_SHARED_SECRET`,
      `TARS_INGEST_API_KEY`); re-run gate
- [ ] [LV] Confirm rotated values landed in `core-bridge` env
- [x] [CU] Add origin allowlist on `tars-ingest` and `tars-downloads`
      (`TARS_ALLOWED_ORIGINS` env, defaults `meeet.world,tars.meeet.world`).
      Shipped via `meeet-solana-state-941a6045#7`.
- [x] [CU] Cross-lane Control Tower scaffolding in core repo
      (`COORDINATION.md`, `docs/CONTROL_TOWER.md`, `npm run gate:control-tower`,
      `SOFT_SMOKE=1` for dev). Shipped via `meeet-solana-state-941a6045#7`.
- [x] [CU] Realign `navbarItemsE2E.test.tsx` with the new Lovable Navbar
      structure (Explore/Economy/Community/Academy + dropdown buttons).
      Shipped via `meeet-solana-state-941a6045#6` (test-only, no UI code).
- [x] [CU] Master release roadmap published in
      `docs/ROADMAP_TO_RELEASE.md` (Phases A–D, slices, owners,
      acceptance, calendar, secrets matrix, rollback). The single source
      of truth for "what is left and who owns it".
- [x] [CU] **Default-EN public surface** — bumped `meeet-lang` →
      `meeet-lang-v2` in `LanguageContext`; legacy `ru` is intentionally
      not migrated. Tars/Tokenomics/Settings translated to clean EN
      baseline. Shipped via `meeet-solana-state-941a6045#8`.
- [x] [CU] **QA browser suite (Phase B skeleton)** — new top-level
      `qa-suite/` with isolated Playwright config, four probes
      (`routing.discover`, `i18n.parity`, `navigation.navbar`,
      `assets.console`), JSON report schema (`qa-report/1.0.0`)
      shared with TARS Layer-1 in `scripts/qa_agent/`. Shipped via
      `meeet-solana-state-941a6045#8`.
- [ ] [LV] Review + merge #6 then #7 (or #8 directly — bundles #6's fix)
      in `meeet-solana-state-941a6045`.
- [ ] [LV] After #7 merges, redeploy `tars-{downloads,ingest}` and set
      `TARS_ALLOWED_ORIGINS` + rotated `TARS_INGEST_API_KEY` secrets in
      `hhpaukjobskcwkxbgecl`.
- [ ] [LV] Continue EN parity sweep on remaining ~38 pages catalogued in
      `docs/ROADMAP_TO_RELEASE.md` §A.2 (`LiveDashboard`, `Referrals`,
      `ArenaEnhanced`, `Staking`, `Economy`, `Parliament`, `Marketplace`,
      `Token`, etc.).
- [ ] [LV] Add `data-testid` selectors to the deploy plan cards / CTA
      and the agent CRUD UI so Cursor can extend qa-suite with deploy
      mock + agent CRUD probes (per `qa-suite/README.md`).
- [ ] [CL] Wire `meeet.world` landing CTA to `GET /api/product/downloads`
      (or static export thereof). See `docs/contracts/MEEET_DOWNLOADS.md`.
- [ ] [CL] Review the master release roadmap and confirm the calendar in
      `docs/ROADMAP_TO_RELEASE.md` §5; align design-system updates to the
      qa-suite expectations.
- [ ] [CU] Extend qa-suite with `forms.*`, `deploy.flow.mock`,
      `agents.crud`, `a11y.axe`, `perf.lcp`, `api.tars-bridge`,
      `api.core-rest` probes (Phase B continuation).
- [ ] [CU] Wire `make gate-release` aggregator command per
      `docs/ROADMAP_TO_RELEASE.md` §4 (Phase D).

### Stage 2 — tars.meeet.world public alpha (1–2 weeks)
- [ ] [CU] Backend: ship Phase O follow-ups already queued in
      `docs/AGENT_HANDOFF.md` § Next Cursor block (none open at the time
      of writing — confirm before starting).
- [ ] [CL] Cockpit chrome polish: ⌘K palette, ThreadTimeline, ChatPane
      hover/motion/copy (per `design-system/tars/MASTER.md`).
- [ ] [CL] Landing download CTAs final visual pass (icons, version
      pulse, sha256 affordance).
- [ ] [CU] Updater channel CI: real signed `.dmg`/`.exe` + manifest.
- [ ] [CL] Brand artefacts: favicon, OG card, social previews from v3
      palette.
- [ ] [LV] Cross-link: meeet.world hero references TARS, TARS landing
      references meeet.world; both share the OG palette.

### Stage 3 — Sync layer 1.1.0 (Phase L5 finish)
- [ ] [CU] Persistent host keyring (Keychain / DPAPI / secret-tool).
- [ ] [CU] Pairing relay rate-limit on meeet side (LV pairs with CU).
- [ ] [CL] Pairing flow visual (host fingerprint pulse, accept-token
      sheet, mobile scan UX) per `docs/contracts/L5_PAIRING_DRAFT.md`.
- [ ] [LV] meeet.world `/pair/<id>` short-URL handler proxying to TARS.

### Stage 4 — Mobile companions
- [ ] [CU] iOS QR + sync polish on `mobile/ios/TARSCompanion/`.
- [ ] [CU] Android Compose pairing + wallet on `mobile/android/`.
- [ ] [CL] Mobile pairing screen visual treatment + walkthrough copy.

### Stage 5 — Marketplace + planner (Phase L6 / L7)
- [ ] [CU] Skill marketplace v1 (manifest schema + signed install).
- [ ] [CL] Marketplace landing surface (browse, install, ratings).
- [ ] [LV] Optional: discovery widget on meeet.world.

---

## Open contracts (do not silently change)

| Contract                  | File                                          | Pinned at |
| ------------------------- | --------------------------------------------- | --------- |
| meeet downloads manifest  | `docs/contracts/MEEET_DOWNLOADS.md`           | 1.0.0     |
| meeet event ingest        | `backend/core/meeet/events.py` (TARSEvent)    | 1.1.0     |
| Pairing handshake         | `docs/contracts/L5_PAIRING_DRAFT.md`          | draft     |
| Analytics                 | `docs/contracts/ANALYTICS.md`                 | 1.0.0     |
| TARS subdomain wiring     | `docs/contracts/TARS_SUBDOMAIN.md`            | 1.0.0     |
| Core bridge (new today)   | `scripts/smoke_core_bridge_e2e.sh`            | 1.0.0     |

Bumping any of these requires a paired PR from both lanes
(producer + consumer) and a row in `docs/CHANGELOG_AGENTS.md`.

---

## Daily ritual (low ceremony)

1. Pull latest `integration/main` (or your repo's canonical remote).
2. Read top of `docs/CHANGELOG_AGENTS.md` (latest 1–2 entries).
3. If touching shared files (see SYNC §3), check the open conflicts
   queue in SYNC §9.
4. Start your slice on a `cursor/...` or `claude/...` branch.
5. When done: append handoff row to SYNC §6 + entry to
   `docs/CHANGELOG_AGENTS.md` + push.
