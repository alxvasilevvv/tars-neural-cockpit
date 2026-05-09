# TARS — Roadmap

> **Honest, dated forward look** for what's NOT in v9.1.0 but is planned.
> Maintained alongside [`docs/WHAT_WORKS.md`](WHAT_WORKS.md) (current
> capabilities) and [`docs/RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md)
> (what just shipped).
>
> **Last updated:** 2026-05-09 (Wave 74 launch package).
>
> Scope estimate legend: **S** = ≤3 days, **M** = ~1–2 weeks, **L** = 3+ weeks.

---

## Shipped in v9.1.0 (2026-05-09)

One-line each — full detail in [`WHAT_WORKS.md`](WHAT_WORKS.md).

- **Wallet (SOL / EVM / TON)** — self-custodial, BIP-39, XChaCha20-Poly1305
  encrypted at rest, Phantom-compatible derivation. → [WHAT_WORKS](WHAT_WORKS.md#fully-implemented-real-in-product-tested)
- **Council LLM** — multi-model deliberation with disagreement / confidence visible.
- **Planner** — chain agents into runnable plans with replay.
- **Playbooks** — deterministic recipes per pack.
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
- **`/install` funnel** — install.sh + magic-link onboarding wizard.
- **dl-proxy** — `/dl/<file>` Cloudflare Pages Function → GitHub Releases.

---

## Coming in v9.1.1 (~2 weeks)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **Magic-link auth** (real, end-to-end) | M | meeet.world brother backend (token mint endpoint) | Onboarding wizard claims magic-link; today it's UI-only. |
| **Real Slack connector** (OAuth + read channels/DMs) | M | brother backend (OAuth bridge) | WHAT_WORKS lists Slack as NOT IMPLEMENTED. |
| **Real Gmail connector** (OAuth + read threads) | M | brother backend (OAuth bridge) | Currently PARTIAL: read-only stub. |
| **Real Calendar connector** (Google Calendar API + ICS parser) | M | brother backend (OAuth bridge) | Today only `.ics` ingest is real. |
| **Wake-word agent (web variant via wasm Picovoice)** | S | none — design + perf budget | Wake-word listed NOT IMPLEMENTED in WHAT_WORKS. |
| **iMessage bridge** (AppleScript + Messages.app DB read) | S | macOS Full-Disk-Access prompt UX | PARTIAL today (Mac-only stub). |
| **Telegram bridge** (telegram-bot-api framework) | S | operator config (bot token) | PARTIAL today (operator config only). |

---

## Coming in v9.2 (~1 month)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **Windows installer** (.msi via pyoxidizer + Authenticode) | L | infra (Windows CI runner + cert purchase) | RELEASE_NOTES known limitation: Mac-only. |
| **Linux installer** (.AppImage + .deb) | M | infra (Linux CI runner) | Same as above. |
| **`sqlite-vec` extension wired** (replace cosine in Python) | M | none — implementation only | Memory KV today does cosine in Python; promised as native. |
| **AI Clone v0.5** (full style replication via fine-tuned model) | L | infra (fine-tune budget) + design (training UX) | Today shipped as v0.1 — explicit promise to upgrade. |
| **XTTS-v2 voice cloning** (separate sidecar bundle) | L | infra (model bundle size + licensing) | TTS works; cloning UI was promised in older waves. |
| **Marketplace MVP** (registry + browse + ratings table, no payouts yet) | L | brother backend (registry API) + design (browse page) | WHAT_WORKS: Marketplace listed NOT IMPLEMENTED. |
| **Skill SDK** (third-party packaging spec + signing) | M | none — spec writing + ed25519 already shipped | Wave 95 shipped scaffolding; needs public spec. |
| **Background daemon proper** (headless mode without uvicorn / Tauri) | M | none — CLI shell + plist | Background TARS exists; promised standalone. |

---

## Coming in v9.3+ (~1–2 months after v9.2)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **T2T (TARS-to-TARS) handshake protocol + Solana escrow** | L | brother (escrow program) + infra (Solana program deploy) | Mock escrow today; live counterparty discovery promised. |
| **Receipt-ledger unified signed-events stream** | M | none — ed25519 already shipped per-event | Receipt ledger is per-event; unified stream promised. |
| **Reputation Graph + leaderboard** | M | T2T + receipt ledger | Wave 80 shipped aggregator; UI / public leaderboard pending. |
| **Marketplace 70/30 revenue share + payouts** | L | brother (payout rails) + legal (per-jurisdiction) | Wave 96 scaffolding; payout rails missing. |
| **Webhooks (incoming + outgoing)** | M | none — dispatcher only | WHAT_WORKS: NOT IMPLEMENTED. |
| **MCP server bridge** (expose TARS skills as MCP tools) | M | none — reference shipped Wave 85, productize | Wave 85 reference; needs canonical bridge. |

---

## Coming in v10.0 (~3 months out)

| Item | Scope | Blocked by | Audit promise it fulfills |
| --- | --- | --- | --- |
| **Multi-tenant + JWT auth** | L | design (auth UX) + brother backend | Single-user today; multi-tenant promised. |
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
