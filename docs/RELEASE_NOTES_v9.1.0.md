# TARS v9.1.0 — release notes

**Released:** 2026-05-09
**Workshop suite addendum:** 2026-05-10 (Waves 80-92)
**Channel:** stable
**Platforms:** macOS only (Apple Silicon native, Intel via Rosetta-on-arm64-dmg)
**Codename:** Phase L9 — production desktop

This is the first production-grade installable. Local-first AI cockpit with
native UX, hardened sidecar lifecycle, authoritative billing mirror, and an
honest scope.

- **Current capabilities:** [`docs/WHAT_WORKS.md`](WHAT_WORKS.md).
- **What's coming next:** [`docs/ROADMAP.md`](ROADMAP.md).
- **Wave-by-wave history:** [`CHANGELOG.md`](../CHANGELOG.md).

This file describes the v9.1.0 delta only.

---

## What's new

### Native desktop (Wave 59 → 62)
- Tauri 2 shell with **system tray icon**, **window state persistence**, **global shortcut** (`Cmd+Shift+Space`), and **deep links** (`tars://onboarding`, `tars://login`, `tars://cockpit`, `tars://thread/<id>`, `tars://settings`).
- **Settings page** — About + Updater + keyboard reference, reachable via `tars://settings`, Cmd+K, or `/settings`.
- **Auto-updater** wired to GitHub Releases `latest.json` channel manifest.

### Reliability (Wave 60 → 61)
- **Sidecar status indicator** in the cockpit (starting / failed / crashed / healthy).
- **Mid-session crash detection** — Rust watcher thread + TS heartbeat. Catches both PID exits and zombie hung processes.
- **Pre-flight build gate** — `desktop/scripts/preflight-build.sh` fails if web/ is empty or icons are missing (prevents silent blank-window installers).

### Cockpit polish (Wave 51 → 70)
- WCAG 2.1 AA modal a11y sweep — focus traps on Onboarding custom-role modal and all 3 Cmd+K palettes.
- ScrollStory regression fix (no more 400vh black gap at section entry/exit).
- Onboarding role chips → design tokens (no hex literals).
- FAQ accordion screen-reader cleanup.
- Force-EN locale (Wave 70) — operator-friendly default until other locales are re-translated.

### Marketing surface (Wave 65 → 71)
- Section divider renumber + tighter section transitions.
- Honest downloads — "Mac only, signed installer" instead of vapor Windows / Linux buttons.
- Reality alignment passes (Wave 71-A backend, Wave 71-B marketing) — every shipping URL resolves, every claimed feature has a code path.

### Backend (Wave 51 → 56)
- POST `/operator/usage` retry-budget exhaustion now emits structured `meeet.mirror.usage.exhausted` log for ops dashboards.
- New ops scripts: `ops_billing_remote_wizard.sh`, `smoke_billing_tars_backend.{sh,py}`, `backend_tars_up.sh`, `dev_tars_stack.sh`.
- New Makefile gates: `smoke-billing-tars`, `backend-tars-up`, `dev-tars-stack`, `ops-billing-remote-wizard`, `test-commercial-readiness`.

### Wave 72 launch hardening
- Sidecar binary name aligned with CI (`tars-sidecar-<triple>` via `bundle.externalBin`); legacy `tars-backend` resolution kept as a fallback.
- `/api/product/downloads` defaults reduced to Mac-only artifacts so the manifest never advertises files the `/dl/<file>` proxy will 404.
- Pairing store backed by SQLite at `~/.tars/pairings.sqlite` — paired devices survive app restart.
- Dead Russian i18n dictionary deleted (~780 lines) — was already unreachable after Wave 70 force-EN, removed to prevent future regression.
- Release workflow boundary documented (`release-desktop-tagged.yml` is authoritative on tag push; `release-tagged.yml` is manual-dispatch only).
- New `eval-suite.yml` CI workflow — runs the eval scaffolding non-blockingly on PRs and nightly.
- `AttachmentChipStrip` wired into Cockpit chat composer.
- `docs/WHAT_WORKS.md` — honest capability ledger created.
- `docs/RELEASE_NOTES_v9.1.0.md` — this file.

### Wave 73 — small real features
Six bounded features (1–3 files each) that close audit gaps:

- **STT** via OpenAI Whisper API — `POST /api/voice/transcribe` (multipart audio); 503 `stt_not_configured` when no key. `backend/core/voice/transcribe.py`.
- **GitHub connector** (token-based) — `/api/connectors/github/health`, `/repos`, `/{owner}/{repo}/issues`, `/{owner}/{repo}/pulls`. 60s LRU cache. `web_extras/routers/github.py`.
- **Memory reflection** — weekly ISO-week summary into `_global` pack. `POST /api/memory/reflect`; opt-in scheduled loop via `TARS_REFLECTION_AUTO=1`. `backend/core/memory/reflection.py`.
- **AI Clone v0.1** — style traits skeleton (sentence length, exclamation/question rate, casual/formal lean, top-50 vocab). `GET /api/clone/profile`, `POST /api/clone/draft`. *Style hint, not full clone.* `backend/core/clone/style.py`.
- **Smart Agent Router** — opt-in LLM-based intent routing (`TARS_SMART_ROUTER=1`); regex parser remains the fallback. `POST /api/agents/route`. `backend/core/agents/router.py`.
- **OpenTelemetry exporter wrapper** — no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set AND deps importable. `backend/core/observability/otel.py`.

### Wave 74 — final launch docs
- New [`docs/ROADMAP.md`](ROADMAP.md) — honest, dated, scope-tagged forward roadmap (v9.1.1 / v9.2 / v9.3+ / v10.0) with explicit "What's NOT planned" section.
- Doc cross-references synced — `README.md` ↔ `WHAT_WORKS.md` ↔ `RELEASE_NOTES_v9.1.0.md` ↔ `ROADMAP.md` ↔ `CHANGELOG.md`.
- New [`CHANGELOG.md`](../CHANGELOG.md) at repo root summarizing Waves 65 → 74.
- README.md aligned with reality — over-claims removed, badges + roadmap pointers added.

### Workshop suite (Waves 80-92) — addendum 2026-05-10

A standalone B2B onboarding surface that teaches teams to operate TARS
in a half-day workshop format. Eight routes + tutorial overlay, 20+
starter playbooks across 5 verticals, and 8 enterprise-template
markdown handouts.

**Frontend routes:**
- `/workshop` — generic 4-phase wizard (Intake → Design → Test → Deploy) with `AgentDesigner`, `Backtest`, `Compliance Console` (Wave 80-D).
- `/workshop/enterprise` — branded B2B workshop landing (Wave 81; renamed from `/workshop/cresco` in Wave 87).
- `/workshop/roi` — interactive ROI calculator (Wave 84).
- `/workshop/materials` — handouts + recipe library + video placeholders + PWA offline (Wave 85).
- `/workshop/assess` — pre-workshop self-assessment quiz (12 Q × 4 categories) (Wave 88).
- `/workshop/cohort` — facilitator dashboard with mock SSE (Wave 89).
- `/compliance` — receipts feed + filters + CSV export + `ReceiptVerifier`.
- In-app interactive tutorial overlay across all workshop pages (Wave 92).

**Workshop content:**
- 20+ starter playbooks under `playbooks/_workshop/{fund,saas,dao,family-office,algotrade,quant}/` plus a recursive playbook loader.
- 8 markdown templates under `docs/workshop/enterprise-template/` (5 emails, facilitator runbook, feedback survey, README).
- Contracts: [`docs/B2B_WORKSHOP.md`](B2B_WORKSHOP.md), [`docs/contracts/WORKSPACES.md`](contracts/WORKSPACES.md), [`docs/contracts/SKILL_SDK.md`](contracts/SKILL_SDK.md).

**Marketing surface:**
- B2B workshop visible from the marketing landing (Wave 82).
- Workshop FE tests + a11y audit + sitemap/OG polish (Wave 83).
- Wave 87 stripped all named-customer / regulatory-acronym branding (Cresco / CARF / 3V / Crypto Fund) → fully generic B2B copy across docs and code.

### Webhooks (Wave 90)

- New module `backend/core/webhooks/` — outgoing dispatcher + signed delivery + inbound playbook trigger + dead-letter queue + inbox.
- HTTP surface: `web_extras/routers/webhooks.py`.
- Webhook contract **v1.0** ships (HMAC signing, retry, dead-letter, inbox queue).
- **Honest scope:** the contract and dispatcher are live, but `receipt.*` event emission is only wired in the algotrade pack — broader emit sites land in v9.3.

### Real Slack / Gmail / Calendar connectors (Wave 91)

Three connectors graduate from PARTIAL/STUB → FULLY IMPLEMENTED:

- `backend/core/connectors/slack.py` — real OAuth + read channels/DMs.
- `backend/core/connectors/gmail.py` — real OAuth + read threads.
- `backend/core/connectors/calendar.py` — real OAuth + Google Calendar events read.
- HTTP surface unified at `web_extras/routers/connectors.py`.

**Env-gated:** all three require `OAUTH_BRIDGE_*` env wired to brother's
meeet.world bridge. **URL-redirect OAuth flow only** — the "Quick
Connect" Chrome extension flow is v9.1.1.

### Hardening summary (Waves 75 → 79)

- Pre-launch security audit at [`docs/security/AUDIT_2026-05-09.md`](security/AUDIT_2026-05-09.md).
- Rate limits on `/api/voice/transcribe`, `/api/agents/route`, `/api/clone/draft`.
- Wallet `sign_message` policy gate.
- 4 failing GitHub workflows repaired (Wave 75).
- Real minisign updater pubkey patched into release pipeline (operator step 2 done).

---

## What's changed

- Default `_DEFAULT_VERSION` in `backend/core/product/manifest.py` bumped from `0.1.0-alpha.2` → `9.1.0`.
- Default artifact filenames migrated to CI naming (`TARS_<version>_<arch>.dmg`, underscore + raw arch).
- `tauri.conf.json` adds `bundle.externalBin: ["binaries/tars-sidecar"]` so Tauri picks the correct target-triple binary at bundle time.
- `experiments/neural-showcase-v3/src/lib/i18n.tsx` is now ~1000 lines (was ~1770); only EN dictionary remains.

## Breaking changes

None for end users. For integrators:
- The `Locale` type in `@/lib/i18n` is now `"en"` only. Code that did `setLocale("ru")` no longer type-checks — it was a no-op anyway after Wave 70.
- `~/.tars/pairings.sqlite` is now created on first sidecar boot. Set `TARS_PAIRINGS_DB=disabled` to opt back into in-memory only (tests / packaged distros).

### Migration notes
- **Pairing store:** in-memory → `~/.tars/pairings.sqlite`. No action required on a clean install; existing in-memory deployments simply lose nothing (in-memory = ephemeral by definition).
- **Webhooks (Wave 90):** new SQLite tables auto-created in the existing app DB. Set `TARS_WEBHOOKS=disabled` to skip (tests).
- **Connector OAuth (Wave 91):** requires `OAUTH_BRIDGE_URL` + `OAUTH_BRIDGE_SHARED_SECRET` env. Connectors return 503 `oauth_bridge_not_configured` if missing.

---

## Known limitations (be honest)

- **macOS only.** Windows + Linux pyoxidizer cross-target builds are scheduled for **v9.2** — the Tauri code path is identical, only the CI matrix is missing.
- **No notarization.** Ad-hoc codesigned only (Apple Developer Program at $99/yr is post-launch). First-run `xattr -dr com.apple.quarantine` documented in install.sh.
- **STT is API-only.** `POST /api/voice/transcribe` calls OpenAI Whisper API; on-device pipeline still pending. Returns 503 `stt_not_configured` when no key.
- **No marketplace.** Third-party skill registry is scaffolded (Wave 49, 96–97) but not live; install via filesystem only. **MVP in v9.2, payouts in v9.3.**
- **No multi-tenant Workspaces.** `WORKSPACES.md` contract published; multi-tenant + JWT auth is **v9.3** (initial) → **v10.0** (full Orgs/Teams/RBAC).
- **No T2T live.** TARS-to-TARS handshake exists in mock-escrow form (Wave 81); live counterparty discovery + Solana escrow scheduled for **v9.3**.
- **Workshop cohort is mock SSE.** `/workshop/cohort` ships the facilitator dashboard UI; live attendee tracking is mock data only.
- **Webhooks `receipt.*` events not yet emitted.** Dispatcher + contract v1.0 ship in Wave 90, but live emit sites are wired only in algotrade today. Broader receipt emit-site coverage is **v9.3**.
- **Slack / Gmail / Calendar Quick Connect.** URL-redirect OAuth flow ships (Wave 91); the one-click Chrome extension flow is **v9.1.1**.
- **Magic-link auth.** Onboarding wizard UI ships; live token mint depends on brother's meeet.world backend — **v9.1.1**.
- **Mac-x64 dmg may fall back to arm64+Rosetta.** When the macos-13 GitHub runner pool is queue-starved, the Intel dmg is missing and the `/dl/TARS_9.1.0_x64.dmg` proxy redirects to the arm64 dmg, which Rosetta runs cleanly.
- **No Windows SmartScreen reputation yet.** First ~50 Windows users (once v9.2 ships) will hit "More info → Run anyway".

See [`docs/WHAT_WORKS.md`](WHAT_WORKS.md) for the full FULLY-IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED breakdown.

---

## Roadmap pointer

- **v9.1.1** (~2 weeks) — Magic-link auth, Slack/Gmail/Calendar Quick Connect (Chrome flow), web wake-word, iMessage + Telegram bridges.
- **v9.2** (~1 month) — Multi-tenant Workspaces (initial), Windows + Linux installers, sqlite-vec wired, AI Clone v1, XTTS-v2 cloning, Marketplace MVP, Skill SDK, headless daemon.
- **v9.3+** — T2T live + Solana escrow, unified receipt-ledger stream, Reputation Graph UI, marketplace 70/30 + payouts, webhooks `receipt.*` emission everywhere, MCP server bridge.
- **v10.0** — Multi-tenant full + Orgs/Teams/RBAC, Shared Agent Sessions, TARS Handoff, edge voice adapter.

Authoritative forward roadmap: [`docs/ROADMAP.md`](ROADMAP.md). Design-phase context: [`docs/PHASE_L_ROADMAP.md`](PHASE_L_ROADMAP.md).

---

## Version → contract → infra mapping

| Surface | Pinned identifier in v9.1.0 |
| --- | --- |
| App version (cockpit + sidecar) | `9.1.0` |
| Tauri config `version` | `9.1.0` (`desktop/src-tauri/tauri.conf.json`) |
| Download manifest `contract_version` | `1.0.0` (`backend/core/product/manifest.py`) |
| Pairing schema (paired devices) | unversioned; one table `pairings` (Wave 72) |
| Updater channel JSON | `latest.json` at `releases/latest/download/latest.json` |
| Marketing site asset hosting | Cloudflare Pages `tars-meeet` → GitHub Releases proxy `/dl/<file>` |
| Magic-link auth | meeet.world bridge, route `tars://login` |
| Allowlisted CSP origins | `127.0.0.1:8765`, `meeet.world` |

---

## Verifying the build

```bash
# Architecture: Tauri 2 shell, CPython 3.12 + FastAPI sidecar, SQLite memory.
# Verify the sidecar before shipping:
codesign --verify --deep --strict --verbose=2 /Applications/TARS.app
xattr -dr com.apple.quarantine /Applications/TARS.app   # first run only
```

Channel manifest (the one Tauri's updater polls):

```bash
curl -s https://github.com/alxvasilevvv/tars-neural-cockpit/releases/latest/download/latest.json | jq .
```

---

## Credits

Wave 72 launch hardening: alienram@icloud.com (operator), Claude (assistant).
Waves 80-92 Workshop suite + webhooks + connectors + Wave 93 docs sync: Claude (assistant).
Backend & desktop: brother-of-meeet.world.
Marketing & cockpit: meeet.world team + Lovable.
