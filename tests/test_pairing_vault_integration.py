"""Phase L5 K1 — PairingStore × FileKeyringVault integration tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.pairing.store import (
    PairingStore,
    _reset_singleton_for_tests,
)
from backend.core.vault import FileKeyringVault
from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


@pytest.fixture(autouse=True)
def disable_default_vault(monkeypatch):
    # Make sure the singleton path uses an isolated vault per test.
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    _reset_singleton_for_tests()
    yield
    _reset_singleton_for_tests()


def test_store_persists_identity_across_restarts(tmp_path: Path) -> None:
    vault_path = tmp_path / "host.json"

    a = PairingStore(vault=FileKeyringVault(vault_path))
    b = PairingStore(vault=FileKeyringVault(vault_path))

    assert a.host_id == b.host_id
    assert a.host_public_key_b64 == b.host_public_key_b64
    assert a.identity_was_freshly_minted is True
    assert b.identity_was_loaded is True
    assert b.identity_was_freshly_minted is False


def test_store_without_vault_mints_fresh_identity_each_time() -> None:
    a = PairingStore()
    b = PairingStore()
    assert a.host_id != b.host_id
    assert a.identity_was_freshly_minted is True
    assert b.identity_was_freshly_minted is True


def test_rotate_host_identity_changes_pubkey(tmp_path: Path) -> None:
    vault = FileKeyringVault(tmp_path / "host.json")
    store = PairingStore(vault=vault)
    before_pub = store.host_public_key_b64
    new_key = store.rotate_host_identity(recovery_fingerprint="ROT123")
    assert new_key.public_b64 != before_pub
    assert store.host_public_key_b64 == new_key.public_b64
    assert store.recovery_fingerprint == "ROT123"

    # And subsequent open finds the rotated key, not the original.
    fresh = PairingStore(vault=FileKeyringVault(tmp_path / "host.json"))
    assert fresh.host_public_key_b64 == new_key.public_b64
    assert fresh.recovery_fingerprint == "ROT123"


def test_pairing_remains_functional_with_vault(tmp_path: Path) -> None:
    """Smoke: end-to-end begin/accept still works with a vault."""

    import base64
    from nacl.public import PrivateKey

    vault = FileKeyringVault(tmp_path / "host.json")
    store = PairingStore(vault=vault)
    client_epk = base64.b64encode(
        bytes(PrivateKey.generate().public_key)
    ).decode("ascii")
    rec = asyncio.run(store.begin(client_epk=client_epk, client_kind="mobile_ios"))
    rec2 = asyncio.run(store.accept(token=rec.accept_token))
    assert rec2.state == "linked"
    assert rec2.host_public_key == store.host_public_key_b64


# ---------------------------------------------------------------------
# /api/pairing/identity surface
# ---------------------------------------------------------------------


def test_identity_endpoint_reports_vault_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TARS_PAIRING_VAULT_PATH", str(tmp_path / "host.json"))
    monkeypatch.setenv("TARS_PAIRING_VAULT", "enabled")
    monkeypatch.setenv("TARS_PAIRING_VAULT_PASSPHRASE", "")
    _reset_singleton_for_tests()

    c = TestClient(app)
    r1 = c.get("/api/pairing/identity")
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["vault"]["configured"] is True
    assert body1["vault"]["freshly_minted"] is True
    assert body1["vault"]["loaded_from_disk"] is False

    # New process: drop the singleton so the next access re-loads.
    _reset_singleton_for_tests()
    r2 = c.get("/api/pairing/identity")
    body2 = r2.json()
    assert body2["host_id"] == body1["host_id"]
    assert body2["host_public_key"] == body1["host_public_key"]
    assert body2["vault"]["loaded_from_disk"] is True
    assert body2["vault"]["freshly_minted"] is False
