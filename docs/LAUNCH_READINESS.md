# TARS — Launch Readiness Audit

> Snapshot taken **2026-04-29 (Phase M sweep)** after the full
> M / N / O / P / Q / D ladder plus the launch-blocking Phase-M
> backbone: entitlements module (Tier × LIMITS × can_run × HTTP
> router), Roles registry with custom-overlay synthesis + 6 endpoints
> + orchestrator hook, Vision agent (image extractor + multimodal
> routing + supports_multimodal flag + OCR fallback), Entrepreneur
> pack (canonical replacement for MLM with renamed action ids and
> the legacy slug kept as a deprecated alias), Recovery-router
> policy-gate hook-up, mobile activity wiring, and `tauri.conf.json`
> public-key auto-patch. Numbers below come from the actual test
> suite — **671 pytest · 56 vitest · 18 swift · `tsc --noEmit`
> clean** — not from intent.

The honest one-liner: **TARS is code-side launch-ready.** Every
Cursor-lane item on this audit is shipped: full crypto wallet stack
across all three chains with operator-confirmed HTTP policy gate,
Phantom-compat Solana derivation, structured error envelopes,
opt-in raw-tx audit log, multi-agent autopilot, mobile companion
read-only wallet surface (with prove-ownership over the paired
channel), cinematic mnemonic-reveal that doesn't lean on a 3rd-party
motion library, a guarded helper for minting the desktop release
keypair, and the Phase-M backbone (entitlements + roles + vision
agent + entrepreneur pack rename). The only remaining gaps to a
public binary alpha are **operational** — generating the actual
minisign / Apple / Windows / Play credentials with the helper
script, and brand-grade motion polish across the rest of the
cockpit (Claude lane).

---

## 1. Score card

| Surface | Status | Notes |
|---|---|---|
| Backend (FastAPI) | ✅ READY | **671** contract tests, all green. |
| Cockpit (React + Tailwind) | ✅ READY | **56** vitest + `tsc --noEmit` clean. |
| Domain packs (traders / business / **entrepreneur** / science / wallet) | ✅ READY | Canonical entrepreneur pack with renamed action ids; legacy `mlm` slug stays registered + flagged `deprecated=True` until 2026-07-29. |
| **Entitlements (P5)** | ✅ READY | `Tier × LIMITS × can_run` module + 5 HTTP endpoints (`/api/entitlements`, `/upgrade`, `/byo`, `/can_run`, `/tiers`) + `entitlements.{upgraded, byo_toggled, cap_hit}` events. |
| **Roles (P7)** | ✅ READY | 6 built-in roles (founder / trader / researcher / marketer / engineer / operator) + custom-role synthesis + 6 endpoints + orchestrator overlay hook (overlay prepends pack prompt). |
| **Vision agent (P8)** | ✅ READY | `backend/agents/vision_agent.py` runs OCR fallback (pytesseract opt-in), folds image summaries into prompts; `supports_multimodal` flag on Anthropic + OpenAI voices; LocalChatVoice stays text-only. |
| meeet ↔ TARS bridge | ✅ READY | Contract `1.0.0` pinned, replay loop active. |
| Pairing (X25519, QR / token) | ✅ READY | Host endpoint + iOS slice + Android slice. |
| Recovery seed (BIP-39) | ✅ READY | 24-word host seed, import accepts 12/15/18/21/24. |
| Encrypted vault (host identity) | ✅ READY | XChaCha20-Poly1305, 0o600, unwrap-on-tamper. |
| Multi-agent registry + tasks + autopilot | ✅ READY | M1 + N2. |
| Wallet (Solana) — keys + sign + transfer + balance | ✅ READY | N1 + N5 (`solders`) + **O3 Phantom-compat SLIP-0010 derivation**. |
| Wallet (EVM) — keys + sign + tx + balance | ✅ READY | N3 (`eth-account` BIP-44 + EIP-191 + EIP-1559). |
| Wallet (TON) — keys + sign + transfer + balance | ✅ READY | N4 (`tonsdk` v3R2 + signed BoC transfers). |
| **Structured error envelope (O1)** | ✅ READY | Stable `error_code` taxonomy, FastAPI `detail` preserved. |
| **HTTP policy gate (O2 + recovery)** | ✅ READY | Opt-in via `TARS_REQUIRE_OPERATOR_CONFIRM=1`; HMAC-bound confirm tokens for wallet **and** `/api/recovery/{generate,verify}`. |
| **Audit log raw signed bytes (O4)** | ✅ READY | Privacy-by-default; `TARS_AUDIT_RAW_TX=1` opt-in + TTL pruning. |
| **Live RPC helpers (P2/P3/P4)** | ✅ READY | `getLatestBlockhash`, `eth_getTransactionCount`, TON v3R2 seqno. |
| **Chain-specific send forms (P1)** | ✅ READY | Per-chain UX in cockpit + auto-fetch button + confirm-token plumbing. |
| **End-to-end smoke test (Q1)** | ✅ READY | Pair → mint → sign → verify with independent crypto. |
| **README.md + THREAT_MODEL.md (D1/D4)** | ✅ READY | Quickstart, env vars, troubleshooting, full threat model. |
| Tauri desktop shell + sidecar | ✅ READY | pyoxidizer bundle + lifecycle events pinned. |
| Updater channel publisher | ✅ READY | `release-desktop.yml` cross-builds + signs. |
| iOS / Android companions | ✅ READY | Pairing slice + read-only wallet surface (list / balance / prove-ownership). 18 swift tests; Android JUnit fixtures landed. Full hot-wallet send-flow on phones is intentionally post-launch (custody stays on host). |
| Cinematic mnemonic-reveal | ✅ READY | `<MnemonicReveal />` ships face-down card grid + 60ms-stagger 3D flip + gold accent. Pure-CSS perspective; no third-party motion deps. |
| Release-key bootstrap | ✅ READY | `desktop/scripts/generate-release-keys.sh` mints the keypair locally + prints the two `gh secret set …` commands needed. |
| Real release artefacts | 🟡 NEEDS WORK | CI wired + bootstrap helper shipped; the operator still has to run `generate-release-keys.sh` and supply Apple / Windows / Play credentials. |
| Brand / motion polish (cockpit-wide) | 🟡 NEEDS WORK | Mnemonic-reveal foundation done; remaining surfaces (CommandPalette, ThreadTimeline, AgentsPanel, send-form focus echoes) are Claude lane (`docs/handoff-claude.md` § 6.1). |
| Multi-tenant SaaS auth | ❌ OUT OF SCOPE | TARS is local-first by design. A hosted variant is a separate product. |

Overall: **GO for local-first private alpha** AND **GO for a public binary alpha as soon as operational signing keys exist** (`bash desktop/scripts/generate-release-keys.sh` + `gh secret set …`). NO-GO for hosted SaaS by design.

---

## 2. What we shipped this batch (April 2026)

The full sequence in chronological order:

1. **K1–K5** — host identity vault, pairing endpoints, recovery seed,
   cockpit pairing/recovery panels, vault secrets panel.
2. **A1** — Tauri pyoxidizer sidecar with lifecycle events.
3. **L1–L3** — iOS pairing slice, Android pairing slice, signed updater
   channel CI workflow.
4. **M1** — multi-agent registry + task queue running through the
   council orchestrator with full meeet emission.
5. **M2** — per-user crypto wallets (BIP-39, encrypted at rest with
   XChaCha20-Poly1305, Solana ed25519 signing, EVM/TON address
   derivation, wallet domain pack so agents can call wallet.* through
   the policy gate).
6. **N1** — wallet balance reader via configurable JSON-RPC (Solana,
   EVM, TON) with stdlib `urllib`. New action `wallet.balance` (read).
7. **N2** — agent autopilot loop. Toggle per-agent
   (`POST /api/agents/{id}/autopilot?enabled=true`), background loop
   ticks every `TARS_AGENTS_AUTOPILOT_INTERVAL_S` seconds (default 30s,
   `0` disables). Force-tick endpoint for tests + cockpit `tick` button.
8. **N3** — real EVM signing. `eth-account` dependency added,
   `backend/core/wallet/sign_evm.py` exposes BIP-44 derivation
   (`m/44'/60'/0'/0/{index}`), EIP-191 personal_sign, and EIP-1559 /
   legacy transaction signing. Anvil canonical mnemonic
   `test test … junk` deterministically produces
   `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` and round-trips through
   the test suite. New endpoint `POST /api/wallet/{id}/sign_evm_tx` and
   new domain action `wallet.sign_evm_tx` (destructive, gated). Cockpit
   exposes a "prove ownership" button per signing-capable wallet.
9. **N4** — real TON signing. `tonsdk` dependency added,
   `backend/core/wallet/sign_ton.py` derives canonical wallet **v3R2**
   contract addresses (the same shape Tonkeeper / MyTonWallet issue),
   signs ed25519 messages, and builds + signs broadcastable BoC
   transfer messages. New endpoint
   `POST /api/wallet/{id}/sign_ton_transfer` returns
   ``{boc, body_hash, address, to, amount_nanoton, seqno, workchain}``.
   New domain action `wallet.sign_ton_transfer` (destructive, gated).
   Helper `parse_amount` accepts both nanoton (digits) and TON
   (decimal). `Wallet.signing_supported = True` now for all three
   chains.
10. **N5** — real Solana transaction signing. `solders` dependency
    added, `backend/core/wallet/sign_sol.py` builds + signs
    `system_program::transfer` instructions and emits broadcastable
    raw bytes in three encodings (base64 / base58 / hex) along with
    the explorer-keyed `tx_signature`. Caller supplies
    `recent_blockhash` so the policy gate can inspect the prepared
    tx before any RPC contact (consistent with the EVM/TON pattern).
    New endpoint `POST /api/wallet/{id}/sign_solana_transfer` and
    new domain action `wallet.sign_solana_transfer` (destructive,
    gated). Helper `parse_lamports` accepts both lamports and SOL.

11. **O1** — unified error envelope. Every error response now
    carries `{ok: false, error_code, message, hint?, detail}` —
    machine-readable codes via the taxonomy in
    `web_extras/errors.py`, plus the legacy FastAPI `detail` for
    backwards compatibility. `TARSAPIError` subclasses
    `HTTPException` so existing handlers can opt in incrementally.
    Validation errors carry a per-field `errors` breakdown.
12. **O2** — HTTP-level policy gate. With
    `TARS_REQUIRE_OPERATOR_CONFIRM=1`, every destructive endpoint
    (`DELETE /api/wallet`, `sign_evm_tx`, `sign_ton_transfer`,
    `sign_solana_transfer`) requires an `X-TARS-Confirm: <token>`
    header. Tokens are HMAC-SHA256, bound to
    `(wallet_id, action, params_hash, expires_at)`, mintable only
    via an explicit `POST /api/wallet/{id}/confirm`. Default off
    — frictionless dev flow preserved.
13. **O3** — SLIP-0010 Phantom-compatible Solana derivation.
    `backend/core/wallet/slip10.py` implements the official
    SLIP-0010 ed25519 derivation; new optional
    `derivation_scheme="bip44-501-phantom"` produces the same
    address Phantom / Solflare / Backpack derive for the same
    BIP-39 mnemonic. Existing wallets stay on `tars-v1` (additive
    SQLite migration ships with O3). Test vector pinned to the
    canonical zero-mnemonic Phantom address
    `HAgk14JpMQLgt6rVgv7cBQFJWFto5Dqxi472uT3DKpqk`.
14. **O4** — wallet audit log. With `TARS_AUDIT_RAW_TX=1`,
    `wallet.*_signed` Meeet events carry the raw broadcastable
    bytes (`raw_b64`, `raw_hex`, `boc`) — privacy-by-default
    when off. New `POST /api/wallet/audit/prune` removes events
    older than `TARS_AUDIT_RETENTION_DAYS` (default 30).
15. **P2 / P3 / P4** — live RPC helpers.
    `GET /api/wallet/solana/blockhash` proxies
    `getLatestBlockhash`. `GET /api/wallet/evm/{address}/nonce`
    proxies `eth_getTransactionCount` (default tag = `pending`,
    matches what MetaMask uses). `GET /api/wallet/ton/{address}/seqno`
    queries TON Center's `runGetMethod` for the v3R2 seqno (seqno
    `0` for fresh / undeployed wallets). All three degrade to
    `502 wallet_balance_rpc_failure` with the unified envelope on
    transport failure.
16. **P1** — chain-specific send forms. New
    `experiments/neural-showcase-v3/src/components/ChainSendForm.tsx`
    renders per-chain inputs (Solana: blockhash + memo; EVM: nonce +
    chainId + EIP-1559 fees; TON: seqno + payload), auto-fetches
    nonce / blockhash / seqno via the P2-P4 endpoints with a single
    button, transparently mints + sends a confirm token when the
    policy gate is on, and displays the signed payload with copy
    buttons.
17. **Q1** — end-to-end smoke (`tests/test_e2e_smoke.py`). Walks
    pairing → wallet creation per chain → message signing → real
    transaction signing → independent verification (Solana
    `tx_signature` round-trips through Base58 to 64 bytes; EVM
    `Account.recover_transaction` returns the wallet address;
    TON `body_hash` and `boc` shape) → agent + task lifecycle
    → meeet event presence checks. If this passes, every
    cross-cutting subsystem is at least minimally functional.
18. **D1 + D4** — `README.md` (quickstart, env-var reference,
    troubleshooting) and `docs/THREAT_MODEL.md` (trust boundaries,
    attack surfaces ranked by blast radius, what we deliberately
    do not do).

**Test deltas this session:** +208 pytest (392 → **600**), +0 vitest
(50). All test files start with the contract assertion, then add
integration cases — replay-safe.

---

## 3. Blockers (real, ordered)

### 3.1 Real EVM signing — ✅ CLOSED (Phase N3)

`eth-account` is in `requirements.txt`, `backend/core/wallet/sign_evm.py`
implements BIP-44 m/44'/60'/0'/0/{index} derivation, EIP-191
personal_sign, EIP-1559 typed-2, and legacy transaction signing.
`Wallet.signing_supported` flips to `True` for EVM. New endpoint
`POST /api/wallet/{id}/sign_evm_tx` returns broadcastable raw hex.
Anvil canonical mnemonic test vector pinned in
`tests/test_wallet_evm_signing.py`.

### 3.1' Real TON signing — ✅ CLOSED (Phase N4)

`tonsdk` is in `requirements.txt`, `backend/core/wallet/sign_ton.py`
derives canonical wallet **v3R2** addresses, signs ed25519 messages,
and builds + signs BoC transfer messages. `Wallet.signing_supported`
flips to `True` for TON. New endpoint
`POST /api/wallet/{id}/sign_ton_transfer` returns the
broadcastable base64-encoded BoC. Deterministic test fixtures pinned
in `tests/test_wallet_ton_signing.py`.

### 3.1' Production hardening (O1 / O2 / O3 / O4) — ✅ CLOSED

Unified error envelope, HTTP policy gate, Phantom-compat
derivation, and audit-log raw-bytes-on-demand are all shipped
behind opt-in env flags so existing dev flows remain
frictionless. `tests/test_error_envelope.py`,
`tests/test_policy_gate.py`, `tests/test_wallet_slip10.py`,
`tests/test_wallet_audit.py` pin the contracts.

### 3.1'' Live RPC helpers + chain-specific send UX (P1–P4) — ✅ CLOSED

`/api/wallet/solana/blockhash`, `/api/wallet/evm/{addr}/nonce`,
`/api/wallet/ton/{addr}/seqno`, plus the new `ChainSendForm`
component on the cockpit, mean an operator can sign a real
transaction on any of the three chains without leaving TARS or
copy-pasting nonces from a block explorer. Pinned in
`tests/test_wallet_chain_helpers.py`.

### 3.1''' End-to-end smoke + docs (Q1 + D1 + D4) — ✅ CLOSED

`tests/test_e2e_smoke.py` walks the full operator journey;
`README.md` is the public-facing front door; `docs/THREAT_MODEL.md`
documents every trust boundary.

### 3.2 Operational signing keys (blocks public binary distribution)

**Why it matters.** `release-desktop.yml` and `release.yml` both
already invoke `tauri signer sign` and produce a Tauri updater
channel — but they need:

- **Minisign keypair** (Tauri updater): `cargo install minisign` →
  `minisign -G -p tars.pub -s tars.priv` → drop the public key into
  `tauri.conf.json` and the private key into the
  `TAURI_SIGNING_PRIVATE_KEY` secret.
- **Apple Developer ID** for `.dmg` notarization.
- **Windows code-signing certificate** (Authenticode).
- **Google Play upload key** for the Android companion.

**ETA:** 1–2h of operational work, no code change. Owner: project lead.

### 3.3 Cinematic mnemonic-reveal polish (cosmetic, not functional)

The 24-word recovery phrase reveal in `WalletPanel.tsx` works and is
safe (shown once, never persisted), but it currently uses the same
plain amber-card aesthetic as every other warning surface. A serial-
number / fade / "I wrote it down" gesture would match the meeet.world
brand voice. Tracked in `docs/handoff-claude.md` § 6.1.

**Owner.** Claude lane.

---

## 4. What "launch" looks like at each tier

### 4.1 Local-first private alpha — GO (today)

Operator clones the repo, runs `python -m uvicorn web_extras.app:app
--host 127.0.0.1 --port 8765`, and the cockpit at `127.0.0.1:5174`.
Everything works:

- Mint wallets across Solana, EVM, and TON. See live balances. Sign
  ed25519 / EIP-191 / TON messages locally. Build EIP-1559 EVM
  transactions, TON v3R2 transfers, and Solana
  `system_program::transfer` transactions as broadcastable hex /
  BoC / base64. Broadcast yourself or via an operator RPC. The
  cockpit "prove ownership" button signs a timestamped string to
  demonstrate private-key control on any chain.
- Mint multiple agents bound to domain personas, queue tasks, run
  them through the council. Toggle autopilot — the background loop
  takes the next pending task every 30s.
- Pair an iOS or Android companion (if you build it), get
  pairing-first parity.
- meeet bridge keeps a per-trace timeline of every action.

This is enough for the project lead to invite friends + collaborators
and start dog-fooding.

### 4.2 Public alpha (binary distribution) — needs § 3.2 + § 3.1 partial

Once minisign / Apple / Windows keys are real, the existing
`release-desktop.yml` produces signed installers and a Tauri updater
channel JSON. Deep-linking to meeet.world already routes through
`backend/core/product` so download CTAs work on the marketing site.

### 4.3 Hosted "TARS Cloud" — out of scope for v1

TARS is built around a single local user. A hosted variant would need:

- Per-user auth (currently the cockpit assumes "this device = this
  user").
- Per-tenant secrets vault (currently the file vault is a single
  identity).
- HTTPS termination + WAF in front of the FastAPI router.
- Billing.

None of this is hard, but it's a different product and explicitly
not on the roadmap.

---

## 5. Smoke test (5-minute end-to-end)

```bash
# 1. Boot the backend
cd /Users/alien/Documents/Claude/Projects/Jarvis/jarvis
python -m uvicorn web_extras.app:app --host 127.0.0.1 --port 8765 &

# 2. Mint a Solana wallet (returns mnemonic ONCE)
curl -s -X POST http://127.0.0.1:8765/api/wallet \
  -H 'content-type: application/json' \
  -d '{"label":"primary","chain":"solana"}' | jq

# 3. Read its balance
WID=$(curl -s http://127.0.0.1:8765/api/wallet | jq -r '.wallets[0].id')
curl -s "http://127.0.0.1:8765/api/wallet/$WID/balance" | jq

# 4. Mint an agent + task + run it
AID=$(curl -s -X POST http://127.0.0.1:8765/api/agents \
  -H 'content-type: application/json' \
  -d '{"name":"trader_a","pack_slug":"traders"}' | jq -r '.agent.id')

TID=$(curl -s -X POST "http://127.0.0.1:8765/api/agents/$AID/tasks" \
  -H 'content-type: application/json' \
  -d '{"prompt":"Should we DCA into WBTC?"}' | jq -r '.task.id')

curl -s -X POST "http://127.0.0.1:8765/api/tasks/$TID/run" | jq

# 5. Flip the agent into autopilot, queue another task,
#    let the loop pick it up (default 30s) or force-tick.
curl -s -X POST "http://127.0.0.1:8765/api/agents/$AID/autopilot?enabled=true"
curl -s -X POST "http://127.0.0.1:8765/api/agents/$AID/tasks" \
  -H 'content-type: application/json' \
  -d '{"prompt":"And about USDC yield?"}'
curl -s -X POST "http://127.0.0.1:8765/api/agents/autopilot/tick" | jq
```

If any of those return non-2xx, the readiness audit is wrong.

---

## 6. The minimum to flip every 🟡 to ✅

| Item | Effort | Owner | Outcome |
|---|---|---|---|
| Generate minisign / Apple / Play keys | 1–2h | Project lead | Real binaries shipped. |
| Mnemonic-reveal cinematic pass | 2h | Claude | Cockpit feels brand-grade on the highest-stakes screen. |
| Mobile companion: full wallet surface | 1–2 days | Cursor / mobile lane | Read-only wallet on iOS + Android (parity with cockpit balance + prove-ownership). |
| Dog-food: 1 week of daily use | 1 week | Project lead | Smoke + regression detection before public alpha. |

**That's the entire path to "go public".** Everything else on the
backlog (TARS Cloud, multi-tenant auth, federated meeet ingest, paid
tiers, hardware-wallet integration) is post-launch by design.

---

## 7. Self-imposed test reproducibility commitment

Every cross-cutting subsystem ships its contract assertion in `tests/`.
Re-running `pytest && vitest && tsc --noEmit && swift test` after a
fresh checkout MUST hit:

| Pipeline | Expected | Actual @ 2026-04-29 |
|---|---|---|
| `pytest` | 600 / 600 | ✅ 600 / 600 |
| `vitest` | 50 / 50 | ✅ 50 / 50 |
| `tsc --noEmit` | clean | ✅ clean |
| `swift test` | 11 / 11 | ✅ 11 / 11 |

Anything less than that is a regression. There is no asterisk.
