"""Phase L5 — sync envelope (XChaCha20-Poly1305 + X25519) tests."""

from __future__ import annotations

import base64

import pytest

from backend.core.crypto import (
    DeviceKey,
    SealedEvent,
    decode_envelope,
    decrypt_event,
    encrypt_event,
    generate_device_key,
)
from backend.core.crypto.envelope import SCHEME


def test_generate_device_key_returns_valid_pair() -> None:
    k = generate_device_key("dev_a")
    assert k.device_id == "dev_a"
    assert len(k.public_key) == 32
    assert k.secret_key is not None and len(k.secret_key) == 32
    pub_only = k.to_public()
    assert pub_only.secret_key is None
    assert pub_only.public_key == k.public_key


def test_round_trip_single_recipient() -> None:
    rec = generate_device_key("dev_a")
    sealed = encrypt_event(
        payload={"text": "hello world", "lang": "en"},
        recipients=[rec.to_public()],
        trace_id="trc_x",
        kind="chat.message.completed",
    )
    assert isinstance(sealed, SealedEvent)
    assert sealed.envelope.scheme == SCHEME
    assert sealed.ciphertext  # base64 string

    out = decrypt_event(
        ciphertext=sealed.ciphertext,
        envelope=sealed.envelope.to_dict(),
        recipient=rec,
        trace_id="trc_x",
        kind="chat.message.completed",
    )
    assert out == {"text": "hello world", "lang": "en"}


def test_round_trip_multi_recipient() -> None:
    a = generate_device_key("dev_a")
    b = generate_device_key("dev_b")
    sealed = encrypt_event(
        payload={"x": 1},
        recipients=[a.to_public(), b.to_public()],
        trace_id="trc_x",
        kind="x.evt",
    )
    assert {row["device_id"] for row in sealed.envelope.recipient_keys} == {
        "dev_a",
        "dev_b",
    }
    # Each recipient can independently decrypt the same content.
    for recipient in (a, b):
        out = decrypt_event(
            ciphertext=sealed.ciphertext,
            envelope=sealed.envelope.to_dict(),
            recipient=recipient,
            trace_id="trc_x",
            kind="x.evt",
        )
        assert out == {"x": 1}


def test_decrypt_with_wrong_key_fails() -> None:
    a = generate_device_key("dev_a")
    intruder = generate_device_key("dev_a")  # same device_id, different keys
    sealed = encrypt_event(
        payload={"secret": "do not leak"},
        recipients=[a.to_public()],
        trace_id="t",
        kind="k",
    )
    with pytest.raises(Exception):
        decrypt_event(
            ciphertext=sealed.ciphertext,
            envelope=sealed.envelope.to_dict(),
            recipient=intruder,
            trace_id="t",
            kind="k",
        )


def test_decrypt_with_unknown_device_id_raises() -> None:
    a = generate_device_key("dev_a")
    b = generate_device_key("dev_b")
    sealed = encrypt_event(
        payload={"x": 1},
        recipients=[a.to_public()],
        trace_id="t",
        kind="k",
    )
    with pytest.raises(ValueError, match="not in envelope"):
        decrypt_event(
            ciphertext=sealed.ciphertext,
            envelope=sealed.envelope.to_dict(),
            recipient=b,
            trace_id="t",
            kind="k",
        )


def test_associated_data_binds_event_metadata() -> None:
    """Tampering with kind/trace_id MUST invalidate the AEAD tag."""

    a = generate_device_key("dev_a")
    sealed = encrypt_event(
        payload={"x": 1},
        recipients=[a.to_public()],
        trace_id="trc_x",
        kind="chat.message.completed",
    )
    with pytest.raises(Exception):
        decrypt_event(
            ciphertext=sealed.ciphertext,
            envelope=sealed.envelope.to_dict(),
            recipient=a,
            trace_id="trc_x",
            kind="chat.message.STOLEN",  # wrong kind
        )
    with pytest.raises(Exception):
        decrypt_event(
            ciphertext=sealed.ciphertext,
            envelope=sealed.envelope.to_dict(),
            recipient=a,
            trace_id="trc_y",  # wrong trace
            kind="chat.message.completed",
        )


def test_encrypt_event_rejects_empty_recipients() -> None:
    with pytest.raises(ValueError):
        encrypt_event(payload={"x": 1}, recipients=[], trace_id="t", kind="k")


def test_encrypt_event_rejects_invalid_pubkey_length() -> None:
    bad = DeviceKey(device_id="bad", public_key=b"\x01" * 7)
    with pytest.raises(ValueError):
        encrypt_event(payload={"x": 1}, recipients=[bad], trace_id="t", kind="k")


def test_decode_envelope_handles_garbage() -> None:
    assert decode_envelope(None) is None
    assert decode_envelope({"scheme": "foo"}) is None  # missing nonce
    assert decode_envelope({}) is None
    parsed = decode_envelope(
        {
            "scheme": SCHEME,
            "nonce": "AAAA",
            "epk": "BBBB",
            "recipient_keys": [{"device_id": "x", "wrapped_key": "y"}],
        }
    )
    assert parsed is not None
    assert parsed.scheme == SCHEME
    assert parsed.recipient_keys[0]["device_id"] == "x"


def test_envelope_recipient_keys_are_base64_urlsafe_decodable() -> None:
    """Sanity: every wrapped_key the encrypter emits is valid base64."""

    k = generate_device_key("dev_a")
    sealed = encrypt_event(
        payload={"x": 1}, recipients=[k.to_public()], trace_id="t", kind="k"
    )
    for row in sealed.envelope.recipient_keys:
        decoded = base64.b64decode(row["wrapped_key"].encode("ascii"))
        # SealedBox: 32-byte epk + ciphertext + 16-byte tag, content key is 32 bytes.
        assert len(decoded) == 32 + 32 + 16
