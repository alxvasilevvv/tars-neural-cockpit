# Roadmap — W234 → v10 (Wave A closure + Cursor parity)

> **Source of truth:** `COMPETITIVE_ANALYSIS_CURSOR.md` §6.1.
> **Companion:** `PRICING_ECONOMICS_v9.2.md` for the numbers brother needs.
> **Owner:** Claude lane W234+; Cursor lane W235 implements concurrently.
> **Author:** TARS strategy desk, 2026-05-15.
> **Format:** each commit ~½ day of work; each item carries an explicit
> success metric and dependency.

This file translates Wave A (Cursor-parity closure) into a sequenced commit
plan. Wave B and C are scoped in the competitive analysis doc but not
expanded here — they unlock after Wave A lands.

---

## 0. Conventions

- Each commit: `Wxxx: <imperative subject>`.
- Each commit is independently revertable.
- Each commit pushes green tests (or adds the tests it needs).
- No commit lands without an entry in `CHANGELOG_PUBLIC.md` if user-facing.
- Backend changes that need brother's side coordinated are tagged
  `[brother dep]` with the contract.
- Frontend changes that need a new endpoint reference the backend wave.

---

## 1. Track summary

| Track     | Waves         | Owner       | Outcome |
|-----------|---------------|-------------|---------|
| Backend usage bus      | W234–W238 | Claude   | `/api/usage/*` endpoints stream live cost |
| Frontend metering console | W239–W244 | Cursor (W235 placeholder) | Cockpit Usage tab live |
| meeet.world billing    | W245–W249 | Brother + Claude | Billing/usage_event + balance endpoints |
| Models switcher        | W250–W252 | Claude   | Provider picker shows cost labels |
| Rules system           | W253–W255 | Claude   | `.tars/rules.yml` loaded into agent prompt |
| `@-mention` resolver   | W256–W258 | Claude   | 4 mention types live in Chat tab |
| MCP servers panel      | W259      | Claude   | Settings → MCP UI |
| Background agents tray | W260      | Claude   | Cockpit tab shows running daemon tasks |

Wave A exit: W260 lands and a Cursor refugee user has no missing friction.

---

## 2. Backend — usage event bus (W234–W238)

### W234 — this commit (analysis + plan, no code)

- `docs/COMPETITIVE_ANALYSIS_CURSOR.md` (this Wave A doc family).
- `docs/ROADMAP_W234_to_v10.md` (this file).
- `docs/PRICING_ECONOMICS_v9.2.md` (numbers for brother).
- Author: `TARS <tars@local>`.
- **Success:** brother + Cursor lane have ground truth for everything that
  follows.

### W235 — usage event schema canonization

- Define `UsageEvent` Pydantic schema in `backend/core/usage/schema.py`:
  ```
  ts, trace_id, action, provider, model, tokens_in, tokens_out,
  cost_usd, cost_meeet, tier, user_id, project_id
  ```
- Migrate existing `usage.tokens` events from `meeet_billing.events` table
  to the new schema with backfill script.
- **Dep:** `backend/core/meeet/store.py`, `backend/core/usage/ledger.py`.
- **Success:** pytest `test_usage_schema.py` round-trips a usage event with
  no field drift.

### W236 — `/api/usage/stream` SSE endpoint

- New FastAPI router `backend/core/usage/router.py`.
- SSE stream: every new `UsageEvent` pushed to subscribed clients within
  100ms.
- Authenticated via existing meeet token middleware.
- **Dep:** W235 schema, FastAPI sse-starlette.
- **Success:** curl with token sees events stream in real time; throughput
  test handles 100 events/sec without dropping.

### W237 — `/api/usage/console` aggregator

- GET endpoint returning last-30d aggregated by action + model + day.
- Query: `?from=ISO8601&to=ISO8601&group_by=model|action|day`.
- Returns JSON `{rows: [...], totals: {usd, meeet, requests}}`.
- **Dep:** W235 schema, sqlite-vec already indexes by ts.
- **Success:** test_usage_console.py validates 7-day window returns
  expected sum within ±0.01 USD.

### W238 — `/api/usage/budget` endpoint + entitlement integration

- GET returns: `{tier, monthly_cap_usd, monthly_cap_meeet, used_usd,
  used_meeet, pct_used, reset_at}`.
- Pulls cap from `backend/core/entitlements/tiers.py` LIMITS table.
- Wired into existing entitlements checker — when `pct_used >= 1.0`,
  consequential actions are denied with HTTP 402.
- **Dep:** W237, entitlements/tiers.py existing.
- **Success:** integration test forces tier=FREE, exhausts budget, next
  /api/voice/command returns 402 with a human-readable hint.

---

## 3. Frontend — consumption console (W239–W244)

Cursor lane (W235 placeholder agent) implements this in parallel. Claude
provides the spec; Cursor writes the components.

### W239 — Cockpit Usage tab scaffold

- New tab in `TARS.app` cockpit nav: `Usage` (between Activity and
  Connectors).
- Tab layout: 3 columns — Live (SSE feed), Today (per-action table),
  Monthly (cap progress bar + sparkline).
- **Dep:** W236, W237, W238.
- **Success:** tab renders with empty state when no events; populates
  within 1s of first event.

### W240 — Live SSE stream component

- Component `UsageLiveFeed.tsx` subscribes to `/api/usage/stream`.
- Renders a tail-style log: `[12:34] voice.transcribe · whisper · 1.2s · $0.003`.
- Auto-trim to last 50 entries.
- **Dep:** W236, W239.
- **Success:** events visible within 1s end-to-end; no memory leak on
  100-event burst.

### W241 — Today breakdown table

- `UsageToday.tsx` polls `/api/usage/console?from=today` every 30s.
- Table: action, model, requests, tokens, $USD, $MEEET.
- Sort/filter on each column.
- **Dep:** W237.
- **Success:** Cypress test populates 5 actions across 3 models, table
  shows correct totals.

### W242 — Monthly cap progress bar

- `UsageMonthlyCap.tsx` polls `/api/usage/budget` every 60s.
- Progress bar with 80% soft-warn color shift (amber) and 100% block-state
  (red).
- Hover: "$12.40 / $20.00 — resets in 14 days".
- **Dep:** W238.
- **Success:** at 80% used, color shifts; at 100%, action buttons in cockpit
  disable with explanatory tooltip.

### W243 — Toast at 80% soft cap

- Global toast fires once per day when crossing 80%.
- "You've used 80% of your monthly budget. Upgrade or wait for reset."
- Dismissible; persists in localStorage to avoid spam.
- **Dep:** W242.
- **Success:** integration test triggers crossing, toast appears,
  localStorage stops it on second load.

### W244 — Hard-block UX

- When entitlements checker returns HTTP 402, cockpit shows a modal:
  "You've hit your monthly cap. Upgrade to Pro for $20/mo or 200 $MEEET."
- CTA: meeet.world checkout URL.
- **Dep:** W238, W242.
- **Success:** force-block in test env triggers modal; CTA links to
  brother's checkout.

---

## 4. meeet.world integration (W245–W249) [brother dep]

Brother's side. Three endpoints. Contracts pinned here, ship to him
verbatim.

### W245 — `POST /api/billing/usage_event` contract

- Receives a `UsageEvent` from TARS over signed webhook (BRIDGE_SHARED_SECRET).
- Increments user's monthly spend counter.
- Idempotency key: `trace_id` (reject duplicate).
- Response: `{ok: true, balance_usd_remaining, balance_meeet_remaining}`.
- **Brother needs:** the schema from W235, the secret from W194.
- **Success:** TARS emits an event; meeet logs it; balance decreases.

### W246 — `GET /api/billing/balance` contract

- Returns `{user_id, tier, balance_usd, balance_meeet, period_start,
  period_end}`.
- Authenticated via magic-link token.
- Cached 60s server-side.
- **Brother needs:** the tier table from `PRICING_ECONOMICS_v9.2.md`.
- **Success:** TARS cockpit polls; balance updates within 60s of last
  spend event.

### W247 — `POST /api/billing/topup` contract

- Body: `{amount_usd | amount_meeet, payment_method}`.
- Routes to existing Solana payment relayer for $MEEET; Stripe (already
  removed per W58 — brother needs to confirm replacement card processor)
  for USD.
- Response: redirect URL for payment flow.
- **Brother needs:** confirm card processor or fall back to $MEEET-only.
- **Success:** test top-up of $10 USD via card processor increments
  balance, emits receipt.

### W248 — TARS-side webhook signer

- `backend/core/meeet_billing/webhook_signer.py` signs every outbound
  usage event with HMAC-SHA256 using BRIDGE_SHARED_SECRET.
- **Dep:** W235, BRIDGE_SHARED_SECRET (W194 already distributed).
- **Success:** brother validates signature on his side; events with bad
  signatures rejected.

### W249 — Reconciliation script

- `scripts/reconcile-meeet-billing.py` — daily cron that compares TARS'
  local ledger with brother's `/api/billing/balance`.
- Drift > $0.50 triggers alert via doctor notification fanout (W162).
- **Dep:** W245, W246.
- **Success:** runs nightly; first 7 days show drift < $0.10.

---

## 5. Models switcher with cost labels (W250–W252)

### W250 — Cost label data plumb

- Extend existing `/api/llm/providers` to include `cost_in_per_mtok` and
  `cost_out_per_mtok` from `backend/core/usage/ledger.py` price table.
- **Dep:** ledger.py already has the table.
- **Success:** API returns `[{id, name, cost_in_per_mtok, cost_out_per_mtok}]`.

### W251 — Cockpit Models switcher UI

- Settings → Models tab: list of providers with toggle, BYO key input,
  and cost label `"$3 / $15 per Mtok"`.
- Per-project default model dropdown.
- **Dep:** W250.
- **Success:** user can pick Sonnet for project A, Haiku for project B;
  selection persists in `~/.tars/projects.json`.

### W252 — Pre-send cost estimator

- Chat tab: before sending, calculate `tokens_in_estimate * cost_in +
  expected_tokens_out * cost_out`.
- Show as a small hint under the input: `~$0.04`.
- Tokenizer: `tiktoken` for OpenAI, Anthropic's tokenizer otherwise.
- **Dep:** W250.
- **Success:** estimate is within ±15% of actual on a 20-prompt sample.

---

## 6. Rules system — `.tars/rules.yml` (W253–W255)

### W253 — Rules schema + loader

- File format:
  ```yaml
  version: 1
  rules:
    - name: "no migrations"
      match: ["**/migrations/**"]
      action: deny_edit
    - name: "prefer fastapi"
      match: ["**/*.py"]
      inject: "When writing Python, prefer FastAPI for HTTP, not Flask."
    - name: "domain pack"
      always: true
      inject: "This project is in the wealth domain pack."
  ```
- Loader at `backend/core/rules/loader.py`. Reads `.tars/rules.yml` from
  current project root.
- **Dep:** none.
- **Success:** pytest validates schema + loader on 3 sample rule files.

### W254 — Rules injection into agent prompt

- `backend/core/agents/runner.py` reads rules at agent start, injects
  matching rules into system prompt.
- `deny_edit` rules halt the agent and emit a receipt with
  `outcome=denied_by_rule`.
- **Dep:** W253.
- **Success:** rule "deny migrations/" actually blocks an agent attempting
  to edit a file under migrations/; receipt recorded.

### W255 — Cockpit rules editor

- Settings → Rules tab: list of rules, edit/add/delete.
- File written back to `.tars/rules.yml`.
- Validation: schema check on save.
- **Dep:** W253.
- **Success:** add a rule via UI; agent picks it up on next run; receipt
  references the rule name.

---

## 7. `@-mention` chat context resolver (W256–W258)

### W256 — Resolver backend

- `backend/core/chat/mentions.py` with 4 resolvers:
  - `@file <path>` → reads file from project, max 50KB.
  - `@folder <path>` → lists folder, reads top 5 files.
  - `@recent-changes` → `git diff HEAD~5..HEAD` truncated to 20KB.
  - `@web <query>` → calls existing web search pack, returns top 3.
- All return `{type, content, source_uri}` for prompt injection.
- **Dep:** code-RAG (W135), search pack.
- **Success:** each resolver returns in <500ms on a 100K-LoC repo.

### W257 — Chat input mention autocomplete

- Frontend: typing `@` opens a popover with categories (file, folder,
  recent-changes, web).
- Type-ahead match against project files / recent diff names.
- Selected mention renders as a chip in the input bar.
- **Dep:** W256.
- **Success:** type `@auth` and see `backend/core/auth.py` in the
  popover; click pins it.

### W258 — Mention persistence across messages

- Pinned mentions in a session are sticky — every subsequent message in
  the thread re-injects them.
- Unpin via chip-click `x`.
- Pinned mentions show in a row above the input.
- **Dep:** W257.
- **Success:** pin `@file auth.py`; send 3 messages; all 3 prompts include
  auth.py content (verified in receipts).

---

## 8. MCP servers panel (W259)

### W259 — Settings → MCP UI

- Lists registered MCP servers from `backend/core/mcp/server.py` registry.
- Toggle on/off (writes to `~/.tars/mcp.json`).
- Status indicator (connected / error / loading).
- "Add server" form with URL + auth token fields.
- **Dep:** W150 MCP registry.
- **Success:** disable an MCP server via UI; next agent invocation does
  not see that server's tools.

---

## 9. Background agents tray (W260)

### W260 — Cockpit Tasks tab

- New tab `Tasks` showing all daemon-spawned + supervisor-spawned agents
  with status (queued / running / waiting-on-HIL / completed / failed).
- Click row → expands to Watch-me-work timeline (W77 component reused).
- Resume button for tasks waiting on HIL.
- Notification badge on the tab when any task changes state.
- **Dep:** W77 timeline, W152 daemon, W76 supervisor.
- **Success:** start an agent; close cockpit; reopen 10 min later; see
  task in Tasks tab with current status.

---

## 10. Cursor Tab equivalent — future design (Wave B sketch)

Not Wave A. Captured here so the Wave A surfaces compose into it.

- Ship as a VS Code extension `tars-tab` published in Cursor's marketplace
  (Cursor inherits VS Code extensions).
- Extension calls `POST /api/completion/inline` against TARS backend on
  every keystroke debounce.
- Backend: routes to user's configured model (from W251 switcher), emits
  a `usage.completion` event per accept (W235 schema).
- Receipt per accept = 1 line, $0.0001-ish, but it builds the audit trail.
- Privacy: completions only hit TARS backend on `localhost:8765` — never
  leave the box without explicit user consent.
- This is *the* path to peeling Cursor's audience: same editor, better
  trust + receipt + multi-asset metering.

---

## 11. Pricing copy update (W260b)

(W260 lands the Tasks tab; W260b is the marketing pass that goes out
with it.)

- Landing page (`web_extras/`): Pricing section reflects new
  PRICING_ECONOMICS_v9.2.md numbers.
- Cockpit Settings → Billing block mirrors landing.
- Cockpit Welcome modal (W205) explains the new metering.
- **Success:** landing, cockpit, and brother's checkout page show identical
  tier numbers.

---

## 12. Definition of done — Wave A

A Cursor-refugee user opens TARS, signs in via magic-link, opens the
Chat tab, and:

- Sees their tier, balance, monthly budget at a glance.
- Sees a cost estimate before sending each prompt.
- Can pin `@file`, `@folder`, `@recent-changes`, `@web` into context.
- Can pick a different model with a visible cost label.
- Can edit `.tars/rules.yml` from Settings to constrain agent behavior.
- Can see active background agents in the Tasks tab.
- Can toggle MCP servers in Settings.
- Sees a toast at 80% budget; sees a hard block at 100%.
- Every prompt + every action emits a verifiable receipt with cost.

If all of the above is true, Wave A is shipped. v9.3.0 ships at W260.

---

## 13. Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Brother slow on W245-W247 | High | TARS-side mock endpoint at `/api/_meeet_mock` so cockpit doesn't block on his ship |
| Tokenizer estimate off by >15% | Med | Calibrate against actual cost on first 100 prompts; auto-adjust |
| SSE stream chokes on >100ev/s | Low | Add per-client rate limit; batch into 100ms windows |
| `.tars/rules.yml` becomes a footgun (deny everything by accident) | Med | First rule fail surfaces a banner; doctor check catches empty allow set |
| `@web` resolver costs $$$ on free tier | Med | Cache results per query for 24h; FREE tier capped at 5 web mentions/day |
| Models switcher confuses non-technical users | Low | Hide behind "Advanced" by default; show only when user has BYO key |

---

## 14. Coordination calendar

- **W234 (today):** Claude lands analysis docs (this commit).
- **W235-W238 (next 4 commits):** Claude lands usage bus backend.
- **W239-W244 (concurrent):** Cursor lane lands frontend; Claude reviews.
- **W245-W249:** brother lands billing endpoints. Synchronous handoff.
- **W250-W260:** Claude lands switcher / rules / mentions / MCP / Tasks.
- **W260b:** marketing pass + v9.3.0 release notes + tag.
- **Target ship date:** 2026-06-12 (4 weeks from W234).

---

## 15. Out of scope for Wave A (deferred to B/C)

- VS Code extension (`tars-tab`) — Wave B.
- Diff renderer for Composer-style edits — Wave B.
- SOC2-branded audit log UI — Wave B.
- Cross-instance T2T code review — Wave C.
- On-prem TARS — Wave C.
- Voice-driven Composer — Wave B (depends on `@-mentions` from Wave A).

These are tracked in `COMPETITIVE_ANALYSIS_CURSOR.md` §6.2 and §6.3 and
will be re-scoped at the W260 retro.

---

## 16. Linkage

- This file lives at `docs/ROADMAP_W234_to_v10.md`.
- Sibling: `docs/COMPETITIVE_ANALYSIS_CURSOR.md` (the why).
- Sibling: `docs/PRICING_ECONOMICS_v9.2.md` (the numbers).
- Brother's handoff: append to `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md`
  before W245 starts; add a section pointing at W245-W249 contracts.
- Cursor lane sync: ping in `docs/SYNC.md` when W235 backend is mergeable.

Wave A is small, mechanical, and high-leverage. Ship it.
