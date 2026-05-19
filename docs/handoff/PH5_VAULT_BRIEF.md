# PH5 — Encrypted Vault (v10.2 gate for "real data")

**Audience:** implementer (Cursor or Claude lane), 1 dev, ~3 weeks.
**Wave tag:** `W310-q`. **Brief file:** `docs/handoff/PH5_VAULT_BRIEF.md`.
**Master plan ref:** `docs/PRODUCT_MASTER_PLAN.md §3.4`.
**IDEAS ref:** `docs/IDEAS.md #16` ("Encrypted vault … Required before MLM /
business adapters touch real data").
**Coupling:** v10.2 release gate. Blocks pack-level adapters
(HubSpot, OAuth, wallet) from touching real customer data. Lands AFTER
`v10.0.0` GA + the Phase 3 keyring brief (PR #195).

---

## §1. Motivation — what's actually missing

A first-time reader of `IDEAS.md #16` might assume "vault" is greenfield.
**It is not.** The crypto envelope, AEAD, and host-identity vault all
already ship in `v10.0.0-rc.1`. The gap is **scope, unlock UX, and
at-rest DB encryption** — not the primitive.

### 1.1 What already exists (do not rebuild)

| Component                              | File                                       | Status        |
| -------------------------------------- | ------------------------------------------ | ------------- |
| XChaCha20-Poly1305 AEAD wrapper        | `backend/core/vault/file_vault.py`         | ✅ shipped    |
| Host X25519 identity, encrypted at rest| `backend/core/vault/file_vault.py`         | ✅ shipped    |
| macOS Keychain CLI passthrough         | `backend/core/vault/keychain.py`           | ✅ shipped    |
| File permission hardening (0600)       | `file_vault.py::_check_permissions`        | ✅ shipped    |
| BIP-39 recovery for host identity      | `backend/core/crypto/recovery.py`          | ✅ shipped    |
| Read-only status endpoint              | `web_extras/routers/vault.py`              | ✅ shipped    |
| PBKDF2-SHA512 KDF (200k iterations)    | `file_vault.py::KDF_ITERATIONS`            | ✅ shipped    |

### 1.2 What is missing (this brief)

1. **Master passphrase**: today the AEAD is keyed off an *empty string*
   when the operator hasn't set one (`file_vault.py` line 7 calls this
   honest "dev-mode keyring"). Real data MUST require a real passphrase.
2. **Adapter migration**: HubSpot / OAuth / wallet keys still resolve via
   `keychain.py::KNOWN_KEYS` — i.e. plaintext when the macOS keychain is
   unlocked (which it is, all day, for any process the operator's running).
3. **Unlock UX**: no cockpit prompt. No session cache. No auto-relock on
   idle. No "vault is locked" state for adapters to check.
4. **Awareness DB at rest**: `~/.tars/meeet.sqlite` is plaintext SQLite.
   Anyone with shell access reads CRM history, message content, traces.
5. **Recovery sweep**: BIP-39 recovers host identity only. The vault
   passphrase + adapter secrets must re-derive from the same mnemonic.
6. **Cross-platform parity**: Windows / Linux paths need the same envelope
   (the host-identity vault already works there; adapter secrets do not).

---

## §2. Goals

- **G1.** Vault has a real master passphrase, KDF'd to a 32-byte AEAD key.
  Empty-passphrase mode preserved behind a `TARS_VAULT_DEV_MODE=1` env
  flag for CI / e2e tests only; explicit warning in `boot.py` if active.
- **G2.** Every adapter secret in `KNOWN_KEYS` (CRM keys, OAuth tokens,
  wallet keys, API keys) reads through `VaultGate.get(key)`, which
  raises `VaultLockedError` if vault is locked.
- **G3.** Cockpit shows vault status + unlock dialog at startup (after
  pairing); unlock is session-cached in process memory; auto-relock after
  configurable idle (default 30 min).
- **G4.** `~/.tars/meeet.sqlite` encrypted at rest via SQLCipher
  (preferred — single dependency, transparent SQL).
- **G5.** BIP-39 recovery mnemonic re-derives the vault passphrase
  alongside the host identity (single seed → both).
- **G6.** Migration is one-shot, auditable, and reversible during the
  v10.1 → v10.2 upgrade. Migration script writes a `vault_migrated_at`
  marker; downgrade path documented but not implemented (rollback = restore
  from pre-migration snapshot).

**Non-goals (out of scope for this brief):**
- Hardware-backed key storage (Secure Enclave, TPM). Defer to v11+.
- Multi-user / multi-vault. Single operator, single vault.
- Server-side vault sync. Vault stays local-first.
- Vault key rotation UI (re-encrypt all secrets under new passphrase) —
  defer to v10.3; for v10.2 we ship rotation only via the recovery flow
  (mnemonic → new passphrase → re-encrypt).

---

## §3. Target architecture

```
                ┌──────────────────────────────────────────┐
                │  Cockpit (apps/cockpit/src/pages/        │
                │   cockpit-entry.ts → vault-unlock-modal) │
                └────────────┬─────────────────────────────┘
                             │
                             │ POST /api/vault/unlock {passphrase}
                             │ POST /api/vault/lock
                             │ GET  /api/vault/status    (extended)
                             ▼
            ┌──────────────────────────────────────────────┐
            │  web_extras/routers/vault.py                 │
            │  - unlock/lock endpoints                     │
            │  - exposes vault_state to all routers        │
            └────────────┬─────────────────────────────────┘
                         │
                         │ derive_key(passphrase) + load AEAD blob
                         ▼
       ┌──────────────────────────────────────────────────┐
       │  backend/core/vault/master.py                    │
       │  - MasterVault (singleton, in-process)           │
       │  - holds 32-byte AEAD key in memory while unlocked│
       │  - auto-zeros on lock / idle / process exit      │
       └────────┬───────────────────────────────────┬─────┘
                │                                   │
                │ get(key) / set(key, val)          │ migrate_keychain()
                ▼                                   ▼
   ┌─────────────────────────┐         ┌────────────────────────┐
   │  vault_blob.json        │         │  one-shot migration    │
   │  (XChaCha20-Poly1305    │         │  - reads each          │
   │  encrypted dict of      │         │    KNOWN_KEY from      │
   │  KNOWN_KEY → secret)    │         │    OS keystore         │
   │  ~/.tars/vault.json     │         │  - writes to vault     │
   │  perms 0600             │         │  - flags as migrated   │
   └─────────────────────────┘         └────────────────────────┘
                ▲
                │ called by HubSpotAdapter, OAuthAdapter, wallet, etc.
                │   via VaultGate.get("HUBSPOT_API_KEY")
                │
   ┌────────────┴──────────────┐
   │  ~/.tars/meeet.sqlite     │
   │  SQLCipher (PRAGMA key)   │
   │  key = derived from same  │
   │  master passphrase        │
   └───────────────────────────┘
```

**Single passphrase, two derivations.** From passphrase + per-install salt:
- `vault_key`  = HKDF(passphrase, salt, info="tars-vault-v1")    → 32 bytes
- `db_key`     = HKDF(passphrase, salt, info="tars-sqlcipher-v1") → 32 bytes

Separate `info` strings → cryptographic domain separation. One typo'd
passphrase fails both checks consistently (no half-unlocked state).

---

## §4. Implementation steps (6 mechanical, independently testable)

### Step 1 — `MasterVault` singleton + AEAD blob format

**File:** `backend/core/vault/master.py` (NEW, ~280 LoC).

**Wire shape** (`~/.tars/vault.json`, 0600):

```jsonc
{
  "version": 1,
  "salt": "base64(16)",
  "kdf": { "algo": "pbkdf2-sha512", "iterations": 200000 },
  "secret": {
    "scheme": "xchacha20-poly1305-v1",
    "nonce": "base64(24)",
    "ciphertext": "base64"  // encrypts JSON dict of KNOWN_KEY → value
  },
  "migrated_at": 1779000000.0,
  "checksum": "sha256"   // over ciphertext, for tamper detection
}
```

**Public surface:**

```python
class MasterVault:
    def status(self) -> dict: ...          # {state: "locked"|"unlocked"|"missing", ...}
    def unlock(self, passphrase: str) -> None: ...    # raises VaultBadPassphraseError
    def lock(self) -> None: ...            # zeros key
    def get(self, key: str) -> str: ...    # raises VaultLockedError
    def set(self, key: str, value: str) -> None: ...  # immediate write + atomic rename
    def list_keys(self) -> list[str]: ...
    def touch(self) -> None: ...           # reset idle timer
    def is_idle_timeout(self) -> bool: ...
```

Reuse `nacl.bindings.crypto_aead_xchacha20poly1305_ietf_*` from
`file_vault.py`. Same KDF constants.

**Tests** (`tests/test_vault_master.py`, ~18 cases):
unlock/lock round-trip, wrong passphrase raises, idle timeout, atomic
write under power loss simulation, tamper detection via checksum.

### Step 2 — `VaultGate` adapter shim

**File:** `backend/core/vault/gate.py` (NEW, ~80 LoC).

Thin wrapper providing two affordances all adapters need:

```python
class VaultGate:
    @staticmethod
    def get(key: str, *, allow_env_fallback: bool = False) -> str:
        """
        Returns secret. Order:
        1. MasterVault if unlocked → return
        2. If allow_env_fallback and TARS_VAULT_DEV_MODE → env var
        3. Raise VaultLockedError (callers must surface to user)
        """
```

Migrate `keychain.py::get` callers in:
- `backend/packs/business/hubspot/*` → `VaultGate.get("HUBSPOT_API_KEY")`
- `backend/packs/wallet/*` (when shipped) → wallet keys
- `web_extras/routers/oauth*.py` → OAuth tokens
- All `os.environ[...]` calls that resolve secrets (audit with
  `rg -n "os\.environ\[.\".*KEY\"" backend/` — should be ~30 hits)

**Tests** (`tests/test_vault_gate.py`, ~6 cases): locked raises, unlocked
returns, env fallback works only in dev mode.

### Step 3 — HTTP unlock surface

**File:** `web_extras/routers/vault.py` (EXTEND existing, +120 LoC).

New endpoints:

```python
POST /api/vault/unlock     {passphrase: str}     → 200 / 401
POST /api/vault/lock                              → 200
POST /api/vault/rotate     {old: str, new: str}  → 200 (re-encrypts all secrets)
GET  /api/vault/status     (EXTEND existing)      → {state, idle_until, key_count}
GET  /api/vault/keys                              → {keys: [...]} (just names, never values)
```

`/api/vault/status` extension surface:

```json
{
  "ok": true,
  "state": "locked",       // "locked" | "unlocked" | "missing"
  "idle_until": 1779001800, // epoch when auto-relock fires; null if locked
  "key_count": 7,
  "known_keys": [...],     // list of expected KNOWN_KEYS for UI to render slots
  "migrated_at": 1779000000.0
}
```

**Security gates on these endpoints:**
- Localhost-only by default (refuse if `X-Forwarded-For` present unless
  `TARS_VAULT_ALLOW_REMOTE=1`).
- Per-IP rate limit: 5 unlock attempts / 5 min, exponential lockout after.
- All attempts logged via `meeet.emit("vault.unlock.attempt", {ok})`
  (only the boolean, never the passphrase — even hashed).

**Tests** (`tests/test_vault_router.py`, ~12 cases): unlock 200,
wrong passphrase 401, rate limit 429, remote refused 403, lock idempotent,
status reflects state.

### Step 4 — One-shot keychain migration

**File:** `backend/core/vault/migrate.py` (NEW, ~140 LoC) +
`scripts/MIGRATE-VAULT.command` (NEW, ~30 LoC).

**Flow:**
1. Operator runs `bash scripts/MIGRATE-VAULT.command`.
2. Script prompts: "Set vault master passphrase (12+ chars, won't echo)".
3. Script prompts: "Confirm passphrase".
4. Calls `vault.master.create(passphrase)`. Writes vault.json.
5. For each key in `keychain.KNOWN_KEYS`:
   - Read from keychain (if present).
   - Write to vault.
   - Delete from keychain (with `--force` confirmation prompt).
6. Sets `migrated_at` marker.
7. Prints recovery mnemonic (BIP-39 re-derive from vault key, prompts
   operator to write it down, asks to confirm 3 random words).

**Rollback**: documented in `docs/VAULT_MIGRATION.md` — restore from
`~/.tars/keychain-backup-pre-vault/` (which migration creates first).

**Tests** (`tests/test_vault_migration.py`, ~10 cases): all keys move,
backup created, partial failure rolls back cleanly, idempotent (running
twice is a no-op).

### Step 5 — SQLCipher for `~/.tars/meeet.sqlite`

**Dependency:** `pysqlcipher3 = "^1.2"` (in `pyproject.toml`).

**File:** `backend/core/awareness/store.py` (modify connection factory,
~20 LoC delta). Replace `sqlite3.connect(...)` with `pysqlcipher3.connect(...)`
and `PRAGMA key = '<derived db_key as hex>';` immediately after open.

**Migration** (`scripts/MIGRATE-VAULT.command` extends Step 4):
- If `~/.tars/meeet.sqlite` exists unencrypted, dump → re-encrypt with
  SQLCipher → atomic rename.
- Uses `ATTACH DATABASE 'encrypted.db' AS encrypted KEY '<key>'; SELECT
  sqlcipher_export('encrypted');` pattern.

**CI gotcha**: SQLCipher requires native OpenSSL. Add to
`.github/workflows/python.yml` matrix: `brew install sqlcipher` on macOS,
`apt-get install libsqlcipher-dev` on Linux. Windows: defer to v10.3
(falls back to plaintext SQLite with prominent warning in cockpit
status — document this gap loudly).

**Tests** (`tests/test_awareness_sqlcipher.py`, ~8 cases): roundtrip
read/write under encryption, wrong key denies access, migration
unencrypted → encrypted preserves all rows.

### Step 6 — Cockpit unlock UX

**Files:**
- `apps/cockpit/src/components/vault-unlock-modal.ts` (NEW, ~180 LoC)
- `apps/cockpit/src/components/vault-status-pill.ts` (NEW, ~80 LoC)
- `apps/cockpit/src/lib/vault-client.ts` (NEW, ~120 LoC)
- `apps/cockpit/src/pages/cockpit-entry.ts` (extend, ~40 LoC delta)

**UX:**
- On boot, after pairing handshake, poll `/api/vault/status`.
- If `state === "locked"` → show modal blocking all other UI.
- Passphrase input (`type="password"`, autocomplete=current-password,
  no autofocus until modal mount completes — prevents browser autofill
  race).
- Show "Show passphrase" eye toggle (3s timeout, auto-hide).
- On submit → POST `/api/vault/unlock`. Show inline error on 401, with
  attempt counter and lockout countdown on 429.
- Once unlocked: dismiss modal, show pill in top-right with `🔒 in 28:14`
  countdown. Click pill → "Lock now" / "Extend session" menu.
- Auto-relock at idle: client poll every 30s; if status returns
  `state === "locked"` → re-show modal.

**Accessibility**:
- Modal traps focus (use `inert` on background).
- Esc closes modal only if state ≠ locked (otherwise blocks).
- Error announcements via `aria-live="polite"`.
- Lockout countdown updates via `aria-live` every 5s, not 1s.

**Tests** (`tests/playwright/vault.spec.ts`, ~6 scenarios): unlock happy
path, wrong passphrase + error display, rate limit lockout countdown,
relock-on-idle, lock-now menu, recovery link (deep-links to recovery flow
from Phase 3 PR #196 brief).

---

## §5. Files touched (summary)

| Area              | Files                                       | LoC est |
| ----------------- | ------------------------------------------- | ------- |
| Core vault        | `backend/core/vault/master.py` (NEW)        | +280    |
|                   | `backend/core/vault/gate.py` (NEW)          | +80     |
|                   | `backend/core/vault/migrate.py` (NEW)       | +140    |
| Adapter migration | grep-and-replace across ~30 callers         | ±60     |
| HTTP surface      | `web_extras/routers/vault.py` (extend)      | +120    |
| Awareness         | `backend/core/awareness/store.py` (modify)  | +20     |
| Cockpit           | `apps/cockpit/src/components/vault-*.ts`    | +260    |
|                   | `apps/cockpit/src/lib/vault-client.ts`      | +120    |
|                   | `apps/cockpit/src/pages/cockpit-entry.ts`   | +40     |
| Scripts           | `scripts/MIGRATE-VAULT.command` (NEW)       | +30     |
| Docs              | `docs/VAULT_MIGRATION.md` (NEW)             | +200    |
|                   | Update `IDEAS.md #16` → ✅ shipped marker   | ±5      |
| Tests             | `tests/test_vault_master.py` (NEW)          | +320    |
|                   | `tests/test_vault_gate.py` (NEW)            | +100    |
|                   | `tests/test_vault_router.py` (NEW)          | +220    |
|                   | `tests/test_vault_migration.py` (NEW)       | +180    |
|                   | `tests/test_awareness_sqlcipher.py` (NEW)   | +140    |
|                   | `tests/playwright/vault.spec.ts` (NEW)      | +180    |
| CI                | `.github/workflows/python.yml` (extend)     | +15     |
| Dependencies      | `pyproject.toml` (`pysqlcipher3`)           | +1      |
| **Total**         |                                             | **≈ 2.5k LoC** |

---

## §6. Coupling to other waves

| Brief / PR                     | Relationship                                                 |
| ------------------------------ | ------------------------------------------------------------ |
| Phase 3 keyring (PR #195)      | **Hard dep.** Cross-platform OS keystore lands first → vault unlock state caches there as a fallback for headless mode (e.g. backend daemon without cockpit). |
| Phase 3 pairing UX (PR #196)   | Recovery flow integration: vault recovery mnemonic share UI re-uses pairing modal styles. |
| Phase 5 policy UI (this trio)  | **Sibling.** Vault status pill sits next to policy-pending pill in top-right. |
| Phase 5 telemetry (this trio)  | **Sibling.** Telemetry counters MUST refuse to ship if vault locked (no opt-in defaults to leak). |
| Phase 1 W309 step 2            | No direct coupling. |
| Phase 4 trio (PRs #199-#201)   | No direct coupling. Vault ships post-GA. |

---

## §7. Test plan

| Category   | Coverage                                                         |
| ---------- | ---------------------------------------------------------------- |
| Unit       | AEAD roundtrip, KDF determinism, atomic writes, tamper detection |
| Integration| All KNOWN_KEYS routable via VaultGate; locked state blocks all   |
| Security   | Rate limit, lockout, no remote, no log leakage of passphrase     |
| Migration  | Idempotent, reversible, partial failure rollback                 |
| Soak       | 24h unlocked → no memory leak; key zero'd on lock (verify mlock) |
| Recovery   | BIP-39 mnemonic → unlock works, single seed → both derivations   |
| Cockpit e2e| Unlock happy path, wrong pwd, rate limit, idle relock            |
| CI parity  | SQLCipher native deps install on macOS / Linux in workflow       |

**Soak protocol**: spin up backend with vault unlocked, drive 24h of
synthetic traffic (load test harness), assert via `tracemalloc` that
the master key bytes stay at a single allocation (no leaked copies in
heap dumps). Run `pmap | grep heap` deltas hourly.

---

## §8. Open questions for operator

1. **Idle relock default**: 30 min suggested. Acceptable? (Some
   operators may want 8h or "never until restart".)
2. **Rotation UI scope for v10.2**: implement passphrase rotation now
   or defer to v10.3? (Recommendation: defer — recovery flow covers the
   "lost passphrase" case.)
3. **Windows SQLCipher**: ship in v10.2 (adds a Visual Studio Build Tools
   dependency to Windows install) or fall back to plaintext SQLite with
   warning? (Recommendation: fall back for v10.2, ship in v10.3.)
4. **Headless mode**: backend daemon without cockpit (e.g. ssh session,
   CI). Allow vault unlock via `TARS_VAULT_PASSPHRASE_FILE=/path/to/file`?
   (Recommendation: yes, gated by `TARS_HEADLESS=1` env flag — explicit
   opt-in only.)
5. **Telemetry coupling**: should `meeet.emit` queue events to disk while
   vault is locked (and flush on unlock), or drop them? (Recommendation:
   queue to a separate plaintext "metadata-only" SQLite buffer keyed on
   timestamps + event names — no payloads. Flush on unlock.)

---

## §9. Effort summary

| Step  | LoC delta (incl tests) | Time   |
| ----- | ---------------------- | ------ |
| 1     | +600                   | 3-4 d  |
| 2     | +180                   | 1-2 d  |
| 3     | +340                   | 2 d    |
| 4     | +320                   | 2 d    |
| 5     | +160                   | 2 d    |
| 6     | +440                   | 3 d    |
| **Total** | **≈ 2k LoC + docs** | **~3 weeks** |

Matches master plan estimate (§3.4 = 2 weeks). The extra week buys
cross-platform SQLCipher CI hardening and the migration script's
rollback rehearsal.

---

## §10. Acceptance criteria for v10.2 ship

- [ ] `MasterVault` ships, all unit + integration tests green.
- [ ] All KNOWN_KEYS route through VaultGate; grep'd zero remaining
  callers of `keychain.get()` outside of the vault module.
- [ ] Cockpit shows unlock modal on locked boot.
- [ ] One-shot migration script tested on a real installation (operator
  reports clean run + restore).
- [ ] SQLCipher confirmed on macOS + Linux; Windows fallback documented.
- [ ] Recovery mnemonic round-trip works (lock → relaunch with passphrase
  forgotten → enter mnemonic → unlock succeeds).
- [ ] `IDEAS.md #16` updated to ✅ shipped.
- [ ] `docs/PRODUCT_MASTER_PLAN.md §3.4` updated to ✅ shipped.
- [ ] Telemetry counter `vault.unlock.attempts` visible in cockpit
  observability surface.

---

## §11. Sources & references

- **Master plan**: `docs/PRODUCT_MASTER_PLAN.md §3.4` (this brief
  implements the bulleted scope verbatim).
- **IDEAS.md #16, #17**: original product framing.
- **Existing AEAD wrapper**: `backend/core/vault/file_vault.py` lines
  53-58 (XChaCha20-Poly1305 from PyNaCl).
- **Existing keychain shim**: `backend/core/vault/keychain.py`
  `KNOWN_KEYS` constant (full enumeration of secrets in scope).
- **Recovery infrastructure**: `backend/core/crypto/recovery.py`
  (BIP-39 mnemonic generation/verification — reuse verbatim).
- **L5 endpoint pattern**: `web_extras/routers/recovery.py` (the
  rate-limit + localhost-only pattern this brief inherits).
- **SQLCipher PRAGMA reference**: https://www.zetetic.net/sqlcipher/sqlcipher-api/

---

*End of brief. PR title: "PH5 — Encrypted vault implementer brief
(v10.2 gate for real data)".*
