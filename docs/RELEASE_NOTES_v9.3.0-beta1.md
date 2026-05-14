# TARS v9.3.0-beta1 — Cursor parity wave + meeet.world billing rails

> Released: 2026-05-15. Beta channel.
> Bundles Wave A (W237-W249). 13 waves, one tag.

This release closes the **Cursor parity gap** that the
`TARS_MASTER_DOC` parity scorecard called out as the v9.2 → v9.3
"must-ship" block: models switcher with live cost labels, MCP servers
panel, rules system, @-mention context, tier cap UX, notepad
templates, privacy mode, background agents tray, Cmd+K palette v2,
codebase indexer, and a unified WS real-time event bus. On the
meeet.world side, the consumption console (W235) now has the full
billing-rails stack underneath it — every metered action emits a
usage event, the tier cap surfaces hard/soft blocks before the spend,
and the topup prompt routes back to the brother's billing endpoints.

After W249's QA pass landed green across pytest + tsc + smoke, we're
cutting beta1 of the v9.3 line. RC and GA follow the operator-blocked
items (signed installer, brother endpoints live).

---

## Highlights (the big wins)

- **Cursor parity, finally.** Models switcher (W237) with per-request
  cost labels, MCP servers panel (W238), rules system (W239), and
  @-mention chat context (W240) — the four Cursor table-stakes panels
  TARS was missing. Side-by-side comparable. Voice-driven too.
- **Cmd+K palette v2** (W246) — fuzzy search across actions / files /
  docs / recents / agents / settings. ~10ms across 5k entries. Recents
  bubble to top, categories collapse for clarity.
- **Codebase indexer v0** (W245) — incremental, multi-language tree-sitter
  index. `/api/codebase/search` returns ranked hits with file:line
  spans. The substrate that @-mention "@code" resolves against.
- **Unified WS real-time event bus** (W248) — replaces seven polling
  loops across cockpit (status, agents, usage, briefing, doctor,
  notepad, mcp). Single WS, typed envelopes, exponential backoff.
- **Tier cap UX** (W242) — soft warning at 80%, hard block at 100%,
  one-tap topup prompt. Wires through W235's consumption console; no
  silent failures when the brother's billing endpoints are live.
- **Privacy mode + data plane** (W244) — explicit per-call toggle for
  "local-only", "cloud-allowed", "cloud-with-redaction". Status bar
  always shows which plane is active.
- **Background agents tray** (W241) — long-running tasks (codebase
  index, batch agent runs, weekly digest) get a tray with progress,
  cancel, retry. Notifications when complete.

---

## New features (by category)

### UI/UX

- **W237 — Models switcher with cost labels.** Cockpit header model
  dropdown now lists every configured provider/model with per-request
  cost estimate ($0.003 / 1k tok, 2k context). Council mode shows
  combined per-turn cost. Voice command "switch to claude haiku" works.
  `experiments/neural-showcase-v3/src/components/ModelSwitcher.tsx`,
  `web_extras/routers/models.py`.

- **W238 — MCP servers panel.** New `/settings/mcp` tab listing every
  configured MCP server (local stdio + remote SSE), with toggles,
  health badges, and a "Test connection" button. Brings the W150 real
  MCP bridge to the surface.
  `experiments/neural-showcase-v3/src/pages/SettingsMCP.tsx`,
  `web_extras/routers/mcp_admin.py`.

- **W240 — @-mention chat context.** Type `@` in the chat box →
  unified resolver popup for `@file:path`, `@docs:slug`, `@web:url`,
  `@recent:N`, `@code:query`, `@agent:name`. Tokens are inlined as
  system context on send.
  `experiments/neural-showcase-v3/src/components/MentionResolver.tsx`,
  `web_extras/routers/mentions.py`.

- **W241 — Background agents tray.** Tray icon next to the model
  switcher; click expands a panel listing every long-running task with
  progress bar, ETA, cancel, retry. Persisted across cockpit reloads.
  `experiments/neural-showcase-v3/src/components/AgentsTray.tsx`,
  `web_extras/routers/tasks.py`.

- **W242 — Tier cap UX.** Cockpit shows a thin top banner when usage
  crosses 80% of the active tier's monthly cap. At 100%, action
  endpoints return a 402 envelope with `topup_url` and the UI surfaces
  a one-tap "Top up via meeet.world" prompt.
  `experiments/neural-showcase-v3/src/components/TierCapBanner.tsx`.

- **W243 — Notepad templates.** Save any cockpit chat as a reusable
  AI workflow. Slash-recall (`/onboard_lp`, `/weekly_digest`). Share
  via signed URL — recipient clicks → installs into their notepad.
  `experiments/neural-showcase-v3/src/pages/Notepad.tsx`,
  `web_extras/routers/notepad.py`.

- **W244 — Privacy mode + data plane.** Three planes — `local`, `cloud`,
  `cloud_redacted`. Per-conversation, per-agent, and global default.
  Always visible in the status bar; receipts include the plane.
  `web_extras/routers/privacy.py`,
  `backend/core/privacy/redactor.py`.

- **W246 — Cmd+K palette v2.** Replaces v1 (W57). Fuzzy match
  (Fuse.js-ish, custom scorer) across actions, files, docs, recent
  chats, agents, settings. Recents bubble; categories collapse.
  Keyboard-only navigation. Tracks W237-tier shortcuts.
  `experiments/neural-showcase-v3/src/components/CmdK.tsx`.

### Backend

- **W245 — Codebase indexer v0.** Tree-sitter incremental index over
  the user's project root (default `~/.tars/projects/*`). Languages:
  TS / JS / Py / Rust / Go / Swift. SQLite-backed with `sqlite-vec`
  for symbol embeddings. `/api/codebase/index`, `/api/codebase/search`,
  `/api/codebase/symbols`. ~600ms for 50k-LOC repo cold, ~30ms warm.
  `backend/core/codebase/`, `web_extras/routers/codebase.py`.

- **W248 — Unified WS real-time event bus.** Single
  `/ws/events?topics=...` subscription replaces seven polling clients.
  Typed envelopes: `status.heartbeat`, `agents.frame`, `usage.delta`,
  `briefing.refresh`, `doctor.changed`, `notepad.update`, `mcp.health`.
  Auto-reconnect with exponential backoff. Falls back to polling if
  WS fails 3x.
  `backend/core/events/bus.py`, `web_extras/routers/events_ws.py`,
  `experiments/neural-showcase-v3/src/hooks/useEventBus.ts`.

### Models & MCP

- **W237 backend — `/api/models`** lists every configured provider/model
  with cost-per-1k-tok metadata and live availability ping. Cached 60s.
  `backend/core/llm/registry.py`.

- **W238 backend — `/api/mcp/servers`, `/api/mcp/test`.** Admin endpoints
  for the MCP servers panel. Test connection performs a real
  `tools/list` round-trip with 5s timeout.

### Rules system

- **W239 — `.tars/rules.yml` + per-pack overlay + Settings editor.**
  Project-level + pack-level rule files (always-on system prompts,
  tool allowlists, refusal patterns). Settings page has a YAML editor
  with schema validation. Rules merge: pack overlay > project >
  defaults.
  `backend/core/rules/`, `web_extras/routers/rules.py`,
  `experiments/neural-showcase-v3/src/pages/SettingsRules.tsx`.

### Billing

- **W235 follow-through (now wired).** Every metered action emits a
  `usage.tokens` or `usage.action` event through the W248 bus and the
  meeet.world ingest pipe. Tier cap (W242) reads from the local replay
  store with brother's `/api/billing/usage` as a tie-breaker. Soft
  warnings at 80%, hard blocks at 100%.

### Voice

- **Voice routes for new panels.** "Open MCP servers", "switch to
  haiku", "show usage", "private mode on" all parse through the W62
  command parser. Persona-router gets new intents in
  `backend/core/persona/router.py`.

### Docs

- **W247 — Master doc sync.** `TARS_MASTER_DOC.md` Cursor parity
  scorecard updated: 6 of 8 rows flip from PARTIAL → DONE. Roadmap
  marks Wave A SHIPPED. Pricing economics unchanged.

- **W249 — Wave A QA audit.** Per-feature pytest sweep, tsc clean,
  smoke green. Bug fixes folded back into the Wave A commits.

---

## Breaking changes

None. Every Wave A addition is additive. Existing endpoints, env vars,
and on-disk schemas are unchanged. Settings pages added; nothing
removed. Cockpit users will see new UI surfaces appear in-place after
rebuild.

---

## Migrations

Nothing to do. The auto-bootstrap from W231 (boot-time DB init) covers
every new SQLite store introduced in Wave A:

- `~/.tars/codebase.sqlite` (W245)
- `~/.tars/tasks.sqlite` (W241)
- `~/.tars/notepad.sqlite` (W243)
- `~/.tars/rules.yml` (W239 — touched if missing)

First boot after upgrade creates them; existing files are left alone.

---

## Known limitations

- **Brother's meeet.world endpoints not yet live.** `/api/billing/usage`,
  `/api/billing/topup`, `/api/billing/tier` are stubbed on the
  meeet.world side. Tier cap UX (W242) falls back to local replay
  store; topup prompt opens the meeet.world dashboard instead of an
  inline flow. `bash scripts/CHECK-MEEET-LIVE.command` verifies status.
- **STT requires `OPENAI_API_KEY` or `whisper.cpp` installed.** Voice
  cockpit gracefully degrades to text-input fallback (W232) if neither
  is configured. No silent failures.
- **Codebase indexer (W245) is single-project.** Multi-project /
  workspace switching is v9.4.
- **MCP servers panel (W238) is read+toggle only.** Add-server UI
  is v9.4; for now, edit `~/.tars/mcp_servers.yml` directly.
- **Privacy mode "cloud_redacted" (W244)** uses regex + NER for PII
  redaction. False negatives possible on uncommon formats. Audit
  every receipt before assuming clean.
- **Mac-only signed installer.** Windows / Linux still build from
  source. Apple Developer cert remains the operator-blocked item from
  v9.1.0.

---

## Upgrade path

The `REBUILD-TARS-APP.command` script does everything. Existing
v9.2.0-beta2 users:

```bash
git pull origin main
bash scripts/REBUILD-TARS-APP.command
```

This rebuilds the Tauri .app with the new control center bundle,
copies it to `/Applications/TARS.app`, clears Gatekeeper quarantine,
and launches it. ~30s incremental, ~5-15 min first time.

If the backend is already running, restart it to pick up the new
routers:

```bash
bash scripts/backend-up.command
```

Then `bash scripts/SMOKE-TEST.command` to confirm all 60+ routes
return 2xx/expected codes.

---

## Commits in this release (Wave A)

```
190ca1c  W237  models switcher with cost-per-request labels
480297f  W238  MCP servers panel — UI + toggles + status
246cfc2  W239  rules system — .tars/rules.yml + per-pack overlay + Settings editor
15065b1  W240  @-mention chat context — file/docs/web/recent/code resolvers
096759d  W241  background agents tray + long-running task status
4d9b76d  W242  tier cap UX — soft warnings + hard block + topup prompt
2ef99c0  W243  notepad templates — save/recall/share AI workflows
30c8127  W244  privacy mode + data plane
a89eefb  W245  codebase indexer v0 — incremental + multi-language + /api/codebase API
d2caaa2  W246  Cmd+K palette v2 — fuzzy search + recents + categories
d72ed8d  W247  master doc sync — Wave A 90% done, parity scorecard
efce37c  W248  unified WS real-time event bus — replace polling with push
22f59db  W249  Wave A QA audit + bug fixes + integration polish
```

---

## What's not in this release (next up — Wave B)

- Multi-project codebase indexer + workspace switcher
- MCP add-server UI (currently YAML-only)
- AI Clone v0.3 — real fine-tuned per-user clone (today: style hint)
- Marketplace payouts (70/30 revenue share — v0 has browse + install)
- Signed Windows / Linux installers (operator-blocked — see brother brief)

---

## Acknowledgments

- **Operator:** alienram@icloud.com — for the patience to let Wave A
  cook for 13 waves before cutting tag.
- **Brother (meeet.world):** for the billing-rails contract pinning so
  W235/W242 could ship without breakage when the endpoints flip live.
- **Cursor parallel lane:** unchanged for Wave A; algotrade pack
  continues on `cursor/algotrade-w*` branches. Wave B will re-merge.
- **Wave A built by:** Claude (Sonnet) in a sustained ~6-hour pass on
  branch `main`. All commits authored locally; pushed via
  `scripts/auto-push.command`.

Tag this release: `bash scripts/RELEASE-v9.3.0-beta1.command`.
