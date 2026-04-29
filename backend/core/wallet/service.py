"""Wallet orchestration service.

Two responsibilities:

1. **Public ledger** — the public-only :class:`Wallet` rows live in
   SQLite (``~/.tars/wallets.sqlite`` by default), one row per wallet.
2. **Encrypted secret store** — the per-wallet private key bytes live
   in a JSON sidecar at ``~/.tars/wallet_secrets.json``, encrypted at
   rest with XChaCha20-Poly1305 keyed by PBKDF2 over the host's
   passphrase (default empty — the file's ``0o600`` mode is the
   primary defence; passphrase support lands when we surface it in
   the cockpit).

Public lookups (``list``, ``get``, ``balance_via_rpc``) never touch
the secret store. ``sign`` and ``propose_send`` do — and are the only
methods that decrypt material.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_KEYBYTES,
    crypto_aead_xchacha20poly1305_ietf_NPUBBYTES,
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
)

from backend.core.crypto.recovery import (
    fingerprint_of,
    generate_mnemonic,
    mnemonic_to_seed,
)

from .derive import derive, sign_message
from .models import Wallet, WalletChain, new_wallet_id


class WalletError(RuntimeError):
    """Domain-level failure (validation, not-found, decryption, …)."""


DEFAULT_DB_PATH = "~/.tars/wallets.sqlite"
DEFAULT_SECRETS_PATH = "~/.tars/wallet_secrets.json"

KDF_ITERATIONS = 200_000
KDF_SALT_BYTES = 16
KEYBYTES = crypto_aead_xchacha20poly1305_ietf_KEYBYTES
NONCEBYTES = crypto_aead_xchacha20poly1305_ietf_NPUBBYTES


_SCHEMA = """
CREATE TABLE IF NOT EXISTS wallets (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    public_key_hex TEXT NOT NULL,
    derivation_path TEXT NOT NULL,
    seed_fingerprint TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    derivation_scheme TEXT NOT NULL DEFAULT 'tars-v1'
);

CREATE INDEX IF NOT EXISTS idx_wallets_chain ON wallets (chain);
CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets (address);
"""

# Phase O3 — additive migration for older DBs that pre-date the
# `derivation_scheme` column. SQLite is fine with idempotent ALTERs
# wrapped in a try/except (cheap; runs once per process).
def _migrate_add_derivation_scheme(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(
            "ALTER TABLE wallets ADD COLUMN derivation_scheme TEXT NOT NULL "
            "DEFAULT 'tars-v1'"
        )
    except sqlite3.OperationalError:
        # Column already exists — fresh install, nothing to do.
        pass


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _resolve_path(env_var: str, default: str, override: str | None = None) -> str:
    raw = override or os.getenv(env_var) or default
    return os.path.expanduser(raw)


def _is_disabled(env_var: str) -> bool:
    flag = (os.getenv(env_var) or "").strip().lower()
    return flag in {"disabled", "off", "0", "false", "no"}


class WalletService:
    """Singleton wallet manager."""

    def __init__(
        self,
        *,
        db_path: str | None = None,
        secrets_path: str | None = None,
        passphrase: str = "",
        enabled: bool | None = None,
    ) -> None:
        self.db_path = _resolve_path("TARS_WALLETS_DB_PATH", DEFAULT_DB_PATH, db_path)
        self.secrets_path = _resolve_path(
            "TARS_WALLETS_SECRETS_PATH", DEFAULT_SECRETS_PATH, secrets_path
        )
        self.passphrase = passphrase or os.getenv("TARS_WALLETS_PASSPHRASE", "")
        self.enabled = (
            (not _is_disabled("TARS_WALLETS_STORE")) if enabled is None else enabled
        )
        if self.enabled:
            self._ensure_schema()
            self._ensure_secrets_file()

    # -- ledger ------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            _migrate_add_derivation_scheme(conn)
        finally:
            conn.close()

    def _row_to_wallet(self, row: sqlite3.Row) -> Wallet:
        # `derivation_scheme` may be missing on rows from a DB that
        # pre-dates the migration; default safely to tars-v1.
        try:
            scheme = row["derivation_scheme"] or "tars-v1"
        except (IndexError, KeyError):
            scheme = "tars-v1"
        return Wallet(
            id=row["id"],
            label=row["label"],
            chain=WalletChain(row["chain"]),
            address=row["address"],
            public_key_hex=row["public_key_hex"],
            derivation_path=row["derivation_path"],
            seed_fingerprint=row["seed_fingerprint"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
            derivation_scheme=scheme,
        )

    # -- secrets file ------------------------------------------------------

    def _ensure_secrets_file(self) -> None:
        path = Path(self.secrets_path)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "items": {}}), encoding="utf-8")
        try:
            path.chmod(0o600)
        except (OSError, PermissionError):
            # On Windows / weird FSes chmod is a no-op; we still
            # write the file with our process umask.
            pass

    def _read_secrets_blob(self) -> dict[str, Any]:
        path = Path(self.secrets_path)
        if not path.exists():
            return {"version": 1, "items": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WalletError(f"wallet secrets file unreadable: {exc}") from exc

    def _write_secrets_blob(self, blob: Mapping[str, Any]) -> None:
        path = Path(self.secrets_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(dict(blob), indent=2), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except (OSError, PermissionError):
            pass
        os.replace(tmp, path)

    def _derive_vault_key(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha512",
            self.passphrase.encode("utf-8"),
            salt,
            KDF_ITERATIONS,
            KEYBYTES,
        )

    def _encrypt_private(
        self, *, wallet_id: str, private_key: bytes, chain: WalletChain
    ) -> dict[str, str]:
        salt = secrets.token_bytes(KDF_SALT_BYTES)
        nonce = secrets.token_bytes(NONCEBYTES)
        vault_key = self._derive_vault_key(salt)
        ad = f"{wallet_id}|{chain.value}".encode("utf-8")
        ct = crypto_aead_xchacha20poly1305_ietf_encrypt(private_key, ad, nonce, vault_key)
        return {
            "salt": _b64e(salt),
            "nonce": _b64e(nonce),
            "ciphertext": _b64e(ct),
            "chain": chain.value,
        }

    def _decrypt_private(
        self, *, wallet_id: str, item: Mapping[str, str], chain: WalletChain
    ) -> bytes:
        salt = _b64d(item["salt"])
        nonce = _b64d(item["nonce"])
        ct = _b64d(item["ciphertext"])
        vault_key = self._derive_vault_key(salt)
        ad = f"{wallet_id}|{chain.value}".encode("utf-8")
        try:
            return crypto_aead_xchacha20poly1305_ietf_decrypt(ct, ad, nonce, vault_key)
        except Exception as exc:  # nacl raises CryptoError on tag mismatch
            raise WalletError(f"wallet secret decryption failed: {exc}") from exc

    # -- public sync helpers (used by async wrappers) ---------------------

    def _insert_wallet_sync(self, wallet: Wallet) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO wallets (
                    id, label, chain, address, public_key_hex,
                    derivation_path, seed_fingerprint, created_at,
                    updated_at, metadata_json, derivation_scheme
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wallet.id,
                    wallet.label,
                    wallet.chain.value,
                    wallet.address,
                    wallet.public_key_hex,
                    wallet.derivation_path,
                    wallet.seed_fingerprint,
                    wallet.created_at,
                    wallet.updated_at,
                    wallet.metadata_json,
                    wallet.derivation_scheme,
                ),
            )
        finally:
            conn.close()

    def _list_sync(self, chain: WalletChain | None) -> list[Wallet]:
        conn = self._connect()
        try:
            if chain is not None:
                rows = conn.execute(
                    "SELECT * FROM wallets WHERE chain = ? ORDER BY created_at DESC",
                    (chain.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM wallets ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_wallet(r) for r in rows]
        finally:
            conn.close()

    def _get_sync(self, wallet_id: str) -> Wallet | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM wallets WHERE id = ?", (wallet_id,)
            ).fetchone()
            return self._row_to_wallet(row) if row else None
        finally:
            conn.close()

    def _delete_sync(self, wallet_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))
            removed = cur.rowcount > 0
        finally:
            conn.close()
        if removed:
            blob = self._read_secrets_blob()
            blob.setdefault("items", {})
            blob["items"].pop(wallet_id, None)
            self._write_secrets_blob(blob)
        return removed

    # -- async public surface --------------------------------------------

    async def create_wallet(
        self,
        *,
        label: str,
        chain: WalletChain | str,
        mnemonic: str | None = None,
        index: int = 0,
        passphrase: str = "",
        metadata: Mapping[str, Any] | None = None,
        derivation_scheme: str = "tars-v1",
    ) -> tuple[Wallet, str | None]:
        """Mint a new wallet.

        Returns ``(wallet, mnemonic_for_one_time_display)``. The
        mnemonic is **only** non-None when the caller did not supply
        one — i.e. the service generated a fresh seed. The caller is
        expected to surface it to the operator exactly once.

        ``derivation_scheme`` selects how the BIP-39 seed maps to the
        chain keypair. ``tars-v1`` (default) is the legacy HMAC path;
        ``bip44-501-phantom`` is the SLIP-0010 path Phantom uses on
        Solana. Non-Solana chains ignore this field.
        """

        if not label.strip():
            raise WalletError("wallet label must be non-empty")
        from .models import DERIVATION_SCHEMES

        if derivation_scheme not in DERIVATION_SCHEMES:
            raise WalletError(
                f"unknown derivation_scheme: {derivation_scheme}; "
                f"expected one of {DERIVATION_SCHEMES}"
            )
        chain_enum = WalletChain.from_str(chain) if isinstance(chain, str) else chain
        return await asyncio.to_thread(
            self._create_wallet_sync,
            label=label.strip(),
            chain=chain_enum,
            mnemonic=mnemonic,
            index=int(index),
            passphrase=passphrase,
            metadata=metadata,
            derivation_scheme=derivation_scheme,
        )

    def _create_wallet_sync(
        self,
        *,
        label: str,
        chain: WalletChain,
        mnemonic: str | None,
        index: int,
        passphrase: str,
        metadata: Mapping[str, Any] | None,
        derivation_scheme: str = "tars-v1",
    ) -> tuple[Wallet, str | None]:
        produced_mnemonic: str | None = None
        if mnemonic is None:
            mnemonic = generate_mnemonic()
            produced_mnemonic = mnemonic
        # Validates the mnemonic + returns the canonical fingerprint.
        seed_fp = fingerprint_of(mnemonic, passphrase=passphrase)
        seed = mnemonic_to_seed(mnemonic, passphrase=passphrase)
        derived = derive(
            chain=chain,
            seed=seed,
            index=index,
            mnemonic=mnemonic,
            derivation_scheme=derivation_scheme,
        )

        wallet = Wallet(
            id=new_wallet_id(),
            label=label,
            chain=chain,
            address=derived.address,
            public_key_hex=derived.public_key.hex(),
            derivation_path=derived.derivation_path,
            seed_fingerprint=seed_fp,
            metadata_json=json.dumps(dict(metadata or {})),
            derivation_scheme=derivation_scheme,
        )
        self._insert_wallet_sync(wallet)
        # Encrypt + persist private material.
        item = self._encrypt_private(
            wallet_id=wallet.id, private_key=derived.private_key, chain=chain
        )
        blob = self._read_secrets_blob()
        blob.setdefault("items", {})
        blob["items"][wallet.id] = item
        self._write_secrets_blob(blob)
        return wallet, produced_mnemonic

    async def list_wallets(
        self, *, chain: WalletChain | str | None = None
    ) -> list[Wallet]:
        chain_enum: WalletChain | None
        if chain is None:
            chain_enum = None
        elif isinstance(chain, WalletChain):
            chain_enum = chain
        else:
            chain_enum = WalletChain.from_str(chain)
        return await asyncio.to_thread(self._list_sync, chain_enum)

    async def get_wallet(self, wallet_id: str) -> Wallet | None:
        return await asyncio.to_thread(self._get_sync, wallet_id)

    async def delete_wallet(self, wallet_id: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, wallet_id)

    async def sign_message(self, *, wallet_id: str, message: bytes) -> bytes:
        wallet = await self.get_wallet(wallet_id)
        if wallet is None:
            raise WalletError(f"wallet_not_found: {wallet_id}")
        if not wallet.signing_supported:
            raise WalletError(
                f"signing_unsupported_for_chain: {wallet.chain.value}"
            )
        blob = await asyncio.to_thread(self._read_secrets_blob)
        item = blob.get("items", {}).get(wallet_id)
        if item is None:
            raise WalletError(f"wallet_secret_missing: {wallet_id}")
        sk = await asyncio.to_thread(
            self._decrypt_private,
            wallet_id=wallet_id,
            item=item,
            chain=wallet.chain,
        )
        return sign_message(chain=wallet.chain, private_key=sk, message=message)

    async def sign_solana_transfer(
        self,
        *,
        wallet_id: str,
        to: str,
        lamports: int,
        recent_blockhash: str,
        memo: str | None = None,
    ) -> dict[str, Any]:
        """Build + sign a Solana ``system_program::transfer`` tx.

        The caller supplies ``recent_blockhash`` (typically fetched via
        ``getLatestBlockhash`` from any Solana RPC); we never reach the
        network from inside the wallet service. Returns the same shape
        as `backend.core.wallet.sign_sol.sign_solana_transfer`.
        """

        wallet = await self.get_wallet(wallet_id)
        if wallet is None:
            raise WalletError(f"wallet_not_found: {wallet_id}")
        if wallet.chain != WalletChain.SOLANA:
            raise WalletError(
                f"sign_solana_transfer requires solana wallet, "
                f"got {wallet.chain.value}"
            )
        blob = await asyncio.to_thread(self._read_secrets_blob)
        item = blob.get("items", {}).get(wallet_id)
        if item is None:
            raise WalletError(f"wallet_secret_missing: {wallet_id}")
        sk = await asyncio.to_thread(
            self._decrypt_private,
            wallet_id=wallet_id,
            item=item,
            chain=wallet.chain,
        )
        from .sign_sol import sign_solana_transfer as _sign_sol

        try:
            return await asyncio.to_thread(
                _sign_sol,
                ed25519_seed=sk,
                to=to,
                lamports=int(lamports),
                recent_blockhash=recent_blockhash,
                memo=memo,
            )
        except (ValueError, TypeError) as exc:
            raise WalletError(f"solana_transfer_invalid: {exc}") from exc

    async def sign_ton_transfer(
        self,
        *,
        wallet_id: str,
        to: str,
        amount_nanoton: int,
        seqno: int,
        payload: str | None = None,
        send_mode: int = 3,
    ) -> dict[str, Any]:
        """Build + sign a wallet v3R2 external transfer message.

        Returns ``{boc, body_hash, address, to, amount_nanoton, seqno,
        workchain}``. ``boc`` is base64 — broadcast via TON Center
        ``sendBoc`` or any liteserver client.
        """

        wallet = await self.get_wallet(wallet_id)
        if wallet is None:
            raise WalletError(f"wallet_not_found: {wallet_id}")
        if wallet.chain != WalletChain.TON:
            raise WalletError(
                f"sign_ton_transfer requires ton wallet, got {wallet.chain.value}"
            )
        blob = await asyncio.to_thread(self._read_secrets_blob)
        item = blob.get("items", {}).get(wallet_id)
        if item is None:
            raise WalletError(f"wallet_secret_missing: {wallet_id}")
        sk = await asyncio.to_thread(
            self._decrypt_private,
            wallet_id=wallet_id,
            item=item,
            chain=wallet.chain,
        )
        from .sign_ton import sign_ton_transfer as _sign_ton_transfer

        try:
            return await asyncio.to_thread(
                _sign_ton_transfer,
                ed25519_seed=sk,
                to=to,
                amount_nanoton=int(amount_nanoton),
                seqno=int(seqno),
                payload=payload,
                send_mode=send_mode,
            )
        except (ValueError, TypeError) as exc:
            raise WalletError(f"ton_transfer_invalid: {exc}") from exc

    async def sign_evm_transaction(
        self,
        *,
        wallet_id: str,
        tx: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Sign an EVM transaction dict.

        Returns ``{raw, hash, r, s, v}`` — `raw` is the hex string the
        operator broadcasts via ``eth_sendRawTransaction``. The wallet
        layer never broadcasts itself; that's the policy gate's
        problem.
        """

        wallet = await self.get_wallet(wallet_id)
        if wallet is None:
            raise WalletError(f"wallet_not_found: {wallet_id}")
        if wallet.chain != WalletChain.EVM:
            raise WalletError(
                f"sign_evm_transaction requires evm wallet, got {wallet.chain.value}"
            )
        blob = await asyncio.to_thread(self._read_secrets_blob)
        item = blob.get("items", {}).get(wallet_id)
        if item is None:
            raise WalletError(f"wallet_secret_missing: {wallet_id}")
        sk = await asyncio.to_thread(
            self._decrypt_private,
            wallet_id=wallet_id,
            item=item,
            chain=wallet.chain,
        )
        from .sign_evm import sign_evm_transaction as _sign_evm_tx

        try:
            return await asyncio.to_thread(
                _sign_evm_tx, private_key=sk, tx=dict(tx)
            )
        except (ValueError, TypeError) as exc:
            raise WalletError(f"evm_tx_invalid: {exc}") from exc

    def build_unsigned_send(
        self,
        *,
        wallet: Wallet,
        to: str,
        amount: str,
        memo: str | None = None,
    ) -> dict[str, Any]:
        """Build an unsigned transaction envelope for cockpit / agent review.

        Returns a chain-shaped dict; signing happens separately when
        the policy gate confirms (and only on chains where signing is
        supported). For unsupported chains the envelope is still
        useful — the user copies it into a real wallet to sign.
        """

        return {
            "chain": wallet.chain.value,
            "from": wallet.address,
            "to": to,
            "amount": amount,
            "memo": memo,
            "derivation_path": wallet.derivation_path,
            "signing_supported": wallet.signing_supported,
            "built_at": time.time(),
        }


_SINGLETON: WalletService | None = None


def get_wallet_service() -> WalletService:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = WalletService()
    return _SINGLETON


def reset_wallet_service_for_tests() -> None:
    global _SINGLETON
    _SINGLETON = None
