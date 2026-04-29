"""Wallet service contract tests (Phase M2).

Covers:

- Mnemonic round-trip: importing a mnemonic always derives the same
  address (deterministic given the seed + chain + index).
- Solana wallet: address is base58 of an ed25519 public key, signing
  works, signature verifies against the public key.
- EVM / TON wallets: addresses derive deterministically; signing is
  rejected with a structured error (signing_supported=False).
- Encryption at rest: the secrets file does not contain plain bytes.
- Delete also drops the encrypted secret.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from collections.abc import Iterator

import pytest
from nacl.signing import VerifyKey

from backend.core.wallet import (
    WalletChain,
    WalletError,
    reset_wallet_service_for_tests,
)
from backend.core.wallet.encoding import b58decode, b58encode
from backend.core.wallet.service import WalletService


@pytest.fixture
def isolated_service(monkeypatch) -> Iterator[WalletService]:
    tmp = tempfile.mkdtemp(prefix="tars_wallet_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    reset_wallet_service_for_tests()
    svc = WalletService()
    yield svc
    reset_wallet_service_for_tests()


# ---------- mnemonic round-trip + determinism ---------------------------


@pytest.mark.asyncio
async def test_create_returns_mnemonic_once(isolated_service: WalletService) -> None:
    wallet, mnemonic = await isolated_service.create_wallet(
        label="primary",
        chain=WalletChain.SOLANA,
    )
    assert mnemonic is not None
    assert len(mnemonic.split()) == 24
    assert wallet.chain is WalletChain.SOLANA
    assert wallet.address
    assert wallet.signing_supported is True


@pytest.mark.asyncio
async def test_address_is_deterministic_for_same_mnemonic(
    isolated_service: WalletService,
) -> None:
    wallet1, mnemonic = await isolated_service.create_wallet(
        label="alpha", chain=WalletChain.SOLANA
    )
    assert mnemonic is not None
    isolated_service2 = WalletService(
        db_path=isolated_service.db_path + ".second",
        secrets_path=isolated_service.secrets_path + ".second",
    )
    wallet2, no_mnemonic = await isolated_service2.create_wallet(
        label="alpha-clone",
        chain=WalletChain.SOLANA,
        mnemonic=mnemonic,
    )
    assert no_mnemonic is None
    assert wallet1.address == wallet2.address
    assert wallet1.public_key_hex == wallet2.public_key_hex


# ---------- per-chain shape ---------------------------------------------


@pytest.mark.asyncio
async def test_solana_address_is_base58_pubkey(
    isolated_service: WalletService,
) -> None:
    wallet, _ = await isolated_service.create_wallet(
        label="sol", chain=WalletChain.SOLANA
    )
    decoded = b58decode(wallet.address)
    assert len(decoded) == 32
    assert decoded.hex() == wallet.public_key_hex


@pytest.mark.asyncio
async def test_evm_address_shape(isolated_service: WalletService) -> None:
    wallet, _ = await isolated_service.create_wallet(
        label="evm", chain=WalletChain.EVM
    )
    assert wallet.address.startswith("0x")
    assert len(wallet.address) == 42
    # Real BIP-44 derivation lands a fully-checksummed (EIP-55) address.
    assert wallet.signing_supported is True
    # Mixed-case (not all-lower) → checksum byte present.
    assert wallet.address != wallet.address.lower()


@pytest.mark.asyncio
async def test_ton_address_shape(isolated_service: WalletService) -> None:
    wallet, _ = await isolated_service.create_wallet(
        label="ton", chain=WalletChain.TON
    )
    # Real wallet v3R2 user-friendly address: bounceable + url-safe
    # base64 of 36 bytes → 48 chars, starting with "EQ" or "UQ".
    assert wallet.address.startswith(("EQ", "UQ"))
    assert len(wallet.address) == 48
    assert wallet.signing_supported is True


# ---------- signing -----------------------------------------------------


@pytest.mark.asyncio
async def test_solana_sign_round_trips(isolated_service: WalletService) -> None:
    wallet, _ = await isolated_service.create_wallet(
        label="sol", chain=WalletChain.SOLANA
    )
    msg = b"hello operator"
    sig = await isolated_service.sign_message(wallet_id=wallet.id, message=msg)
    pk = bytes.fromhex(wallet.public_key_hex)
    VerifyKey(pk).verify(msg, sig)


@pytest.mark.asyncio
async def test_ton_sign_message_round_trips(
    isolated_service: WalletService,
) -> None:
    """TON ed25519 personal_sign now works locally."""

    wallet, _ = await isolated_service.create_wallet(
        label="ton", chain=WalletChain.TON
    )
    sig = await isolated_service.sign_message(
        wallet_id=wallet.id, message=b"meeet.world ton proof"
    )
    assert len(sig) == 64  # ed25519 detached signature


@pytest.mark.asyncio
async def test_sign_unknown_wallet_raises(isolated_service: WalletService) -> None:
    with pytest.raises(WalletError):
        await isolated_service.sign_message(wallet_id="wlt_deadbeef", message=b"x")


# ---------- secrets at rest --------------------------------------------


@pytest.mark.asyncio
async def test_secrets_file_does_not_contain_plain_private_key(
    isolated_service: WalletService,
) -> None:
    wallet, mnemonic = await isolated_service.create_wallet(
        label="x", chain=WalletChain.SOLANA
    )
    raw = open(isolated_service.secrets_path).read()
    blob = json.loads(raw)
    item = blob["items"][wallet.id]
    assert {"salt", "nonce", "ciphertext", "chain"} == set(item.keys())
    # Ciphertext must not be the plain private key (different length, b64).
    ct = base64.b64decode(item["ciphertext"])
    # Solana ed25519 secret is 32 bytes; XChaCha tag adds 16 → 48 bytes.
    assert len(ct) == 48


@pytest.mark.asyncio
async def test_delete_drops_secret(isolated_service: WalletService) -> None:
    wallet, _ = await isolated_service.create_wallet(
        label="x", chain=WalletChain.SOLANA
    )
    removed = await isolated_service.delete_wallet(wallet.id)
    assert removed is True
    blob = json.loads(open(isolated_service.secrets_path).read())
    assert wallet.id not in blob["items"]
    second = await isolated_service.delete_wallet(wallet.id)
    assert second is False


# ---------- listing / filtering ----------------------------------------


@pytest.mark.asyncio
async def test_list_filters_by_chain(isolated_service: WalletService) -> None:
    await isolated_service.create_wallet(label="s", chain=WalletChain.SOLANA)
    await isolated_service.create_wallet(label="e", chain=WalletChain.EVM)
    await isolated_service.create_wallet(label="t", chain=WalletChain.TON)
    sol_only = await isolated_service.list_wallets(chain=WalletChain.SOLANA)
    assert len(sol_only) == 1 and sol_only[0].label == "s"
    everything = await isolated_service.list_wallets()
    assert len(everything) == 3


# ---------- encoding sanity --------------------------------------------


def test_b58_round_trip_bytes() -> None:
    for raw in [b"", b"\x00\x01", b"hello", b"\x00" * 5 + b"abc"]:
        assert b58decode(b58encode(raw)) == raw


def test_b58_rejects_invalid_chars() -> None:
    with pytest.raises(ValueError):
        b58decode("0OIl")
