# WHAT_WORKS — TARS v9.1.0 honest capability ledger

> **Source of truth** for what actually works in v9.1.0.
> Maintained for the operator (brother / Cursor) and for investor
> conversations where over-claiming is worse than under-claiming.
> Updated by the Wave 72 backend audit (2026-05-09).

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
| /dl proxy → GitHub Releases | `experiments/neural-showcase-v3/functions/dl/[file].ts` |
| Marketing landing + cockpit shell | `experiments/neural-showcase-v3/src/` |

---

## PARTIAL / STUB (wired but not "real" — set expectations)

| Capability | Status | Files |
| --- | --- | --- |
| Gmail connector | Read-only stub via OAuth bridge; no send / labels mutation | `backend/core/connectors/gmail*` |
| Google Calendar | Read-only `.ics` ingest; no event creation | `backend/core/calendar/ics_reader.py` |
| GitHub connector | Token-based read; no PR creation flow | `backend/core/github/connector.py` |
| Background TARS (daemon triggers) | Daemon runs; trigger DSL is minimal | `backend/core/background/` |
| Notification bridges (iMessage/Telegram/Email) | iMessage Mac-only; Telegram / Email require operator config | `backend/core/notifications/` |
| Eval suite | Scaffolding shipped (Wave 72 wired into CI as non-blocking) | `web_extras/eval/`, `.github/workflows/eval-suite.yml` |
| AI Clone v1 | Per-user style learning runs; draft suggestions are heuristic, not LLM-backed | `backend/core/ai_clone/` |

---

## NOT IMPLEMENTED in v9.1.0 (do NOT demo / claim)

| Capability | Status | Roadmap |
| --- | --- | --- |
| STT (speech-to-text) | No on-device pipeline shipped; hooks exist for future Whisper integration | v9.2 |
| Wake-word | Browser experiment removed; native equivalent missing | v9.3 |
| Marketplace (third-party skills) | Backend tables + browse page were prototyped (Wave 49/96–97), no live registry | v9.3 |
| T2T (TARS-to-TARS handshake) | Mock escrow only; no live counterparty discovery | v9.3 |
| RBAC (org-level roles) | Org/team scaffolding exists, role assignment UI does not | v9.4 |
| Webhooks (incoming + outgoing) | No live dispatcher in v9.1.0 build | v9.4 |
| Shared agent sessions (multiplayer) | UI mocked, no realtime sync layer | v9.5 |
| Slack connector | Not wired; OAuth bridge stub only | v9.4 |
| Pyoxidizer Win/Linux desktop builds | CI only ships macOS dmg/app for v9.1.0 | v9.2 |
| Public skill ratings + reviews aggregation | Tables exist, no submission flow | v9.5 |

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
