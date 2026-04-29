# TARS — Security model

> **Status:** living document. Last reviewed 2026-04-29.
> **Cryptographic primitives** pinned in `docs/contracts/
> L5_PAIRING_DRAFT.md` (canonical) and `backend/core/crypto/
> envelope.py` (implementation).
> **Disclosure:** security@meeet.world. 90-day coordinated disclosure.

This document describes how TARS protects an operator's data,
machine, and identity. It is meant to be auditable — every claim
maps to a file, a test, or a contract.

---

## 1. Threat model (STRIDE-aligned)

| Threat | Asset at risk | Mitigation |
|--------|---------------|------------|
| **S**poofing — attacker impersonates operator's TARS to a remote skill or T2T peer | Operator identity, $MEEET balance, T2T deal authority | Per-action Ed25519-signed receipts; X25519 long-term identity bound to macOS Keychain / Windows DPAPI; T2T handshake validates peer fingerprint before settling escrow |
| **T**ampering — adversary modifies on-disk TARS state (memory ledger, attachments) | Audit trail, AI Clone training data, signed-receipt chain | Hash-chained receipts (SHA-256); optional daily Solana memo anchor; SQLite WAL with `synchronous=FULL` per database |
| **R**epudiation — operator denies a destructive action they authorised | Compliance trail | Every destructive action requires explicit operator confirm via the policy gate; the confirmation token is persisted with TTL + signature in `policy_actions` |
| **I**nformation disclosure — prompts or files leak to a third party | Prompts, files, chat history, embeddings | Local-first by default; cloud sync is opt-in; ciphertext-only at rest in meeet.world (XChaCha20-Poly1305); LLM API calls only when a cloud voice is explicitly selected |
| **D**enial of service — runaway agent or malicious skill burns through quota / disk | Cloud LLM budget, disk space, CPU | Cost ledger with `cloud_usd_cap` per tier (P5); supervisor with budget cap + rate limit + kill switch (task #76, shipped); attachment ingest 25 MB cap (env-tunable) |
| **E**levation of privilege — agent runs an action it wasn't granted | Operator's machine, files, network | sandbox-exec profile per Mac action; policy gate's `destructive: true` flag blocks autopilot; receipts log capability used |

---

## 2. Architecture (data flow)

```
┌────────────────── operator's machine ───────────────────┐
│                                                          │
│  ┌──────────────┐   ┌──────────────┐  ┌──────────────┐   │
│  │ Cockpit (UI) │←─→│ Local daemon │←→│ Vault        │   │
│  └──────────────┘   │ (FastAPI)    │  │ Keychain/    │   │
│                     │              │  │ DPAPI        │   │
│                     │ ┌──────────┐ │  └──────────────┘   │
│                     │ │Council   │ │                     │
│                     │ │Policy    │ │  ┌──────────────┐   │
│                     │ │Playbooks │ │  │ Memory ledger│   │
│                     │ └──────────┘ │  │ ~/.tars/     │   │
│                     │              │  │ *.sqlite     │   │
│                     └─┬────────┬───┘  └──────────────┘   │
│                       │        │                         │
│                  sandbox-       (encrypted               │
│                  exec for       envelope                 │
│                  destructive    only when                │
│                  Mac actions    sync opted in)           │
└───────────────────────┼────────┼─────────────────────────┘
                        │        │
              opt-in    │        │  opt-in (Pro+)
              cloud LLM │        │  E2E-encrypted sync
                        │        │
              ┌─────────▼──┐  ┌──▼──────────────────────┐
              │ Anthropic /│  │ meeet.world             │
              │ OpenAI etc.│  │ • identity              │
              │ (DPAs apply)│ │ • encrypted ingest      │
              └────────────┘  │ • marketplace           │
                              └─────────────────────────┘
```

**Key points:**

1. The local daemon binds to `127.0.0.1:8765` only — no inbound from
   LAN by default.
2. All persistent state is under `~/.tars/`, owned by the operator
   user. No setuid binaries.
3. Cloud LLM calls happen only when the active voice is configured
   for a cloud provider AND that provider's API key is present.
4. meeet.world stores opaque ciphertext. The host wraps a symmetric
   key for each currently paired device per event; revocation =
   stop wrapping.

---

## 3. Cryptographic primitives

| Purpose | Algorithm | Source / Lib |
|---------|-----------|--------------|
| Long-term identity | X25519 (32 bytes) | `pynacl` on host; CryptoKit on iOS; Tink/Conscrypt on Android |
| AEAD (sync envelope) | XChaCha20-Poly1305 | `crypto_aead_xchacha20poly1305_ietf` (libsodium) |
| KDF | HKDF-SHA-256, 16-byte salt | `cryptography` (host); platform KDF on mobile |
| Receipt signature | Ed25519 | `pynacl` |
| Receipt chain | SHA-256 hash chain | stdlib |
| QR / pairing seed | bech32m, HRP `tars1` | `bech32` ref impl |
| Embeddings (cosine + BM25) | normalised float32 vectors | `text-embedding-3-small` (cloud) or hash-bigram (offline) — neither is a security primitive, listed for completeness |

Tested against `pynacl` test vectors before each release. Mobile
companion implementations validate interop against host-generated
ciphertexts in CI before declaring green.

---

## 4. Sandboxing — Mac Operator

Every destructive Mac action runs inside an Apple `sandbox-exec`
profile that whitelists exactly:

- **Filesystem:** the source/destination paths the action requires
  (e.g. `~/Downloads`), no broader.
- **Network:** the specific host the action declared (e.g.
  `api.github.com`), no broader.
- **Subprocess:** none, except the action's own binary.
- **Mach lookup:** denied.

Profiles live in `playbooks/sandbox-profiles/<action_id>.sb`. New
profile + corresponding action go through a manual review checklist
before merge (`docs/contracts/SANDBOX_REVIEW.md`).

For reversible operations (file moves within the same volume), the
receipt includes an `undo` payload. Operator has 10 minutes to undo
from the cockpit's receipts panel.

For irreversible operations (`rm -rf`, network sends, payment
transfers), the policy gate **always** blocks autopilot. Two-voice
council must propose, operator must press a green Confirm.

---

## 5. Policy gate

Every destructive action is annotated with `destructive: true` in
its `ActionSpec`. Three modes (`autopilot | confirm | dry_run`,
default `confirm`) controlled per-request via the
`x-tars-policy-mode` header.

State machine:

```
proposed → queued → (operator confirms) → allowed → completed
                  ↘ (operator cancels)  → cancelled
```

Every transition emits `policy.<state>` events into the meeet store.
Confirmation tokens have TTL (default 10 min) and live in the
`policy_actions` SQLite table with operator signature.

Spec: `backend/core/policy/`. Tests: `tests/test_policy.py` (15
cases).

---

## 6. Audit log + signed receipts

Every action that crosses a service boundary — LLM call, Mac action,
T2T deal, attachment ingest — emits a receipt:

```jsonc
{
  "receipt_id": "rcp_a91f0c2...",
  "trace_id":   "trc_...",
  "action_id":  "business.draft_email",
  "operator_sig": "ed25519:...",
  "ts":         1745798400.0,
  "inputs_hash": "sha256:...",
  "outputs_hash": "sha256:...",
  "prev_hash":   "sha256:...",   // chain link
  "status":      "completed",
  "cost_usd":    0.0042
}
```

- **Local store:** `~/.tars/receipts.sqlite`. Hash chain validated on
  startup; mismatch → warning + audit event.
- **Optional Solana anchor:** daily Merkle root of new receipts
  posted to a Solana memo. Tamper-evident across machine reinstalls.
- **Export:** Settings → Data → Export Audit dumps JSONL. Bundle
  includes receipts table + meeet event log + cost ledger.

Spec: task #67 (Receipt-ledger), task #89 (Solana memo anchoring).

---

## 7. Sync — L5 envelope (contract 1.1.0)

Once two devices are paired, every meeet event row carries:

```jsonc
{
  "kind": "chat.message.completed",
  "trace_id": "...",
  "payload": null,                                 // legacy slot
  "ciphertext": "base64(XChaCha20-Poly1305 sealed)",
  "envelope": {
    "scheme": "xchacha20-poly1305-x25519-v1",
    "nonce":   "base64(24 bytes)",
    "epk":     "base64(ephemeral X25519 public key)",
    "recipient_keys": [
      { "device_id": "...", "wrapped_key": "base64(...)" },
      ...
    ]
  }
}
```

- Host produces one ciphertext per event, wraps the symmetric key
  for each paired device.
- Revocation: stop wrapping for that device's id; old ciphertexts
  remain unreadable to it without an explicit re-key event.
- meeet.world **never** sees plaintext. Replay flow on a paired
  device decrypts before the local indexes ingest.

Spec: `docs/contracts/L5_PAIRING_DRAFT.md`. Tests:
`tests/test_pairing_envelope_e2e.py`,
`tests/test_meeet_contract_v11.py`.

---

## 8. Recovery seed

On first install, a 24-word BIP-39 seed is generated and **shown
once**. Operator prints / stores offline. The seed deterministically
derives the master X25519 key, so:

- Host machine lost → buy new hardware → install TARS → "Restore
  from seed" → master key reconstituted → existing ciphertexts in
  meeet.world become readable again.
- Without the seed, ciphertext blobs at meeet.world stay encrypted
  — by design. We cannot help recover them.

Spec: `docs/contracts/L5_PAIRING_DRAFT.md` § 9 (failure / recovery).

---

## 9. Network surface

By default, TARS opens **one** TCP listener:

- `127.0.0.1:8765` — local daemon HTTP/SSE for the cockpit.

No inbound LAN. No mDNS/bonjour broadcast unless L5 pairing flow
explicitly enabled (and then only for the 120-second pairing
window, then closed).

Outbound:
- Cloud LLM endpoints (when configured).
- meeet.world (`*.meeet.world`) when sync / $MEEET / T2T are
  opted in.
- The skills you connect (Slack API, GitHub API, etc.) — same as
  any browser.

No telemetry endpoints. No crash analytics. No "phone home".

---

## 10. Vulnerability disclosure

Email **security@meeet.world**. PGP key at
[meeet.world/.well-known/security.asc](https://meeet.world/.well-known/security.asc).

**90-day coordinated disclosure.** We commit to:

- Acknowledge within 48h.
- First triage update within 7 days.
- Patch + advisory within 90 days for critical/high.
- Public hall-of-fame credit unless reporter prefers anonymity.

**In scope:**
- TARS daemon (any version on macOS / Linux).
- Public manifest endpoints.
- L5 pairing endpoints.
- meeet.world ingest, identity, marketplace.

**Out of scope:**
- DoS via runaway prompt costs (use the policy gate / supervisor).
- Social engineering of operators.
- Phishing the meeet.world OAuth flow.

Bounty: paid in $MEEET, scaled with severity (50-5000 $MEEET range
2026-04-29).

---

## 11. Compliance

- **GDPR:** export + deletion shipped. Sub-processor list in
  `docs/PRIVACY_POLICY.md`. Data Processing Agreement available on
  request from legal@meeet.world.
- **CCPA:** same primitives as GDPR; "do not sell" is the default
  for everyone — we don't sell data to anyone.
- **SOC 2:** in progress (Type I expected Q3 2026). Until then,
  Business tier customers can request our security questionnaire.

---

## 12. Threat-model gaps we acknowledge

Honesty over polish:

1. **Cold-boot attack on master key** — if an attacker has root +
   physical access while macOS Keychain is unlocked, they can read
   the master X25519. macOS FileVault + screen-lock are still your
   responsibility.
2. **Side-channel timing on AEAD verify** — libsodium constant-time;
   no known leak.
3. **Quantum** — X25519 is **not** post-quantum. We track the
   liboqs / Kyber-768 hybrid path; will migrate when stable.
4. **Supply chain** — we ship signed binaries (codesign + notarize
   on macOS, Authenticode on Windows). Build provenance via SLSA
   level 2 in v9.2.

---

*Pin this file: `docs/SECURITY.md`. Web rendering: [/security](https://meeet.world/security).*
