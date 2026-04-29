"""Real Solana transaction signing contract tests (Phase N5).

Closes the last "tx-signing not yet" cell in the wallet matrix from
`docs/LAUNCH_READINESS.md`. Solana wallets already had ed25519
*message* signing via PyNaCl; this suite covers full
``system_program::transfer`` signing via ``solders``.

Coverage:

- :func:`derive_solana_keypair` — deterministic, address matches
  Base58 of the public key, raises on bad seed length.
- :func:`sign_solana_transfer` — produces base64 / base58 / hex
  encodings of the same raw bytes; ``tx_signature`` matches the
  first signature inside the raw tx; deterministic for a fixed
  ``(seed, recipient, lamports, blockhash)``; rejects bad recipient,
  bad blockhash, negative lamports.
- :func:`parse_lamports` — accepts SOL decimal, lamports digits,
  ints, floats, hex; rejects empty.
- HTTP route ``POST /api/wallet/{id}/sign_solana_transfer`` returns
  the signed dict, rejects non-Solana wallets / unknown wallets /
  invalid amounts.
- Wallet pack action ``wallet.sign_solana_transfer`` returns ok=true
  with the same shape; missing args return ok=false; non-Solana
  wallets return ok=false; destructive flag pinned.
- End-to-end via service: derived address from the wallet store
  matches ``signed["signer"]``.
"""

from __future__ import annotations

import base64
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
from backend.core.wallet.sign_sol import (
    derive_solana_keypair,
    parse_lamports,
    sign_solana_transfer,
)


DETERMINISTIC_SEED = bytes(range(32))
# Address that solders.Keypair.from_seed(bytes(0..31)).pubkey() yields.
EXPECTED_ADDR = "FAe4sisG95oZ42w7buUn5qEE4TAnfTTFPiguZUHmhiF"
# Valid Solana addresses: SystemProgram and a known TARS recipient.
RECIPIENT = "11111111111111111111111111111112"
# Default Hash (all-1s in base58) — used for determinism only.
ZERO_BLOCKHASH = "11111111111111111111111111111111"
# A second blockhash so we can prove signatures change with it.
ALT_BLOCKHASH = "11111111111111111111111111111112"


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_sol_")
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


# ---------- derivation -------------------------------------------------


def test_derive_solana_address_is_deterministic() -> None:
    a = derive_solana_keypair(ed25519_seed=DETERMINISTIC_SEED)
    b = derive_solana_keypair(ed25519_seed=DETERMINISTIC_SEED)
    assert a.address == b.address == EXPECTED_ADDR


def test_derive_solana_address_matches_base58_pubkey() -> None:
    """The address rendering matches the existing TARS Base58 helper."""
    from backend.core.wallet.encoding import b58encode

    derived = derive_solana_keypair(ed25519_seed=DETERMINISTIC_SEED)
    assert derived.address == b58encode(derived.public_key)
    assert len(derived.public_key) == 32
    assert len(derived.secret_key) == 64


def test_derive_solana_invalid_seed_length() -> None:
    with pytest.raises(ValueError):
        derive_solana_keypair(ed25519_seed=b"\x00" * 31)
    with pytest.raises(ValueError):
        derive_solana_keypair(ed25519_seed=b"\x00" * 33)


# ---------- transfer signing ------------------------------------------


def test_sign_transfer_returns_all_encodings() -> None:
    out = sign_solana_transfer(
        ed25519_seed=DETERMINISTIC_SEED,
        to=RECIPIENT,
        lamports=1_000,
        recent_blockhash=ZERO_BLOCKHASH,
    )
    raw = base64.b64decode(out["raw_b64"])
    assert len(raw) > 0
    assert out["raw_hex"] == "0x" + raw.hex()
    # base58-decode the base58 encoding back to the same bytes.
    from backend.core.wallet.encoding import b58decode

    assert b58decode(out["raw_b58"]) == raw
    assert out["signer"] == EXPECTED_ADDR
    assert out["recipient"] == RECIPIENT
    assert out["lamports"] == 1_000
    assert out["blockhash"] == ZERO_BLOCKHASH


def test_tx_signature_matches_first_signature_in_raw() -> None:
    """``tx_signature`` is the explorer key — the first 64 bytes after
    the signature-count varint."""
    from solders.transaction import Transaction

    out = sign_solana_transfer(
        ed25519_seed=DETERMINISTIC_SEED,
        to=RECIPIENT,
        lamports=10,
        recent_blockhash=ZERO_BLOCKHASH,
    )
    raw = base64.b64decode(out["raw_b64"])
    tx = Transaction.from_bytes(raw)
    assert str(tx.signatures[0]) == out["tx_signature"]


def test_sign_transfer_is_deterministic() -> None:
    a = sign_solana_transfer(
        ed25519_seed=DETERMINISTIC_SEED,
        to=RECIPIENT,
        lamports=42,
        recent_blockhash=ZERO_BLOCKHASH,
    )
    b = sign_solana_transfer(
        ed25519_seed=DETERMINISTIC_SEED,
        to=RECIPIENT,
        lamports=42,
        recent_blockhash=ZERO_BLOCKHASH,
    )
    assert a["raw_b64"] == b["raw_b64"]
    assert a["tx_signature"] == b["tx_signature"]


def test_sign_transfer_blockhash_changes_signature() -> None:
    a = sign_solana_transfer(
        ed25519_seed=DETERMINISTIC_SEED,
        to=RECIPIENT,
        lamports=1,
        recent_blockhash=ZERO_BLOCKHASH,
    )
    b = sign_solana_transfer(
        ed25519_seed=DETERMINISTIC_SEED,
        to=RECIPIENT,
        lamports=1,
        recent_blockhash=ALT_BLOCKHASH,
    )
    assert a["tx_signature"] != b["tx_signature"]


def test_sign_transfer_invalid_recipient() -> None:
    with pytest.raises(ValueError):
        sign_solana_transfer(
            ed25519_seed=DETERMINISTIC_SEED,
            to="not-a-pubkey",
            lamports=1,
            recent_blockhash=ZERO_BLOCKHASH,
        )


def test_sign_transfer_invalid_blockhash() -> None:
    with pytest.raises(ValueError):
        sign_solana_transfer(
            ed25519_seed=DETERMINISTIC_SEED,
            to=RECIPIENT,
            lamports=1,
            recent_blockhash="not-a-hash",
        )


def test_sign_transfer_negative_lamports_rejected() -> None:
    with pytest.raises(ValueError):
        sign_solana_transfer(
            ed25519_seed=DETERMINISTIC_SEED,
            to=RECIPIENT,
            lamports=-1,
            recent_blockhash=ZERO_BLOCKHASH,
        )


# ---------- amount parsing ---------------------------------------------


def test_parse_lamports_handles_decimal_and_integer() -> None:
    assert parse_lamports("0.5") == 500_000_000
    assert parse_lamports("1") == 1
    assert parse_lamports("1500000000") == 1_500_000_000
    assert parse_lamports(2) == 2
    assert parse_lamports(1.5) == 1_500_000_000
    assert parse_lamports("0xFF") == 255


def test_parse_lamports_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_lamports("")
    with pytest.raises(ValueError):
        parse_lamports("   ")


# ---------- HTTP route + wallet pack -----------------------------------


def test_http_sign_solana_transfer_route(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "sol", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_solana_transfer",
        json={
            "to": RECIPIENT,
            "amount": "0.5",
            "recent_blockhash": ZERO_BLOCKHASH,
            "memo": "meeet test",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["signed"]["raw_b64"]
    assert body["signed"]["tx_signature"]
    assert body["signed"]["lamports"] == 500_000_000


def test_http_sign_solana_transfer_rejects_evm(client: TestClient) -> None:
    create = client.post("/api/wallet", json={"label": "evm", "chain": "evm"}).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_solana_transfer",
        json={
            "to": RECIPIENT,
            "amount": "0.5",
            "recent_blockhash": ZERO_BLOCKHASH,
        },
    )
    assert r.status_code == 400
    assert "solana wallet" in r.json()["detail"]


def test_http_sign_solana_transfer_unknown_wallet(client: TestClient) -> None:
    r = client.post(
        "/api/wallet/wlt_deadbeef/sign_solana_transfer",
        json={
            "to": RECIPIENT,
            "amount": "0.5",
            "recent_blockhash": ZERO_BLOCKHASH,
        },
    )
    assert r.status_code == 404


def test_http_sign_solana_transfer_invalid_amount(client: TestClient) -> None:
    create = client.post(
        "/api/wallet", json={"label": "sol", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    r = client.post(
        f"/api/wallet/{wid}/sign_solana_transfer",
        json={
            "to": RECIPIENT,
            "amount": "abc",
            "recent_blockhash": ZERO_BLOCKHASH,
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_pack_action_sign_solana_transfer() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="sol", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_solana_transfer"].handler(
        {
            "wallet_id": wallet.id,
            "to": RECIPIENT,
            "amount": "0.1",
            "recent_blockhash": ZERO_BLOCKHASH,
        }
    )
    assert out["ok"] is True
    assert out["signed"]["tx_signature"]


@pytest.mark.asyncio
async def test_pack_action_sign_solana_transfer_rejects_evm() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="evm", chain=WalletChain.EVM)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_solana_transfer"].handler(
        {
            "wallet_id": wallet.id,
            "to": RECIPIENT,
            "amount": "0.1",
            "recent_blockhash": ZERO_BLOCKHASH,
        }
    )
    assert out["ok"] is False
    assert "solana wallet" in out["error"]


@pytest.mark.asyncio
async def test_pack_action_sign_solana_transfer_missing_args() -> None:
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    out = await by_id["sign_solana_transfer"].handler({"wallet_id": "anything"})
    assert out["ok"] is False
    assert "required" in out["error"]


def test_pack_action_destructive_flag() -> None:
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["sign_solana_transfer"].destructive is True


# ---------- service end-to-end ----------------------------------------


@pytest.mark.asyncio
async def test_service_sign_solana_transfer_signer_matches_address() -> None:
    """The wallet's stored address matches the signer field of the
    signed tx — proves the same private key was used end-to-end."""
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="sol", chain=WalletChain.SOLANA)
    out = await svc.sign_solana_transfer(
        wallet_id=wallet.id,
        to=RECIPIENT,
        lamports=1_000,
        recent_blockhash=ZERO_BLOCKHASH,
    )
    assert out["signer"] == wallet.address


@pytest.mark.asyncio
async def test_service_sign_solana_transfer_unknown_wallet_raises() -> None:
    svc = get_wallet_service()
    with pytest.raises(WalletError) as exc:
        await svc.sign_solana_transfer(
            wallet_id="wlt_deadbeef",
            to=RECIPIENT,
            lamports=1,
            recent_blockhash=ZERO_BLOCKHASH,
        )
    assert "wallet_not_found" in str(exc.value)
