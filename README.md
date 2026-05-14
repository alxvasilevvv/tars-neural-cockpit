# TARS — local-first, voice-native, receipt-anchored AI cockpit

> Billed through [`meeet.world`](https://meeet.world). Cursor-grade polish.
> 7 life-domain packs. Voice-first. Sovereign data. On-chain proof.

[![version](https://img.shields.io/badge/version-10.0.0--rc1-blueviolet)](docs/RELEASE_NOTES_v10.0-rc1.md)
[![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20on--prem-lightgrey)](docs/ONPREM_DEPLOYMENT_GUIDE.md)
[![tests](https://img.shields.io/badge/pytest-400%2B%20passed-brightgreen)](docs/SMOKE-TEST-RESULTS.md)
[![meeet](https://img.shields.io/badge/meeet.world-integrated-7c3aed)](docs/HANDOFF_v9.2.0-beta2_FOR_BROTHER.md)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

## What's new in v10.0.0-rc.1 (Wave A + B + C bundled)

Three waves of work close the Cursor parity gap, ship TARS-unique edge,
and move beyond Cursor into surfaces it structurally cannot serve.

- **Wave A (W237-W249)** — Cursor parity panels, Cmd+K palette v2,
  codebase indexer v0, unified WS event bus, tier-cap UX, privacy mode.
  Originally shipped as `v9.3.0-beta1`.
- **Wave B (W250-W259)** — Voice-driven Composer (W253) with diff
  preview + receipt anchoring, `tars-tab` VS Code extension scaffold
  (W254), receipt-anchored audit explorer (W255), domain-pack-aware
  composer (W256), SOC2 + GDPR + compliance bundle (W257), real
  launchd bg-agents + VS Code marketplace publish prep (W258 + W259).
- **Wave C (W260-W263)** — T2T code review handoff (W260), agent
  marketplace v0 (W261), voice-first pair programming in Composer
  (W262), **on-prem TARS deployment kit** (W263) with one-line
  installer, Postgres parity, SAML/OIDC bridge, systemd unit, and a
  435-line operator playbook.

Path to GA: 1-week rc1 soak + 4 operator items
([release notes §10](docs/RELEASE_NOTES_v10.0-rc1.md)).

## Read first

> **`TARS_MASTER_DOC.md`** — the single source of truth (1200+ lines).
> Vision, architecture, Cursor parity scorecard, roadmap, pricing, operator
> manual, brother brief, anti-patterns. Re-read §1 and §11 before saying yes
> to any new feature.
>
> **`PROJECT_INDEX.md`** — every doc in the repo, one line each.

## Quick start

```bash
# 1. One-click boot
bash scripts/LAUNCH-NOW.command

# 2. After UI changes
bash scripts/REBUILD-TARS-APP.command

# 3. Use
open /Applications/TARS.app
```

If brother's `meeet.world` endpoints aren't live yet, click
**"Skip — local-only mode"** on the auth screen and TARS runs FREE-tier
forever. To verify brother readiness:
`bash scripts/CHECK-MEEET-LIVE.command`.

---

## What this is

TARS is the agent surface that sits between you and your tools. It runs
**entirely on your machine**: a Python sidecar wrapped by a small Tauri
binary. There is no SaaS account, no remote inference path you can't
inspect, and no telemetry you didn't approve.

Inside the cockpit you can:

- **Talk to a council of models.** Two or more LLMs deliberate every
  turn. Disagreement, confidence, and the per-model votes are visible.
- **Plan and run agents across packs.** Six domain packs ship in v9.1.0
  (wealth / health / family / product / brand / entrepreneur). The
  planner chains them; playbooks make recipes deterministic; the smart
  router (opt-in, Wave 73) picks the right pack from intent. Real
  Watch-me-work timeline of structured events.
- **Hold real crypto.** Solana, EVM, and TON wallets. BIP-39 seeds
  generated and re-imported locally, encrypted at rest with
  XChaCha20-Poly1305. Transactions signed on-device with `eth-account`,
  `solders`, and `tonsdk`. Phantom-compatible derivation supported.
- **Pair your phone.** iOS and Android companions complete an X25519
  handshake with the host (SQLite-persisted since Wave 72) so chat,
  traces, and (read-only) wallet state stream over an encrypted channel
  that bypasses the cloud entirely.
- **Bridge to meeet.world.** Optional outbound stream of structured
  events with full trace context. Same pipe Claude / Cursor / external
  agents read from.

> **Honest scope.** v9.1.0 is Mac-only, no marketplace, no live T2T,
> no multi-tenant, AI Clone is v0.1 (style hint, not full clone),
> magic-link auth depends on the meeet.world brother backend. Full
> ledger: [`docs/WHAT_WORKS.md`](docs/WHAT_WORKS.md). What's coming:
> [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Quickstart

### 1. Prereqs

- **Backend / dev cockpit:** macOS, Windows, or Linux all work.
- **Production installer (Tauri .dmg):** macOS only in v9.1.0. Windows
  / Linux installers are scheduled for v9.2 — see [`docs/ROADMAP.md`](docs/ROADMAP.md).
- **Python 3.12** (`uv` or stdlib `venv` both fine).
- **Node 20+** for the cockpit bundle.
- **Rust toolchain** (only if you want to build the Tauri binary).

### 2. Run the backend

```bash
cd jarvis
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn web_extras.app:app --host 127.0.0.1 --port 8765
```

### 3. Run the cockpit (dev)

```bash
cd jarvis/experiments/neural-showcase-v3
npm install
npm run dev
```

Open http://localhost:5173. The cockpit auto-detects the local sidecar.

### 4. Run the desktop binary (production)

```bash
cd jarvis/desktop
npm install
npm run tauri build
```

Produces a signed installer under `desktop/src-tauri/target/release`.

> Code-signing requires your own Apple Developer ID (macOS) /
> Authenticode cert (Windows) / Minisign keypair (auto-update). See
> [docs/RELEASE.md](docs/RELEASE.md).

---

## Configuration

All config lives in environment variables. Sensible defaults; nothing
is required to launch.

### Crypto wallets

| Variable | Default | Effect |
| --- | --- | --- |
| `TARS_WALLETS_DB_PATH` | `~/.tars/wallets.sqlite` | Public ledger of created wallets. |
| `TARS_WALLETS_SECRETS_PATH` | `~/.tars/wallet_secrets.json` | XChaCha20-Poly1305 encrypted private keys. |
| `TARS_WALLETS_PASSPHRASE` | empty | Optional BIP-39 passphrase for new wallets. |
| `TARS_WALLETS_STORE` | enabled | Set to `disabled` to fully turn off the wallet surface. |
| `TARS_SOLANA_RPC_URL` | `mainnet-beta` | Override the JSON-RPC endpoint for balance / blockhash reads. |
| `TARS_EVM_RPC_URL` | `eth.llamarpc.com` | Override the EVM JSON-RPC endpoint. |
| `TARS_TON_RPC_URL` | `toncenter.com/api/v2/jsonRPC` | Override the TON HTTP API. |

### Operator hardening

| Variable | Default | Effect |
| --- | --- | --- |
| `TARS_REQUIRE_OPERATOR_CONFIRM` | `0` | Set to `1` to require an `X-TARS-Confirm: <token>` header on every destructive endpoint. Tokens are minted via `POST /api/wallet/{id}/confirm` and HMAC-signed. |
| `TARS_CONFIRM_KEY` | random | Signing key for confirm tokens. Set to a stable value for multi-process deployments. |
| `TARS_AUDIT_RAW_TX` | `0` | Set to `1` to persist raw signed bytes (raw_b64 / boc / raw_hex) in the meeet event log. Off by default for privacy. |
| `TARS_AUDIT_RETENTION_DAYS` | `30` | Retention window for audit-tagged events; pruned via `POST /api/wallet/audit/prune`. |
| `TARS_HIDE_TRACEBACKS` | `0` | Set to `1` in production so unhandled exceptions return the unified envelope instead of a stack trace. |

### Pairing / sync

| Variable | Default | Effect |
| --- | --- | --- |
| `TARS_PAIRING_VAULT` | enabled | Encrypted vault for pairing keys. Set to `disabled` for stateless dev. |
| `TARS_VAULT_KEY` | random | Master key for the pairing vault. Set explicitly to persist across reboots. |
| `TARS_PAIRING_STORE` | `~/.tars/pairing.sqlite` | Where the X25519 handshake state lives. |

### Meeet bridge

| Variable | Default | Effect |
| --- | --- | --- |
| `MEEET_INGEST_URL` | unset | Push structured events to your meeet.world tenant. Off by default. |
| `MEEET_API_KEY` | unset | API key for the ingest endpoint. |
| `MEEET_SOURCE` | `tars` | Source label on every event. |
| `MEEET_CONTRACT_VERSION` | `1.0.0` | Pinned contract version. |
| `MEEET_LOCAL_LOG` | `~/.tars/meeet.sqlite` | Local replay log. |
| `MEEET_STORE` | enabled | Set to `disabled` to turn off the local log. |

---

## Architecture (5-second tour)

```
┌──────────────────────────────────────────────────────────────────┐
│  Cockpit (React, Tailwind, Vite — hosted by Tauri or vite dev)  │
└───────────────────────┬──────────────────────────────────────────┘
                        │   loopback HTTP, no auth
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI sidecar (web_extras/)                                  │
│  ├── routers/agents      ── multi-agent + autopilot              │
│  ├── routers/wallet      ── self-custodial Solana/EVM/TON        │
│  ├── routers/pairing     ── X25519 handshake                     │
│  ├── routers/recovery    ── BIP-39 mnemonic round-trip           │
│  ├── routers/chat        ── council of models                    │
│  └── ...                                                          │
└───────────────────────┬──────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────────────┐
        ▼               ▼                       ▼
┌─────────────┐  ┌──────────────┐       ┌──────────────────┐
│ wallet/     │  │ council/     │       │ meeet/ bridge    │
│ vault/      │  │ orchestrator │       │ (event emit +    │
│ recovery/   │  │              │       │ trace context)   │
│ agents/     │  │              │       │                  │
└─────────────┘  └──────────────┘       └────────┬─────────┘
                                                 │  optional
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  meeet.world ingest         │
                                  │  (Claude / Cursor / agents) │
                                  └─────────────────────────────┘
```

For the full picture see:

- [`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md) — current state + pending work.
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) — trust boundaries.
- [`docs/LAUNCH_READINESS.md`](docs/LAUNCH_READINESS.md) — what's blocking launch.
- [`docs/contracts/`](docs/contracts/) — JSON Schema event contracts.
- [`design-system/tars/MASTER.md`](design-system/tars/MASTER.md) — visual source of truth.

---

## Common operations

### Create a wallet

```bash
curl -s -XPOST localhost:8765/api/wallet \
  -H 'content-type: application/json' \
  -d '{"label":"primary","chain":"solana"}'
# → { ok: true, wallet: {...}, mnemonic: "abandon ..." }
```

> The mnemonic is returned **once**. It is never re-shown by any
> later API call. Write it down.

### Phantom-compatible Solana wallet

```bash
curl -s -XPOST localhost:8765/api/wallet \
  -H 'content-type: application/json' \
  -d '{"label":"phantom","chain":"solana","derivation_scheme":"bip44-501-phantom"}'
```

The address now matches what Phantom / Solflare / Backpack derive
for the same recovery phrase.

### Sign a Solana transfer

```bash
# 1. Fetch a fresh blockhash.
BH=$(curl -s localhost:8765/api/wallet/solana/blockhash | jq -r '.blockhash')

# 2. Sign locally.
curl -s -XPOST localhost:8765/api/wallet/<wallet_id>/sign_solana_transfer \
  -H 'content-type: application/json' \
  -d "{\"to\":\"<recipient>\",\"amount\":\"0.1\",\"recent_blockhash\":\"$BH\"}"
```

### Pair a phone

1. Open the iOS / Android companion → "Pair" → scan QR.
2. The host shows a 4-byte fingerprint; confirm it on both devices.
3. From this point on, chat threads + (read-only) wallet state
   stream over the X25519-paired channel. The cloud is not involved.

---

## Troubleshooting

### `WalletError: mnemonic must have …`

Pre-launch we accepted only 24-word phrases. As of N3 we accept
12 / 15 / 18 / 21 / 24 — the standard BIP-39 set. If you still see
this, you're probably running an old image; redeploy.

### `wallet_balance_rpc_failure`

The configured `TARS_*_RPC_URL` is unreachable. Either point at a
private RPC or check your network. Wallet state is read-only, so
the rest of TARS keeps working.

### Cockpit shows blank panels

The sidecar isn't running on `127.0.0.1:8765`. Check
`uvicorn web_extras.app:app --port 8765` is up; the cockpit will
auto-recover within ~3s.

### Pairing fingerprint mismatch

Reject the pair; mint a new one via `POST /api/pairing/begin`. Never
accept a fingerprint you can't read off both devices side-by-side.

### `precondition_required`

The HTTP policy gate is on. Mint a confirm token via
`POST /api/wallet/{id}/confirm`, resend the destructive call with
`X-TARS-Confirm: <token>`. Set `TARS_REQUIRE_OPERATOR_CONFIRM=0`
to disable for dev.

---

## Tests

```bash
PYTHONPATH=. .venv/bin/python -m pytest        # backend (≈600 tests)
cd experiments/neural-showcase-v3 && npx vitest run  # cockpit logic (50 tests)
cd experiments/neural-showcase-v3 && npx tsc --noEmit
cd mobile/ios/TARSCompanion && swift test
```

The **end-to-end smoke** (`tests/test_e2e_smoke.py`) walks pairing →
wallet creation → message signing → real transaction signing →
verification by independent crypto primitives. If it passes, every
cross-cutting subsystem is at least minimally functional.

---

## Contributing

Cursor and Claude Code agents pick up from
[`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md) — read it first.

The per-edit log is [`docs/CHANGELOG_AGENTS.md`](docs/CHANGELOG_AGENTS.md).
Append, don't rewrite.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
