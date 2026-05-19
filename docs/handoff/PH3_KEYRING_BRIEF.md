# Phase 3 — Cross-platform persistent host keyring (v10.1)

**Authoring agent:** Cursor agent (Claude Opus 4.7), W310-j (continuation)
**Authoring date:** 2026-05-18
**Implementer:** TBD (next L5-lane Cursor/Claude session)
**Target release:** `v10.1.0` (post-GA security polish)
**Depends on:** v10.0.0 GA tag (no hard dep on Phase 2 briefs — orthogonal lane)
**Phase ID in master plan:** `ph3-keyring` (companion: `ph3-pairing-ux`, separate brief — UI side)

---

## 1. Why this brief exists

`v10.0.0-rc.1` ships **real L5 crypto** (`REAL_CRYPTO_SHIPPED`,
confirmed in W310-a): XChaCha20-Poly1305 + X25519 envelope sealing,
BIP-39 24-word recovery seed, host identity derivation. The crypto
itself is sound — but **persistent storage for the resulting keys
is currently macOS-only**:

| Platform | Long-term host identity (X25519) | API keys (OpenAI, ElevenLabs, ...) |
| -------- | -------------------------------- | ----------------------------------- |
| macOS | ✓ `FileKeyringVault` (XChaCha20-Poly1305 file) OR Keychain via `_to_keychain` write-back | ✓ Keychain via `security` CLI (`backend/core/vault/keychain.py`) |
| Linux | ✓ file vault, dev-mode (empty passphrase default) | ✗ **env var only** — lost on reboot |
| Windows | ✓ file vault, dev-mode (empty passphrase default) | ✗ **env var only** — lost on reboot |

Phase 3 keyring closes this gap by adding two new OS-native backends
behind the same `KeyringVault` abstract base that `FileKeyringVault`
already implements:

- **Windows:** `wincred` via the `keyring` Python package (or `pywin32`
  direct), backed by Windows Credential Manager.
- **Linux:** `Secret Service` API via `secretstorage` (D-Bus interface
  to GNOME Keyring / KWallet), backed by the user's session keyring.

Plus a small factory that picks the right backend per platform with
explicit fallback to `FileKeyringVault` when the OS keyring isn't
reachable (e.g., headless Linux, missing D-Bus, locked KDE Wallet).

Both new backends store **both** the host identity (currently
file-vault-only on non-macOS) AND the API-key secrets (currently
env-only on non-macOS) — closing the persistence gap for both.

---

## 2. Goals / non-goals

### Goals

| ID | Goal | Acceptance |
| -- | ---- | ---------- |
| G1 | Host X25519 identity persists across reboot on all 3 platforms with OS-native protection | Fresh install on each of macOS / Windows / Linux GNOME → reboot → host identity loads from OS keyring, no manual env vars |
| G2 | API key secrets persist across reboot on all 3 platforms | Set OPENAI_API_KEY via cockpit settings UI → reboot → key is still resolvable via `get_secret` |
| G3 | Graceful fallback to file vault when OS keyring is missing | Headless Linux without D-Bus → file vault used, log line emitted explaining fallback |
| G4 | Single resolution chain `env → OS keyring → file vault → missing` for both vaults | Test: each layer wins over deeper layers; bypassing env still resolves from OS keyring |
| G5 | Zero new third-party deps if avoidable | Use stdlib + the existing `keyring` ecosystem only; do not pull in `pywin32` if `keyring.backends.Windows.WinVaultKeyring` works |

### Non-goals

- **Encrypted vault** (libsodium + Keychain master-key wrap of arbitrary blobs). That's Phase 5 (`ph5-vault`, v10.2) — different scope, gates "real data" workloads.
- **Cockpit pairing/recovery UX.** Companion brief `ph3-pairing-ux` (separate). This brief is backend-only.
- **Mobile keyring.** Phase 3 mobile slot (`ph3-mobile-pairing`, v10.2) covers iOS Keychain / Android Keystore in the companion app — different module path.
- **`pair_id` TTL on relay.** Phase 3 brother-coord slot (`ph3-pair-ttl`, v10.2) lives on `meeet.world` side — out of scope here.
- **Operator-supplied passphrase on file vault.** File vault's `_derive_vault_key` already supports passphrases; this brief doesn't change that — operators who want a passphrase still get one.

---

## 3. Current state baseline

### Backend (`v10.0.0-rc.1`)

`backend/core/vault/` ships two related modules:

1. **`keychain.py`** — API-key resolver. `get_secret`, `set_secret`, `delete_secret`, `list_known`, `status_for_keys`. Resolution: `env → macOS Keychain → None`. **Non-Darwin hosts: `_from_keychain` returns `None`; only env path runs.**
2. **`file_vault.py`** — Host identity vault. `FileKeyringVault.load/save/rotate/clear`. Encrypts the X25519 secret half with XChaCha20-Poly1305 (PBKDF2-SHA512 KDF, 200K iterations). **Cross-platform; uses the same code path on all 3 OSes.**

`backend/core/vault/__init__.py` already re-exports both surfaces
behind a single import path — clean place to plug in the new
backends without churning every call site.

`KeyringVault` (`file_vault.py:128`) is **already abstract** with
the right methods: `load`, `save`, `rotate`, `exists`, `clear`.
New backends just implement that ABC.

### Tests (preserve)

- `tests/test_vault_file.py` — file vault round-trip + corruption + permissions
- `tests/test_vault_router.py` — HTTP endpoints for vault operations
- `tests/test_vault_write_back.py` — Keychain write-back path
- `tests/test_pairing_vault_integration.py` — integration with L5 pairing flow

These must keep passing. New backends earn new test files.

---

## 4. Target architecture

```
backend/core/vault/
├── __init__.py                  # re-exports + new get_default_vault()
├── keychain.py                  # macOS API-key resolver (existing, unchanged)
├── file_vault.py                # FileKeyringVault (existing, unchanged)
├── wincred_vault.py     NEW     # Windows Credential Manager backend
├── secretstorage_vault.py NEW   # Linux Secret Service backend
├── factory.py           NEW     # picks the right backend, logs fallback
└── api_keyring.py       NEW     # cross-platform extension of keychain.py
                                 # (env → wincred/secretstorage → None on
                                 # non-macOS instead of env → None)
```

### New `factory.py`

```python
def get_default_vault(
    *, identity_path: Path | None = None,
    prefer_file: bool = False,
) -> KeyringVault:
    """Return the OS-native vault for this platform, falling back to
    FileKeyringVault when the OS keyring isn't reachable.

    `prefer_file=True` short-circuits to file vault — used in tests
    and headless CI runs where the OS keyring would prompt.
    """
    if prefer_file:
        return FileKeyringVault(identity_path)

    if sys.platform == "darwin":
        # macOS file vault already gets Keychain write-back via the
        # existing _to_keychain helper in keychain.py; FileKeyringVault
        # stays canonical here. Future work could swap to a pure
        # KeychainKeyringVault, but the file path is battle-tested.
        return FileKeyringVault(identity_path)

    if sys.platform == "win32":
        try:
            from .wincred_vault import WincredKeyringVault
            return WincredKeyringVault()
        except Exception as exc:
            log.warning("wincred unavailable: %s; falling back to file vault", exc)
            return FileKeyringVault(identity_path)

    if sys.platform.startswith("linux"):
        try:
            from .secretstorage_vault import SecretServiceKeyringVault
            return SecretServiceKeyringVault()
        except Exception as exc:
            log.warning("secretservice unavailable: %s; falling back to file vault", exc)
            return FileKeyringVault(identity_path)

    return FileKeyringVault(identity_path)
```

### New `api_keyring.py` (cross-platform extension of keychain.py)

Adds analogues of `_from_keychain` / `_to_keychain` / `_delete_keychain`
for wincred and secretstorage, then changes `get_secret` /
`set_secret` / `delete_secret` to chain through whichever backend the
platform provides. macOS behaviour unchanged.

**Do NOT modify `keychain.py` directly** — keep it as the macOS
canonical implementation. `api_keyring.py` imports from it and the
new backends, and re-exports a single `get_secret` etc. that the rest
of the codebase already calls (via `from backend.core.vault import
get_secret`).

`vault/__init__.py` then re-exports from `api_keyring` instead of
`keychain` directly. **One-line change** at the import site.

---

## 5. API contracts

The public API surface **does not change**. All new code lives behind
the existing facade:

```python
from backend.core.vault import (
    get_secret, set_secret, delete_secret, list_known, status_for_keys,
    KeyringVault, FileKeyringVault, StoredHostIdentity,
    # ↓ NEW exports
    get_default_vault,
    WincredKeyringVault,      # importable for tests / explicit choice
    SecretServiceKeyringVault,
)
```

### Resolution chain (new)

`get_secret(key)` chain by platform:

- **macOS:** `env → macOS Keychain → None` (unchanged)
- **Windows:** `env → Windows Credential Manager → None` (NEW; was `env → None`)
- **Linux:** `env → Secret Service (GNOME Keyring / KWallet) → None` (NEW; was `env → None`)

`set_secret(key, value)` returns `SecretRef(source="env" | "keychain" | "wincred" | "secretservice")`.

### Host identity vault selection (new)

`get_default_vault()` returns a `KeyringVault` instance:

- **macOS:** `FileKeyringVault` (file written to `~/.tars/host_identity.json`, encrypted with XChaCha20-Poly1305, optionally write-back to Keychain via existing `_to_keychain` helper). **Unchanged.**
- **Windows:** `WincredKeyringVault` (host identity stored as a single Credential Manager entry, `tars/host_identity`, value = JSON blob from `StoredHostIdentity.to_dict()`).
- **Linux:** `SecretServiceKeyringVault` (host identity stored as a single Secret Service item, schema `org.tars.HostIdentity`, attribute `version=1`).
- **Fallback (any OS, if keyring unreachable):** `FileKeyringVault` with `log.warning(...)` line so operators can grep for "falling back to file vault".

---

## 6. Implementation steps (mechanical)

Each step is independently mergeable. Land in order.

### Step 1 — `WincredKeyringVault` backend

**Branch:** `cursor/ph3-keyring-step1-wincred`
**Files:**
- `backend/core/vault/wincred_vault.py` (NEW):
  ```python
  class WincredKeyringVault(KeyringVault):
      SERVICE = "tars"
      ACCOUNT = "host_identity"

      def __init__(self) -> None:
          # Probe `keyring` lib at construction; raise if missing so
          # factory.py can downgrade cleanly.
          import keyring  # noqa
          self._keyring = keyring

      def load(self) -> StoredHostIdentity | None: ...
      def save(self, identity: StoredHostIdentity, *, passphrase: str = "") -> None: ...
      def rotate(self, ...) -> StoredHostIdentity: ...
      def exists(self) -> bool: ...
      def clear(self) -> None: ...
  ```
- `requirements.txt` — add `keyring>=24.3.0,<26.0.0` as a **conditional dep** (`keyring; sys_platform == "win32"` if pip supports markers; else hard-require).
- `backend/core/vault/__init__.py` — re-export.

**Tests:**
- `tests/test_vault_wincred.py` (NEW, 8 cases): construction (skip on non-Windows via `pytest.mark.skipif`), save/load round-trip, idempotent save, missing-then-load returns None, clear+exists, rotate updates rotated_at, error path (`keyring` raises on access).

**Acceptance:**
- All 8 tests pass on Windows CI runner.
- Non-Windows runners skip cleanly with `pytest.mark.skipif(sys.platform != "win32")`.

---

### Step 2 — `SecretServiceKeyringVault` backend

**Branch:** `cursor/ph3-keyring-step2-secretservice`
**Files:**
- `backend/core/vault/secretstorage_vault.py` (NEW):
  ```python
  class SecretServiceKeyringVault(KeyringVault):
      SCHEMA = "org.tars.HostIdentity"
      LABEL = "TARS host identity"

      def __init__(self) -> None:
          import secretstorage  # noqa
          self._bus = secretstorage.dbus_init()
          # Open default collection; fail if locked.
          self._collection = secretstorage.get_default_collection(self._bus)
          if self._collection.is_locked():
              raise RuntimeError("secretservice collection is locked")

      # Same KeyringVault interface as wincred backend.
      ...
  ```
- `requirements.txt` — add `secretstorage>=3.3.3,<4.0.0` as a conditional dep (`secretstorage; sys_platform == "linux"`).
- `backend/core/vault/__init__.py` — re-export.

**Tests:**
- `tests/test_vault_secretservice.py` (NEW, 8 cases). Use the `keyring` library's testing mock or `pytest-mock` to fake the D-Bus interface so tests run without a real Secret Service. `pytest.mark.skipif(not sys.platform.startswith("linux"))` for integration test path.

**Acceptance:**
- 8 unit tests pass on macOS / Linux CI runners (mocked D-Bus).
- 1 integration test passes on Linux CI runner with real GNOME Keyring (mark `@pytest.mark.integration`, opt-in).

---

### Step 3 — `factory.get_default_vault()` + fallback logging

**Branch:** `cursor/ph3-keyring-step3-factory`
**Files:**
- `backend/core/vault/factory.py` (NEW) — implementation per §4.
- `backend/core/vault/__init__.py` — re-export `get_default_vault`.

**Tests:**
- `tests/test_vault_factory.py` (NEW, 6 cases):
  - macOS → `FileKeyringVault`
  - Windows with wincred available → `WincredKeyringVault`
  - Windows without keyring module → `FileKeyringVault` + warning logged
  - Linux with secretservice available → `SecretServiceKeyringVault`
  - Linux without D-Bus → `FileKeyringVault` + warning logged
  - `prefer_file=True` always returns `FileKeyringVault`

**Acceptance:**
- All call sites that construct `FileKeyringVault(...)` directly migrated to `get_default_vault(identity_path=...)`.
- Grep for `FileKeyringVault(` returns only `factory.py` + tests.

---

### Step 4 — `api_keyring.py` cross-platform secret resolver

**Branch:** `cursor/ph3-keyring-step4-api-cross-platform`
**Files:**
- `backend/core/vault/api_keyring.py` (NEW):
  ```python
  # Public surface mirrors keychain.py but dispatches per platform.

  def get_secret(key, *, service=DEFAULT_SERVICE, timeout_s=2.0):
      val = _from_env(key)
      if val is not None: return val

      if sys.platform == "darwin":
          return _from_keychain(key, service=service, timeout_s=timeout_s)
      if sys.platform == "win32":
          return _from_wincred(key, service=service)
      if sys.platform.startswith("linux"):
          return _from_secretservice(key, service=service)
      return None

  # set_secret / delete_secret / list_known follow the same pattern.
  ```
- `backend/core/vault/__init__.py` — change re-exports of `get_secret` etc. from `keychain` to `api_keyring`.
- `backend/core/vault/keychain.py` — **leave untouched** as the macOS canonical implementation. `api_keyring.py` imports `_from_keychain`, `_to_keychain`, `_delete_keychain` from it.

**Tests:**
- `tests/test_api_keyring.py` (NEW, 12 cases):
  - Each platform branch hit independently with `monkeypatch.setattr(sys, "platform", "win32")` style
  - Each backend's success / missing / error path
  - Source attribution correct in `SecretRef`
  - `list_known` returns correct `source` per platform
- `tests/test_vault_router.py` — update fixture if it pins `sys.platform`, otherwise unchanged.

**Acceptance:**
- All existing vault tests pass unchanged on macOS (back-compat).
- Windows runner: `get_secret` resolves wincred entries.
- Linux runner: `get_secret` resolves secretservice entries.

---

### Step 5 — Migration helper + CLI

**Branch:** `cursor/ph3-keyring-step5-migrate`
**Files:**
- `scripts/migrate_vault_to_os_keyring.py` (NEW) — one-shot script for existing operators on Windows/Linux who have a `file_vault` host identity and env-var-backed API keys. Reads file vault + env, writes to OS keyring, then optionally clears file vault. **Idempotent**, dry-run by default.
- Add help text to existing onboarding flow so fresh installs go through the new keyring path by default.

**Tests:**
- `tests/test_migrate_vault.py` (NEW, 6 cases): dry-run mode (no writes), migrate identity-only, migrate secrets-only, migrate both, idempotent re-run, error path (keyring locked).

**Acceptance:**
- Existing Linux operator with file vault + env-only API keys can run `python scripts/migrate_vault_to_os_keyring.py --apply` and have everything in Secret Service after.
- Re-running the script is a no-op.

---

### Step 6 — Cockpit settings UX delta (small)

**Branch:** `cursor/ph3-keyring-step6-cockpit-status`
**Files:**
- `web_extras/routers/vault.py` — add `GET /api/vault/storage_info` returning the active backend per platform:
  ```json
  {
    "host_identity_backend": "wincred" | "secretservice" | "file" | "keychain",
    "api_keys_backend": "wincred" | "secretservice" | "keychain" | "env_only",
    "fallback_reason": null | "no_dbus" | "keyring_module_missing" | "locked",
    "migration_available": false | true
  }
  ```
- `apps/cockpit/src/pages/cockpit-entry.ts` (or wherever settings panel ships post-W309 step 2) — surface a small badge: "Keys stored in: Windows Credential Manager / GNOME Keyring / Keychain / file vault". One-line UI delta.

**Tests:**
- `tests/test_vault_router_storage_info.py` (NEW, 4 cases): macOS / Windows / Linux happy / fallback responses.

**Acceptance:**
- Cockpit shows correct backend per OS.
- Operator can spot at a glance if they're on the insecure file-vault fallback (and the migration script docs are linked from the badge).

---

## 7. Acceptance criteria (Phase 3 keyring done = all of these)

- [ ] Host X25519 identity persists across reboot on macOS, Windows, Linux/GNOME without any manual env vars
- [ ] API keys (OpenAI, ElevenLabs, etc.) persist across reboot on all 3 platforms
- [ ] Headless Linux without D-Bus → file vault fallback with explicit warning log line
- [ ] Existing file-vault operators have a one-command migration to OS keyring
- [ ] Cockpit settings panel surfaces active backend per platform
- [ ] No existing test regression (vault, crypto, pairing tests all green)
- [ ] No new event kinds (purely a storage refactor)

---

## 8. Test plan summary

| Layer | New tests | Modified tests | Coverage |
| ----- | --------- | -------------- | -------- |
| Unit (wincred) | `test_vault_wincred.py` (8) | none | construct / save / load / rotate / clear / errors |
| Unit (secretservice) | `test_vault_secretservice.py` (8) | none | same |
| Unit (factory) | `test_vault_factory.py` (6) | none | per-platform branch + fallback + prefer_file |
| Unit (api_keyring cross-platform) | `test_api_keyring.py` (12) | none | dispatch + source attribution + each backend's get/set/delete |
| Unit (migration) | `test_migrate_vault.py` (6) | none | dry-run + apply + idempotent + error |
| Integration | `test_vault_router_storage_info.py` (4) | none | per-platform endpoint |
| Regression | none | `test_vault_file.py`, `test_vault_router.py`, `test_vault_write_back.py`, `test_pairing_vault_integration.py` | unchanged |

**Total: 44 new tests; 0 modified.**

---

## 9. Rollback strategy

| Step | Rollback |
| ---- | -------- |
| 1 | Revert PR. Windows hosts fall back to file vault. |
| 2 | Revert PR. Linux hosts fall back to file vault. |
| 3 | Revert PR. Callers go back to constructing `FileKeyringVault` directly. |
| 4 | Revert PR. `vault/__init__.py` re-exports go back to `keychain.py`; Windows/Linux secret resolution returns to env-only. |
| 5 | Revert PR. Migration script disappears; manually-migrated operators are fine (data is in OS keyring). |
| 6 | Revert PR. Cockpit badge disappears; no functional impact. |

Every step is independently revertable. **Operator never loses data** —
the file vault remains the canonical fallback storage; OS keyring is
an addition, not a replacement.

---

## 10. Open questions for operator (resolve before step 1 starts)

| # | Question | Default if operator silent |
| - | -------- | -------------------------- |
| Q1 | Use the `keyring` Python library for wincred, or `pywin32` direct? | `keyring` — smaller dep tree, cross-platform abstraction we may need later anyway |
| Q2 | For Linux: `secretstorage` (raw D-Bus) or `keyring.backends.SecretService`? | `secretstorage` — fewer abstraction layers, fail-loud when D-Bus missing |
| Q3 | Should the migration script be a CLI flag on the main TARS binary, or a separate script? | Separate `scripts/migrate_vault_to_os_keyring.py` — easier to support, doesn't bloat main binary |
| Q4 | Pop a modal in cockpit on first launch for existing operators to run migration? | No — surface in settings panel as a banner with "Run migration" button. Modals are intrusive. |
| Q5 | Should we encrypt the wincred / secretservice JSON blob with XChaCha20-Poly1305 like file vault, or trust the OS keyring's own protection? | Trust the OS keyring. Double-encryption would just add a key-management problem. macOS Keychain operators don't double-encrypt either. |

If operator doesn't override within the first step's PR, defaults stick.

---

## 11. Estimated effort

- Step 1 (wincred backend): ~5 h, 1 PR, medium risk (Windows-specific testing)
- Step 2 (secretservice backend): ~5 h, 1 PR, medium risk (D-Bus mocking)
- Step 3 (factory): ~2 h, 1 PR, low risk
- Step 4 (api_keyring cross-platform): ~4 h, 1 PR, medium risk (touches many call sites)
- Step 5 (migration script): ~4 h, 1 PR, low risk (idempotent + dry-run)
- Step 6 (cockpit settings UX): ~3 h, 1 PR, low risk (small UI delta)

**Total:** ~23 h, 6 PRs, distributable across 1 week at one-step-per-day cadence.

Comparable in size to the Phase 2 voice gallery brief (~17 h, 4 PRs).
Significantly smaller than Phase 2 STT brief (~38 h, 7 PRs).

---

## 12. Pointers / references

- Current macOS-only baseline: `backend/core/vault/keychain.py`, `backend/core/vault/file_vault.py`
- Existing `KeyringVault` ABC: `backend/core/vault/file_vault.py:128`
- L5 crypto canonical implementation: `backend/core/crypto/envelope.py`, `backend/core/crypto/recovery.py` (BIP-39 24-word recovery, `REAL_CRYPTO_SHIPPED` per W310-a)
- Existing tests to preserve: `tests/test_vault_*.py`, `tests/test_crypto_envelope.py`, `tests/test_pairing_vault_integration.py`
- Master plan slot: `docs/PRODUCT_MASTER_PLAN.md` — Phase 3 (`ph3-keyring`)
- Companion brief (UI lane, separate): `ph3-pairing-ux` — TODO, not in this brief's scope
- Wave summary that scheduled this work: `docs/W310_WAVE_SUMMARY.md`

---

**End of brief.**
