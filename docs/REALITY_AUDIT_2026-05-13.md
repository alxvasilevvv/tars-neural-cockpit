# TARS Reality Audit — 2026-05-13

> Read-only forensic audit by a fresh agent reading code (not docs).
> Goal: separate what truly works end-to-end from what is mocked,
> stubbed, gated behind unset env vars, or aspirational. The marketing
> on `tars.meeet.world` MUST be a strict subset of the FULLY column
> below.

---

## 1. Executive summary

Counted by subsystem (16 audited):

- **FULLY (production-ready end-to-end):** **3**
  Receipts ledger (hash chain + Merkle compute), Compliance export
  bundler, Workshop pages (FE shell).
- **PARTIAL (works but mocked / env-gated at a real seam):** **9**
  Cowork backend, Webhooks (out + in), Scheduler, Outreach,
  Marketplace, Connectors (Slack/Gmail/Cal/Telegram), AI Clone v0.1,
  Background TARS, Mac actions / Calendar reader, Voice STT/TTS.
- **STUB (returns deterministic responses, no real integration):** **2**
  Solana Merkle anchor (real code, off by default; never demonstrated
  firing on the operator's machine), Telegram outbound (requires token
  the operator may not have).
- **MISSING (claimed in docs, no shipping code):** **2**
  iMessage bridge (`backend/core/notifications/imessage.py` does not
  exist), AI Clone v1 fine-tune (only v0.1 style-hint ships), HTTP
  router for `/api/cowork/*` (module exists, surface does not).

**Bottom line:** the *engines* are wired in Python; what's missing in
many subsystems is the **HTTP surface, real third-party credentials,
or the live execution context**. A demo on a fresh laptop with no env
vars gives a clean Python module-imports-cleanly story (the W139
sign-off claim, which is true) but does NOT give a clean
end-user-can-hit-it story for most named features.

---

## 2. Per-subsystem analysis

### Subsystem matrix

| # | Subsystem | State | Evidence |
| - | --- | --- | --- |
| 1 | Cowork backend module | 🟡 PARTIAL | `backend/core/cowork/` ships clean (4 tables, store, presence, stream, handoff). 38/38 pytest. But **no HTTP router** in `web_extras/routers/` — 10 advertised `/api/cowork/*` routes deferred to v9.1.1 brother handoff. |
| 2 | Cowork orchestrator fan-out | 🟡 PARTIAL | `backend/core/agents/runner.py:111-196` emits `task.{started,completed,failed}` only when `metadata['cowork_session_id']` is set. Opt-in, never auto-attached by any caller in the repo. |
| 3 | Webhooks — outgoing dispatch | ✅ FULLY (engine) / 🟡 PARTIAL (coverage) | Real HMAC sign + retry budget + 4 attempts + Retry-After honored in `dispatcher.py`. **But emit sites are sparse**: WHAT_WORKS.md row 142 admits per-feature emit (outreach, scheduler, files, reports, compliance) is incremental and full coverage is v9.3. |
| 4 | Webhooks — incoming inbox | 🟡 PARTIAL | Real HMAC verify + token lookup + playbook trigger in `inbox.py`. Route exists. Needs an externally reachable URL (operator's local box is firewalled by default) — works when exposed via tunnel. |
| 5 | Receipts ledger | ✅ FULLY | Hash-chained NDJSON store + chain verification + Merkle compute live. `record()`, `verify_chain()`, `compute_root()` all real. NDJSON path under `~/.tars/receipts/`. |
| 6 | Receipts — Solana anchor | ⚠️ STUB (in practice) | Real code in `anchor.py` using `solders` lib. **Gated by TWO env vars:** `TARS_RECEIPT_ANCHOR_ENABLED=1` AND `SOLANA_KEYPAIR_PATH`. Default off. The merkle loop in `app.py:556-625` only fires after UTC midnight + 1h on the host. No evidence it has ever fired on the operator's box. |
| 7 | Scheduler | 🟡 PARTIAL | Cron parsing + tick loop in `runner.py`. **Disabled by default** — needs `TARS_SCHEDULER_ENABLED=1`. Tick interval default 30s. Persistence + restart-safety implemented. |
| 8 | Outreach (Gmail send) | 🟡 PARTIAL | Real Gmail API call via `users.messages.send` in `sender.py:181-192`. Depends on Wave 91 Gmail OAuth token being present. Falls through with `gmail_not_configured` / `gmail_no_token` errors otherwise. |
| 9 | Outreach — AI Clone drafting | 🟡 PARTIAL | Uses AI Clone v0.1 (style hint), not real per-user fine-tune. Real LLM call goes to Anthropic / OpenAI when keyed. Output quality bounded by the style heuristic. |
| 10 | Marketplace v0 | 🟡 PARTIAL | In-process registry + 12 seed listings in `backend/core/marketplace/`. Real ed25519 signature **opportunistic** ("warn, don't block" per `installer.py:24-30`). **Payouts not live**, third-party publish not live (matches WHAT_WORKS row 145/146). |
| 11 | Compliance export bundler | ✅ FULLY | `bundler.py` walks every SQLite DB under `~/.tars/`, hash-chains receipts, signs manifest, ships `verifier.py` for offline check + `gdpr.py` + `redaction.py`. Audit-grade as claimed. |
| 12 | Workspaces (W110) | 🟡 PARTIAL (schema-only) | `backend/core/workspaces/middleware.py:1-25` explicitly says "**does not enforce fencing on any existing endpoint** — deferred to v9.3." A schema only. Personal workspace auto-creates. No tenant isolation in v9.1.0. |
| 13 | Connectors — Slack/Gmail/Calendar | 🟡 PARTIAL | Real OAuth v2 flows + `urllib` read API in `slack.py`/`gmail.py`/`calendar.py`. Require `*_CLIENT_ID`/`*_CLIENT_SECRET`/`*_REDIRECT_URI` env. Slack writes intentionally stubbed (`post_message` returns `{"ok": False, "error": "post_disabled"}`). |
| 14 | Connectors — Telegram | 🟡 PARTIAL | Real bot client in `telegram.py` (long-poll + webhook + outbound). Requires `TELEGRAM_BOT_TOKEN`. Outbound `telegram://` webhook delivery hooked into the dispatcher (`dispatcher.py:117-174`). |
| 15 | Connectors — GitHub | 🟡 PARTIAL | Token-based read (`web_extras/routers/github.py`) with 60s LRU. **Write side missing** (WHAT_WORKS row 141 — v9.3 with webhooks). |
| 16 | AI Clone v0.1 | 🟡 PARTIAL | `backend/core/clone/style.py` ships heuristic style profiler + similar-message lookup + LLM rewrite. Real, but explicitly labeled "style hint, not full clone" in WHAT_WORKS row 52. |
| 17 | AI Clone v1 (fine-tune) | ❌ MISSING | No fine-tune code path. WHAT_WORKS row 154 acknowledges this is v9.2. |
| 18 | Background TARS daemon | ❌ MISSING (despite older claims) | No `backend/core/background/` directory. WHAT_WORKS row 143 admits "trigger DSL is minimal" and v9.2 → standalone headless mode. The "daemon" today is the FastAPI app's lifespan loops (Merkle loop, dispatcher loop, scheduler) — not a separate process. |
| 19 | Mac actions / Calendar reader | 🟡 PARTIAL | Calendar reader: real ICS parsing in `backend/core/connectors/calendar.py`. Mac actions live as Tauri sidecar code in `desktop/src-tauri/`. Sort/Summarize/Web/Run/Anchor exist as endpoints but most chain to LLM (so quality bounded by LLM contract). |
| 20 | Voice STT (Whisper API) | 🟡 PARTIAL | Real POST to `api.openai.com/v1/audio/transcriptions` in `transcribe.py`. 503 when `OPENAI_API_KEY` unset. Optional local `WHISPER_LOCAL_PATH` is best-effort. |
| 21 | Voice TTS (XTTS + fallback) | 🟡 PARTIAL | XTTS-v2 + system-voice fallback in `synthesis.py`. Real. Voice-cloning bundle deferred to v9.2 per WHAT_WORKS row 159. |
| 22 | iMessage bridge | ❌ MISSING | `backend/core/notifications/imessage.py` does **not exist** (verified by Grep — no path matches `notifications/imessage`). WHAT_WORKS row 144 admits "Mac-only stub. v9.1.1." but file is absent. |

---

## 3. Honest claim vs marketing-claim discrepancies

> Comparison between WHAT_WORKS.md (the internal honest ledger) and
> the actual code, plus where outside-facing copy may have drifted.

### 3.1 Cowork — biggest drift

- **WHAT_WORKS row 121 (the headline-flag row)** says: *"Backend module
  ships in this release; the 10 `/api/cowork/*` HTTP routes land in
  v9.1.1 (brother handoff at `docs/handoff/COWORK_WIRING_FOR_CURSOR.md`).
  Frontend transparently mocks until then."*
- `COWORK_HEALTH_SNAPSHOT.md` correctly notes **"NONE in primary SPA"**
  for the frontend (the React surface was deleted in `e5f1911`).
- **Net effect today:** Cowork backend is real, exhaustively tested,
  but **invisible to any end-user** — no HTTP, no UI in the desktop
  shell. The row claims "Backend module ships" which is true, but a
  reader could easily infer that the whole subsystem is shippable.

### 3.2 Background TARS — claim outruns code

- WHAT_WORKS row 143 says "Daemon runs; trigger DSL is minimal."
- Reality: there is **no separate background process**. The lifespan
  hooks inside the main FastAPI app run a Merkle loop, scheduler tick,
  and webhook retry loop. Calling that "Background TARS" is a stretch.
- Marketing copy that says "TARS keeps working when you close it"
  would be wrong on most user machines, since the FastAPI server is
  not a daemon — it dies with the shell.

### 3.3 Solana anchoring — capability exists, fires never

- The `anchor_to_solana()` function in `backend/core/receipts/anchor.py`
  is genuinely live code, signs a real Solana memo transaction.
- But **two env gates** (`TARS_RECEIPT_ANCHOR_ENABLED=1` AND
  `SOLANA_KEYPAIR_PATH`) must be set for it to fire. On a stock dev
  box neither is set. **No evidence this has fired in production.**
- Marketing claims like "audit-grade compliance anchored on Solana"
  are *conditionally true* — the auditor would have to verify env
  was set.

### 3.4 Workspaces — schema-only, not multi-tenant

- WHAT_WORKS row 164 says "Single-user only today; `WORKSPACES.md`
  contract published; Wave 110 backend MVP in flight (additive,
  schema-only)."
- Code confirms: `middleware.py:1-25` explicitly says it **does not
  enforce fencing**. So any marketing copy implying "multi-tenant
  ready" is wrong. Reads/writes have no `workspace_id` gate.

### 3.5 Marketplace — no payouts, no third-party submit

- WHAT_WORKS rows 145-146 are honest: "70/30 payouts NOT live",
  "third-party publish flow pending."
- Code matches: 12 seed listings hardcoded; `installer.py:25-30`
  admits "v0 trust model is warn-don't-block" for signatures.

### 3.6 iMessage — claimed, file absent

- WHAT_WORKS row 144 says "Mac-only stub. v9.1.1."
- Code search returns zero hits for `backend/core/notifications/`. The
  module simply doesn't exist. Even the "stub" claim is too generous.

### 3.7 Webhooks event coverage

- WHAT_WORKS row 142 explicitly admits emit sites are wired
  "incrementally." Confirmed: only `algotrade` and the unified receipt
  ledger emit `receipt.*` today. Outreach/scheduler/files/reports/
  compliance — all on v9.3.

### 3.8 AI Clone

- Honestly labeled v0.1 (style hint). The "AI Clone v1" capability in
  Pro tier marketing would need to call this out — what ships is a
  small, useful style-rewrite layer, not a real per-user fine-tuned
  model.

---

## 4. Critical gaps blocking real adoption

### 4.1 No HTTP surface for Cowork

The marquee Cowork feature has **zero routes wired in the FastAPI app**.
The brother needs to ship `web_extras/routers/cowork.py` (10 routes)
before any user can hit it. Until then, it's a library, not a feature.

### 4.2 No persistent daemon

"Continuous awareness" and "Background TARS" assume a process keeps
running. Today it's a uvicorn invocation that dies when the desktop
sidecar exits. The Tauri sidecar (`desktop/src-tauri/src/sidecar.rs`)
restarts on crash, but the user has to keep the desktop app open.

### 4.3 Solana anchor unverified in production

No environment in the repo has both env vars set by default. There is
no e2e test that exercises a real testnet anchor (would require a
fixture keypair). The compliance-export claim that receipts are
"audit-grade and anchored" is only true when the operator pastes a
keypair path into `.env`.

### 4.4 Workspaces is a feature flag, not a feature

`X-Workspace-Id` is read but ignored. Every connector pull, every
receipt write, every webhook delivery operates on a single global
store. A second org dropping into the same TARS instance would
collide. Anything sold as "multi-tenant" today is misleading.

### 4.5 Most connectors need OAuth client credentials the user lacks

Slack/Gmail/Calendar OAuth flows are real, but require `SLACK_CLIENT_ID`,
`GOOGLE_CLIENT_ID`, etc. — these are app-registration secrets the
operator's friend (the brother running meeet.world) controls, not
something an end user provides. URL-redirect OAuth ships; the Chrome
"Quick Connect" extension doesn't.

### 4.6 Frontend gap is enormous

The W142 cleanup deleted the React SPA. The marketing site
(`tars.meeet.world`) is served by a small CF Pages function set that
just redirects to GitHub Releases for installer downloads. There is
**no operator UI in this repo today** — the user has to install the
desktop bundle (`desktop/src-tauri/web/` static shell, ~44 assets) and
use that. Many "features" referenced in WHAT_WORKS are backend-only
or trivially-rendered desktop pages.

### 4.7 Background loops are off by default

- `TARS_SCHEDULER_ENABLED` — default off
- `TARS_RECEIPT_ANCHOR_ENABLED` — default off
- `TARS_COWORK_STORE=disabled` is a kill switch (on by default, but
  the store is empty until the HTTP surface lands)
- Webhooks dispatcher tick loop — runs when store enabled, but no
  outgoing webhooks are seeded.

A first-run user effectively sees a quiet system unless they read
env-var docs.

---

## 5. What CAN we honestly say about TARS today?

Strip everything down to verifiable truth, in the language of a B2B
diligence call:

1. **TARS is a local-first Python backend plus a Tauri desktop shell.**
   `make desktop-build` produces a signed (ad-hoc) macOS `.dmg` and the
   v9.1.0 GitHub Release has it. The release has been downloaded 194
   times.

2. **It runs a real LLM council** (`backend/core/council/`) plus a
   playbook engine, planner, agent runner, and 6 domain packs. These
   are tested + production-quality code.

3. **It records every privileged action as a signed receipt** in a
   hash-chained NDJSON ledger, computes daily Merkle roots, and can
   optionally anchor those roots on Solana (off by default).

4. **It can export an audit-grade compliance bundle**: every SQLite
   DB, every receipt, every Merkle proof, a verifier script that runs
   offline. This is the strongest, cleanest claim in the product.

5. **It speaks OAuth to Slack, Gmail, Google Calendar, GitHub (read),
   and Telegram (bot bridge).** Real OAuth code; requires the operator
   to supply client credentials. Writes are intentionally limited
   (Slack writes are stubbed; GitHub writes missing; Gmail send works
   for approved outreach drafts).

6. **It ships a webhook framework** with HMAC v1 signing, retry
   budget, dead-letter, inbox playbook trigger. Emit coverage is
   partial (only a couple sites emit today).

7. **It ships a cron-based playbook scheduler** that survives restart,
   when enabled.

8. **It has a Cowork backend module** that implements shared sessions,
   presence, cursors, and a one-time handoff token — but **no HTTP
   surface and no UI in this release**. The feature is shipped as
   library code, not as a usable surface.

9. **What it is NOT (must clarify before any sales call):**
   - Multi-tenant. (Workspaces is schema-only.)
   - A SaaS. (Local-first; no hosted service from this repo.)
   - A continuously-running background agent. (Lifespan loops only
     while the desktop app is open.)
   - A creator-economy platform. (No payouts, no third-party submit.)
   - A real "AI Clone." (Style heuristic only.)
   - A multi-OS product. (Windows/Linux builds NOT in v9.1.0.)
   - A multiplayer collab tool today. (Cowork has no routes/UI.)

10. **Honest one-line pitch:** "Local-first, receipt-anchored personal
    AI workspace, with OAuth bridges to your tools, an audit-grade
    export, and a council of agents you can shape with playbooks.
    Desktop-only on macOS today; multiplayer + multi-tenant on the
    v9.2/v9.3 roadmap."

---

## Appendix A — files actually verified

Read directly:

- `docs/WHAT_WORKS.md` (226 lines)
- `docs/V9_1_0_LAUNCH_READINESS.md` (201 lines)
- `docs/AGENT_HANDOFF.md` (top + SYNC markers, ~200 lines)
- `docs/contracts/COWORK.md` (151 lines)
- `docs/contracts/CORE_BRIDGE.md` (140 lines)
- `docs/COWORK_HEALTH_SNAPSHOT.md` (61 lines)
- `backend/core/cowork/__init__.py` (135 lines)
- `backend/core/agents/runner.py` (199 lines)
- `backend/core/webhooks/dispatcher.py` (368 lines)
- `backend/core/receipts/anchor.py` (205 lines)
- `backend/core/receipts/store.py` (partial)
- `backend/core/scheduler/runner.py` (partial)
- `backend/core/outreach/sender.py` (partial)
- `backend/core/marketplace/installer.py` (partial)
- `backend/core/compliance_export/bundler.py` (partial)
- `backend/core/workspaces/__init__.py` + `middleware.py` (partial)
- `backend/core/connectors/slack.py` (partial)
- `backend/core/clone/style.py` (partial)
- `backend/core/voice/transcribe.py` (partial)
- `web_extras/app.py` (Merkle loop section, lines 555-625)
- `web_extras/routers/receipts.py` (anchor wiring)

Grepped (negative results captured):

- `backend/core/notifications/imessage.py` → file absent.
- `backend/core/background/` directory → does not exist.
- `web_extras/routers/*cowork*` → no router file. Confirmed Cowork
  HTTP surface is NOT in this repo.

---

## Appendix B — env-var gates that hide features by default

| Env var | Default | Effect if unset |
| --- | --- | --- |
| `TARS_SCHEDULER_ENABLED` | unset | Scheduler tick loop never runs. |
| `TARS_RECEIPT_ANCHOR_ENABLED` | unset | Merkle anchor loop computes roots but never fires Solana memo. |
| `SOLANA_KEYPAIR_PATH` | unset | Anchor returns `not_configured` even if flag is on. |
| `TARS_COWORK_STORE` | live (good) | Set to `disabled` to kill module. |
| `WHISPER_LOCAL_PATH` | unset | STT goes cloud-only (OpenAI). |
| `OPENAI_API_KEY` | unset | STT returns 503. |
| `SLACK_CLIENT_ID`/`SECRET`/`REDIRECT_URI` | unset | Slack connector returns `ConnectorNotConfigured`. |
| `GOOGLE_CLIENT_ID`/etc | unset | Gmail/Calendar connector unreachable. |
| `TELEGRAM_BOT_TOKEN` | unset | Telegram bridge inert; `telegram://` webhooks fail with `connector_unavailable`. |
| `TARS_OUTREACH_FROM` | optional | Outreach From: header defaults to `me@`. |
| `TARS_WORKSPACES_STORE` | live | Set to `disabled` to kill workspace module. |
| `MEEET_BILLING_*` | unset | Local entitlements only, no remote mirror. |
| `BRIDGE_SHARED_SECRET` | unset | `core-bridge` smoke tests fail. |
| `TAURI_SIGNING_PRIVATE_KEY` | unset on a fresh box | Release pipeline can't sign updater. |

The implicit feature surface depends heavily on which of these are
pasted into the operator's `.env`. **Many of the marketing claims
are conditional on environment configuration the end user does not
control.** That's the single most important thing for the roadmap
to address: either drive features to work out-of-the-box, or be
explicit that TARS today is "operator-installed plumbing, not a
turnkey product."

---

End of audit. No code modified.
