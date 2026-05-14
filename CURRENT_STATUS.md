# CURRENT_STATUS — daily-glance snapshot

> Live one-pager. If you want the full story, open `TARS_MASTER_DOC.md`.
> If you want the doc map, open `PROJECT_INDEX.md`. This page is the
> 60-second pulse check.

**Last updated:** 2026-05-15 (W247). **Tag in flight:** `v9.3.0` once
W245/W246/brother-billing land.

---

## Last 10 commits

| SHA | Wave | Subject |
|---|---|---|
| `2ef99c0` | W243 | Notepad templates — save/recall/share AI workflows |
| `096759d` | W241 | Background agents tray + long-running task status |
| `30c8127` | W244 | Privacy mode + data plane |
| `4d9b76d` | W242 | Tier cap UX — soft warnings + hard block + topup prompt |
| `15065b1` | W240 | `@-mention` chat context — file / docs / web / recent / code resolvers |
| `246cfc2` | W239 | Rules system — `.tars/rules.yml` + per-pack overlay + Settings editor |
| `480297f` | W238 | MCP servers panel — UI + toggles + status |
| `190ca1c` | W237 | Models switcher with cost-per-request labels |
| `bf550b8` | W236 | Master project documentation (`TARS_MASTER_DOC.md` + `PROJECT_INDEX.md` + README upgrade) |
| `1b248ce` | W235 | Consumption console + usage metering middleware + meeet.world billing event ingest |

W247 (this commit) lands the master-doc sync immediately after.

---

## What's working right now (end-user can use today)

- **Voice cockpit** — full-screen monolith, wake-word + STT (whisper.cpp / OpenAI fallback) + TTS, text-input fallback under the mic.
- **Auth gate** — magic-link + OAuth via `meeet.world`, or "Skip — local-only mode" for FREE forever.
- **Models switcher (W237)** — 9 models, cost-per-request labels, choice persisted at `~/.tars/active_model`.
- **MCP servers panel (W238)** — 5 endpoints, JSON storage, running / stopped / error indicators (spawn supervisor still pending).
- **Rules for TARS (W239)** — `.tars/rules.yml`, per-pack overlay, injected into every chat system prompt.
- **`@-mention` chat context (W240)** — file / docs / web / recent / code, 4KB cap.
- **Background agents tray (W241)** — tray chip + dropdown, SQLite store, SSE stream.
- **Tier cap UX (W242)** — 60 / 80 / 90 / 100% banners + hard-block modal + de-duped notification fanout.
- **Notepad templates (W243)** — FTS5 search, 5 seeds, variable substitution.
- **Privacy mode (W244)** — normal / privacy / strict, data-plane indicator, recent-flows ring buffer.
- **Consumption console (W235)** — `/api/usage/console`, per-action / per-model / per-day aggregation.
- **All v9.2.0-beta2 surface** — receipts ledger, Solana anchor, 7 domain packs, Cowork, vision/OCR, daemon + tars-doctor, iMessage / Telegram / Email bridges, AI Clone v0.2.

---

## What needs brother (blocking the `v9.3.0` cut)

TARS-side is **ready and waiting**. Brother on `api.meeet.world` ships:

1. `POST /api/billing/usage_event` — HMAC-signed `UsageEvent` ingest, debits balance, idempotency on `trace_id`.
2. `GET /api/billing/balance` — `{tier, balance_usd, balance_meeet, period_start, period_end}`.
3. `POST /api/billing/topup` — Solana ($MEEET) + card processor flow.
4. Reconciliation handshake — daily drift check via `scripts/reconcile-meeet-billing.py`, alert on >$0.50 drift.

Auth-side 4 endpoints (magic-link start / redeem, OAuth start, `/api/me`)
are the **other** brother dep — already specced in `docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md`,
runnable check via `scripts/CHECK-MEEET-LIVE.command`.

`BRIDGE_SHARED_SECRET` distributed W194. Schemas live in
`backend/core/usage/schema.py` and `backend/core/receipts/schema.py`.

---

## Next 3 things shipping (Claude lane)

| # | Wave | Status | What |
|---|------|--------|------|
| 1 | W245 | 🚧 In flight | Codebase indexer v0 — incremental + multi-language + `/api/codebase` API. Closes Cursor parity row 6. |
| 2 | W246 | 🚧 In flight | Cmd+K palette v2 — fuzzy + recents + categories. Final Wave A polish. |
| 3 | W248 | ⏳ Pending | Unified WS real-time event bus — consolidate Watch-me-work + cowork + agents tray + doctor onto one stream. |

After those land: `v9.3.0` tag (assuming brother is also live on his 4
billing endpoints). Target ship date `2026-06-12`.

---

**Status (W247):** Wave A 90% complete (8 of 10 must-haves shipped). 2 in
flight Claude-side; 1 external dependency (brother billing). On track for
`v9.3.0` by 2026-06-12.
