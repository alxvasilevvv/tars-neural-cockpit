"""Phase L5 — end-to-end test: pair a device, encrypt to it, decrypt.

This test ties the three modules together:

- ``backend.core.pairing.store`` (host knows the device pubkey).
- ``backend.core.crypto`` (XChaCha20-Poly1305 + X25519 envelope).
- ``backend.core.meeet`` client (1.1.0 contract event with envelope).

A 1.0.0 consumer ignoring the new fields would still see a valid
``payload`` (empty dict in our convention); a 1.1.0 paired device
unwraps the envelope and decrypts the real payload.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from nacl.public import PrivateKey

from backend.core.crypto import (
    DeviceKey,
    decrypt_event,
    encrypt_event,
)
from backend.core.meeet import (
    BASELINE_CONTRACT_VERSION,
    ENCRYPTED_CONTRACT_VERSION,
    MeeetConfig,
    MeeetStore,
    trace_scope,
)
from backend.core.meeet.client import MeeetClient
from backend.core.pairing.store import (
    PairingStore,
    _reset_singleton_for_tests,
)


@pytest.fixture(autouse=True)
def reset_pairing(monkeypatch):
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    _reset_singleton_for_tests()
    yield
    _reset_singleton_for_tests()


def _client_keypair() -> tuple[PrivateKey, str]:
    sk = PrivateKey.generate()
    return sk, base64.b64encode(bytes(sk.public_key)).decode("ascii")


def test_pair_device_then_encrypt_for_it_and_decrypt() -> None:
    store = PairingStore()
    client_sk, client_epk = _client_keypair()

    rec = asyncio.run(
        store.begin(client_epk=client_epk, client_kind="mobile_ios")
    )
    asyncio.run(store.accept(token=rec.accept_token))

    paired_keys = store.device_keys()
    assert len(paired_keys) == 1
    paired = paired_keys[0]
    assert paired.public_key == bytes(client_sk.public_key)

    # Host encrypts a payload addressed to the paired device.
    sealed = encrypt_event(
        payload={"text": "Иди дальше по плану", "lang": "ru"},
        recipients=[paired],
        trace_id="trc_e2e",
        kind="chat.message.completed",
    )
    assert sealed.envelope.recipient_keys[0]["device_id"] == paired.device_id

    # The mobile device opens the envelope with its secret key.
    device_for_decrypt = DeviceKey(
        device_id=paired.device_id,
        public_key=bytes(client_sk.public_key),
        secret_key=bytes(client_sk),
    )
    out = decrypt_event(
        ciphertext=sealed.ciphertext,
        envelope=sealed.envelope.to_dict(),
        recipient=device_for_decrypt,
        trace_id="trc_e2e",
        kind="chat.message.completed",
    )
    assert out == {"text": "Иди дальше по плану", "lang": "ru"}


def test_emit_encrypted_event_lands_in_store_with_envelope(tmp_path: Path) -> None:
    pair_store = PairingStore()
    client_sk, client_epk = _client_keypair()
    rec = asyncio.run(
        pair_store.begin(client_epk=client_epk, client_kind="desktop_windows")
    )
    asyncio.run(pair_store.accept(token=rec.accept_token))
    paired = pair_store.device_keys()[0]

    cfg = MeeetConfig(
        ingest_url=None,
        contract_version=BASELINE_CONTRACT_VERSION,
        api_key=None,
        source="tars",
        local_log_path=None,
    )
    meeet_store = MeeetStore(str(tmp_path / "meeet.sqlite"))
    client = MeeetClient(cfg, store=meeet_store)

    async def _emit() -> dict:
        # Encrypt under the same trace context that emit() will see —
        # the AAD binds ciphertext to trace_id|kind.
        with trace_scope(parent="trc_emit") as trace_id:
            sealed = encrypt_event(
                payload={"text": "encrypted body"},
                recipients=[paired],
                trace_id=trace_id,
                kind="chat.message.completed",
            )
            return await client.emit(
                "chat.message.completed",
                payload={},
                **sealed.to_kwargs(),
            )

    body = asyncio.run(_emit())
    assert body["contract_version"] == ENCRYPTED_CONTRACT_VERSION
    assert body["ciphertext"]

    # Round-trip the SQLite store: envelope + ciphertext stay intact.
    rows = asyncio.run(meeet_store.list_events(kind="chat.message.completed"))
    assert len(rows) == 1
    row = rows[0]
    assert row.contract_version == ENCRYPTED_CONTRACT_VERSION
    assert row.ciphertext == body["ciphertext"]

    # And the device can still decrypt it from the store row directly.
    device_for_decrypt = DeviceKey(
        device_id=paired.device_id,
        public_key=bytes(client_sk.public_key),
        secret_key=bytes(client_sk),
    )
    out = decrypt_event(
        ciphertext=row.ciphertext or "",
        envelope=row.envelope or {},
        recipient=device_for_decrypt,
        trace_id=row.trace_id,
        kind=row.kind,
    )
    assert out == {"text": "encrypted body"}


def test_revoking_device_drops_its_pubkey() -> None:
    store = PairingStore()
    _client_sk, client_epk = _client_keypair()
    rec = asyncio.run(store.begin(client_epk=client_epk, client_kind="mobile_android"))
    asyncio.run(store.accept(token=rec.accept_token))
    assert store.device_keys()
    paired = store.device_keys()[0]
    assert asyncio.run(store.revoke(device_id=paired.device_id)) is True
    assert store.device_keys() == ()
