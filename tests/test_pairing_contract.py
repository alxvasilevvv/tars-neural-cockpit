"""Phase L5 — pairing contract pin tests.

These tests pin the wire shape from
``docs/contracts/L5_PAIRING_DRAFT.md``. The internals of begin/accept
swap from mock-crypto to real X25519 in Phase L5 F1, but every
assertion below stays.
"""

from __future__ import annotations

import base64
import time

import pytest
from fastapi.testclient import TestClient
from nacl.public import PrivateKey

from backend.core.domains import packs as _packs  # noqa: F401
from backend.core.pairing.store import _reset_singleton_for_tests
from web_extras.app import app
from web_extras.rate_limit import reset_rate_limiter


def _fresh_epk_b64() -> str:
    """Return a freshly-minted base64 X25519 public key for tests."""

    return base64.b64encode(bytes(PrivateKey.generate().public_key)).decode("ascii")


@pytest.fixture(autouse=True)
def reset_pairing_store(monkeypatch, tmp_path):
    # The in-process vault default writes to ~/.tars/; tests must not
    # touch the developer's real home dir.
    monkeypatch.setenv("TARS_PAIRING_VAULT", "disabled")
    # Pin the meeet event store to a tmp path so accumulated events
    # from earlier tests don't overflow the ``list_events(limit=500)``
    # window the assertions use. Previously this fixture left
    # ``~/.tars/meeet.sqlite`` in place, which made
    # ``test_pair_attempted_event_emitted`` /
    # ``test_pair_linked_event_emitted_on_accept`` flake once the
    # backend suite grew past ~500 events.
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    from backend.core.meeet import store as meeet_store_mod
    monkeypatch.setattr(
        meeet_store_mod, "_SINGLETON", None, raising=False
    )
    from backend.core.meeet import client as meeet_client_mod
    monkeypatch.setattr(
        meeet_client_mod, "_SINGLETON", None, raising=False
    )
    _reset_singleton_for_tests()
    # The pairing rate limiter is a process-wide singleton; reset it
    # so a previous test's begin attempts don't drain the bucket and
    # cause a 429 on the next test's first call.
    reset_rate_limiter()
    yield
    _reset_singleton_for_tests()
    reset_rate_limiter()
    monkeypatch.setattr(
        meeet_store_mod, "_SINGLETON", None, raising=False
    )
    monkeypatch.setattr(
        meeet_client_mod, "_SINGLETON", None, raising=False
    )


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------
# /api/pairing/begin
# ---------------------------------------------------------------------


def test_begin_returns_full_envelope(client: TestClient) -> None:
    res = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    for key in (
        "ok",
        "pair_id",
        "accept_token",
        "host_id",
        "host_fingerprint",
        "host_public_key",
        "expires_at",
        "trace_id",
    ):
        assert key in body, f"missing {key}"
    assert body["ok"] is True
    assert isinstance(body["pair_id"], str) and len(body["pair_id"]) == 16
    assert isinstance(body["accept_token"], str) and len(body["accept_token"]) == 32
    assert "-" in body["host_fingerprint"]
    # host_public_key is a 32-byte X25519 pubkey, base64-encoded.
    assert len(base64.b64decode(body["host_public_key"].encode("ascii"))) == 32
    assert body["expires_at"] > time.time()


def test_begin_rejects_unknown_kind(client: TestClient) -> None:
    res = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "smart_fridge"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid_kind"


def test_begin_rejects_invalid_client_epk(client: TestClient) -> None:
    res = client.post(
        "/api/pairing/begin",
        json={"client_epk": "AAAAAAAAAAAAAAAA==", "kind": "mobile_ios"},  # 12 bytes, not 32
    )
    assert res.status_code == 400
    assert res.json()["detail"].startswith("invalid_client_epk")


def test_begin_with_explicit_pair_id_is_idempotent(client: TestClient) -> None:
    payload = {
        "client_epk": _fresh_epk_b64(),
        "kind": "desktop_macos",
        "pair_id": "1234567890abcdef",
    }
    a = client.post("/api/pairing/begin", json=payload).json()
    b = client.post("/api/pairing/begin", json=payload).json()
    assert a["pair_id"] == b["pair_id"]
    assert a["accept_token"] == b["accept_token"]
    assert a["host_fingerprint"] == b["host_fingerprint"]


# ---------------------------------------------------------------------
# /api/pairing/accept/{token}
# ---------------------------------------------------------------------


def test_accept_links_device(client: TestClient) -> None:
    begun = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "mobile_android"},
    ).json()
    res = client.post(f"/api/pairing/accept/{begun['accept_token']}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["state"] == "linked"
    assert body["device_id"]
    assert body["linked_at"]
    devices = client.get("/api/pairing/devices").json()
    assert devices["count"] == 1
    assert devices["devices"][0]["device_id"] == body["device_id"]
    assert devices["devices"][0]["kind"] == "mobile_android"


def test_accept_unknown_token_404(client: TestClient) -> None:
    res = client.post("/api/pairing/accept/nonsense")
    assert res.status_code == 404
    assert res.json()["detail"] == "pair_not_found"


def test_accept_after_reject_returns_409(client: TestClient) -> None:
    begun = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"},
    ).json()
    client.post(f"/api/pairing/reject/{begun['accept_token']}")
    res = client.post(f"/api/pairing/accept/{begun['accept_token']}")
    assert res.status_code == 409
    assert res.json()["detail"] == "pair_rejected"


# ---------------------------------------------------------------------
# /api/pairing/status
# ---------------------------------------------------------------------


def test_status_pending_then_linked(client: TestClient) -> None:
    begun = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "desktop_windows"},
    ).json()
    pending = client.get(f"/api/pairing/status?pair_id={begun['pair_id']}").json()
    assert pending["state"] == "pending"
    client.post(f"/api/pairing/accept/{begun['accept_token']}")
    linked = client.get(f"/api/pairing/status?pair_id={begun['pair_id']}").json()
    assert linked["state"] == "linked"
    assert linked["device_id"]


def test_status_unknown_pair_id_404(client: TestClient) -> None:
    res = client.get("/api/pairing/status?pair_id=missing")
    assert res.status_code == 404


# ---------------------------------------------------------------------
# /api/pairing/revoke + /devices
# ---------------------------------------------------------------------


def test_revoke_removes_paired_device(client: TestClient) -> None:
    begun = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"},
    ).json()
    accept = client.post(f"/api/pairing/accept/{begun['accept_token']}").json()
    device_id = accept["device_id"]
    res = client.post("/api/pairing/revoke", json={"device_id": device_id})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["device_id"] == device_id
    listing = client.get("/api/pairing/devices").json()
    assert listing["count"] == 0


def test_revoke_unknown_device_404(client: TestClient) -> None:
    res = client.post("/api/pairing/revoke", json={"device_id": "ghost"})
    assert res.status_code == 404


# ---------------------------------------------------------------------
# meeet event side-effects
# ---------------------------------------------------------------------


def test_pair_attempted_event_emitted(client: TestClient) -> None:
    import asyncio

    from backend.core.meeet import get_store

    store = get_store()
    before = len(asyncio.run(store.list_events(limit=500, kind="pair.attempted")))
    client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "mobile_ios"},
    )
    after = asyncio.run(store.list_events(limit=500, kind="pair.attempted"))
    assert len(after) == before + 1
    payload = after[0].payload
    if isinstance(payload, str):
        import json as _json

        payload = _json.loads(payload)
    assert payload["kind"] == "mobile_ios"
    assert "pair_id" in payload
    assert "host_fingerprint" in payload


def test_pair_linked_event_emitted_on_accept(client: TestClient) -> None:
    import asyncio

    from backend.core.meeet import get_store

    begun = client.post(
        "/api/pairing/begin",
        json={"client_epk": _fresh_epk_b64(), "kind": "desktop_macos"},
    ).json()
    store = get_store()
    before = len(asyncio.run(store.list_events(limit=500, kind="pair.linked")))
    client.post(f"/api/pairing/accept/{begun['accept_token']}")
    after = asyncio.run(store.list_events(limit=500, kind="pair.linked"))
    assert len(after) == before + 1
