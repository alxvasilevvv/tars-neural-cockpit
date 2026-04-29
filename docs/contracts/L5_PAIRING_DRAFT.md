# Contract draft — L5 device pairing + encrypted sync envelope

> **Status:** SHIPPED (v1, host-only).
>   - ✅ Pairing endpoints `POST/GET /api/pairing/*` (real X25519
>     identity, validated `client_epk`, exposed `host_public_key`) —
>     `tests/test_pairing_contract.py`.
>   - ✅ `meeet` contract bumped to **1.1.0** with optional
>     `ciphertext` + `envelope` fields (additive; 1.0.0 events ride
>     the same wire unchanged) — `tests/test_meeet_contract_v11.py`.
>   - ✅ XChaCha20-Poly1305 + X25519 envelope module
>     (`backend/core/crypto/envelope.py`); host can encrypt for any
>     paired device, device decrypts with its secret key, AAD binds
>     trace_id|kind so tampering breaks the AEAD tag —
>     `tests/test_crypto_envelope.py`, `tests/test_pairing_envelope_e2e.py`.
>   - 🟡 Persistent host keyring (Keychain / DPAPI), recovery seed
>     UI, multi-host federation, and the relay-mode `meeet.world`
>     forwarder are still pending.
> **Owner:** Cursor agent (Phase L5 backend) + mobile companions (Phase L10).
> **Goal:** stop hand-waving the multi-device story; freeze field
> names, key namespaces, and QR payload shape so the Tauri shell, the
> iOS app, and the Android app all build against the same blueprint.

This document is **functional spec only**. No crypto code lives in
this commit. It exists so a fresh agent picking up Phase L5 (or
Phase L10 mobile pairing) reads the same fields off the same page.

## 1. Devices and roles

```
                            ┌──────── meeet.world ────────┐
                            │ relay (encrypted blobs only) │
                            └─────▲────────────────▲───────┘
                                  │                │
   pairing seed (QR / hex)        │                │  encrypted sync stream
                                  │                │
   ┌──────────────────────────────┴────┐    ┌──────┴────────────────────┐
   │  TARS · macOS / Windows  (HOST)   │    │  TARS · iOS / Android     │
   │  full backend, master keyring     │    │  thin client, derived key │
   └───────────────────────────────────┘    └───────────────────────────┘
```

Roles:

- **HOST** — a desktop install (macOS or Windows) running the full
  backend, master keyring sealed in macOS Keychain or DPAPI.
- **CLIENT** — a paired device (iPhone, Android phone, second
  desktop). Holds **only** derived per-device keys; revocation by
  the host wipes its access in O(1).

**Trust anchor:** the master keyring is born on the first desktop
install. Subsequent devices are paired *into* that anchor — there is
no "create a new vault on the phone".

## 2. Field naming policy (frozen)

All identifiers are short, lowercase, snake_case to match the existing
`meeet` event payload style. Wire size matters for QR codes.

| Field | Type | Notes |
|-------|------|-------|
| `device_id` | `str` (16 hex) | UUID4 truncated; lifetime: device lifetime. |
| `host_id`   | `str` (16 hex) | Same shape; identifies the host that minted the pairing. |
| `pair_id`   | `str` (16 hex) | One per pairing handshake; logged into the meeet store. |
| `kind`      | `str` enum    | `desktop_macos` `desktop_windows` `mobile_ios` `mobile_android`. |
| `created_at` / `expires_at` | float (Unix s, UTC) | Pairing seed expires in **120 s** by default. |
| `version`   | `str`         | Semver of the contract on this side. |

## 3. Pairing payload (the QR code)

A QR code carries one **bech32-style** envelope so an operator can
type it in a pinch. Maximum payload size: **256 bytes** before
encoding. The envelope is **plaintext** — its only job is to bootstrap
a one-shot ephemeral key exchange. The actual pairing secret never
leaves the LAN unless `meeet.world` relays it (see § 4 fallback).

### 3.1 Envelope shape

```jsonc
{
  "v": "1",                       // pairing payload version (separate from meeet contract)
  "host_id": "a1b2c3d4e5f60718",
  "host_kind": "desktop_macos",
  "pair_id":  "9988aa77ccd00ff1",
  "expires_at": 1745798400,
  "lan_url": "http://192.168.1.42:8765",
  "relay_url": "https://meeet.world/pair/9988aa77ccd00ff1",
  "fingerprint": "QXr7-8mB9-nJ2L",   // human-readable host fingerprint
  "epk": "base64(xchacha20-x25519-publickey)"
}
```

Notes:

- `lan_url` is preferred; the client tries it first (sub-100 ms).
- `relay_url` is the fallback when LAN is unreachable; it points at a
  short-lived endpoint on `meeet.world` that **never sees plaintext**
  — same envelope-encryption rules as § 4.
- `fingerprint` is rendered in two places (host UI, client UI) so the
  operator can sanity-check the QR code matches the prompted phone
  before accepting.

### 3.2 Operator-typeable fallback

If a camera isn't available, the operator can paste a **24-char**
bech32 string (`tars1…`) carrying the same envelope, encoded with the
existing meeet contract's bech32 helpers (when they land).

## 4. Encrypted sync envelope (`meeet` contract 1.1.0 deltas)

After pairing, every device emits **already-encrypted** blobs into the
meeet store. The `meeet` contract gains exactly two new optional
fields on each event row; legacy 1.0.0 consumers ignore them safely.

```jsonc
{
  "kind": "chat.message.completed",
  "trace_id": "...",
  "payload": "<EXISTING JSON>",
  "ciphertext": "base64(XChaCha20-Poly1305 sealed payload)",
  "envelope": {
    "scheme": "xchacha20-poly1305-x25519-v1",
    "nonce":   "base64(24 bytes)",
    "epk":     "base64(ephemeral X25519 public key)",
    "recipient_keys": [
      { "device_id": "a1b2…", "wrapped_key": "base64(...)" },
      { "device_id": "9988…", "wrapped_key": "base64(...)" }
    ]
  }
}
```

Rules:

1. When `ciphertext` is present, `payload` MUST also be present and
   equal `null` or `{}` — the legacy field is a placeholder for
   compatibility with 1.0.0 consumers.
2. The host produces one ciphertext per event and wraps the symmetric
   key for each currently paired device. Revocation = stop wrapping
   for that device's id; old ciphertexts remain unreadable to it
   without a re-key event.
3. **`meeet.world`** stores the ciphertext + envelope **opaquely** —
   it never sees `payload` plaintext. Replay flow on the device
   decrypts before the existing local cost ledger / search indexes
   ingest it.

## 5. Key namespaces (frozen)

| Namespace | Purpose | Storage |
|-----------|---------|---------|
| `tars/master` | Master keyring (host only). 32-byte X25519 long-term key. | macOS Keychain (service `tars`, account `master`); DPAPI on Windows. |
| `tars/device/<device_id>` | Per-device public key (host knows all of them). | Same store. |
| `tars/sync/epoch` | Monotonic counter for re-keys after revocation. | Same store. |
| **iOS** Secure Enclave: `world.meeet.tars.<device_id>` | Sealed device key. | Per-device. |
| **Android** Keystore: `tars_<device_id>` | Same; uses StrongBox when available. | Per-device. |

## 6. Pairing handshake (LAN-preferred)

```
HOST                                  CLIENT
 │ 1. operator → "Pair phone"          │
 │ 2. mint pair_id, ephemeral X25519   │
 │ 3. render QR (envelope above)       │
 │                                     │
 │            ←────── 4. scan QR ──── │
 │                                     │
 │                                     │ 5. POST /api/pairing/begin
 │                                     │    { pair_id, client_epk, kind }
 │ 6. derive shared secret             │
 │ 7. log pair.attempted event         │
 │ 8. respond { accept_token }         │
 │            ─────── 9. accept ─────→ │
 │                                     │
 │ 10. operator confirms fingerprint   │
 │     (UI: same string both sides)    │
 │                                     │
 │ 11. wrap a fresh sync key for       │
 │     CLIENT.device_id                │
 │ 12. emit meeet event "pair.linked"  │
 │     (envelope-encrypted; § 4)       │
```

If LAN fails, steps 5+ run against `https://meeet.world/pair/...`
which carries the **same** envelope unchanged.

## 7. Endpoints (planned, FastAPI)

```
POST /api/pairing/begin            { pair_id, client_epk, kind } → { accept_token, host_fingerprint }
POST /api/pairing/accept/{token}   {} (operator-confirmed UI)     → 204
GET  /api/pairing/status           ?pair_id=…                     → { state: pending|linked|expired|rejected }
POST /api/pairing/revoke           { device_id }                  → 204
GET  /api/pairing/devices                                         → list of paired devices + last-seen ts
```

All routes are gated by the existing **policy gate** (`destructive: true`
on `revoke`). Every state transition emits `pair.<state>` events into
the meeet store; replay on a paired device gives them the same audit
trail that already exists for tool-calls and policy actions.

## 8. Cryptographic primitives

- Long-term identity: **X25519** (32 bytes).
- AEAD: **XChaCha20-Poly1305** (libsodium `crypto_aead_xchacha20poly1305_ietf`).
- KDF: **HKDF-SHA-256** with a 16-byte salt per envelope.
- QR transport: **bech32m** with HRP `tars1`.

Implementation will use `pynacl` (Python) on the host and platform
primitives on mobile (CryptoKit on iOS, Tink/Conscrypt on Android) —
all interop tested against `pynacl` test vectors before L5 declares
green.

## 9. Failure / recovery

| Failure | Recovery |
|---------|----------|
| QR expired (>120 s) | Operator regenerates; old `pair_id` rejected. |
| LAN unreachable | Fall back to `relay_url` on `meeet.world`. |
| Phone lost | Operator runs `revoke device_id` from the host; sync key epoch increments; remaining devices re-key. |
| Host re-installed | Master keyring is restored from macOS Keychain (it never leaves the device). If the host machine is gone, the operator pairs from a new host using the **recovery seed** (24-word BIP-39, generated on first install, displayed exactly once). |

## 10. Out of scope for L5 v1

- Web client. Browsers cannot hold long-term keys safely; a future
  PWA is conditional on Passkeys + `webauthn` re-auth flow.
- Multi-host topology. v1 has **exactly one** host per master key.
- Federation between distinct masters. v1 is single-operator.

## 11. Acceptance criteria for L5 v1

A Phase L5 PR is "done" when:

1. The five `/api/pairing/*` endpoints exist with their wire shapes
   pinned by `tests/test_pairing_contract.py` (≥ 10 tests).
2. The meeet contract bumps to **1.1.0** with the two new optional
   fields, and `tests/test_meeet_contract.py` covers both 1.0.0 and
   1.1.0 events round-tripping.
3. The host's chat orchestrator + cost ledger + search indexes
   transparently encrypt/decrypt without behavioural change for
   solo-host operators (i.e. the legacy single-device flow stays
   identical).
4. A working pairing demo between the desktop shell (Phase L9) and a
   throwaway curl client.
5. Documentation: this file gets the `DRAFT` removed; a follow-up
   `MEEET_SYNC_ENVELOPE.md` documents the cryptographic envelope
   independently of pairing.

## 12. Open questions (to lock before code)

- Re-key cadence after revocation: per-event or per-day epoch? Lean
  toward **per-revocation** — cheap because the host already wraps
  per-device.
- Do we lift `recipient_keys` from each event into a thread-level
  envelope to save bandwidth? Probably yes for chat messages
  (one-key-per-thread) — defer until we benchmark.
- Should `pair.accepted` carry a screenshot/image of the operator's
  acceptance for audit? **No** — leak risk too high; rely on the
  policy-gate confirmation token already shipped.

