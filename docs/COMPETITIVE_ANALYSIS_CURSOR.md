# Competitive Analysis — TARS vs Cursor

> **Author:** TARS strategy desk (Claude lane), 2026-05-15.
> **Companion docs:** `ROADMAP_W234_to_v10.md` (commit-sized closure plan),
> `PRICING_ECONOMICS_v9.2.md` (the numbers brother needs), `MASTER_ROADMAP_v9.1_to_v10.0.md`
> (six-month north star).
> **Scope:** Cursor (cursor.com, the AI-native IDE) is the closest analogue to
> TARS' "agent cockpit" framing in the public market. This doc lays out where
> we lose, where we win, and the surgical sequence of commits that closes the
> meaningful gap.
> **Method:** read of W1–W233 commit history; cross-checked against
> `docs/WHAT_WORKS_v9.2.0-beta2.md`, `backend/core/*`, `desktop/`, and the
> launch readiness audit.

---

## 1. Cursor — feature inventory (current, May 2026)

This section is a flat capability dump of Cursor as a competitive surface.
The point isn't to praise Cursor — it's to enumerate every visible surface so
the gap matrix in §1.3 has somewhere to point.

### 1.1.1 Editor core

- VS Code fork. Inherits the entire VS Code extension marketplace
  (~50K extensions), keymap, terminal, git panel, debug protocol, settings
  schema. This is Cursor's single largest moat — every dev habit transfers.
- Multi-pane editor, split view, integrated terminal, Source Control panel,
  Run/Debug panel, Extensions panel.
- File tree with search, find-in-files (Cmd+Shift+F), go-to-definition,
  refactor menu, problem diagnostics.
- Tabs + breadcrumbs + minimap + sticky scroll + bracket matching + linked
  editing of HTML/JSX tags.
- Themes (dark/light + custom), font ligatures, indent guides, whitespace
  rendering. All inherited from VS Code.

### 1.1.2 Inline AI — Cursor Tab

- Predictive multi-line completion. Trained on a custom model
  (Cursor's internal "fast model"); ships as a default-on greyed-out
  suggestion you accept with `Tab`.
- Smart cursor-jump: Tab not only inserts the suggested edit but also moves
  the cursor to the next logical edit site (the "next edit prediction"
  feature). This is the single biggest reason devs switch from Copilot.
- Suggestions are token-streamed inline; per-completion latency typically
  <300ms.
- Free in the Hobby plan (capped); unlimited in Pro/Business.

### 1.1.3 Composer (Cmd+I) — multi-file edits

- Sidebar/inline modal that accepts a natural-language prompt and produces a
  cross-file diff.
- Preview pane with file-by-file diff, accept/reject per hunk, partial accept.
- Operates on the entire context the user has pinned (open files, mentioned
  files, mentioned docs).
- Composer-Agent mode lets the model run terminal commands, read additional
  files mid-task, and self-correct.

### 1.1.4 Agent mode + background agents

- Agent mode (default in 0.42+): a long-running, looping agent that plans
  and executes against your codebase. Reads files, runs the terminal,
  iterates on test failures, edits, repeats.
- Background agents (0.45+): you start an agent, close the window, and pick
  up the result later via the activity sidebar. Runs server-side on Cursor's
  fleet; the user's machine isn't required to stay open.
- Model picker: Claude 4.5 Sonnet, Claude 4.5 Opus, GPT-5, GPT-5-mini,
  Cursor's own `cursor-small`/`cursor-fast`, o1, Gemini 2.5 Pro. Toggle per
  request.

### 1.1.5 Context system — `@-mentions`

- `@file <name>`: pins a specific file into the prompt context.
- `@folder <name>`: pins a directory.
- `@docs <name>`: pins documentation pages Cursor has pre-indexed (FastAPI,
  React, Stripe, etc.).
- `@web <query>`: live web search; results auto-summarized into the prompt.
- `@recent-changes`: pins recent git diff.
- `@symbol <name>`: pins a specific function/class via the symbol index.
- `@codebase`: instructs the model to query the embedded codebase index
  semantically before answering.
- All `@-mentions` survive across messages in the same chat.

### 1.1.6 Codebase indexing

- Codebase is embedded into a vector index on first project open.
- Index is rebuilt incrementally on file save.
- Indexing scales to multi-million-LoC monorepos (publicly demonstrated by
  Cursor on the Chromium and Linux trees).
- Index is hosted by Cursor (default) or local (Privacy Mode).
- Powers `@codebase`, semantic search, agent context retrieval.

### 1.1.7 Privacy modes

- **Default:** code is sent to Cursor; Cursor sends to model providers;
  zero-data-retention contracts with Anthropic/OpenAI; nothing is trained on.
- **Privacy Mode:** no code is ever stored on Cursor's servers — only
  in-flight to the model and back. Index is local.
- **Enterprise:** SOC2 Type II, BAA available, SAML SSO, audit logs,
  admin policy enforcement.

### 1.1.8 Rules for AI ("Cursor Rules")

- Per-project file at `.cursor/rules/*.mdc` (Markdown with frontmatter).
- Pinned conventions: code style, frameworks to prefer, files/folders to
  always include, restrictions ("don't edit `migrations/`").
- Auto-attached based on glob match or always-on.
- Survive across chat sessions; ship in repo, version controlled.

### 1.1.9 Notepads

- Saved chat templates with pinned context (files, docs, rules).
- Re-runnable: "review-PR notepad" or "scaffold-test notepad".
- Effectively the team's library of repeatable agent recipes.

### 1.1.10 MCP server config

- Settings → MCP. Per-project and per-user MCP server registrations.
- Toggle servers on/off per chat; mcp tools appear as `@<server>:<tool>`.
- One-click connect for known servers (Linear, Sentry, Notion, GitHub).
- Status indicator (connected/error/loading).

### 1.1.11 Pricing & metering

- **Hobby (free):** 50 "fast" requests / 200 "slow" requests per month;
  2K Cursor Tab completions/month; basic models only.
- **Pro ($20/mo):** 500 fast requests, unlimited slow, unlimited Cursor Tab,
  all premium models. Overage available at metered cost.
- **Business ($40/seat/mo):** Pro + SSO, audit log, admin dashboard, private
  index, centralized billing, no-train opt-in default.
- **Enterprise (custom):** SLA, dedicated support, SOC2/BAA, on-prem index
  option, model BYO.
- Usage console: settings → Usage shows fast/slow/Tab counters with a soft
  cap warning at 80% and a hard cut-off at 100% (or overage billing if
  enabled).
- Per-model pricing labels in the picker (e.g. "Claude 4.5 Opus — 3x req
  cost").

### 1.1.12 Settings panel

- Models — toggle which providers are enabled, set BYO API keys.
- Rules for AI — global and per-project.
- Notepads — manage saved templates.
- MCP Servers — register, toggle.
- Editor — VS Code's full settings tree (inherited).
- Privacy — toggle Privacy Mode, manage data retention.
- Account — sign in via cursor.com (email magic-link or OAuth via Google/GitHub).

### 1.1.13 Auth, update, telemetry

- Auth: cursor.com magic-link or SSO; session token in keychain.
- Update channel: stable, early-access (0.x.y nightly).
- Telemetry: anonymous usage + error reporting; opt-out in Settings → Privacy.
- Crash reports via Sentry-style aggregator.

---

## 2. TARS — current feature inventory (W1–W233)

Mirror format. Source of truth: git log + `WHAT_WORKS_v9.2.0-beta2.md` +
`backend/core/*` module tree.

### 2.1 Editor

- **None.** TARS is not an IDE. It does not own the buffer.
- Code-RAG index (sqlite-vec) sits next to a project but does not edit it.
- Voice cockpit can dictate edits via OS-level keystroke automation
  (Mac actions), but there is no in-app editor surface.

### 2.2 Agent runtime

- `workflow_engine` (W45): chain agents, schedule, branching, replay.
- 7 killer agents (W47): research, analyst, meeting, doc, scraper,
  translator, image.
- Multi-agent planner (W16) with native tool-calling (W22) for
  OpenAI + Anthropic.
- Smart Agent Router (W116) — LLM-based intent routing.
- Supervisor (W76) — budget cap, rate limit, kill switch, HIL gate.
- Council (W56) — two-voice / multi-LLM dissent before consequential actions.

### 2.3 Context / RAG

- Code RAG over sqlite-vec (Iter E / W135).
- Knowledge Brain (W46) — universal RAG ingestion (PDF/URL/Office/code).
- Memory reflection (W72) — weekly summaries with user confirmation.
- Memory UI over SQLite (Iter C).
- Universal File Drop (W117) — drop zone + ingest pipeline.

### 2.4 Domain packs (7)

- Wealth / Health / Family / Product / Brand / Entrepreneur / Civic.
- `business`, `entrepreneur`, `science`, `algotrade`, `traders`, `wallet`,
  `web search`, `civic` per `WHAT_WORKS_v9.2.0-beta2.md`.
- Pack catalog at `/api/domains/manifest`; pack-aware actions per pack.

### 2.5 Voice cockpit

- Cinematic JARVIS-grade visuals (W230 storyboard).
- MediaRecorder STT pipeline (W229) — POST `/api/voice/transcribe`
  via whisper.cpp / OpenAI Whisper fallback.
- `/api/voice/command` (W220) full-screen cockpit.
- Wake-word (W36) — web Picovoice WASM in PWA path.
- TTS — XTTS-v2 voice cloning endpoint (W39) + per-persona SSML prosody
  (W43).

### 2.6 Auth

- meeet.world magic-link auth gate (W219).
- Google / Apple OAuth via meeet.world bridge (W219).
- Token persist to `~/.tars/meeet_token` (W203 `/api/auth/meeet`).
- Awaiting brother's `/api/magic-link/redeem` for full end-to-end (W233).

### 2.7 Connectors (real OAuth where marked)

- Slack — real OAuth + read (W91).
- Gmail — real OAuth + read (W91).
- Google Calendar — real OAuth + read (W91); .ics reader for Daily Briefing
  (Iter A).
- GitHub — token-based, not mock (Iter F / W136).
- Telegram — bridge connector (W108), beta.
- iMessage — real bridge (W160) — read via AppleScript + Messages.app DB.
- Email/SMTP — third notification sibling (W163).
- Brave / SearXNG / DuckDuckGo — web search pack.

### 2.8 Receipts & on-chain anchoring

- Receipt-ledger (W67) — signed action receipts.
- Hash-chained + Solana memo anchor (W89, W95) — batched Merkle root.
- Public verifiable-proof endpoints (W204) — no-auth Merkle verifier.
- `/api/receipts/recent`, `/api/receipts/merkle/{day}`,
  `/api/public/proof/anchor/{root}`, `/api/public/proof/verify`.

### 2.9 Watchdog & ops

- Background daemon (W152) — real launchd plist + Python entrypoint.
- Linux systemd user-unit parity (W153).
- Windows schtasks parity (W171).
- `tars-doctor` CLI (W154) — 10+ health checks with `--fix`, `--watch`,
  `--test-notify`.
- `/api/doctor` HTTP exposure (W155, W167, W168).
- Backend autorestart watchdog (W207).

### 2.10 Notification bridges

- iMessage (W160), Telegram (W161), Email/SMTP (W163) siblings.
- Auto-fanout from `doctor_watch` (W162).
- Unified `NOTIFICATIONS.md` contract (W164).

### 2.11 $MEEET economy

- Balance, spend, earn, quests v2 (W48).
- Native skills: Quest / Stake / Arena / Discovery / Wallet (W75).
- Marketplace 70/30 payouts on Solana (W96).

### 2.12 T2T agent handshake protocol

- TARS-to-TARS handshake (W81) + mock escrow.
- Relayer-based off-chain escrow adapter (W86).
- T2T frontend (W88).

### 2.13 Cowork (multiplayer agent sessions)

- Backend cowork module (W129): sessions, presence, stream, handoff.
- Cowork HTTP router (W149).
- Orchestrator emits `agent_frame` to cowork (W131).
- Two browsers see each other's presence in <2s (target).

### 2.14 B2B Workshop mode

- Workshop functionality (W80) — companies/funds onboard via TARS.
- ROI calculator (W84), assessment quiz (W88), cohort dashboard (W89).
- Compliance export bundle (W104) — audit-grade.

### 2.15 Cockpit (TARS.app desktop)

- Tauri 2 wrapper (W201) — UI moved out of HTML into native app.
- 9-tab nav: Status / Agents / Chat / Activity / Connectors / Cowork /
  Vision / Plugins / Settings.
- Tier pill from `/api/entitlements`.
- Welcome modal (W205), Today briefing (W206), weekly digest (W209).
- Doctor panel embedded.
- Vision tab (W203) — capture + analyze + OCR.

### 2.16 MCP server bridge

- MCP reference server (W85) — exposes 5 native skills as tools.
- Real (not stub) implementation (W150).

### 2.17 What's still missing (TARS side, honest)

- No editor / no Composer / no Tab completion.
- No `@-mention` chat context resolver.
- No per-request usage meter UI surfaced in cockpit (ledger exists; console
  doesn't).
- No `.tars/rules.yml` project pinning.
- No background agents accessible from a "running tasks" panel.
- No Models switcher with cost-per-request label.
- No MCP servers panel in cockpit (registry exists in backend).

---

## 3. Gap matrix

Legend: shipped (Y) · partial / beta (P) · absent (N) · N/A doesn't apply by design.

| #  | Capability                                  | Cursor | TARS today | Delta |
|----|---------------------------------------------|--------|------------|-------|
| 1  | Code editor (own the buffer)                | Y      | N          | gap   |
| 2  | Inline Tab completion                       | Y      | N          | gap   |
| 3  | Composer (multi-file edit + diff)           | Y      | N          | gap   |
| 4  | Agent mode (looping autonomous agent)       | Y      | Y          | parity (different surface) |
| 5  | Background agents (resume later)            | Y      | P          | partial — daemon exists, no UI |
| 6  | Codebase index                              | Y      | Y          | parity — sqlite-vec |
| 7  | `@file` context pin                         | Y      | N          | gap   |
| 8  | `@folder` context pin                       | Y      | N          | gap   |
| 9  | `@docs` context pin                         | Y      | N          | gap   |
| 10 | `@web` live search                          | Y      | P          | brave/searxng/ddg pack exists; not surfaced inline |
| 11 | `@recent-changes` (git diff)                | Y      | N          | gap   |
| 12 | `@symbol`                                   | Y      | N          | gap   |
| 13 | Rules for AI (project-level conventions)    | Y      | N          | gap   |
| 14 | Notepads (saved chat templates)             | Y      | P          | playbooks cover backend half |
| 15 | MCP servers settings panel                  | Y      | P          | backend has it, no UI |
| 16 | Model switcher with cost labels             | Y      | P          | provider switcher exists, no cost label |
| 17 | Privacy Mode                                | Y      | N/A        | TARS is local-first by default |
| 18 | SOC2 / enterprise compliance UI             | Y      | P          | compliance_export exists, not branded SOC2 |
| 19 | Per-request usage meter                     | Y      | P          | ledger emits events; no console |
| 20 | Soft cap warning at 80%                     | Y      | N          | gap (planned W235+) |
| 21 | Hard block at 100% / overage path           | Y      | P          | entitlements checker blocks; no UX |
| 22 | Magic-link auth                             | Y      | P          | TARS side ready, brother pending |
| 23 | OAuth (Google/Apple/GitHub)                 | Y      | Y          | parity |
| 24 | Update channel                              | Y      | P          | Tauri updater wired, no published JSON |
| 25 | Telemetry opt-out                           | Y      | Y          | local-first → opt-in by design |
| 26 | Voice-first cockpit                         | N      | Y          | TARS wins |
| 27 | TTS narration / SSML persona                | N      | Y          | TARS wins |
| 28 | Wake-word                                   | N      | Y          | TARS wins |
| 29 | Hash-chained receipt ledger                 | N      | Y          | TARS wins |
| 30 | Solana anchor of agent actions              | N      | Y          | TARS wins |
| 31 | Public Merkle verifier (no-auth)            | N      | Y          | TARS wins |
| 32 | Domain packs (wealth/health/family/etc)     | N      | Y          | TARS wins |
| 33 | Multi-agent council / dissent               | N      | Y          | TARS wins |
| 34 | T2T agent handshake protocol                | N      | Y          | TARS wins |
| 35 | Cowork multiplayer sessions                 | N      | Y          | TARS wins |
| 36 | $MEEET token economy                        | N      | Y          | TARS wins |
| 37 | Marketplace 70/30 on Solana                 | N      | Y          | TARS wins |
| 38 | Workshop B2B mode                           | N      | Y          | TARS wins |
| 39 | iMessage / Telegram / Email bridges         | N      | Y          | TARS wins |
| 40 | Local file system access (real Mac actions) | P      | Y          | TARS wins (Cursor has terminal only) |
| 41 | Real Calendar / Gmail / Slack OAuth         | P (MCP)| Y          | TARS wins natively |
| 42 | Vision / screen capture                     | N      | Y          | TARS wins |
| 43 | OCR / accessibility helpers                 | N      | Y          | TARS wins |
| 44 | Watchdog + auto-restart daemon              | N      | Y          | TARS wins |
| 45 | tars-doctor CLI                             | N      | Y          | TARS wins |

**Tally:** Cursor ahead on 13 capabilities (rows 1–25 chunk). TARS ahead on
20 (rows 26–45). Net direction: TARS plays a *broader* board (life ops,
not just code); Cursor plays a *deeper* board (best-in-class IDE).

---

## 4. What TARS has that Cursor doesn't (the asymmetric edge)

### 4.1 Local-first by default

- Receipts on disk. Memory on disk. Vector index on disk. LLM keys in macOS
  Keychain (or BYO).
- The user can air-gap the laptop and TARS still functions for everything
  that doesn't strictly need a cloud LLM call.
- Cursor's Privacy Mode is opt-in and degrades search (codebase index moves
  local but `@docs`, `@web`, model inference still leave the box).

### 4.2 Hash-chained receipt ledger + Solana anchor

- Every agent action emits a signed receipt; receipts hash-chain so any
  tampering is detectable.
- Daily Merkle root is anchored on Solana as a memo (W89).
- Public verifier endpoint replays the Merkle proof with no auth, no DB
  call — third parties can verify a TARS user's claim of having taken some
  action at some time.
- Cursor has no equivalent. "Did the agent really do that?" is unanswerable
  without their internal logs.

### 4.3 Domain packs (life-ops surface, not dev-ops)

- Wealth, Health, Family, Product, Brand, Entrepreneur, Civic.
- Civic pack (W204) does free public-records lookups for every tier.
- Cursor is dev-only by design. Even if it spawned a "wealth pack" tomorrow,
  it would have no native OAuth path for non-dev SaaS (Plaid, Apple Health,
  etc.) — that's not where the IDE community lives.

### 4.4 Voice-first cockpit (JARVIS-grade)

- Wake-word → STT → router → action → TTS narration → receipt.
- Cinematic visuals (W230) — purposeful, not a parlor trick; the visuals
  *are* the affordance for an ambient agent.
- Cursor has no voice surface at all.

### 4.5 $MEEET token economy

- On-chain payments, on-chain rewards, on-chain payouts to skill
  publishers.
- Marketplace 70/30 split is enforceable in code, not in a Stripe Connect
  contract.
- A user can earn $MEEET (quests, contribution, referrals) and spend it
  back on TARS subscription — closed loop.

### 4.6 Workshop B2B mode

- Funds and companies onboard their team via TARS workshops.
- ROI calculator, assessment, cohort dashboard, compliance export.
- This is a B2B revenue motion that Cursor doesn't have an equivalent for
  (Cursor is bottom-up dev sales; TARS can sell to a CFO).

### 4.7 Cowork (multiplayer agent sessions)

- Two humans + their TARS agents share a session, see each other's presence,
  hand off mid-task.
- Cursor's "Cursor Live" exists but is single-user pairing on a single
  buffer; TARS Cowork is N-user pairing across N agents.

### 4.8 T2T agent handshake protocol

- Agent A from TARS instance #1 negotiates a deal with agent B from TARS
  instance #2. Escrow via meeet relayer.
- This is the substrate for an *agent economy* (not just agent productivity).
- Cursor has no protocol for inter-instance commerce.

### 4.9 Real OAuth across 8+ connectors

- Slack, Gmail, Calendar, GitHub, Telegram, iMessage, Email/SMTP, web search.
- Cursor depends on MCP servers for non-code SaaS — which exist but require
  the user to install + register them per project.

### 4.10 Receipt-based consumption transparency

- The ledger emits a receipt per action. Cost, model, tokens in/out, latency
  — all on disk, all verifiable.
- Cursor's usage is opaque: "you used 432/500 fast requests"; what is a
  "fast request" worth in dollars? The user doesn't know.
- TARS' transparency *is* the moat for the trust-conscious audience
  (funds, lawyers, healthcare ops, anyone whose compliance officer asks
  "what did your AI do last quarter?").

---

## 5. What Cursor has that TARS doesn't (the gap to close)

The mirror of §4. These are the items that, if a Cursor user looked at TARS,
would make them say "cute, but I'd lose this."

### 5.1 Inline Tab completion (Cursor Tab)

- The single biggest reason devs are paying Cursor over Copilot/Continue.
- TARS has no editor. Closing this requires either (a) shipping a TARS
  editor surface — wildly out of scope this quarter — or (b) building a
  Tab-equivalent as a VS Code extension that calls back into TARS for
  inference, telemetry, and receipts.
- **Recommendation:** option (b) — ship `tars-tab` VS Code extension in
  Wave C. It piggy-backs on the existing editor real estate the dev already
  has open, and routes all completions through TARS' usage ledger.

### 5.2 Composer multi-file refactor

- Diff preview, per-hunk accept, terminal command execution mid-task.
- TARS' workflow_engine + supervisor can sequence this, but no diff UI.
- Closure path: `@-mention` resolver + diff renderer in TARS.app + receipt
  per accepted hunk. Pieces exist; gluing is Wave B.

### 5.3 Codebase indexing at production grade

- Cursor indexes millions of LoC; TARS' sqlite-vec scales to ~100K files
  before query latency becomes annoying.
- Closure: rebuild index path on watchdog file-change events; warm cache
  for hot files; embed via local model when key absent. Wave B.

### 5.4 `@-mention` chat context system

- This is the *interaction model*, not just a feature. Users want
  type-as-you-go context pinning.
- Closure: small but high-impact frontend work in Wave A.

### 5.5 Privacy mode + SOC2 + enterprise compliance UI

- TARS *is* private by default; the gap is the *branding + audit
  documentation*. Compliance export bundle (W104) exists. Wrap it in a
  "SOC2-style audit log" UI in cockpit. Wave B.

### 5.6 Per-request usage meter

- Cursor shows "432 / 500 fast requests, 87% used, resets in 14 days".
- TARS' ledger emits the data; the meter UI is missing.
- **This is Wave A item #1.** Already scoped for W235 (concurrent agent).

### 5.7 Cursor Rules equivalent

- `.tars/rules.yml` in project root. Loaded at agent start; injected into
  system prompt; survives across sessions; version-controlled.
- Wave A. Easy.

### 5.8 MCP servers settings panel

- Backend registry exists (W150). UI panel doesn't.
- Wave A. Drop-in component.

### 5.9 Background agents (Cursor 0.42+)

- Long-running agents you check on later, surfaced in a "running tasks"
  tray.
- TARS has the daemon (W152) and supervisor (W76). What's missing is the
  cockpit surface — a tray that lists active agents with progress
  indicators.
- Wave A. Cockpit tab + WS feed (already partially built — Watch-me-work
  W77).

### 5.10 Notepads (saved AI conversations as templates)

- Playbooks (W122) cover the *executable* half. What's missing is the
  *chat-template* half — a saved prompt + pinned context that the user
  triggers from the cockpit.
- Wave B.

### 5.11 Models switcher with cost-per-request labels

- Provider switcher (W55) exists. What's missing is the per-model cost
  label and the live "this prompt will cost ~$0.04" estimator.
- Wave A. The price table is already in `backend/core/usage/ledger.py`.

---

## 6. Prioritized closure roadmap

Gaps from §5 grouped into three waves. Each item carries a 1-line
description, effort estimate (S/M/L/XL), dependency, success metric.

### 6.1 Wave A — must-have to compete (0–4 weeks, W234–W260)

| #  | Item                          | Desc | Effort | Dep | Success metric |
|----|-------------------------------|------|--------|-----|----------------|
| A1 | Consumption meter UI          | Cockpit tab streaming `/api/usage/stream` with per-action breakdown | M | usage events emitted (W195) | Operator sees a live cost line within 1s of a request |
| A2 | Usage-per-request log         | Persistent table at `/api/usage/console` aggregating last 30d | S | ledger.py | 100% of last-30d requests retrievable with cost field |
| A3 | Models switcher with cost label | Provider picker shows `$3/$15 per Mtok` next to each model | S | price table exists | User can pick by cost; choice persists per project |
| A4 | Cost estimator                | Pre-send "this prompt will cost ~$0.04" hint in Chat tab | S | A3 | Estimate within ±15% of actual |
| A5 | MCP servers panel             | Settings → MCP listing registered servers + toggle | S | W150 registry | Operator can disable an MCP server without editing config |
| A6 | `.tars/rules.yml` loader      | Project rules loaded into agent system prompt | M | none | Two projects with different rules behave differently in same TARS |
| A7 | `@-mention` chat context      | `@file`, `@folder`, `@recent-changes`, `@web` resolvers | M | code-RAG + search pack | All 4 mention types resolve in <500ms |
| A8 | Background agents tray        | Cockpit tab listing active daemon tasks with progress | M | W77 Watch-me-work + W152 daemon | Operator starts an agent, closes window, sees status next morning |
| A9 | Pricing copy update           | Landing + cockpit reflect new tier numbers (see PRICING_ECONOMICS_v9.2.md) | S | brother numbers locked | Free/Pro/Business tier numbers match across landing + cockpit + billing |
| A10 | Tier soft-cap warning        | Toast at 80% of monthly $MEEET / USD budget | S | A1 + entitlements checker | Warning fires deterministically at 80%, not 75 or 85 |

**Wave A exit criteria:** a Cursor user looking at TARS doesn't say "where's
my usage meter?" or "why can't I pin a file?" Those frictions are gone.

### 6.2 Wave B — TARS-unique edge (4–12 weeks, W261–W320)

| #  | Item                                | Desc | Effort | Dep | Success metric |
|----|-------------------------------------|------|--------|-----|----------------|
| B1 | Voice-driven Composer               | "Hey TARS, refactor `auth.py` to use the new vault" → diff preview opens | L | A7 + voice cockpit | E2E demo: voice → diff → accept in <30s |
| B2 | Multi-file refactor + receipt-anchored diffs | Every accepted hunk emits a receipt; Merkle root anchors that day | M | B1 + receipts | Diff acceptance shows receipt ID; verifiable next day on chain |
| B3 | On-chain audit trail for code changes | Code-change receipts tagged separately; queryable by repo | M | B2 | `tars audit <repo>` returns N receipts with proofs |
| B4 | Domain-pack-aware code suggestions  | Wealth pack pins `tax.py`; product pack pins `roadmap.md`; etc. | M | A6 rules + A7 mentions | Same prompt, different pack → different file context |
| B5 | SOC2-style audit log UI             | Cockpit tab rendering W104 compliance export | M | W104 | Operator generates quarterly audit bundle in 1 click |
| B6 | Privacy Mode branding               | Toggle in Settings; visible badge in cockpit; doc update | S | already local-first | "Private" badge visible when no cloud LLM keys set |
| B7 | Notepad templates                   | Saved prompts + pinned context, runnable from Cmd+K | M | A6 + A7 | 5 starter notepads ship with v9.3 |
| B8 | `tars-tab` VS Code extension        | Inline completion via TARS backend; receipts per accept | L | A1 + A7 | First Cursor user installs both side-by-side and says "I'd switch" |
| B9 | Codebase index scale-up             | Incremental rebuild on file save; warm cache; local model fallback | L | sqlite-vec | Query latency <200ms on a 500K-LoC repo |
| B10 | Update channel published           | Tauri updater JSON live + signed | S | Apple cert | First in-app auto-update lands without operator action |

### 6.3 Wave C — beyond Cursor (12+ weeks, W321+)

| #  | Item | Desc | Effort | Dep | Success metric |
|----|------|------|--------|-----|----------------|
| C1 | TARS-to-TARS handoff for code review | PR-style review where my agent hands the diff to your agent for second opinion | XL | T2T (W81) + B2 | One TARS user reviews another's PR via T2T; both sign the receipt |
| C2 | B2B compliance export for code changes | Quarterly bundle of "every code change agent made, with proof, with model, with cost" — sellable to regulated industries | L | B5 + B3 | First fund/enterprise customer pays for the export |
| C3 | Voice-first pair programming | Operator dictates intent; TARS narrates back what it will edit; receipt-confirms each step | XL | B1 + voice cockpit | E2E demo: 20-minute pair session with zero clicks |
| C4 | Agent economy marketplace | Third-party agents listed by capability + price/call; T2T discovery | L | T2T + marketplace | 10 third-party agents earning $MEEET |
| C5 | On-prem TARS for funds/enterprises | Air-gapped install with local models + audit | XL | privacy + compliance | First on-prem deployment to a regulated org |
| C6 | Domain-pack federation | Wealth pack can call Health pack mid-flow under user consent | M | rules + receipts | Cross-pack action emits a federated receipt |

---

## 7. Pricing & metering strategy alignment

### 7.1 Cursor's model

```
tier (Hobby/Pro/Business)
  -> request quota (500/mo fast, unlimited slow, 2K Tab)
  -> soft-warn at 80%
  -> hard-block at 100% (or overage billing if enabled)
  -> opaque cost-per-request (user doesn't see $/req)
```

Strengths: simple, predictable, fits a typical SaaS subscriber's mental
model. Weaknesses: opaque (what's a "fast request"?), per-request not
per-action (the unit isn't aligned with the value the user perceives),
single-currency, no audit trail.

### 7.2 TARS' proposed model

```
tier (FREE/PRO/BUSINESS via meeet.world)
  -> metered $MEEET spend per action (or USD via Solana/card)
  -> real-time console (cockpit Usage tab streams every event)
  -> receipt ledger anchors every spend (hash-chained + Solana memo)
  -> multi-asset: pay in USD, pay in $MEEET, earn $MEEET back
  -> audit-grade: every dollar maps to a verifiable receipt
```

### 7.3 Why TARS' approach is structurally better

1. **Transparency.** Per-action cost surfaces in the cockpit; user sees
   exactly where their money went. Cursor's "fast request" abstraction
   hides the underlying model + token cost.
2. **Immutable audit.** Hash-chained receipts + Solana anchor mean a B2B
   customer's compliance officer can verify "in Q3, your AI ran N actions
   costing $X" without trusting our internal logs. Cursor cannot offer
   this — their audit log is their own database.
3. **Multi-asset.** USD via card, $MEEET via Solana, earn-back via quests.
   The user has currency optionality; the platform has demand drivers for
   the token. Cursor is USD-only.
4. **On-chain proof for B2B compliance.** A regulated fund running TARS
   under Workshop can attach Solana-anchored Merkle proofs to its
   quarterly compliance pack. Their auditor can verify without our
   cooperation. This is the wedge to sell into industries Cursor can't
   touch (regulated finance, healthcare, legal, anything HIPAA/GDPR/SOX).
5. **Closed-loop economy.** $MEEET earned via marketplace contributions
   (publishing a skill that someone installs, contributing to a Cowork
   session, completing a quest) cycles back into TARS subscription. This
   creates non-monetary acquisition that Cursor structurally cannot
   replicate.

### 7.4 The risk and the mitigation

Risk: $MEEET token volatility could make the per-action cost opaque to the
user ("how much is 5 $MEEET in dollars right now?"). Mitigation: cockpit
always shows both ($MEEET *and* USD-equivalent at current rate) and the
receipt records both for the audit trail. Quarterly compliance bundle
converts to USD at the daily VWAP, locking in a defensible cost basis.

Risk: regulators view $MEEET-priced services as securities. Mitigation:
$MEEET is a utility token; USD is always an accepted alternative; user
never has to touch the token to use TARS. Pricing page leads with USD;
token is "advanced settings."

---

## 8. Recommended sequencing — exec summary

**Next 2 weeks (W234–W260, Wave A):** ship usage meter, models switcher,
rules system, `@-mentions`, MCP panel, background agents tray. This makes
TARS competitive on Cursor's strongest features.

**Weeks 4–12 (Wave B):** ship voice-driven Composer, code-change receipts,
SOC2 audit UI, `tars-tab` VS Code extension. This pulls Cursor's
dev-audience floor toward TARS without becoming a VS Code fork.

**Weeks 12+ (Wave C):** T2T code review, on-prem TARS, voice pair-programming,
agent economy marketplace. This is where TARS leaves Cursor's surface and
plays a board Cursor cannot reach.

**Underneath all three:** the receipt-and-Solana metering substrate.
Cursor would need to redesign their economic model from scratch to match;
brother only needs to wire the usage_event endpoint and we're live.

The strategy is not "out-Cursor Cursor." It is: be unambiguously better
on the audience Cursor cannot serve (life ops, regulated industries,
on-chain transparency), while closing the friction gap on the surface
Cursor's audience overlaps with ours (devs who also live their life).

---

## 9. Open questions for operator

1. Does the $20/mo Pro price point hold, or do we test $25 with the new
   metered features?
2. Do we ship `tars-tab` as a separate VS Code extension (lower friction,
   broader reach) or only inside TARS.app (tighter receipt-loop, higher
   trust)?
3. Is on-prem TARS (C5) a 2026 deliverable or a 2027 deliverable? It blocks
   the largest B2B deals but consumes a quarter of engineering time.
4. Domain-pack-aware code suggestions (B4) is a unique angle — does the
   operator want it surfaced as a marketing message ("TARS knows your life,
   not just your codebase") or hidden as a power-user feature?

Decisions on these four unlock the W261+ commit sequence. None of them
block Wave A.

---

## 10. Appendix — Cursor positioning vs TARS positioning

Cursor's pitch in 2026 reads: "the AI code editor — faster than Copilot,
agent-native, your codebase indexed." It's a tool that wins on *velocity
inside the IDE*.

TARS' pitch should read: "the local-first operator console for AI agents
on your Mac. Voice. Receipts. Council. Domain packs. Cowork. On-chain
verifiable. Not just for code." It's a tool that wins on *trust + breadth
+ proof*.

Both can exist. They overlap on the "AI agent runs my computer" surface
and diverge on everything else. Wave A closes the overlap-surface
frictions; Wave B+C extends TARS into space Cursor can't follow without
abandoning its core thesis.

That divergence is the strategic asset. Defend it.
