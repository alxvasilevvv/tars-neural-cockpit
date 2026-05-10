# TARS — Roadmap

> **Honest, dated forward look** for what's NOT in v9.1.0 but is planned.
> Maintained alongside [`docs/WHAT_WORKS.md`](WHAT_WORKS.md) (current
> capabilities) and [`docs/RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md)
> (what just shipped).
>
> **Last updated:** 2026-05-10 (Wave 109 sync after B2B production suite Waves 94-108).
>
> Scope estimate legend: **S** = ≤3 days, **M** = ~1–2 weeks, **L** = 3+ weeks.

---

## Shipped in v9.1.0 (2026-05-09 → 2026-05-10 addendum)

One-line each — full detail in [`WHAT_WORKS.md`](WHAT_WORKS.md).

### Core platform
- **Wallet (SOL / EVM / TON)** — self-custodial, BIP-39, XChaCha20-Poly1305
  encrypted at rest, Phantom-compatible derivation. → [WHAT_WORKS](WHAT_WORKS.md#fully-implemented-real-in-product-tested)
- **Council LLM** — multi-model deliberation with disagreement / confidence visible.
- **Planner** — chain agents into runnable plans with replay.
- **Playbooks** — deterministic recipes per pack, recursive loader.
- **Chat + Attachments** — multi-thread, SQLite-backed, with `AttachmentChipStrip`.
- **Memory KV** — per-pack, TTL, SQLite store.
- **TTS** — XTTS-v2 with system-voice fallback.
- **STT (Wave 73)** — `POST /api/voice/transcribe` via Whisper API; 503 when no key.
- **Voice intents** — regex parser → persona router dispatch.
- **Pairing crypto** — X25519 handshake, SQLite-persisted (Wave 72).
- **Recovery** — passphrase → vault round-trip.
- **Meeet event store** — local replay log + optional outbound bridge.
- **Entitlements** — Free / Pro / Business / Lifetime tier gating.
- **6 domain packs** — wealth / health / family / product / brand / entrepreneur.
- **Vision agent** — image attachments with thumbnails (P8).
- **GitHub connector (Wave 73)** — token-based read of `/user`, `/repos`,
  `/issues`, `/pulls` with 60s LRU cache.
- **Memory reflection (Wave 73)** — weekly ISO-week summary into `_global` pack.
- **AI Clone v0.1 (Wave 73)** — style traits skeleton (sentence length,
  exclamation rate, vocab) — *style hint, not full clone*.
- **Smart Agent Router (Wave 73)** — opt-in LLM-based intent routing
  (`TARS_SMART_ROUTER=1`); regex fallback always on.
- **OpenTelemetry wrapper (Wave 73)** — no-op until
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- **Tauri shell + tray + global shortcut + deep links + sidecar crash watcher**
  (Waves 59 → 61).
- **`/install` funnel** — install.sh + magic-link onboarding wizard (UI).
- **dl-proxy** — `/dl/<file>` Cloudflare Pages Function → GitHub Releases.

### Workshop suite (Waves 80-92, addendum 2026-05-10)
- **`/workshop`** — generic 4-phase wizard (Intake → Design → Test → Deploy).
- **`/workshop/enterprise`** — branded B2B workshop landing (renamed from `/workshop/cresco` in Wave 87).
- **`/workshop/roi`** — interactive ROI calculator (Wave 84).
- **`/workshop/materials`** — handouts + recipe library + PWA offline (Wave 85).
- **`/workshop/assess`** — pre-workshop self-assessment quiz, 12 Q × 4 categories (Wave 88).
- **`/workshop/cohort`** — facilitator dashboard with **real SSE + attendee tracking** (Wave 89 UI → Wave 94 backend).
- **`/compliance`** — receipts feed + filters + CSV export + ReceiptVerifier.
- **In-app tutorial overlay** across all workshop pages (Wave 92).
- **20+ workshop playbooks** under `playbooks/_workshop/` (fund / saas / dao / family-office / algotrade / quant).
- **8 enterprise-template handouts** under `docs/workshop/enterprise-template/` (5 emails + facilitator runbook + feedback survey + README).
- **Contracts:** [`docs/B2B_WORKSHOP.md`](B2B_WORKSHOP.md), [`docs/contracts/WORKSPACES.md`](contracts/WORKSPACES.md), [`docs/contracts/SKILL_SDK.md`](contracts/SKILL_SDK.md).

### Webhooks (Wave 90)
- **Webhooks module** — outgoing dispatcher + signed delivery + inbound playbook trigger + dead-letter queue + inbox.
- **Webhook contract v1.0** (HMAC, retry).
- *(Honest scope: the unified receipt ledger emits `receipt.*` (Wave 95); per-feature emit sites wire incrementally.)*

### Real connectors (Waves 91, 108)
- **Slack** — real OAuth + read channels/DMs (Wave 91).
- **Gmail** — real OAuth + read threads (Wave 91).
- **Google Calendar** — real OAuth + events read (Wave 91).
- **Telegram** — bot bridge with long-poll + webhook + outbound (Wave 108).
- Slack/Gmail/Calendar env-gated on `OAUTH_BRIDGE_*`. Telegram env-gated on `TELEGRAM_BOT_TOKEN`.

### B2B production suite (Waves 94-108, addendum 2026-05-10)
- **Wave 94 — Cohort backend** — real attendee tracking + SSE for `/workshop/cohort` (replaces Wave 89 mock).
- **Wave 95 — Receipt ledger unified** — hash chain + Merkle root + Solana memo anchor.
- **Wave 96 — Reporting dashboard** — `/dashboard` with 10 widgets, 5 default layouts.
- **Wave 97 — Playbook scheduler** — cron-based, persisted, restart-safe. `/schedules`.
- **Wave 98 — Email outreach** — Gmail send + AI Clone drafting + HIL gate + 5 starter templates. `/outreach`.
- **Wave 99 — Org onboarding wizard** — `/onboard/org` 5-step.
- **Wave 101 — HIL inbox** — `/inbox` approval queue + bulk approve + policy thresholds.
- **Wave 102 — Files management** — `/files` document UI + bulk ops + 8 categories + tagging.
- **Wave 103 — Reports module** — `/reports` 6 templates + scheduling + PDF/PPTX/XLSX.
- **Wave 104 — Compliance export** — audit-grade bundle + verifier + GDPR + PII redaction.
- **Wave 105 — E2E test suite** — 10 cross-module scenarios (12 pass + 1 skip).
- **Wave 106 — Marketplace v0** — registry + browse + install + ratings + 12 seed listings (payouts + third-party publish are v9.2/v9.3).
- **Wave 107 — Vertical bundles** — 7 org-type ready-to-demo packs at `/bundles`.
- **Wave 108 — Telegram bridge** — bot connector with long-poll + webhook.
- **Wave 108 — Performance dashboard** — `/admin/perf` p50/p95/p99 + throughput + error rate + active sessions.

### Hardening (Waves 75-79)
- 4 failing CI workflows repaired (Wave 75).
- Release pipeline hardened — minisign updater pubkey patched (Wave 76).
- Pre-launch security audit at [`docs/security/AUDIT_2026-05-09.md`](security/AUDIT_2026-05-09.md).
- Rate limits on `/voice/transcribe`, `/agents/route`, `/clone/draft`.
- Wallet `sign_message` policy gate (Wave 79).
- Eval suite in CI (non-blocking).

---

## Coming in v9.1.1 (~2 weeks)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **Magic-link auth** (real, end-to-end) | M | meeet.world brother backend (token mint endpoint) | Onboarding wizard claims magic-link; today it's UI-only. |
| **Wake-word web (PWA / wasm Picovoice)** | S | none — design + perf budget | Wake-word listed NOT IMPLEMENTED in WHAT_WORKS. |
| **iMessage bridge** (AppleScript + Messages.app DB read) | S | macOS Full-Disk-Access prompt UX | NOT IMPLEMENTED today (Mac-only stub). |

---

## Coming in v9.2 (~1 month)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **Multi-tenant Workspaces (initial)** | L | brother backend (workspace API) + design (workspace switcher UI) | Plan agent's risk-flagged 7-day work; backend MVP in flight (Wave 110, additive schema-only). |
| **Windows installer** (.msi via pyoxidizer + Authenticode) | L | infra (Windows CI runner + cert purchase) | RELEASE_NOTES known limitation: Mac-only. |
| **Linux installer** (.AppImage + .deb) | M | infra (Linux CI runner) | Same as above. |
| **`sqlite-vec` extension wired** (replace cosine in Python) | M | none — implementation only | Memory KV today does cosine in Python; promised as native. |
| **AI Clone v1** (real fine-tune per-user) | L | infra (storage budget + GPU pool) + design (training UX) | v0.1 ships Wave 73 (style hint); Wave 98 outreach uses style-hint draft. Real fine-tune still pending. |
| **XTTS-v2 voice cloning** (separate sidecar bundle) | L | infra (model bundle size + licensing) | TTS works; cloning UI was promised in older waves. |
| **Marketplace 70/30 payouts** | L | brother (payout rails) + legal (per-jurisdiction) | Wave 106 ships browse + install + ratings; payouts pending. |
| **Skill SDK third-party publishing** (packaging spec + ed25519 signing flow) | M | none — spec writing + ed25519 already shipped | Wave 106 marketplace uses in-process registry; third-party publish flow promised. |

---

## Coming in v9.3+ (~1–2 months after v9.2)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **T2T (TARS-to-TARS) live + Solana escrow** | L | brother (escrow program) + infra (Solana program deploy) | Mock escrow today; live counterparty discovery promised. |
| **Reputation Graph + leaderboard (public UI)** | M | T2T + receipt ledger | Wave 80 shipped aggregator; UI / public leaderboard pending. |
| **Webhooks `receipt.*` event emission everywhere** | M | none — wire emit sites in core receipt path | Unified ledger emits (Wave 95); per-feature emit sites incremental. Full coverage promised. |
| **MCP server bridge** (canonical productized form) | M | none — reference shipped Wave 85, productize | Wave 85 reference; needs canonical bridge. |
| **Webhooks central registry (cross-tenant)** | M | multi-tenant Workspaces (v9.2) | Per-instance registry today. |
| **GitHub connector — write side** (PR creation + issue write) | M | webhooks `receipt.*` + Wave 91 OAuth refresh | Read shipped Wave 73; write side promised. |

---

## Coming in v10.0 (~3 months out)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **Multi-tenant + JWT auth (full)** | L | v9.2 Workspaces initial + design (auth UX) + brother backend | Single-user today; multi-tenant promised. |
| **Organizations + Teams + RBAC** | L | multi-tenant + design (role assignment UI) | Wave 50 scaffolded; UI missing. |
| **Shared Agent Sessions (multiplayer)** | L | multi-tenant + realtime layer | Wave 99 UI mocked; no realtime sync. |
| **TARS Handoff (viral handoff between users)** | M | multi-tenant + share-link rewrite | Wave 100 scaffolded; depends on multi-tenant. |
| **Edge compute adapter for voice latency** | M | infra (edge worker pool) | Wave 106 shipped local adapter; edge variant promised. |

---

## What's NOT planned (explicitly out-of-scope)

These were on earlier task lists but are now superseded — do **not** reintroduce
without an explicit decision:

- **The original 8 v7.1 agents** (browser / code / shell / vision / advisor /
  builder / cursor / local_model) — replaced by the **6 domain packs** model.
  Their behaviours are folded into pack-scoped playbooks where they earned
  their keep; the rest were fan-fiction.
- **The "7 killer agents"** (research / analyst / meeting / doc / scraper /
  translator / image — Wave 47) — superseded by the **planner + smart router**
  combo. Same outcomes, smaller surface.
- **Iron-Man specials** (Strategy / NewsRadar / Negotiator / MeetingPrep /
  Lawyer-lite / Coach — Wave 56) — replaced by **voice personas** layered on
  top of the Council. Persona is a config, not a binary.
- **3D neural-brain visualization in main UI** — removed in Wave 71 simplify
  pass. Survives as an experiment under `experiments/neural-showcase-v3/`
  scenes; not on the cockpit critical path.
- **Quests UI in main cockpit** — same Wave 71 simplify cut. Quests live in
  the meeet.world economy backend; TARS surfaces them only via the receipt
  ledger.
- **5 MEEET Native Skills (Quest / Stake / Arena / Discovery / Wallet)** as
  *first-class cockpit panels* — collapsed into the wallet + receipt-ledger
  surfaces. The skills exist as MCP tools (Wave 85); they are not UI
  destinations.
- **i18n beyond English** — Wave 70 → 72 force-EN. Re-translation only happens
  *after* a paying user asks; the dictionary infrastructure (`useT()`,
  per-route OG, popover) is preserved but un-routed.
- **The `tars-backend` legacy binary name** — Wave 72 aligned on
  `tars-sidecar-<triple>`. Fallback resolution stays for one minor version,
  then dies.
- **Named-customer / regulatory-acronym branding in workshop content** —
  Wave 87 stripped Cresco / CARF / 3V / Crypto Fund. All workshop copy is
  generic B2B; per-customer branding lives in private deployments only.

---

## How this file is maintained

- Every wave that ships an item from this roadmap MUST move it from here
  into [`WHAT_WORKS.md`](WHAT_WORKS.md) **with file paths**, and add a
  line in [`RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md) (or its
  successor) under "What's new".
- Every audit that demotes a capability MUST move its row from
  WHAT_WORKS back into the appropriate version section here.
- Dates on this file slip with the calendar, not the wishlist. Update the
  "Last updated" line every time you touch it.
- The "What's NOT planned" section grows — never shrinks — without an
  explicit decision logged in [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md).

---

## See also

- [`docs/WHAT_WORKS.md`](WHAT_WORKS.md) — current honest capability ledger.
- [`docs/RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md) — what just shipped.
- [`CHANGELOG.md`](../CHANGELOG.md) — wave-by-wave log.
- [`docs/PHASE_L_ROADMAP.md`](PHASE_L_ROADMAP.md) — design-phase roadmap.
- [`docs/THREAT_MODEL.md`](THREAT_MODEL.md) — security boundaries.
- [`docs/LAUNCH_READINESS.md`](LAUNCH_READINESS.md) — launch blocker list.
- [`docs/B2B_WORKSHOP.md`](B2B_WORKSHOP.md) — Workshop suite contract.
- [`docs/contracts/WORKSPACES.md`](contracts/WORKSPACES.md) — multi-tenant Workspaces contract (v9.2 target).
- [`docs/contracts/SKILL_SDK.md`](contracts/SKILL_SDK.md) — third-party Skill SDK contract (v9.2 target).
- [`docs/security/AUDIT_2026-05-09.md`](security/AUDIT_2026-05-09.md) — pre-launch security audit.
