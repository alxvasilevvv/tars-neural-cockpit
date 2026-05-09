# WHAT_WORKS — TARS v9.1.0 honest capability ledger

> **Source of truth** for what actually works in v9.1.0.
> Maintained for the operator (brother / Cursor) and for investor
> conversations where over-claiming is worse than under-claiming.
> Updated by Wave 74 (2026-05-09) after Wave 73 ships.
>
> **What just shipped:** see [`RELEASE_NOTES_v9.1.0.md`](RELEASE_NOTES_v9.1.0.md).
> **What's coming:** see [`ROADMAP.md`](ROADMAP.md).

Legend:
- **FULLY IMPLEMENTED** — code path exists, ships in v9.1.0, has tests
  or live smoke verification, end-user can hit it.
- **PARTIAL / STUB** — wired in, returns deterministic responses, but
  the underlying integration is mocked / OAuth-only / behind a feature flag.
- **NOT IMPLEMENTED** — referenced in marketing or older docs but no
  shipping code path; do **not** demo this.

---

## FULLY IMPLEMENTED (real, in-product, tested)

| Capability | Files |
| --- | --- |
| Wallet / SOL+SPL balance + spend | `backend/core/wallet/service.py`, `web_extras/routers/wallet.py` |
| Council agents (6 packs + router) | `backend/core/council/`, `backend/agents/`, `backend/core/router/` |
| Planner (chain agents → run) | `backend/core/planner/`, `backend/core/planner/store.py` |
| Playbooks (deterministic recipes) | `playbooks/`, `backend/core/playbooks/` |
| Chat (multi-thread, SQLite-backed) | `backend/core/chat/store.py`, `web_extras/routers/chat.py` |
| Memory KV (per-pack, TTL, SQLite) | `backend/core/memory/store.py` |
| TTS (XTTS-v2 + system fallback) | `backend/core/voice/tts.py`, `web_extras/routers/voice.py` |
| STT (Whisper API; 503 when no key) *(Wave 73)* | `backend/core/voice/transcribe.py`, `web_extras/routers/voice.py` |
| Voice intents (parse + dispatch) | `backend/core/voice/intents.py`, `backend/agents/persona_router.py` |
| Pairing (host identity + QR) | `backend/core/pairing/store.py` *(SQLite-backed in Wave 72)*, `backend/core/crypto/` |
| Recovery (passphrase → vault) | `backend/core/vault/`, `backend/core/pairing/recovery.py` |
| Meeet bridge (relayer + economy) | `backend/core/meeet/`, `web_extras/routers/meeet*.py` |
| Entitlements (tier gating) | `backend/core/entitlements/`, `web_extras/routers/entitlements.py` |
| 6 domain packs | `backend/core/domains/packs/{wealth,health,family,product,brand,entrepreneur}/` |
| Tauri desktop sidecar | `desktop/src-tauri/src/{main.rs,sidecar.rs}` |
| Sidecar crash watcher (Wave 61) | `desktop/src-tauri/src/sidecar.rs` (watcher thread) |
| Updater channel (live JSON) | `backend/core/product/updater.py`, `web_extras/routers/product.py` |
| Receipt ledger (signed events) | `backend/core/receipts/` |
| Watch-me-work (real WS events) | `backend/core/orchestrator/`, `web_extras/routers/timeline.py` |
| Health endpoint + cockpit indicator | `web_extras/routers/health.py`, frontend Status page |
| OAuth bridge protocol | `backend/core/oauth_bridge/`, `web_extras/routers/oauth_bridge.py` |
| GitHub connector (token-based read; 60s LRU) *(Wave 73)* | `web_extras/routers/github.py` |
| Memory reflection (weekly ISO-week summary) *(Wave 73)* | `backend/core/memory/reflection.py`, `playbooks/_global/memory_reflection.json` |
| AI Clone v0.1 (style traits skeleton — *style hint, not full clone*) *(Wave 73)* | `backend/core/clone/style.py`, `web_extras/routers/clone.py` |
| Smart Agent Router (LLM intent routing; opt-in `TARS_SMART_ROUTER=1`) *(Wave 73)* | `backend/core/agents/router.py`, `web_extras/routers/agents.py` |
| OpenTelemetry exporter wrapper (no-op unless OTLP endpoint set) *(Wave 73)* | `backend/core/observability/otel.py` |
| /dl proxy → GitHub Releases | `experiments/neural-showcase-v3/functions/dl/[file].ts` |
| Marketing landing + cockpit shell | `experiments/neural-showcase-v3/src/` |

---

## PARTIAL / STUB (wired but not "real" — set expectations)

| Capability | Status | Files |
| --- | --- | --- |
| Gmail connector | Read-only stub via OAuth bridge; no send / labels mutation. v9.1.1 → real OAuth read. | `backend/core/connectors/gmail*` |
| Google Calendar | Read-only `.ics` ingest; no event creation. v9.1.1 → real Google Calendar API. | `backend/core/calendar/ics_reader.py` |
| GitHub connector — **write side** | Read shipped Wave 73; PR creation / issue write pending. v9.3 with webhooks. | `web_extras/routers/github.py` |
| Background TARS (daemon triggers) | Daemon runs; trigger DSL is minimal. v9.2 → standalone headless mode. | `backend/core/background/` |
| Notification bridges (iMessage/Telegram/Email) | iMessage Mac-only stub; Telegram / Email require operator config. v9.1.1 → real bridges. | `backend/core/notifications/` |
| Eval suite | Scaffolding shipped (Wave 72 wired into CI as non-blocking) | `web_extras/eval/`, `.github/workflows/eval-suite.yml` |

---

## NOT IMPLEMENTED in v9.1.0 (do NOT demo / claim)

| Capability | Status | Roadmap |
| --- | --- | --- |
| AI Clone v0.5+ (fine-tuned style replication) | v0.1 ships in Wave 73 (style hint only); full clone uses fine-tuned model | v9.2 |
| Wake-word | Browser experiment removed; native equivalent missing | v9.1.1 (web wasm Picovoice) |
| Slack connector (real) | Not wired; OAuth bridge stub only | v9.1.1 |
| Magic-link auth (real, end-to-end) | Onboarding wizard UI shipped; live token mint depends on brother backend | v9.1.1 |
| Pyoxidizer Win/Linux desktop builds | CI only ships macOS dmg/app for v9.1.0 | v9.2 |
| `sqlite-vec` extension wired | Memory KV does cosine in Python today | v9.2 |
| XTTS-v2 voice cloning (separate sidecar bundle) | TTS ships; voice-cloning bundle not yet | v9.2 |
| Marketplace (third-party skills) | Backend tables + browse page were prototyped (Wave 49/96–97), no live registry | v9.2 (MVP) → v9.3 (payouts) |
| Skill SDK (third-party packaging spec + signing) | Wave 95 scaffolding; needs public spec | v9.2 |
| Background daemon (proper headless mode) | Background TARS exists inside uvicorn / Tauri; standalone pending | v9.2 |
| T2T (TARS-to-TARS handshake) | Mock escrow only; no live counterparty discovery | v9.3 |
| Receipt-ledger unified signed-events stream | Per-event ed25519 today; unified stream pending | v9.3 |
| Reputation Graph + leaderboard (public UI) | Wave 80 aggregator shipped; public UI pending | v9.3 |
| Webhooks (incoming + outgoing) | No live dispatcher in v9.1.0 build | v9.3 |
| MCP server bridge (canonical productized form) | Reference shipped Wave 85; canonical bridge pending | v9.3 |
| Multi-tenant + JWT auth | Single-user only today | v10.0 |
| Organizations + Teams + RBAC | Org/team scaffolding exists, role assignment UI does not | v10.0 |
| Shared agent sessions (multiplayer) | UI mocked, no realtime sync layer | v10.0 |
| TARS Handoff (viral hand-off between users) | Wave 100 scaffolded; depends on multi-tenant | v10.0 |
| Edge compute adapter for voice latency | Local adapter shipped Wave 106; edge variant pending | v10.0 |
| Public skill ratings + reviews aggregation | Tables exist, no submission flow | v9.3 (with marketplace) |

Full forward-looking detail: [`ROADMAP.md`](ROADMAP.md).

---

## Platform support (v9.1.0)

| Target | Status |
| --- | --- |
| macOS arm64 (Apple Silicon) | shipping (signed ad-hoc, not notarized) |
| macOS x64 (Intel) | best-effort — falls back to arm64 dmg + Rosetta when CI runner is queue-starved |
| Windows | NOT shipping in v9.1.0 (pyoxidizer cross-target pipeline pending) |
| Linux | NOT shipping in v9.1.0 (same reason) |

---

## How this file is maintained

- Wave 72 is the baseline. Every subsequent wave that ships a real
  capability MUST move its row from PARTIAL/STUB or NOT IMPLEMENTED
  into FULLY IMPLEMENTED, with file paths.
- If a capability regresses, demote it. Never delete a row — strike
  it through with the wave number that removed it.
- Marketing copy on `tars.meeet.world` MUST be a strict subset of the
  FULLY IMPLEMENTED column.
