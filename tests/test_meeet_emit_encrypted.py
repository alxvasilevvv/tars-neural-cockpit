"""``MeeetClient.emit_encrypted`` convenience wrapper.

The bare :meth:`MeeetClient.emit` accepts ``ciphertext`` + ``envelope``
kwargs but the caller is responsible for grabbing paired device keys,
calling :func:`backend.core.crypto.encrypt_event`, and binding the AAD
trace id correctly. That's ~10 lines of boilerplate per call site
(`tests/test_pairing_envelope_e2e.py:test_emit_encrypted_event_lands_in_store_with_envelope`
demonstrates the bare-emit pattern).

`emit_encrypted` collapses that into one call:

- Pulls paired devices from the singleton ``PairingStore`` when
  ``recipients`` is omitted.
- Pins the trace id BEFORE sealing so the AAD ``trace_id|kind`` binding
  matches what ``emit()`` stamps.
- Falls through to plain ``emit()`` when no devices are paired (unless
  ``require_recipients=True`` opts into a strict-failure mode).

These tests pin all three contracts.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from nacl.public import PrivateKey

from backend.core.crypto import DeviceKey, decrypt_event
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
import backend.core.pairing.store as pairing_store_mod


@pytest.fixture(autouse=True)
def reset_pairing(monkeypatch):
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    # Force in-memory pairings so each test starts from zero devices —
    # without this, ``_pair_one_device`` reuses
    # ``~/.tars/pairings.sqlite`` and ``device_keys()[0]`` may return a
    # device from a previous run (different secret key → decrypt fails).
    monkeypatch.setenv("TARS_PAIRINGS_DB", "disabled")
    _reset_singleton_for_tests()
    yield
    _reset_singleton_for_tests()


def _client_keypair() -> tuple[PrivateKey, str]:
    sk = PrivateKey.generate()
    return sk, base64.b64encode(bytes(sk.public_key)).decode("ascii")


def _make_client(tmp_path: Path) -> MeeetClient:
    cfg = MeeetConfig(
        ingest_url=None,
        contract_version=BASELINE_CONTRACT_VERSION,
        api_key=None,
        source="tars",
        local_log_path=None,
    )
    return MeeetClient(cfg, store=MeeetStore(str(tmp_path / "meeet.sqlite")))


def _pair_one_device(monkeypatch) -> tuple[DeviceKey, PrivateKey]:
    """Spin a PairingStore singleton with exactly one paired device.

    Returns the recipient public-side ``DeviceKey`` and the device's
    secret key (so the test can decrypt the round-trip).
    """

    pair_store = PairingStore()
    monkeypatch.setattr(
        pairing_store_mod, "_singleton", pair_store, raising=False
    )

    client_sk, client_epk = _client_keypair()
    rec = asyncio.run(
        pair_store.begin(client_epk=client_epk, client_kind="mobile_ios")
    )
    asyncio.run(pair_store.accept(token=rec.accept_token))
    paired = pair_store.device_keys()[0]
    return paired, client_sk


# ----------------------------------------------------------------- happy path


def test_emit_encrypted_uses_singleton_pairing_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default path: caller passes no recipients, helper resolves them
    from the singleton ``PairingStore``, seals once, emits."""

    paired, client_sk = _pair_one_device(monkeypatch)
    client = _make_client(tmp_path)

    body = asyncio.run(
        client.emit_encrypted(
            "chat.message.completed",
            payload={"text": "round-trip me", "lang": "en"},
        )
    )

    assert body["contract_version"] == ENCRYPTED_CONTRACT_VERSION
    assert body["payload"] == {}, "actual payload must be sealed inside ciphertext"
    assert body["ciphertext"], "must have a ciphertext blob"
    assert body["envelope"]["scheme"].startswith("xchacha20-poly1305"), (
        "envelope must declare the v1 scheme"
    )

    # The paired device decrypts cleanly with its secret key.
    device_for_decrypt = DeviceKey(
        device_id=paired.device_id,
        public_key=bytes(client_sk.public_key),
        secret_key=bytes(client_sk),
    )
    out = decrypt_event(
        ciphertext=body["ciphertext"],
        envelope=body["envelope"],
        recipient=device_for_decrypt,
        trace_id=body["trace_id"],
        kind=body["kind"],
    )
    assert out == {"text": "round-trip me", "lang": "en"}


def test_emit_encrypted_accepts_explicit_recipients(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the caller passes ``recipients=`` explicitly the helper
    skips the singleton lookup. Useful for fan-out integration tests
    or when the caller wants to send to a subset of paired devices."""

    # Drop the singleton so a stray import doesn't accidentally fall back to it.
    pairing_store_mod._singleton = PairingStore()

    sk = PrivateKey.generate()
    explicit = DeviceKey(
        device_id="dev_explicit",
        public_key=bytes(sk.public_key),
    )
    client = _make_client(tmp_path)

    body = asyncio.run(
        client.emit_encrypted(
            "chat.message.completed",
            payload={"text": "explicit recipient"},
            recipients=[explicit],
        )
    )
    assert body["contract_version"] == ENCRYPTED_CONTRACT_VERSION

    decrypt_key = DeviceKey(
        device_id="dev_explicit",
        public_key=bytes(sk.public_key),
        secret_key=bytes(sk),
    )
    out = decrypt_event(
        ciphertext=body["ciphertext"],
        envelope=body["envelope"],
        recipient=decrypt_key,
        trace_id=body["trace_id"],
        kind=body["kind"],
    )
    assert out == {"text": "explicit recipient"}


# ------------------------------------------------------------------- AAD bind


def test_emit_encrypted_pins_trace_id_before_sealing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The AAD ``trace_id|kind`` must match between encrypt_event() and
    the trace id stamped on the emitted body — otherwise a paired
    device can never decrypt because the AAD won't verify."""

    paired, client_sk = _pair_one_device(monkeypatch)
    client = _make_client(tmp_path)

    # No outer trace_scope — emit_encrypted must mint one and reuse it
    # for both the AAD and the wire body.
    body = asyncio.run(
        client.emit_encrypted("chat.message.completed", payload={"text": "x"})
    )
    assert body["trace_id"]

    # Decrypt under the body's trace id should succeed; under a wrong
    # trace id should fail (AAD mismatch).
    decrypt_key = DeviceKey(
        device_id=paired.device_id,
        public_key=bytes(client_sk.public_key),
        secret_key=bytes(client_sk),
    )
    out = decrypt_event(
        ciphertext=body["ciphertext"],
        envelope=body["envelope"],
        recipient=decrypt_key,
        trace_id=body["trace_id"],
        kind=body["kind"],
    )
    assert out == {"text": "x"}

    with pytest.raises(Exception):
        decrypt_event(
            ciphertext=body["ciphertext"],
            envelope=body["envelope"],
            recipient=decrypt_key,
            trace_id="trc_wrong",
            kind=body["kind"],
        )


def test_emit_encrypted_reuses_outer_trace_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When called inside a ``trace_scope``, the helper must reuse the
    outer trace id (no extra scope nesting that would shadow it)."""

    paired, client_sk = _pair_one_device(monkeypatch)
    client = _make_client(tmp_path)

    async def inside_scope():
        with trace_scope(parent="trc_outer_e2e") as tid:
            body = await client.emit_encrypted(
                "chat.message.completed", payload={"text": "outer scope"}
            )
            return tid, body

    tid, body = asyncio.run(inside_scope())
    assert tid == "trc_outer_e2e"
    assert body["trace_id"] == "trc_outer_e2e"

    decrypt_key = DeviceKey(
        device_id=paired.device_id,
        public_key=bytes(client_sk.public_key),
        secret_key=bytes(client_sk),
    )
    out = decrypt_event(
        ciphertext=body["ciphertext"],
        envelope=body["envelope"],
        recipient=decrypt_key,
        trace_id="trc_outer_e2e",
        kind="chat.message.completed",
    )
    assert out == {"text": "outer scope"}


# -------------------------------------------------------------------- degrade


def test_emit_encrypted_degrades_when_no_recipients(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No paired devices + ``require_recipients=False`` (default) →
    helper falls through to plain :meth:`emit` so cockpit-only operators
    don't have to fork their call sites."""

    pairing_store_mod._singleton = PairingStore()  # empty
    client = _make_client(tmp_path)

    body = asyncio.run(
        client.emit_encrypted(
            "chat.message.completed",
            payload={"text": "no devices"},
        )
    )
    assert body["contract_version"] == BASELINE_CONTRACT_VERSION
    assert body["payload"] == {"text": "no devices"}
    assert "ciphertext" not in body
    assert "envelope" not in body


def test_emit_encrypted_strict_mode_raises_without_recipients(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``require_recipients=True`` is the e2e-privacy guarantee: refuse
    to emit anything when there's nobody to decrypt for. Callers in
    chat / wallet flows opt in when leaking to plaintext is unsafe."""

    pairing_store_mod._singleton = PairingStore()  # empty
    client = _make_client(tmp_path)

    with pytest.raises(ValueError, match="no paired devices"):
        asyncio.run(
            client.emit_encrypted(
                "wallet.signing.requested",
                payload={"chain": "solana"},
                require_recipients=True,
            )
        )


# -------------------------------------------------------------- store survives


def test_emit_encrypted_round_trips_through_durable_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sealed event must survive the SQLite WAL durable buffer with the
    envelope intact — a later ``replay_unpushed`` must be able to
    re-push the same ciphertext + envelope upstream."""

    paired, client_sk = _pair_one_device(monkeypatch)
    client = _make_client(tmp_path)

    body = asyncio.run(
        client.emit_encrypted(
            "chat.message.completed",
            payload={"text": "store me"},
        )
    )

    rows = asyncio.run(client.store.list_events(kind="chat.message.completed"))
    assert len(rows) == 1
    row = rows[0]
    assert row.contract_version == ENCRYPTED_CONTRACT_VERSION
    assert row.ciphertext == body["ciphertext"]
    assert row.envelope == body["envelope"]
    assert row.trace_id == body["trace_id"]

    decrypt_key = DeviceKey(
        device_id=paired.device_id,
        public_key=bytes(client_sk.public_key),
        secret_key=bytes(client_sk),
    )
    out = decrypt_event(
        ciphertext=row.ciphertext or "",
        envelope=row.envelope or {},
        recipient=decrypt_key,
        trace_id=row.trace_id,
        kind=row.kind,
    )
    assert out == {"text": "store me"}
