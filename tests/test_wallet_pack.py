"""Wallet domain pack contract tests.

Ensures the pack registers correctly and that calling its actions
through the standard ``DomainPack`` surface yields the expected
shape — this is the path agents (Phase M1) take when they call
``wallet.list``, ``wallet.address``, etc.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import get_pack
from backend.core.wallet import (
    WalletChain,
    get_wallet_service,
    reset_wallet_service_for_tests,
)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_wallet_pack_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    reset_wallet_service_for_tests()
    yield
    reset_wallet_service_for_tests()


def test_wallet_pack_registered() -> None:
    pack = get_pack("wallet")
    assert pack is not None
    action_ids = {a.id for a in pack.actions()}
    assert action_ids >= {"list", "address", "propose_send", "sign_message"}


def test_destructive_flags() -> None:
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["list"].destructive is False
    assert by_id["address"].destructive is False
    assert by_id["propose_send"].destructive is True
    assert by_id["sign_message"].destructive is True


@pytest.mark.asyncio
async def test_list_action_uses_service() -> None:
    svc = get_wallet_service()
    await svc.create_wallet(label="alpha", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["list"].handler({})
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["wallets"][0]["label"] == "alpha"


@pytest.mark.asyncio
async def test_address_action_round_trips() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="x", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["address"].handler({"wallet_id": wallet.id})
    assert out["ok"] is True
    assert out["address"] == wallet.address


@pytest.mark.asyncio
async def test_propose_send_returns_envelope() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="x", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["propose_send"].handler(
        {"wallet_id": wallet.id, "to": "Sendr111", "amount": "0.5"}
    )
    assert out["ok"] is True
    env = out["envelope"]
    assert env["chain"] == "solana"
    assert env["from"] == wallet.address
    assert env["signing_supported"] is True


@pytest.mark.asyncio
async def test_sign_message_action() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="x", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_message"].handler(
        {"wallet_id": wallet.id, "message": "hi"}
    )
    assert out["ok"] is True
    assert out["signature_b64"]


@pytest.mark.asyncio
async def test_sign_message_ton_round_trips() -> None:
    """All three chains now sign locally — TON via wallet v3R2 ed25519."""
    import base64

    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="x", chain=WalletChain.TON)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_message"].handler(
        {"wallet_id": wallet.id, "message": "hi"}
    )
    assert out["ok"] is True
    sig_bytes = base64.b64decode(out["signature_b64"])
    assert len(sig_bytes) == 64  # ed25519 detached signature


@pytest.mark.asyncio
async def test_sign_message_evm_round_trips() -> None:
    """EVM personal_sign produces a 65-byte EIP-191 signature."""
    import base64

    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="x", chain=WalletChain.EVM)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_message"].handler(
        {"wallet_id": wallet.id, "message": "hi"}
    )
    assert out["ok"] is True
    sig_bytes = base64.b64decode(out["signature_b64"])
    assert len(sig_bytes) == 65  # r (32) || s (32) || v (1)


def test_wallet_pack_declares_vault_keys() -> None:
    pack = get_pack("wallet")
    assert "TARS_EVM_RPC_URL" in pack.auth_vault_keys()
    assert "TARS_SOLANA_RPC_URL" in pack.auth_vault_keys()
