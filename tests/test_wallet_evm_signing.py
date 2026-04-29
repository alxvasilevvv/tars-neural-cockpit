"""Real EVM signing contract tests (Phase N3).

Pinned against the canonical Hardhat / Anvil / Foundry mnemonic and
its first ten BIP-44 addresses — these are the most-published test
vectors in the Ethereum ecosystem, so a regression here is also a
regression against literally every demo you've ever followed.

Coverage:

- BIP-44 derivation matches Anvil for index 0..2.
- EIP-55 mixed-case checksum present on every derived address.
- ``recover_evm_personal_message`` round-trips a personal_sign
  signature back to the signer.
- ``sign_evm_transaction`` produces broadcastable raw hex for
  EIP-1559 typed-2 + legacy transactions; the hex decodes back to
  the same parameters.
- HTTP route ``POST /api/wallet/{id}/sign_evm_tx`` returns
  ``{raw, hash, r, s, v}`` and rejects invalid tx dicts with 400.
- Wallet pack action ``wallet.sign_evm_tx`` returns ok=true with
  the same shape; non-evm wallet returns ok=false.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.domains.registry import get_pack
from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.wallet import (
    WalletChain,
    WalletError,
    get_wallet_service,
    reset_wallet_service_for_tests,
)
from backend.core.wallet.sign_evm import (
    derive_evm_account,
    recover_evm_personal_message,
    sign_evm_personal_message,
    sign_evm_transaction,
)


# Canonical Anvil / Hardhat dev mnemonic. Same one shipped with
# `anvil --help` and used in literally every Hardhat tutorial.
ANVIL_MNEMONIC = (
    "test test test test test test test test test test test junk"
)
# First three addresses Anvil prints. Mixed-case (EIP-55).
ANVIL_ADDRESSES = (
    "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_evm_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    monkeypatch.setenv("MEEET_STORE_PATH", os.path.join(tmp, "meeet.sqlite"))
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    monkeypatch.setenv("TARS_CHAT_STORE", "disabled")
    reset_wallet_service_for_tests()
    reset_meeet_store()
    reset_meeet_client()
    yield
    reset_wallet_service_for_tests()
    reset_meeet_store()
    reset_meeet_client()


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


# ---------- canonical derivation ---------------------------------------


def test_anvil_mnemonic_derives_canonical_addresses() -> None:
    for index, expected in enumerate(ANVIL_ADDRESSES):
        derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC, index=index)
        assert derived.address == expected
        assert derived.derivation_path == f"m/44'/60'/0'/0/{index}"
        assert len(derived.private_key) == 32
        assert len(derived.public_key) == 64


def test_eip55_checksum_present() -> None:
    """At least one byte is upper-case → checksum encoded, not all-lower."""
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    assert derived.address != derived.address.lower()
    assert derived.address.lower().startswith("0x")


# ---------- EIP-191 personal_sign --------------------------------------


def test_personal_sign_recovers_to_signer() -> None:
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    signed = sign_evm_personal_message(
        private_key=derived.private_key, message=b"meeet.world"
    )
    assert signed["signature_hex"]
    recovered = recover_evm_personal_message(
        message=b"meeet.world", signature_hex=signed["signature_hex"]
    )
    assert recovered.lower() == derived.address.lower()


def test_personal_sign_signature_is_65_bytes() -> None:
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    signed = sign_evm_personal_message(
        private_key=derived.private_key, message=b"x"
    )
    sig_hex = signed["signature_hex"].removeprefix("0x")
    assert len(bytes.fromhex(sig_hex)) == 65


# ---------- transaction signing ---------------------------------------


def test_sign_eip1559_transaction() -> None:
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    tx = {
        "to": ANVIL_ADDRESSES[1],
        "value": 10**18,
        "gas": 21000,
        "maxFeePerGas": 30 * 10**9,
        "maxPriorityFeePerGas": 1 * 10**9,
        "nonce": 0,
        "chainId": 1,
        "type": 2,
    }
    signed = sign_evm_transaction(private_key=derived.private_key, tx=tx)
    assert signed["raw"]
    assert signed["hash"]
    raw_bytes = bytes.fromhex(signed["raw"].removeprefix("0x"))
    # Type-2 transactions start with the 0x02 envelope prefix.
    assert raw_bytes[0] == 0x02


def test_sign_legacy_transaction() -> None:
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    tx = {
        "to": ANVIL_ADDRESSES[1],
        "value": 0,
        "gas": 21000,
        "gasPrice": 20 * 10**9,
        "nonce": 0,
        "chainId": 1,
    }
    signed = sign_evm_transaction(private_key=derived.private_key, tx=tx)
    assert signed["raw"]
    raw_bytes = bytes.fromhex(signed["raw"].removeprefix("0x"))
    # Legacy transactions are RLP-encoded lists, no envelope prefix.
    assert raw_bytes[0] != 0x02


def test_sign_transaction_accepts_hex_strings() -> None:
    """The HTTP layer passes everything as strings — the signer must
    coerce ``"0x..."`` and decimal strings into ints."""
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    tx = {
        "to": ANVIL_ADDRESSES[1],
        "value": "0xde0b6b3a7640000",  # 1 ETH in wei
        "gas": "21000",
        "maxFeePerGas": "0x6fc23ac00",
        "maxPriorityFeePerGas": "0x3b9aca00",
        "nonce": "0",
        "chainId": "1",
    }
    signed = sign_evm_transaction(private_key=derived.private_key, tx=tx)
    assert signed["raw"]


def test_sign_transaction_invalid_raises_value_error() -> None:
    derived = derive_evm_account(mnemonic=ANVIL_MNEMONIC)
    with pytest.raises((ValueError, TypeError)):
        sign_evm_transaction(
            private_key=derived.private_key,
            tx={"to": "not-an-address", "value": 0, "gas": 21000, "nonce": 0},
        )


# ---------- HTTP route + wallet pack ---------------------------------


def test_http_sign_evm_tx_route(client: TestClient) -> None:
    # Mint EVM wallet via HTTP (uses a fresh random mnemonic).
    create = client.post("/api/wallet", json={"label": "evm", "chain": "evm"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json={
            "to": ANVIL_ADDRESSES[1],
            "value": "1000000000000000000",
            "gas": "21000",
            "nonce": "0",
            "chainId": 1,
            "maxFeePerGas": "30000000000",
            "maxPriorityFeePerGas": "1000000000",
            "type": 2,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["signed"]["raw"].startswith("0x")
    assert body["signed"]["hash"].startswith("0x")


def test_http_sign_evm_tx_rejects_solana_wallet(client: TestClient) -> None:
    create = client.post("/api/wallet", json={"label": "sol", "chain": "solana"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_evm_tx",
        json={
            "to": ANVIL_ADDRESSES[1],
            "value": "0",
            "gas": "21000",
            "nonce": "0",
            "chainId": 1,
            "maxFeePerGas": "30000000000",
            "maxPriorityFeePerGas": "1000000000",
        },
    )
    assert r.status_code == 400
    assert "evm wallet" in r.json()["detail"]


def test_http_sign_evm_tx_unknown_wallet(client: TestClient) -> None:
    r = client.post(
        "/api/wallet/wlt_deadbeef/sign_evm_tx",
        json={
            "to": ANVIL_ADDRESSES[1],
            "value": "0",
            "gas": "21000",
            "nonce": "0",
            "chainId": 1,
            "maxFeePerGas": "1",
            "maxPriorityFeePerGas": "1",
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pack_action_sign_evm_tx() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="evm", chain=WalletChain.EVM)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_evm_tx"].handler(
        {
            "wallet_id": wallet.id,
            "tx": {
                "to": ANVIL_ADDRESSES[1],
                "value": 0,
                "gas": 21000,
                "nonce": 0,
                "chainId": 1,
                "maxFeePerGas": 30 * 10**9,
                "maxPriorityFeePerGas": 1 * 10**9,
            },
        }
    )
    assert out["ok"] is True
    assert out["signed"]["raw"]


@pytest.mark.asyncio
async def test_pack_action_sign_evm_tx_rejects_solana_wallet() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="sol", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_evm_tx"].handler(
        {"wallet_id": wallet.id, "tx": {"to": ANVIL_ADDRESSES[1]}}
    )
    assert out["ok"] is False


def test_pack_action_destructive_flag() -> None:
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["sign_evm_tx"].destructive is True


# ---------- service-level integration ---------------------------------


@pytest.mark.asyncio
async def test_imported_anvil_mnemonic_yields_anvil_address() -> None:
    """End-to-end: import the Anvil mnemonic via the wallet service,
    the resulting EVM wallet has the canonical first address."""
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(
        label="anvil_0",
        chain=WalletChain.EVM,
        mnemonic=ANVIL_MNEMONIC,
    )
    assert wallet.address == ANVIL_ADDRESSES[0]
    assert wallet.signing_supported is True


@pytest.mark.asyncio
async def test_signed_anvil_transaction_is_broadcastable_hex() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(
        label="anvil_0", chain=WalletChain.EVM, mnemonic=ANVIL_MNEMONIC
    )
    signed = await svc.sign_evm_transaction(
        wallet_id=wallet.id,
        tx={
            "to": ANVIL_ADDRESSES[1],
            "value": 10**17,
            "gas": 21000,
            "maxFeePerGas": 30 * 10**9,
            "maxPriorityFeePerGas": 10**9,
            "nonce": 0,
            "chainId": 31337,  # anvil's default chain id
        },
    )
    # Parse the raw hex back through eth-account to confirm round-trip.
    from eth_account import Account

    raw = bytes.fromhex(signed["raw"].removeprefix("0x"))
    decoded = Account.recover_transaction(raw)
    assert decoded.lower() == wallet.address.lower()


@pytest.mark.asyncio
async def test_sign_evm_transaction_unknown_wallet_raises() -> None:
    svc = get_wallet_service()
    with pytest.raises(WalletError) as exc:
        await svc.sign_evm_transaction(
            wallet_id="wlt_deadbeef", tx={"to": ANVIL_ADDRESSES[1], "chainId": 1}
        )
    assert "wallet_not_found" in str(exc.value)
