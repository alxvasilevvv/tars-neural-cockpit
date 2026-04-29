"""File-backed keyring vault.

Stores the TARS host's long-term X25519 identity at a path of the
caller's choosing (default: ``~/.tars/host_identity.json``). The
secret half is **always** encrypted at rest via XChaCha20-Poly1305;
the passphrase defaults to an empty string when the operator doesn't
set one (this is honest about being a dev-mode keyring — the file
permissions are still 0600 and the wrapper is still a real AEAD,
just keyed off a publicly-known input).

Wire shape (single JSON file):

```jsonc
{
  "version": 1,
  "host_id": "9ebd45c6de53f838",
  "public_key": "base64",
  "created_at": 1777414501.785,
  "rotated_at": null,
  "recovery_fingerprint": "B00DAEBD10BD",
  "kdf": {
    "algo": "pbkdf2-sha512",
    "iterations": 200000,
    "salt": "base64(16 bytes)"
  },
  "secret": {
    "scheme": "xchacha20-poly1305-v1",
    "nonce": "base64(24 bytes)",
    "ciphertext": "base64"
  }
}
```

The file is written with ``0o600`` permissions and read with a strict
permission check — if anything has chmod'd it wider, the loader
refuses to open it (raises :class:`VaultPermissionError`).
"""

from __future__ import annotations

import abc
import base64
import hashlib
import json
import os
import secrets
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_KEYBYTES,
    crypto_aead_xchacha20poly1305_ietf_NPUBBYTES,
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
)
from nacl.public import PrivateKey

from backend.core.crypto import DeviceKey


VAULT_VERSION = 1
KDF_ALGO = "pbkdf2-sha512"
KDF_ITERATIONS = 200_000
KDF_SALT_BYTES = 16
SCHEME = "xchacha20-poly1305-v1"
KEYBYTES = crypto_aead_xchacha20poly1305_ietf_KEYBYTES
NONCEBYTES = crypto_aead_xchacha20poly1305_ietf_NPUBBYTES


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------


class VaultCorruptError(RuntimeError):
    """Raised when a vault file is unreadable or fails AEAD verification."""


class VaultPermissionError(RuntimeError):
    """Raised when the vault file's POSIX permissions are too wide."""


# ---------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class StoredHostIdentity:
    host_id: str
    device_key: DeviceKey
    created_at: float
    rotated_at: float | None
    recovery_fingerprint: str | None


# ---------------------------------------------------------------------
# KDF + helpers
# ---------------------------------------------------------------------


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _derive_vault_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha512",
        (passphrase or "").encode("utf-8"),
        salt,
        KDF_ITERATIONS,
        KEYBYTES,
    )


# ---------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------


class KeyringVault(abc.ABC):
    """Abstract interface every vault implementation honours."""

    @abc.abstractmethod
    def load(self) -> StoredHostIdentity | None:
        """Return the persisted identity or ``None`` when none exists."""

    @abc.abstractmethod
    def save(
        self,
        device_key: DeviceKey,
        *,
        recovery_fingerprint: str | None = None,
    ) -> StoredHostIdentity:
        """Persist ``device_key`` and return what landed on disk."""

    @abc.abstractmethod
    def rotate(
        self,
        device_key: DeviceKey,
        *,
        recovery_fingerprint: str | None = None,
    ) -> StoredHostIdentity:
        """Replace the persisted identity, recording a rotation timestamp."""

    @abc.abstractmethod
    def exists(self) -> bool:
        ...

    @abc.abstractmethod
    def clear(self) -> None:
        ...


# ---------------------------------------------------------------------
# File implementation
# ---------------------------------------------------------------------


class FileKeyringVault(KeyringVault):
    """JSON-on-disk vault. The default backend until Keychain lands."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        passphrase: str = "",
    ) -> None:
        self._path = Path(os.path.expanduser(str(path)))
        self._passphrase = passphrase

    # -- public API ---------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def load(self) -> StoredHostIdentity | None:
        if not self.exists():
            return None
        self._check_permissions()
        try:
            blob = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VaultCorruptError(f"vault file unreadable: {exc}") from exc
        return self._decode(blob)

    def save(
        self,
        device_key: DeviceKey,
        *,
        recovery_fingerprint: str | None = None,
    ) -> StoredHostIdentity:
        return self._write(
            device_key,
            recovery_fingerprint=recovery_fingerprint,
            rotated=False,
        )

    def rotate(
        self,
        device_key: DeviceKey,
        *,
        recovery_fingerprint: str | None = None,
    ) -> StoredHostIdentity:
        return self._write(
            device_key,
            recovery_fingerprint=recovery_fingerprint,
            rotated=True,
        )

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()

    # -- internal -----------------------------------------------------

    def _write(
        self,
        device_key: DeviceKey,
        *,
        recovery_fingerprint: str | None,
        rotated: bool,
    ) -> StoredHostIdentity:
        if device_key.secret_key is None:
            raise ValueError("device_key must carry a secret_key to persist")

        salt = secrets.token_bytes(KDF_SALT_BYTES)
        nonce = secrets.token_bytes(NONCEBYTES)
        vault_key = _derive_vault_key(self._passphrase, salt)
        ad = device_key.device_id.encode("utf-8")
        ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
            device_key.secret_key, ad, nonce, vault_key
        )

        existing_created = (
            self._existing_created_at() if self.exists() and rotated else None
        )
        now = time.time()
        created_at = existing_created or now
        rotated_at = now if rotated and self.exists() else None

        blob: dict[str, Any] = {
            "version": VAULT_VERSION,
            "host_id": device_key.device_id,
            "public_key": _b64e(device_key.public_key),
            "created_at": created_at,
            "rotated_at": rotated_at,
            "recovery_fingerprint": recovery_fingerprint,
            "kdf": {
                "algo": KDF_ALGO,
                "iterations": KDF_ITERATIONS,
                "salt": _b64e(salt),
            },
            "secret": {
                "scheme": SCHEME,
                "nonce": _b64e(nonce),
                "ciphertext": _b64e(ciphertext),
            },
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file in the same dir, fsync, then rename for
        # crash safety; chmod 0600 BEFORE writing the secret.
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            os.chmod(tmp, 0o600)
            json.dump(blob, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)
        os.chmod(self._path, 0o600)

        return StoredHostIdentity(
            host_id=device_key.device_id,
            device_key=device_key,
            created_at=created_at,
            rotated_at=rotated_at,
            recovery_fingerprint=recovery_fingerprint,
        )

    def _existing_created_at(self) -> float | None:
        try:
            blob = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        ts = blob.get("created_at")
        return float(ts) if isinstance(ts, (int, float)) else None

    def _decode(self, blob: dict[str, Any]) -> StoredHostIdentity:
        try:
            version = int(blob.get("version") or 0)
            if version != VAULT_VERSION:
                raise VaultCorruptError(
                    f"unsupported vault version {version!r}; expected {VAULT_VERSION}"
                )
            host_id = str(blob["host_id"])
            public_key = _b64d(str(blob["public_key"]))
            kdf = blob.get("kdf") or {}
            salt = _b64d(str(kdf.get("salt", "")))
            secret = blob.get("secret") or {}
            nonce = _b64d(str(secret.get("nonce", "")))
            ciphertext = _b64d(str(secret.get("ciphertext", "")))
        except (KeyError, ValueError) as exc:
            raise VaultCorruptError(f"vault file malformed: {exc}") from exc

        if len(salt) != KDF_SALT_BYTES:
            raise VaultCorruptError(
                f"salt has wrong length: {len(salt)} != {KDF_SALT_BYTES}"
            )
        if len(nonce) != NONCEBYTES:
            raise VaultCorruptError(
                f"nonce has wrong length: {len(nonce)} != {NONCEBYTES}"
            )

        vault_key = _derive_vault_key(self._passphrase, salt)
        try:
            secret_key = crypto_aead_xchacha20poly1305_ietf_decrypt(
                ciphertext, host_id.encode("utf-8"), nonce, vault_key
            )
        except Exception as exc:
            raise VaultCorruptError(
                "vault decryption failed (wrong passphrase or tampered file)"
            ) from exc

        if len(secret_key) != 32 or len(public_key) != 32:
            raise VaultCorruptError("decoded keys have wrong length")

        # Sanity: re-derive public from the decrypted secret and reject
        # mismatches — catches passphrase-collision corruption.
        derived_public = bytes(PrivateKey(secret_key).public_key)
        if derived_public != public_key:
            raise VaultCorruptError(
                "public key in vault doesn't match decrypted secret key"
            )

        return StoredHostIdentity(
            host_id=host_id,
            device_key=DeviceKey(
                device_id=host_id,
                public_key=public_key,
                secret_key=secret_key,
            ),
            created_at=float(blob.get("created_at") or 0.0),
            rotated_at=(
                float(blob["rotated_at"])
                if isinstance(blob.get("rotated_at"), (int, float))
                else None
            ),
            recovery_fingerprint=(
                str(blob["recovery_fingerprint"])
                if blob.get("recovery_fingerprint")
                else None
            ),
        )

    def _check_permissions(self) -> None:
        # POSIX-only check; on Windows the security model is different
        # and we trust the caller (DPAPI lands in the next slice).
        if os.name != "posix":
            return
        try:
            mode = self._path.stat().st_mode
        except OSError as exc:
            raise VaultCorruptError(f"vault stat failed: {exc}") from exc
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise VaultPermissionError(
                f"vault file {self._path} is group/world readable "
                f"(mode={oct(mode & 0o777)}); refusing to open. "
                f"Run `chmod 600 {self._path}` to recover."
            )
