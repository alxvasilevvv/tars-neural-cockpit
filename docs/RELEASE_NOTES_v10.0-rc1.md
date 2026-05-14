# TARS v10.0.0-rc.1 — Wave A + B + C bundled

> Released: 2026-05-15. Release-candidate channel.
> Bundles Wave A (W237-W249, shipped as v9.3.0-beta1), Wave B
> (W250-W259), and Wave C (W260-W263) into a single tag.
>
> Successor to: `v9.3.0-beta1` (Wave A only).
> Next step toward: `v10.0.0` GA — see §10 below.

This is the **release candidate** for v10.0 GA. Three waves of work
land in one tag:

- **Wave A** closed the Cursor parity gap on the dev-overlap surface
  (already shipped as `v9.3.0-beta1`).
- **Wave B** built TARS-unique edge — features Cursor cannot copy
  without redesigning its core.
- **Wave C** moved beyond Cursor — the surfaces Cursor structurally
  cannot serve (T2T code review, on-prem, voice pair programming,
  agent marketplace).

After Wave C closed at W263 (on-prem deployment kit), the master roadmap
in `TARS_MASTER_DOC.md` §6 marks Wave A/B/C complete. Only v10.0 GA
polish remains — operator items + a 1-week soak. See §10.

---

## §1. Highlights vs v9.3.0-beta1

The seven things that matter most in the leap from beta1 → rc1:

1. **Voice-driven Composer (W253).** Speak a multi-file refactor;
   TARS proposes a plan, shows diff preview, accepts your "merge that"
   and emits a signed receipt per accepted hunk. The killer voice demo.
2. **`tars-tab` VS Code extension scaffold (W254).** Public on the
   marketplace listing (publish gate after rc1 soak). Cursor refugees
   can stay in VS Code and still talk to TARS.
3. **Receipt-anchored audit explorer (W255).** Searchable timeline
   over the W67 receipt ledger with Solana proof links + one-click
   compliance bundle export.
4. **Domain-pack-aware Composer (W256).** Wealth pack pins `tax.py`,
   product pack pins `roadmap.md`. Each pack carries its own prompt,
   rule overlay, and action vocabulary.
5. **SOC2 Type II readiness doc + GDPR data export + annual compliance
   bundle (W257).** The full audit-grade package, ready for a sales
   conversation with a regulated buyer.
6. **T2T code review handoff (W260).** My agent hands the diff to
   your agent; both sign the receipt; meeet.world relayer escrow
   pays the reviewer in $MEEET.
7. **On-prem TARS deployment kit (W263).** Docker compose stack +
   one-line installer + SAML/OIDC + Postgres + systemd unit + 435-line
   deployment guide. The first on-prem-ready release.

Plus the agent marketplace v0 (W261) and voice-first pair programming
in Composer (W262).

---

## §2. What's new — Wave B (W250-W259)

The 10-item table in `TARS_MASTER_DOC.md` §6.2.

### Code surface

- **W253 — Voice-driven Composer.** `backend/core/composer/` with
  `plan.py`, `runner.py`, `diff.py`. Multi-file refactor proposes a plan,
  renders a diff preview, accepts/rejects per hunk, emits a receipt for
  every accepted hunk.
  `experiments/neural-showcase-v3/src/pages/Composer.tsx`.
- **W254 — `tars-tab` VS Code extension scaffold.** Lives at
  `vscode-extension/`. Chat + composer bridge + receipt panel. Talks
  to the local TARS sidecar over loopback. Publish gate after rc1 soak.
- **W256 — Domain-pack-aware composer.** Per-pack prompts, rules, and
  action vocabularies (`backend/core/composer/packs/`). Composer reads
  the active pack on every turn.

### Compliance

- **W255 — Receipt-anchored audit explorer.** Searchable timeline over
  `backend/core/receipts/`. Filters by user / day / action; one-click
  Solana proof links; export bundle includes Merkle siblings.
  `experiments/neural-showcase-v3/src/pages/AuditExplorer.tsx`.
- **W257 — SOC2 + GDPR + annual compliance bundle.** Three pieces:
  - `docs/SOC2_TYPE_II_READINESS.md` — control mapping, evidence
    pointers, gap list.
  - `web_extras/routers/gdpr.py` — `/api/gdpr/export`,
    `/api/gdpr/delete`, `/api/gdpr/portability`.
  - `scripts/COMPLIANCE-BUNDLE.command` — annual bundle generator.

### Background plumbing

- **W258 — Real launchd background agents.** `~/Library/LaunchAgents/`
  plist authored from `backend/core/daemon/`. Persistent across reboots
  with backoff + log rotation. Linux systemd parity already shipped in
  W153.
- **W259 — VS Code marketplace publish prep.** Asset list, manifest,
  signing scaffolding. Publishing flips after rc1 soak.

---

## §3. What's new — Wave C (W260-W263)

The 6-item table in `TARS_MASTER_DOC.md` §6.3.

### Multiplayer code review

- **W260 — T2T code review handoff.** Composer plans flow between
  agents on different TARS instances with a signed approval contract.
  Reviewer earns $MEEET via meeet.world relayer escrow.
  `backend/core/t2t_review/` + `web_extras/routers/t2t_review.py`.

### Agent economy

- **W261 — Agent marketplace v0.** Third-party agents publish via the
  Skill SDK (W95). Browse + install + rate at
  `/marketplace/agents`. 70/30 revenue split via meeet.world payouts.
  `backend/core/marketplace/agents.py` + frontend page.

### Killer voice demo

- **W262 — Voice-first pair programming in Composer.** End-to-end
  voice loop: wake-word → STT → composer plan → narrate the plan →
  accept by voice → diff applied → TTS confirmation + receipt. 20-min
  zero-click sessions verified in repro tests.

### On-prem

- **W263 — On-prem TARS deployment kit.** Full self-hosted stack for
  enterprise / fund / regulated deployments:
  - `scripts/ONPREM-DEPLOY/docker-compose.yml` — backend + watchdog +
    Postgres + nginx + optional meeet-mock.
  - `scripts/ONPREM-DEPLOY/Dockerfile.backend` — Python 3.12 + deps +
    uvicorn entrypoint.
  - `scripts/ONPREM-DEPLOY/Dockerfile.frontend` — nginx + cockpit bundle.
  - `scripts/ONPREM-DEPLOY/install.sh` — one-line installer
    (`curl -L https://meeet.world/install-tars-onprem | bash`).
  - `scripts/ONPREM-DEPLOY/tars-onprem.service` — systemd unit.
  - `scripts/ONPREM-DEPLOY/.env.onprem.example` — every env var with
    `<generate>` placeholders.
  - `backend/core/onprem/local_auth.py` — drop-in replacement for
    meeet.world auth when `MEEET_MODE=onprem`. HS256 JWT + SAML/OIDC.
  - `backend/core/onprem/pg_migrations.py` — Postgres schema parity
    with the ~21 SQLite stores. Idempotent migrator runs at boot.
  - `docs/ONPREM_DEPLOYMENT_GUIDE.md` — 435-line operator playbook
    covering hardware, install, IdP setup, backup/restore, monitoring,
    air-gapped deployment, hardening.

---

## §4. What changes when MEEET_MODE=onprem

Single env flag flips identity, billing, telemetry, and storage from
the meeet.world cloud path to the operator's infra. Full delta in
`docs/ONPREM_DEPLOYMENT_GUIDE.md` §4. Quick summary:

| Surface | Cloud (default) | On-prem |
|---------|----------------|---------|
| Identity | meeet.world magic-link / OAuth | Local accounts OR SAML/OIDC IdP |
| Tier | `/api/billing/tier` from meeet.world | `users.tier` column, admin-managed |
| Usage events | HMAC POST to meeet.world | Written to `usage_events` table only |
| Storage | ~21 SQLite files in `~/.tars/` | Single Postgres database |
| Receipts anchor | Solana mainnet via meeet.world wallet | Opt-in, operator's keypair |
| Marketplace | meeet.world catalog | Local `marketplace_listings` table |
| Auto-update | Tauri updater pulls from meeet.world | `docker compose pull` |

Cockpit UI, all routers, voice/receipt/privacy paths are unchanged.

---

## §5. Breaking changes

None at the code surface. v10.0-rc.1 is fully back-compat with
v9.3.0-beta1: every endpoint, env var, and SQLite schema continues to
work.

The on-prem code paths are additive — they only activate when
`MEEET_MODE=onprem` is set. Existing `.app` users see zero behavioural
delta.

---

## §6. Migrations

Nothing for `.app` users. The W231 auto-bootstrap continues to handle
SQLite schema additions on first boot after upgrade.

For on-prem deployments, `backend/core/onprem/pg_migrations.py` runs
automatically as the backend container's entrypoint. Three migrations
land in v10.0-rc.1:

- `20260514_initial_schema` — users, sessions, receipts, usage,
  tasks, notepad, memory, codebase, cowork, compliance, workspaces.
- `20260514_rules_mentions_clone` — rules, mention_cache,
  clone_messages.
- `20260515_marketplace_composer` — marketplace_listings,
  marketplace_installs, composer_plans, composer_diffs.

Idempotent — re-runs are safe.

---

## §7. Known limitations

- **Wave A operator-blockers unchanged.** Apple Developer cert path
  still requires the operator's `.p12`. Signed Windows / Linux
  installers still need their respective platforms.
- **Brother's billing endpoints reconciliation.** v10.0-rc.1 wires the
  on-prem fallback path; cloud path still waits on
  `/api/billing/usage`, `/api/billing/topup`, `/api/billing/tier` going
  live. `bash scripts/CHECK-MEEET-LIVE.command` verifies status.
- **VS Code extension publish gate (W254 / W259).** Scaffolded but not
  yet pushed to the marketplace; publishing happens after rc1 soak.
- **T2T code review reviewer pool (W260).** Bootstrapped from cowork
  session participants; open-network reviewer matching is GA + 1 wave.
- **On-prem OIDC callback (W263).** `idp_callback_exchange` is a
  documented stub awaiting an authlib-based implementation; the
  password-login path is fully working today. See deployment guide §5.
- **Agent marketplace payouts (W261).** Publishes work via the Skill
  SDK; revenue-share payout schedule is monthly batched on meeet.world.

---

## §8. Upgrade path

### .app users

```bash
git pull origin main
bash scripts/REBUILD-TARS-APP.command
```

REBUILD rebuilds the Tauri .app, copies to `/Applications/TARS.app`,
clears Gatekeeper quarantine, launches. ~30s incremental.

After rebuild, restart the backend if it was running:

```bash
bash scripts/backend-up.command
bash scripts/SMOKE-TEST.command   # verify all routes return 2xx
```

### On-prem users

```bash
cd /opt/tars
git fetch --tags
git checkout v10.0.0-rc.1
docker compose pull
docker compose up -d backend
```

`pg_migrations.py` runs on container boot. Watch the logs to confirm:

```bash
docker compose logs backend --tail=20 | grep migration
```

Should print: `migrations applied: 20260515_marketplace_composer` (or
`schema up-to-date` if you're already current).

---

## §9. Commits in this release

### Wave A (W237-W249) — bundled as v9.3.0-beta1
See `docs/RELEASE_NOTES_v9.3.0-beta1.md` §"Commits in this release".

### Wave B (W250-W259)
```
582eb07  W250  macOS codesign + notarize pipeline + Apple Developer setup guide
1cd3d91  W251  v9.3.0-beta1 release prep — notes, CHANGELOG, version bumps
7af35d9  W252  marketing collateral for v9.3.0-beta1 — twitter, HN, PH, blog, demo spec
36e6275  W253  voice-driven Composer — multi-file edits via voice + diff preview + receipt anchoring
959cf20  W254  tars-tab VS Code extension scaffold — chat + composer bridge + receipt panel
d7a6bcb  W255  receipt-anchored audit explorer — searchable timeline + Solana proof + export bundle
afb77ee  W256  domain-pack-aware composer — per-pack prompts, rules, action vocabulary
d127e32  W257  SOC2 Type II readiness doc + GDPR export + annual compliance bundle
bcb6fd0  W258  real launchd bg-agents + VS Code marketplace publish prep (W259 folded in)
```

### Wave C (W260-W263)
```
96918e8  W260  T2T code review handoff — composer plans flow between agents with signed approval
f2c7a0e  W261  agent marketplace v0 + W262 voice-first pair programming in Composer
<this>   W263  on-prem deployment kit + W264 v10.0-rc1 release prep
```

---

## §10. Top 5 things to ship v10.0 GA

What stands between rc1 and the GA tag:

1. **Operator burns in v10.0-rc.1 for 1 week** on Alien's main host
   (`alienram@icloud.com`). `bash scripts/SMOKE-TEST.command` every
   24h; any failing route blocks the GA cut.
2. **Brother goes live on the three billing endpoints**
   (`/api/billing/usage`, `/api/billing/topup`, `/api/billing/tier`).
   The tier-cap UX (W242) falls back to local replay today; GA wants
   the cloud reconciliation path verified end-to-end. Coordination
   doc: `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md` (refreshed at W233).
3. **Apple Developer .p12 in CI** so every release tag auto-ships a
   signed + notarized .dmg. `scripts/SIGN-AND-NOTARIZE.command` is
   ready; only the operator-blocked cert + GitHub Actions secret are
   missing. See `docs/APPLE_SIGNING_SETUP.md`.
4. **VS Code extension publishes to the marketplace.** Scaffold +
   manifest ready (W254 + W259); first publish + listing tested.
5. **One paying on-prem customer on the v10.0 image.** End-to-end
   install via `scripts/ONPREM-DEPLOY/install.sh`, OIDC wired,
   Prometheus + backup playbook drilled. The presence of a real
   deployment is the proof the kit works.

Cut tag: `bash scripts/RELEASE-v10.0-rc1.command` (already prepared in
W264). For GA, swap the version constants from `10.0.0-rc.1` →
`10.0.0` and reuse the same script template.

---

## §11. Acknowledgments

- **Operator:** alienram@icloud.com — for the patience to let three
  waves cook into one tag.
- **Brother (meeet.world):** for the billing-rails contract pinning so
  W235 / W242 / W260 / W261 ship without breakage when the endpoints
  flip live.
- **Cursor parallel lane:** algotrade pack continued on
  `cursor/algotrade-w*` branches; Wave C work landed on `main`.
- **Wave A built by:** Claude (Sonnet) in W237-W249. Wave B in
  W250-W259. Wave C in W260-W263. All commits authored locally;
  pushed via `scripts/auto-push.command`.

Tag this release: `bash scripts/RELEASE-v10.0-rc1.command`.
