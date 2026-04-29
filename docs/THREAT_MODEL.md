# TARS — Threat Model

> Living document. Every new surface (router, store, pack, sync
> channel) MUST be added here before merging. If a security claim is
> not in this document, it is not a security claim.

Last reviewed: **2026-04-29** at end of Phase Q1.
Contract version pinned to **`1.0.0`**.

---

## 1. What TARS is, in one paragraph

A local-first FastAPI sidecar plus React cockpit. Runs on the user's
machine. Holds private cryptographic material (BIP-39 seeds, X25519
device keys, confirm-token signing keys). Talks to LLM providers over
the public internet. Talks to public JSON-RPC endpoints over the
public internet. Optionally streams structured event payloads to
`meeet.world`. Optionally streams payloads to a paired phone over an
X25519 key exchange.

---

## 2. Trust boundaries

| Zone | Trust | Owner |
| --- | --- | --- |
| **Z0 — host process** | TRUSTED | the operator's machine, kernel, file system permissions |
| **Z1 — TARS sidecar** | TRUSTED | TARS code (this repo) |
| **Z2 — TARS cockpit** | TRUSTED | TARS code (this repo) |
| **Z3 — paired phone** | TRUSTED *after* X25519 fingerprint match | mobile companions, this repo |
| **Z4 — LLM providers** | UNTRUSTED for content; trusted for transport | OpenAI, Anthropic, local Ollama, ... |
| **Z5 — chain RPCs** | UNTRUSTED for content; trusted for transport | mainnet-beta, llamarpc, toncenter, ... |
| **Z6 — meeet.world ingest** | UNTRUSTED for downstream replay | the operator's meeet.world tenant |
| **Z7 — public internet** | UNTRUSTED | everyone else |

Anything that crosses a Z2 → Z* boundary is documented below.

---

## 3. What we trust the operator's machine to do

- File system permissions on `~/.tars/` keep secrets out of other
  users' read paths.
- `loopback (127.0.0.1)` is not reachable by other machines on the
  LAN. We bind only to loopback by default.
- The kernel's source of randomness (`/dev/urandom`,
  `BCryptGenRandom`, ...) is not compromised.
- The Python interpreter is the one we shipped (we are not defending
  against an attacker with arbitrary code-exec on the host).

If any of those are false, TARS is fully owned. Match the host's
trust posture to the value of the keys you mint inside TARS.

---

## 4. Crypto material we hold

| Material | Where | Encryption at rest |
| --- | --- | --- |
| BIP-39 mnemonics | RAM only, surfaced once via `POST /api/wallet` | n/a — never persisted |
| Per-wallet private keys (Solana ed25519, EVM secp256k1, TON ed25519) | `~/.tars/wallet_secrets.json` | XChaCha20-Poly1305 with key in `~/.tars/host_identity.json` |
| Host long-term identity (X25519) | `~/.tars/host_identity.json` | OS keychain when available, else passphrase-derived |
| Pairing vault (per-device shared secrets) | `~/.tars/pairing.sqlite` | XChaCha20-Poly1305 with `TARS_VAULT_KEY` |
| Meeet event log | `~/.tars/meeet.sqlite` | by default plaintext; `ciphertext` column reserved for L5 envelopes |
| Confirm-token signing key (O2) | RAM by default, env-overridable | n/a |

**Read this twice:** the only material that ever leaves Z1 in
plaintext is the mnemonic, and it leaves through the cockpit (Z2)
exactly once for the operator to write down. If you see another
plaintext exit, that's a bug — file an issue.

---

## 5. Attack surfaces, ranked by blast radius

### 5.1 Local malware on the host (Z0 compromised)

**Mitigations:** none — we cannot defend against arbitrary code-exec
on the same machine that holds the keys. We deliberately do not
implement "anti-debug" or anti-tamper, because false security is worse
than honest helplessness.

**What we *do* do:**

- Never log private keys, even at DEBUG level.
- Encrypt secrets at rest so a backup script that grabs `~/.tars/`
  without `host_identity.json` is useless.
- Surface mnemonics exactly once — they go from RAM to the operator's
  paper, no intermediate disk write.

### 5.2 Network attacker between TARS and an LLM provider

**Mitigations:** TLS via the standard system trust store. We never
send private keys / mnemonics / signed transactions to LLMs — full
stop. Audit: there is no code path in `web_extras/routers/chat.py`
or `backend/core/council/` that touches `wallet_secrets.json`.

**Residual risk:** the LLM provider sees the plaintext of your chat
turns. That is by design. Run a local model if the chat content
itself is sensitive.

### 5.3 Network attacker between TARS and a chain RPC

**Mitigations:** TLS again. Balance / blockhash / nonce / seqno reads
are not security-sensitive — a malicious RPC could return a stale
nonce, but the resulting signed tx would just fail to broadcast.
**No attacker who controls the RPC can extract private keys.** We
sign locally; the RPC sees only the broadcastable bytes (and only
when the operator explicitly broadcasts).

**Residual risk:** a malicious RPC could feed you a fake balance to
trick you into signing a bad amount. UX-side mitigation: the cockpit
shows the RPC URL it just queried.

### 5.4 Network attacker between TARS and meeet.world

**Mitigations:** L5 envelope (X25519 + XChaCha20-Poly1305) when both
ends opt in. Without it, payloads are plaintext over TLS to your
own ingest endpoint.

**By design:** we never push private keys to meeet. We push
**event metadata** — `wallet.created` carries the public address and
seed fingerprint, never the seed.

**With `TARS_AUDIT_RAW_TX=1`:** raw signed transaction bytes are
attached to `wallet.*_signed` events. They contain destination,
amount, and signature — but **not** the private key. Decide whether
your meeet.world tenant should hold them.

### 5.5 Compromised paired phone (Z3 turns hostile)

**Mitigations:** the pairing flow uses an X25519 ECDH and shows the
operator a 4-byte fingerprint on both devices. A MITM that flipped
the keys would cause a fingerprint mismatch.

**Residual risk:** if the phone is *legitimately* paired and *later*
compromised (malware, theft), the attacker can:

- Read the chat threads that were synced to the phone.
- Replay confirm-token UX if you blindly tap "approve".

**Mitigation knob:** revoke a paired device via
`POST /api/pairing/revoke` from the host the moment you suspect it.
The phone is then locked out.

### 5.6 Cockpit XSS

**Mitigations:** the cockpit is a static SPA bundle we ship — there
is no user-controlled HTML render path. All chat / agent / wallet
content is rendered with React's default escape behaviour. We do
**not** use `dangerouslySetInnerHTML`.

If you add a markdown / HTML render path, document it here first.

### 5.7 Loopback hijack via another local user

**Mitigations:** by default we bind to `127.0.0.1`, not `0.0.0.0`.
Other LAN machines cannot reach the sidecar.

**Residual risk on multi-user systems:** another local user could
`curl http://127.0.0.1:8765/api/wallet/...`. We do not implement
auth on the loopback interface (the trust model assumes one human
per machine). If you run on a shared host, set
`TARS_REQUIRE_OPERATOR_CONFIRM=1` so destructive endpoints need an
explicit confirm token, and run TARS as a dedicated user.

### 5.8 Confused-deputy via destructive HTTP routes

**Mitigation:** `TARS_REQUIRE_OPERATOR_CONFIRM=1` activates the
HTTP policy gate (Phase O2). With the gate on, every destructive
endpoint (`DELETE /api/wallet`, `sign_*_tx`, `sign_*_transfer`)
requires an `X-TARS-Confirm: <token>` header. The token is HMAC-SHA256
signed, bound to `(wallet_id, action, params_hash, expires_at)`, and
mintable only via an explicit `POST /api/wallet/{id}/confirm`.

**Without the gate**, anything that can reach loopback can sign.

### 5.9 Polluted dependency / supply-chain compromise

**Mitigations:**

- All Python deps pinned in `requirements.txt` to narrow ranges.
- All Node deps pinned via `package-lock.json` in
  `experiments/neural-showcase-v3/`.
- We do not auto-update at runtime. Updates are explicit binary
  releases, signed via Minisign (operator-owned key, see
  `docs/RELEASE.md`).

**Residual risk:** if `eth-account` / `tonsdk` / `solders` /
`pynacl` / `cryptography` is compromised upstream, we are too.
Periodically diff against the latest pinned hash.

---

## 6. What we deliberately do not do

- **No remote backup of private material.** Mnemonics are paper-only.
  Cloud sync of seeds is a category mistake.
- **No "social recovery" wizard.** Out of scope for v1.
- **No anti-debug / anti-VM.** False positives hurt operators more
  than they hurt attackers.
- **No "scan all your files" feature.** TARS only reads `~/.tars/`
  and the user-authored chat / pack content.
- **No browser extension.** Browsers have a hostile attacker model
  we do not want to inherit.
- **No "smart" gas / fee picker.** The operator decides. We display
  the fields; we do not pre-pick them based on telemetry.
- **No tx broadcast from the sidecar.** We sign; the operator (or an
  explicitly-approved tool) broadcasts. Two separate decisions.
- **No SaaS account.** The only network endpoints we initiate are:
  LLM providers (operator-configured), chain RPCs (operator-
  configured), meeet.world ingest (operator-configured).

---

## 7. Logging policy

| Level | What goes there |
| --- | --- |
| `DEBUG` | nothing sensitive. Free for handler-internal trace. |
| `INFO` | event kinds, request paths, public addresses, fingerprints. |
| `WARNING` | retried RPC, dropped event, recoverable validation. |
| `ERROR` | unhandled exception (with `TARS_HIDE_TRACEBACKS=0`). |

**Never logged:** private keys, mnemonics, seed bytes, confirm-token
signing key, X25519 secret keys, AEAD keys, base-64 secrets,
operator passphrases. Greppable: `pytest -k "no_secret_in_logs"` is
a future safety test we owe you.

---

## 8. Cryptographic primitives — and why those

| Use | Primitive | Why |
| --- | --- | --- |
| BIP-39 → seed | PBKDF2-SHA512 (2048 rounds) | Spec-mandated, widely audited. |
| Solana keypair | ed25519 (PyNaCl libsodium) | Native to Solana, libsodium is the gold standard. |
| EVM keypair | secp256k1 (coincurve, libsecp256k1) + Keccak-256 | Bitcoin / Ethereum standard. |
| TON keypair | ed25519 (PyNaCl) + Cell encoding (`tonsdk`) | TON spec. |
| AEAD at rest | XChaCha20-Poly1305 | Modern AEAD, 192-bit nonce, no nonce-misuse class hazard. |
| Key exchange (pairing) | X25519 (PyNaCl) | Constant-time, side-channel resistant. |
| Confirm tokens | HMAC-SHA256 | Pure stdlib, deterministic, low surface. |

We do **not** roll our own crypto. If you ever feel the need to
implement AES-CBC by hand, you are wrong.

---

## 9. Security contact

`security@meeet.world`. Do not file public GitHub issues for
exploitable bugs. We will publish CVE-style advisories under
`docs/security/`.

---

## 10. Open questions

- Code-signing for Linux binaries (we cover macOS / Windows).
- Mobile companion: at-rest encryption of the chat replay buffer.
- Hardware-wallet integration (Ledger / Trezor) — wanted, not in v1.

Track these in [`docs/IDEAS.md`](IDEAS.md).
