"""In-memory pairing store.

Phase L5 v0 keeps state in-process — same approach the policy gate
took before SQLite-backed persistence. The interface is async so the
real persistent store can be swapped in without changing callers.

Phase L5 v1 (this revision) plumbs **real X25519 keys** through the
flow:

- The host owns a long-term X25519 keypair (lifetime: device lifetime,
  re-keyed only on revocation epoch bumps).
- Each ``begin`` call validates the client's ephemeral public key
  (32 bytes, base64) and stores the long-term host pubkey in the
  record so the client can pin it on first contact.
- Each ``accept`` mints a per-device key for the linked client (the
  host stores the public half; the client's secret half is its own
  responsibility — Secure Enclave on iOS, Keystore/StrongBox on
  Android, libsodium-managed on desktop).

The actual encryption / decryption of synced events is the envelope
module's job; this store only handles **identity** and **lifecycle**.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Literal

from backend.core.crypto import DeviceKey, generate_device_key
from backend.core.crypto.envelope import PUBLICKEYBYTES
from backend.core.vault import KeyringVault, StoredHostIdentity, VaultCorruptError


PairingState = Literal["pending", "accepted", "rejected", "expired", "linked"]
DeviceKind = Literal["desktop_macos", "desktop_windows", "mobile_ios", "mobile_android"]

DEFAULT_PAIR_TTL = 120.0  # seconds; matches the QR envelope expiry policy.


class PairingNotFound(Exception):
    """Raised when a token / pair_id does not match a stored record."""


@dataclass
class PairingRecord:
    pair_id: str
    accept_token: str
    host_id: str
    host_fingerprint: str
    host_public_key: str  # base64 X25519 long-term host pubkey
    client_kind: DeviceKind
    client_epk: str       # base64 X25519 ephemeral client pubkey
    state: PairingState = "pending"
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + DEFAULT_PAIR_TTL)
    linked_at: float | None = None
    rejected_reason: str | None = None
    device_id: str | None = None  # set when state == "linked"

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "accept_token": self.accept_token,
            "host_id": self.host_id,
            "host_fingerprint": self.host_fingerprint,
            "host_public_key": self.host_public_key,
            "client_kind": self.client_kind,
            "client_epk": self.client_epk,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "linked_at": self.linked_at,
            "rejected_reason": self.rejected_reason,
            "device_id": self.device_id,
        }


@dataclass
class PairedDevice:
    device_id: str
    kind: DeviceKind
    linked_at: float
    last_seen_at: float
    pair_id: str
    public_key: str  # base64 X25519 device pubkey (host knows the public half only)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "kind": self.kind,
            "linked_at": self.linked_at,
            "last_seen_at": self.last_seen_at,
            "pair_id": self.pair_id,
            "public_key": self.public_key,
        }


def _make_id(prefix_bytes: int = 8) -> str:
    return secrets.token_hex(prefix_bytes)


def _validate_b64_pubkey(value: str, *, label: str) -> bytes:
    """Decode a base64 X25519 public key, raising if it's the wrong length."""

    try:
        raw = base64.b64decode(value.encode("ascii"))
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise ValueError(f"{label}: not valid base64") from exc
    if len(raw) != PUBLICKEYBYTES:
        raise ValueError(f"{label}: expected {PUBLICKEYBYTES} bytes, got {len(raw)}")
    return raw


class PairingStore:
    def __init__(
        self,
        host_id: str | None = None,
        *,
        vault: KeyringVault | None = None,
    ) -> None:
        self._vault = vault
        self._identity_loaded_from_vault = False
        self._identity_freshly_minted = False
        self._identity_recovery_fingerprint: str | None = None

        # Resolve the host identity: prefer a vault-persisted key,
        # otherwise mint a fresh one and persist when a vault is set.
        loaded: StoredHostIdentity | None = None
        if vault is not None:
            try:
                loaded = vault.load()
            except VaultCorruptError:
                # The next slice should surface this via a meeet
                # ``host.identity.corrupt`` event so the cockpit can
                # prompt for recovery; for now, refuse to silently
                # mint a new identity and re-raise.
                raise

        if loaded is not None:
            self._host_id = loaded.host_id
            self._host_identity = loaded.device_key
            self._identity_loaded_from_vault = True
            self._identity_recovery_fingerprint = loaded.recovery_fingerprint
        else:
            self._host_id = host_id or _make_id()
            self._host_identity = generate_device_key(self._host_id)
            self._identity_freshly_minted = True
            if vault is not None:
                stored = vault.save(self._host_identity)
                self._identity_recovery_fingerprint = stored.recovery_fingerprint

        self._host_public_key_b64 = self._host_identity.public_b64
        self._lock = asyncio.Lock()
        self._records: dict[str, PairingRecord] = {}
        self._by_token: dict[str, str] = {}
        self._devices: dict[str, PairedDevice] = {}
        # Cache of paired-device public keys keyed by device_id so the
        # crypto layer can encrypt to all paired devices in one pass.
        self._device_keys: dict[str, DeviceKey] = {}

    @property
    def vault(self) -> KeyringVault | None:
        return self._vault

    @property
    def identity_was_loaded(self) -> bool:
        """True when the host identity was loaded from the vault, not minted."""

        return self._identity_loaded_from_vault

    @property
    def identity_was_freshly_minted(self) -> bool:
        return self._identity_freshly_minted

    @property
    def recovery_fingerprint(self) -> str | None:
        return self._identity_recovery_fingerprint

    def rotate_host_identity(
        self, *, recovery_fingerprint: str | None = None
    ) -> DeviceKey:
        """Mint a fresh host identity and persist it via the vault.

        Returns the new ``DeviceKey``. Existing paired devices are
        invalidated by design (they pinned the old public key) — the
        caller is expected to walk ``list_devices()`` and emit a
        ``pair.epoch_bumped`` event before clearing them.
        """

        new_identity = generate_device_key(self._host_id)
        if self._vault is not None:
            stored = self._vault.rotate(
                new_identity, recovery_fingerprint=recovery_fingerprint
            )
            self._identity_recovery_fingerprint = stored.recovery_fingerprint
        else:
            self._identity_recovery_fingerprint = recovery_fingerprint
        self._host_identity = new_identity
        self._host_public_key_b64 = new_identity.public_b64
        return new_identity

    @property
    def host_id(self) -> str:
        return self._host_id

    @property
    def host_public_key_b64(self) -> str:
        return self._host_public_key_b64

    def host_identity(self) -> DeviceKey:
        """Return the host's long-term keypair (use sparingly)."""

        return self._host_identity

    def device_keys(self) -> tuple[DeviceKey, ...]:
        """Snapshot of paired-device public keys; safe to read anywhere."""

        return tuple(self._device_keys.values())

    @staticmethod
    def fingerprint(*, host_id: str, pair_id: str) -> str:
        """Stable hex digest visible to the operator on both sides.

        Real crypto swaps this for a fingerprint of the host's
        long-term public key (libsodium ``crypto_box_keypair`` →
        SHA-256 → first 12 hex chars), but the wire string format
        stays — three groups of four chars separated by ``-``, e.g.
        ``QXr7-8mB9-nJ2L``.
        """

        digest = hashlib.sha256(f"{host_id}:{pair_id}".encode("utf-8")).hexdigest().upper()
        # Normalise to a 12-char string in 4-4-4 groups.
        clean = digest.replace("0", "X").replace("O", "Y")[:12]
        return f"{clean[0:4]}-{clean[4:8]}-{clean[8:12]}"

    async def begin(
        self,
        *,
        client_epk: str,
        client_kind: DeviceKind,
        pair_id: str | None = None,
        ttl: float = DEFAULT_PAIR_TTL,
    ) -> PairingRecord:
        # Validate the ephemeral key shape before taking any state — a
        # broken QR code should fail fast, not pollute the store.
        _validate_b64_pubkey(client_epk, label="client_epk")

        async with self._lock:
            pid = pair_id or _make_id()
            if pid in self._records:
                # Re-issuing the same pair_id is fine, return the
                # existing record (idempotent retries).
                rec = self._records[pid]
                if rec.state == "pending" and rec.expires_at > time.time():
                    return rec
                # Stale or finalised record; replace it.
                self._by_token.pop(rec.accept_token, None)
                del self._records[pid]

            token = secrets.token_hex(16)
            fingerprint = self.fingerprint(host_id=self._host_id, pair_id=pid)
            now = time.time()
            rec = PairingRecord(
                pair_id=pid,
                accept_token=token,
                host_id=self._host_id,
                host_fingerprint=fingerprint,
                host_public_key=self._host_public_key_b64,
                client_kind=client_kind,
                client_epk=client_epk,
                state="pending",
                created_at=now,
                expires_at=now + ttl,
            )
            self._records[pid] = rec
            self._by_token[token] = pid
            return rec

    async def accept(self, *, token: str) -> PairingRecord:
        async with self._lock:
            pid = self._by_token.get(token)
            if pid is None:
                raise PairingNotFound(token)
            rec = self._records[pid]
            if rec.state != "pending":
                return rec
            if rec.expires_at < time.time():
                rec.state = "expired"
                return rec

            device_id = _make_id()
            rec.state = "linked"
            rec.linked_at = time.time()
            rec.device_id = device_id

            # The client's ephemeral key from begin() is what we keep as
            # the long-term device key for v1 — once Phase L5.2 lands a
            # post-handshake key rotation, this is the single line that
            # changes.
            client_pub_bytes = base64.b64decode(rec.client_epk.encode("ascii"))
            device_key = DeviceKey(
                device_id=device_id,
                public_key=client_pub_bytes,
            )
            self._device_keys[device_id] = device_key

            self._devices[device_id] = PairedDevice(
                device_id=device_id,
                kind=rec.client_kind,
                linked_at=rec.linked_at,
                last_seen_at=rec.linked_at,
                pair_id=pid,
                public_key=rec.client_epk,
            )
            return rec

    async def reject(self, *, token: str, reason: str = "operator_declined") -> PairingRecord:
        async with self._lock:
            pid = self._by_token.get(token)
            if pid is None:
                raise PairingNotFound(token)
            rec = self._records[pid]
            if rec.state == "pending":
                rec.state = "rejected"
                rec.rejected_reason = reason
            return rec

    async def status(self, *, pair_id: str) -> PairingRecord:
        async with self._lock:
            rec = self._records.get(pair_id)
            if rec is None:
                raise PairingNotFound(pair_id)
            if rec.state == "pending" and rec.expires_at < time.time():
                rec.state = "expired"
            return rec

    async def revoke(self, *, device_id: str) -> bool:
        async with self._lock:
            removed = self._devices.pop(device_id, None) is not None
            self._device_keys.pop(device_id, None)
            return removed

    async def list_devices(self) -> list[PairedDevice]:
        async with self._lock:
            return list(self._devices.values())

    async def expire_stale(self, *, now: float | None = None) -> int:
        ts = now or time.time()
        expired = 0
        async with self._lock:
            for rec in self._records.values():
                if rec.state == "pending" and rec.expires_at < ts:
                    rec.state = "expired"
                    expired += 1
            return expired

    # Test hook; production should never reset the singleton.
    async def reset(self) -> None:
        async with self._lock:
            self._records.clear()
            self._by_token.clear()
            self._devices.clear()
            self._device_keys.clear()


_singleton: PairingStore | None = None


def _build_default_vault() -> KeyringVault | None:
    """Resolve a vault from environment, or return ``None``.

    Behaviour:

    - ``TARS_PAIRING_VAULT=disabled`` → no vault (in-memory; legacy).
    - ``TARS_PAIRING_VAULT_PATH`` set → :class:`FileKeyringVault` at that path.
    - default → :class:`FileKeyringVault` at
      ``~/.tars/host_identity.json`` with passphrase from
      ``TARS_PAIRING_VAULT_PASSPHRASE`` (or empty).
    """

    flag = (os.getenv("TARS_PAIRING_VAULT") or "").strip().lower()
    if flag in {"disabled", "off", "0", "false", "no"}:
        return None

    from backend.core.vault import FileKeyringVault

    raw_path = os.getenv("TARS_PAIRING_VAULT_PATH") or "~/.tars/host_identity.json"
    passphrase = os.getenv("TARS_PAIRING_VAULT_PASSPHRASE") or ""
    return FileKeyringVault(raw_path, passphrase=passphrase)


def get_pairing_store() -> PairingStore:
    global _singleton
    if _singleton is None:
        _singleton = PairingStore(vault=_build_default_vault())
    return _singleton


def _reset_singleton_for_tests() -> None:
    """Drop the singleton (test fixtures only)."""

    global _singleton
    _singleton = None
