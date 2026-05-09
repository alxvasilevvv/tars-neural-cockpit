# Changelog

All notable changes to TARS at the **release** level. Per-wave detail
lives in [`docs/CHANGELOG_AGENTS.md`](docs/CHANGELOG_AGENTS.md). Honest
capability ledger: [`docs/WHAT_WORKS.md`](docs/WHAT_WORKS.md). Forward
roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md).

The format is loosely based on [Keep a Changelog](https://keepachangelog.com).

---

## v9.1.0 — 2026-05-09

First production-grade installable. Local-first AI cockpit with native
desktop UX, hardened sidecar lifecycle, and an honest scope. Full release
notes: [`docs/RELEASE_NOTES_v9.1.0.md`](docs/RELEASE_NOTES_v9.1.0.md).

### Added (real features)
- **Wave 73:** STT via Whisper API (`POST /api/voice/transcribe`).
- **Wave 73:** GitHub connector (token-based read of `/user`, `/repos`,
  `/issues`, `/pulls`; 60s LRU cache).
- **Wave 73:** Memory reflection (weekly ISO-week summary into `_global`
  pack; opt-in scheduled loop via `TARS_REFLECTION_AUTO=1`).
- **Wave 73:** AI Clone v0.1 (style traits skeleton — sentence length,
  exclamation/question rate, casual/formal lean, top-50 vocab). Style
  hint, not full clone — see `clone_version` in profile JSON.
- **Wave 73:** Smart Agent Router (opt-in LLM-based intent routing via
  `TARS_SMART_ROUTER=1`; regex parser stays as fallback).
- **Wave 73:** OpenTelemetry exporter wrapper (no-op unless
  `OTEL_EXPORTER_OTLP_ENDPOINT` set).
- **Wave 72:** SQLite-backed pairing store (`~/.tars/pairings.sqlite`) —
  paired devices survive app restart.
- **Wave 72:** `eval-suite.yml` CI workflow (non-blocking on PRs +
  nightly).
- **Wave 72:** `AttachmentChipStrip` wired into Cockpit chat composer.
- **Waves 65–67:** Landing visual + perf audit, Install Instructions
  modal, section divider renumber, tighter section transitions.
- **Wave 64:** Operator launch playbook + auto-precheck + marketing
  templates.
- **Waves 60–62:** Sidecar status indicator, mid-session crash detection
  (Rust watcher + TS heartbeat), `/settings` page + updater UI, Cmd+K
  palette index.
- **Waves 59-1 → 59-9:** ScrollStory empty-space fix, pre-build validator,
  window state persistence, system tray icon (macOS menu bar), global
  shortcut `Cmd+Shift+Space`, deep-link handler `tars://*`.

### Changed
- **Wave 70:** i18n forced to EN-only (RU dictionary removed in Wave 72
  to prevent regression).
- **Wave 71-A:** Backend reality alignment — version bump 9.1.0,
  dl-proxy allowlist, memory copy honest.
- **Wave 71-B:** Marketing copy aligned with shipped code (every
  claimed feature has a code path; every shipping URL resolves).
- **Wave 72:** Pairing store migrated in-memory → `~/.tars/pairings.sqlite`.
- **Wave 72:** Sidecar binary name aligned with CI
  (`tars-sidecar-<triple>` via `bundle.externalBin`); legacy
  `tars-backend` resolution kept as fallback for one minor version.
- **Wave 72:** `/api/product/downloads` defaults reduced to Mac-only
  artifacts so the manifest never advertises files the `/dl/<file>`
  proxy will 404.

### Removed
- **Wave 71-B:** False marketing claims about marketplace, "5 native
  skills", `sqlite-vec` (not yet wired), and live T2T.
- **Wave 72:** Russian i18n dictionary (~780 lines, already unreachable
  after Wave 70 force-EN).
- **Wave 71 (simplify):** 3D neural-brain, quests UI, surplus personas
  removed from main cockpit (kept under `experiments/` for posterity).

### Known limitations
- **macOS only.** Windows / Linux installers scheduled for v9.2.
- **No marketplace.** Third-party skill registry scaffolded (Wave 49,
  96–97) but not live; v9.2 MVP, v9.3 with payouts.
- **No live T2T.** Mock escrow only (Wave 81); live counterparty
  discovery in v9.3.
- **Single-user.** Multi-tenant + JWT auth scheduled for v10.0.
- **Magic-link auth** depends on the meeet.world brother backend
  (token mint endpoint). Onboarding wizard UI ships; live mint pending
  in v9.1.1.
- **AI Clone is v0.1** — style hint, not fine-tuned clone. v9.2 ships
  full style replication via fine-tuned model.
- **No notarization.** Ad-hoc codesigned only. First-run
  `xattr -dr com.apple.quarantine` documented in `install.sh`.
- **No STT on-device** — Whisper API call (Wave 73). On-device pipeline
  not in v9.1.0.

Full breakdown: [`docs/WHAT_WORKS.md`](docs/WHAT_WORKS.md). Forward
plan: [`docs/ROADMAP.md`](docs/ROADMAP.md).

### Migrations
- **Pairing store:** in-memory → `~/.tars/pairings.sqlite` (auto-created
  on first sidecar boot). Set `TARS_PAIRINGS_DB=disabled` to opt back
  into in-memory only (tests / packaged distros).
- **Sidecar binary name:** `tars-backend` → `tars-sidecar-<triple>`.
  Legacy resolution kept as a fallback for v9.1.x; will be removed in
  v9.2.
- **Locale type:** `Locale` in `@/lib/i18n` is now `"en"` only. Code
  that did `setLocale("ru")` no longer type-checks (was a no-op anyway
  after Wave 70).

### Credits
- Operator: alienram@icloud.com
- Backend & desktop: brother-of-meeet.world
- Marketing & cockpit: meeet.world team + Lovable
- Wave 72 launch hardening + Wave 73 + Wave 74 docs: Claude

---

## Earlier history

For releases before v9.1.0, see [`docs/CHANGELOG_AGENTS.md`](docs/CHANGELOG_AGENTS.md)
(per-wave append-only log). Notable milestones:

- **v9.0** (Wave Final-8) — first installable; honest WHAT_WORKS
  baseline; OAuth bridge + health endpoint + connector status badges.
- **v8.x** (Waves 65 → 138) — Background TARS, receipt ledger, native
  skills MVP, T2T mock escrow, MCP server reference, AI Clone v1
  (heuristic), Skill SDK, marketplace REST + browse page,
  multi-tenant scaffolding, edge compute adapter, OpenTelemetry,
  subscription tiers, public skill ratings.
- **v8.0** (Wave 40) — JARVIS → TARS rebrand merged with v7.6
  monorepo.
- **v7.x** — Original 8 agents (browser/code/shell/vision/advisor/
  builder/cursor/local_model), multi-user + JWT, plugin signing,
  Workflow Engine, Knowledge Brain.
