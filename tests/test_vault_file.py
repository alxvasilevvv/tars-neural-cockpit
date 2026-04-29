"""Phase L5 K1 — file-backed keyring vault tests."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from backend.core.crypto import generate_device_key
from backend.core.vault import (
    FileKeyringVault,
    StoredHostIdentity,
    VaultCorruptError,
    VaultPermissionError,
)


# ---------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------


def test_save_load_round_trip_no_passphrase(tmp_path: Path) -> None:
    vault = FileKeyringVault(tmp_path / "host.json")
    key = generate_device_key("host_a")
    saved = vault.save(key, recovery_fingerprint="DEADBEEF1234")
    assert isinstance(saved, StoredHostIdentity)
    assert saved.recovery_fingerprint == "DEADBEEF1234"
    assert vault.exists()

    again = FileKeyringVault(tmp_path / "host.json")
    loaded = again.load()
    assert loaded is not None
    assert loaded.host_id == "host_a"
    assert loaded.device_key.public_key == key.public_key
    assert loaded.device_key.secret_key == key.secret_key
    assert loaded.recovery_fingerprint == "DEADBEEF1234"


def test_save_load_round_trip_with_passphrase(tmp_path: Path) -> None:
    vault_a = FileKeyringVault(tmp_path / "host.json", passphrase="correct horse")
    key = generate_device_key("host_b")
    vault_a.save(key)
    loaded = FileKeyringVault(
        tmp_path / "host.json", passphrase="correct horse"
    ).load()
    assert loaded is not None
    assert loaded.device_key.secret_key == key.secret_key


def test_load_with_wrong_passphrase_raises(tmp_path: Path) -> None:
    vault = FileKeyringVault(tmp_path / "host.json", passphrase="correct horse")
    vault.save(generate_device_key("host_c"))

    bad = FileKeyringVault(tmp_path / "host.json", passphrase="wrong horse")
    with pytest.raises(VaultCorruptError):
        bad.load()


def test_load_with_no_file_returns_none(tmp_path: Path) -> None:
    assert FileKeyringVault(tmp_path / "missing.json").load() is None


# ---------------------------------------------------------------------
# Persistence semantics
# ---------------------------------------------------------------------


def test_file_is_chmodded_to_0600(tmp_path: Path) -> None:
    vault = FileKeyringVault(tmp_path / "host.json")
    vault.save(generate_device_key("host_d"))
    if os.name != "posix":
        return  # permission semantics differ on Windows
    mode = stat.S_IMODE(os.stat(tmp_path / "host.json").st_mode)
    assert mode == 0o600


def test_widening_permissions_blocks_load(tmp_path: Path) -> None:
    if os.name != "posix":
        return
    path = tmp_path / "host.json"
    vault = FileKeyringVault(path)
    vault.save(generate_device_key("host_e"))
    os.chmod(path, 0o644)
    with pytest.raises(VaultPermissionError):
        vault.load()


def test_save_is_atomic_via_temp_file(tmp_path: Path) -> None:
    vault = FileKeyringVault(tmp_path / "host.json")
    vault.save(generate_device_key("host_f"))
    # No leftover .tmp file in the parent dir.
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


# ---------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------


def test_rotate_replaces_secret_and_records_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "host.json"
    vault = FileKeyringVault(path)
    first = vault.save(generate_device_key("host_g"))

    new_key = generate_device_key("host_g")
    rotated = vault.rotate(new_key, recovery_fingerprint="NEWFP123")

    assert rotated.created_at == first.created_at  # preserved
    assert rotated.rotated_at is not None
    assert rotated.rotated_at >= first.created_at
    assert rotated.recovery_fingerprint == "NEWFP123"

    loaded = FileKeyringVault(path).load()
    assert loaded is not None
    assert loaded.device_key.secret_key == new_key.secret_key
    assert loaded.device_key.secret_key != first.device_key.secret_key


# ---------------------------------------------------------------------
# Corruption / tampering
# ---------------------------------------------------------------------


def test_tampering_with_ciphertext_raises(tmp_path: Path) -> None:
    path = tmp_path / "host.json"
    vault = FileKeyringVault(path)
    vault.save(generate_device_key("host_h"))

    blob = json.loads(path.read_text())
    blob["secret"]["ciphertext"] = (
        blob["secret"]["ciphertext"][:-2] + "AA"
    )
    if os.name == "posix":
        os.chmod(path, 0o600)
    path.write_text(json.dumps(blob))
    if os.name == "posix":
        os.chmod(path, 0o600)

    with pytest.raises(VaultCorruptError):
        vault.load()


def test_tampering_with_public_key_raises(tmp_path: Path) -> None:
    """Mismatched public/secret pair must be rejected."""

    path = tmp_path / "host.json"
    vault = FileKeyringVault(path)
    vault.save(generate_device_key("host_i"))

    blob = json.loads(path.read_text())
    other = generate_device_key("host_j")
    import base64 as _b

    blob["public_key"] = _b.b64encode(other.public_key).decode("ascii")
    if os.name == "posix":
        os.chmod(path, 0o600)
    path.write_text(json.dumps(blob))
    if os.name == "posix":
        os.chmod(path, 0o600)

    with pytest.raises(VaultCorruptError, match="doesn't match"):
        vault.load()


def test_garbage_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "host.json"
    path.write_text("{not even valid json")
    if os.name == "posix":
        os.chmod(path, 0o600)
    with pytest.raises(VaultCorruptError):
        FileKeyringVault(path).load()


def test_clear_removes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "host.json"
    vault = FileKeyringVault(path)
    vault.save(generate_device_key("host_k"))
    assert vault.exists()
    vault.clear()
    assert not vault.exists()
    # Idempotent — clearing a missing file is fine.
    vault.clear()
