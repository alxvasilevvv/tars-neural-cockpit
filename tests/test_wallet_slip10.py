"""SLIP-0010 ed25519 derivation contract tests (Phase O3).

Pinned against:

1. The official **SLIP-0010 ed25519** test vector (master node from
   the seed ``000102030405060708090a0b0c0d0e0f``) — proves our
   primitive matches the spec.
2. The canonical 12-word BIP-39 zero mnemonic
   (``"abandon abandon … about"``) at path ``m/44'/501'/0'/0'`` —
   this is the path Phantom / Solflare / Backpack use, so anyone
   running the verification can re-import that mnemonic into their
   wallet of choice and confirm the address matches.

Coverage:

- Master node bytes match the SLIP-0010 spec.
- Phantom-default path produces the expected Base58 address.
- ``account`` index changes the derived address.
- Wallet service end-to-end: ``create_wallet(..., derivation_scheme=
  "bip44-501-phantom")`` stores the scheme in SQLite and returns it
  in the API response.
- Schemes are mutually independent: same mnemonic, different scheme
  → different addresses.
- Unknown scheme rejected with `WalletError`.
- Migration: old wallets without the column default to ``tars-v1``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.crypto.recovery import mnemonic_to_seed
from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.wallet import (
    WalletChain,
    WalletError,
    get_wallet_service,
    reset_wallet_service_for_tests,
)
from backend.core.wallet.slip10 import (
    HARDENED_OFFSET,
    _ckd_priv,
    _master_node,
    derive_solana_phantom,
)


# -----------------------------------------------------------------------
# SLIP-0010 §3 official test vector (ed25519, seed = bytes 0x00..0x0f).
# https://github.com/satoshilabs/slips/blob/master/slip-0010.md#test-vector-1-for-ed25519
# -----------------------------------------------------------------------

SLIP10_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
SLIP10_MASTER_PRIV = "2b4be7f19ee27bbf30c667b642d5f4aa69fd169872f8fc3059c08ebae2eb19e7"
SLIP10_MASTER_CC = "90046a93de5380a72b5e45010748567d5ea02bbf6522f979e05c0d8d8ca9fffb"


def test_slip10_master_node_matches_spec() -> None:
    sk, cc = _master_node(SLIP10_SEED)
    assert sk.hex() == SLIP10_MASTER_PRIV
    assert cc.hex() == SLIP10_MASTER_CC


def test_slip10_ckd_priv_hardened() -> None:
    """Each CKD step must mix in the hardened-offset index."""
    sk_master, cc_master = _master_node(SLIP10_SEED)
    sk_a, _ = _ckd_priv(sk_master, cc_master, 0)
    sk_b, _ = _ckd_priv(sk_master, cc_master, HARDENED_OFFSET)
    # 0 and HARDENED_OFFSET should produce the SAME child (the
    # function adds the offset when missing).
    assert sk_a == sk_b


# -----------------------------------------------------------------------
# Phantom-default derivation against the canonical zero mnemonic.
# -----------------------------------------------------------------------

ZERO_MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)
EXPECTED_PHANTOM_ADDR = "HAgk14JpMQLgt6rVgv7cBQFJWFto5Dqxi472uT3DKpqk"


def test_phantom_zero_mnemonic_matches_published_vector() -> None:
    seed = mnemonic_to_seed(ZERO_MNEMONIC)
    derived = derive_solana_phantom(seed, account=0, change=0)
    assert derived.address == EXPECTED_PHANTOM_ADDR
    assert derived.derivation_path == "m/44'/501'/0'/0'"
    assert len(derived.private_key) == 32
    assert len(derived.public_key) == 32


def test_phantom_account_index_changes_address() -> None:
    seed = mnemonic_to_seed(ZERO_MNEMONIC)
    a = derive_solana_phantom(seed, account=0)
    b = derive_solana_phantom(seed, account=1)
    assert a.address != b.address
    assert a.derivation_path != b.derivation_path


def test_phantom_address_is_deterministic() -> None:
    seed = mnemonic_to_seed(ZERO_MNEMONIC)
    a = derive_solana_phantom(seed)
    b = derive_solana_phantom(seed)
    assert a.address == b.address
    assert a.private_key == b.private_key


# -----------------------------------------------------------------------
# End-to-end through the wallet service / HTTP route.
# -----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_slip10_")
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


@pytest.mark.asyncio
async def test_service_phantom_scheme_yields_phantom_address() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(
        label="phantom",
        chain=WalletChain.SOLANA,
        mnemonic=ZERO_MNEMONIC,
        derivation_scheme="bip44-501-phantom",
    )
    assert wallet.address == EXPECTED_PHANTOM_ADDR
    assert wallet.derivation_scheme == "bip44-501-phantom"
    assert wallet.derivation_path == "m/44'/501'/0'/0'"


@pytest.mark.asyncio
async def test_service_default_scheme_differs_from_phantom() -> None:
    """Same mnemonic + tars-v1 → different (legacy) address."""
    svc = get_wallet_service()
    wallet_default, _ = await svc.create_wallet(
        label="legacy",
        chain=WalletChain.SOLANA,
        mnemonic=ZERO_MNEMONIC,
    )
    assert wallet_default.derivation_scheme == "tars-v1"
    assert wallet_default.address != EXPECTED_PHANTOM_ADDR


@pytest.mark.asyncio
async def test_service_unknown_scheme_rejected() -> None:
    svc = get_wallet_service()
    with pytest.raises(WalletError):
        await svc.create_wallet(
            label="bad",
            chain=WalletChain.SOLANA,
            derivation_scheme="cosmic-unknown-v9",
        )


def test_http_create_with_phantom_scheme(client: TestClient) -> None:
    r = client.post(
        "/api/wallet",
        json={
            "label": "phantom-test",
            "chain": "solana",
            "derivation_scheme": "bip44-501-phantom",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["wallet"]["derivation_scheme"] == "bip44-501-phantom"
    # Path is the BIP-44 / 501 / 0' / 0' shape, not the legacy m/tars/v1/...
    assert body["wallet"]["derivation_path"].startswith("m/44'/501'")


def test_http_import_with_phantom_scheme(client: TestClient) -> None:
    r = client.post(
        "/api/wallet/import",
        json={
            "label": "phantom-imported",
            "chain": "solana",
            "mnemonic": ZERO_MNEMONIC,
            "derivation_scheme": "bip44-501-phantom",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["wallet"]["address"] == EXPECTED_PHANTOM_ADDR


def test_http_unknown_scheme_returns_envelope(client: TestClient) -> None:
    r = client.post(
        "/api/wallet",
        json={
            "label": "bad",
            "chain": "solana",
            "derivation_scheme": "lol-nope",
        },
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert "derivation_scheme" in body["message"]


def test_http_default_scheme_when_omitted(client: TestClient) -> None:
    r = client.post("/api/wallet", json={"label": "default", "chain": "solana"})
    assert r.status_code == 200
    assert r.json()["wallet"]["derivation_scheme"] == "tars-v1"


# -----------------------------------------------------------------------
# Migration safety: old DB without the column.
# -----------------------------------------------------------------------


def test_migration_adds_column_on_legacy_db(monkeypatch) -> None:
    """A DB that pre-dates the migration should pick up the new
    column on first connect, and existing rows default to tars-v1."""

    import sqlite3

    tmp = tempfile.mkdtemp(prefix="tars_slip10_legacy_")
    db_path = os.path.join(tmp, "wallets.sqlite")
    # Hand-craft a pre-O3 schema (no derivation_scheme column).
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE wallets (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            chain TEXT NOT NULL,
            address TEXT NOT NULL,
            public_key_hex TEXT NOT NULL,
            derivation_path TEXT NOT NULL,
            seed_fingerprint TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        INSERT INTO wallets VALUES (
            'wlt_legacy', 'old', 'solana', 'addr', '00', 'm/x', null, 0, 0, '{}'
        );
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("TARS_WALLETS_DB_PATH", db_path)
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "secrets.json")
    )
    reset_wallet_service_for_tests()

    svc = get_wallet_service()
    # Migration runs in __init__; column should now exist.
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(wallets)").fetchall()}
    conn.close()
    assert "derivation_scheme" in cols
    # Legacy row should default to tars-v1 when read.
    import asyncio

    wallet = asyncio.run(svc.get_wallet("wlt_legacy"))
    assert wallet is not None
    assert wallet.derivation_scheme == "tars-v1"
