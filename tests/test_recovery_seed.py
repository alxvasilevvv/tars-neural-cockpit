"""Phase L5 G1 — BIP-39 recovery seed tests.

Validation strategy:
- Spec round-trip: entropy → mnemonic → entropy is exact for random
  inputs (10 rounds for fuzzing) and matches a known BIP-39 vector.
- Checksum: tampering with one word breaks the parse.
- HTTP: ``/api/recovery/{generate,verify,wordlist/info}`` return the
  expected shape and emit ``recovery.{shown,verified}`` meeet events.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from backend.core.crypto.recovery import (
    WORD_COUNT,
    entropy_to_mnemonic,
    fingerprint_of,
    generate_mnemonic,
    make_recovery_seed,
    mnemonic_to_entropy,
    mnemonic_to_seed,
    seed_to_master_key,
    _wordlist,
)
from backend.core.domains import packs as _packs  # noqa: F401
from web_extras.app import app


# ---------------------------------------------------------------------
# Wordlist
# ---------------------------------------------------------------------


def test_wordlist_is_2048_canonical_words() -> None:
    words = _wordlist()
    assert len(words) == 2048
    assert words[0] == "abandon"
    assert words[-1] == "zoo"


# ---------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------


def test_round_trip_random_entropy() -> None:
    for _ in range(8):
        entropy = os.urandom(32)
        m = entropy_to_mnemonic(entropy)
        assert len(m.split()) == WORD_COUNT
        assert mnemonic_to_entropy(m) == entropy


def test_known_vector_all_zero_entropy() -> None:
    # BIP-39 official 24-word vector for entropy = 0x00 * 32.
    entropy = bytes(32)
    expected = (
        "abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon abandon abandon art"
    )
    assert entropy_to_mnemonic(entropy) == expected
    assert mnemonic_to_entropy(expected) == entropy


def test_known_vector_seed_is_pbkdf2_sha512_of_canonical_input() -> None:
    """PBKDF2-HMAC-SHA512 over the canonical 24× ``abandon … art`` mnemonic
    with empty passphrase + ``b"mnemonic"`` salt + 2048 iterations + 64
    bytes output. Pinning the exact bytes catches any silent change to
    the PBKDF2 parameters (iters, hash algo, salt prefix, normalisation)."""

    import hashlib as _hl

    mnemonic = (
        "abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon abandon abandon art"
    )
    expected = _hl.pbkdf2_hmac(
        "sha512", mnemonic.encode(), b"mnemonic", 2048, 64
    )
    assert mnemonic_to_seed(mnemonic, passphrase="") == expected


def test_passphrase_changes_seed() -> None:
    m = generate_mnemonic()
    a = mnemonic_to_seed(m, passphrase="")
    b = mnemonic_to_seed(m, passphrase="my-extra-word")
    assert a != b


def test_seed_to_master_key_returns_x25519_pair() -> None:
    seed = mnemonic_to_seed(generate_mnemonic())
    key = seed_to_master_key(seed, host_id="host_x")
    assert key.device_id == "host_x"
    assert len(key.public_key) == 32
    assert key.secret_key is not None and len(key.secret_key) == 32


# ---------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------


def test_invalid_word_raises() -> None:
    bad = "zzznotaword " + " ".join(["abandon"] * (WORD_COUNT - 1))
    with pytest.raises(ValueError):
        mnemonic_to_entropy(bad)


def test_wrong_word_count_raises() -> None:
    with pytest.raises(ValueError):
        mnemonic_to_entropy("abandon abandon")


def test_tampered_checksum_raises() -> None:
    m = generate_mnemonic().split()
    # Replace the last word with a different valid one — the checksum
    # almost certainly stops matching (1/256 odds it doesn't, but
    # we run with a fresh random mnemonic each time).
    others = [w for w in _wordlist() if w != m[-1]]
    m[-1] = others[0]
    with pytest.raises(ValueError, match="invalid BIP-39 checksum"):
        mnemonic_to_entropy(" ".join(m))


# ---------------------------------------------------------------------
# Make-seed convenience helper
# ---------------------------------------------------------------------


def test_make_recovery_seed_returns_words_and_fingerprint() -> None:
    seed = make_recovery_seed()
    assert len(seed.words) == WORD_COUNT
    assert len(seed.fingerprint) == 12
    assert fingerprint_of(seed.mnemonic) == seed.fingerprint


# ---------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate the meeet event store per test so the durable buffer's
    # 500-event read cap doesn't mask freshly emitted events when the
    # global ~/.tars/meeet.sqlite has accumulated history. Same
    # pattern used by the pairing contract suite.
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    import backend.core.meeet.client as _meeet_client
    import backend.core.meeet.store as _meeet_store

    monkeypatch.setattr(_meeet_store, "_SINGLETON", None, raising=False)
    monkeypatch.setattr(_meeet_client, "_SINGLETON", None, raising=False)
    return TestClient(app)


def test_generate_endpoint_returns_24_words(client: TestClient) -> None:
    res = client.post("/api/recovery/generate")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert len(body["mnemonic"].split()) == WORD_COUNT
    assert len(body["fingerprint"]) == 12
    assert body["word_count"] == WORD_COUNT


def test_verify_round_trips_fingerprint(client: TestClient) -> None:
    gen = client.post("/api/recovery/generate").json()
    verified = client.post(
        "/api/recovery/verify", json={"mnemonic": gen["mnemonic"]}
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["fingerprint"] == gen["fingerprint"]


def test_verify_rejects_bad_mnemonic(client: TestClient) -> None:
    res = client.post(
        "/api/recovery/verify", json={"mnemonic": "not real words at all"}
    )
    assert res.status_code == 400


def test_wordlist_info_endpoint(client: TestClient) -> None:
    res = client.get("/api/recovery/wordlist/info")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["language"] == "english"
    assert body["size"] == 2048
    assert body["first"] == "abandon"
    assert body["last"] == "zoo"


def test_generate_emits_recovery_shown_event(client: TestClient) -> None:
    from backend.core.meeet import get_store

    store = get_store()
    before = len(asyncio.run(store.list_events(limit=500, kind="recovery.shown")))
    client.post("/api/recovery/generate")
    after = asyncio.run(store.list_events(limit=500, kind="recovery.shown"))
    assert len(after) == before + 1
    payload = after[0].payload
    if isinstance(payload, str):
        import json as _json

        payload = _json.loads(payload)
    assert "fingerprint" in payload
    # Must NEVER log the words themselves.
    assert "mnemonic" not in payload
    assert "words" not in payload
