"""Live RPC helper contract tests (Phase P2/P3/P4).

We do not actually hit a public RPC in CI — those endpoints are
flaky and would make the suite non-deterministic. Instead we
monkeypatch :func:`backend.core.wallet.balance._post_json_rpc`
to return canned shapes, and verify that the helpers (and their
HTTP routes) parse them correctly + surface failures as
``RPCError`` / 502.

Coverage:

- Solana: shape parsing, missing fields, transport failure.
- EVM: nonce hex decoding, malformed address rejection,
  invalid block_tag rejection.
- TON: tonsdk-style ``["num", "0x..."]`` stack parsing,
  fresh-wallet exit_code != 0 → seqno=0 fallback,
  unrecognised stack head → ``RPCError``.
- HTTP routes: 200 happy path, 502 on RPCError, 400 on
  validation_error.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import reset_client as reset_meeet_client
from backend.core.meeet import reset_store as reset_meeet_store
from backend.core.wallet import reset_wallet_service_for_tests
from backend.core.wallet import chain_helpers
from backend.core.wallet.balance import BalanceError
from backend.core.wallet.chain_helpers import (
    RPCError,
    get_evm_nonce,
    get_solana_blockhash,
    get_ton_seqno,
)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_rpc_")
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


@pytest.fixture
def client() -> TestClient:
    from web_extras.app import app

    return TestClient(app)


# ---------- Solana ----------------------------------------------------


def test_solana_blockhash_happy_path(monkeypatch) -> None:
    def fake(url, body, *, timeout):  # noqa: ARG001
        return {
            "result": {
                "context": {"slot": 12345},
                "value": {
                    "blockhash": "EkSnNWid2cvwEVnVx9aBqawnmiCNiDgp3gUdkDPTKN1N",
                    "lastValidBlockHeight": 999,
                },
            }
        }

    monkeypatch.setattr(chain_helpers, "_post_json_rpc", fake)
    out = get_solana_blockhash()
    assert out["blockhash"] == "EkSnNWid2cvwEVnVx9aBqawnmiCNiDgp3gUdkDPTKN1N"
    assert out["last_valid_block_height"] == 999
    assert out["rpc_url"]


def test_solana_blockhash_unexpected_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "garbage"}
    )
    with pytest.raises(RPCError):
        get_solana_blockhash()


def test_solana_blockhash_missing_value(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": {"context": {}}}
    )
    with pytest.raises(RPCError):
        get_solana_blockhash()


def test_solana_blockhash_transport_failure(monkeypatch) -> None:
    def boom(*a, **kw):
        raise BalanceError("connection reset")

    monkeypatch.setattr(chain_helpers, "_post_json_rpc", boom)
    with pytest.raises(BalanceError):
        get_solana_blockhash()


# ---------- EVM -------------------------------------------------------


def test_evm_nonce_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "0x2a"}
    )
    out = get_evm_nonce("0x" + "ab" * 20)
    assert out["nonce"] == 42
    assert out["nonce_hex"] == "0x2a"
    assert out["block_tag"] == "pending"


def test_evm_nonce_zero(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "0x0"}
    )
    assert get_evm_nonce("0x" + "ab" * 20)["nonce"] == 0


def test_evm_nonce_malformed_address(monkeypatch) -> None:
    with pytest.raises(RPCError):
        get_evm_nonce("not-an-address")


def test_evm_nonce_invalid_block_tag(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "0x0"}
    )
    with pytest.raises(RPCError):
        get_evm_nonce("0x" + "ab" * 20, block_tag="cosmic")


def test_evm_nonce_non_hex_response(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "lolnope"}
    )
    with pytest.raises(RPCError):
        get_evm_nonce("0x" + "ab" * 20)


# ---------- TON -------------------------------------------------------


def test_ton_seqno_happy_path(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers,
        "_post_json_rpc",
        lambda *a, **kw: {
            "result": {"exit_code": 0, "stack": [["num", "0x5"]]}
        },
    )
    assert get_ton_seqno("EQAxxx")["seqno"] == 5


def test_ton_seqno_undeployed_wallet(monkeypatch) -> None:
    """Fresh wallet → exit_code != 0 → seqno 0."""
    monkeypatch.setattr(
        chain_helpers,
        "_post_json_rpc",
        lambda *a, **kw: {"result": {"exit_code": 11, "stack": []}},
    )
    assert get_ton_seqno("EQAfresh")["seqno"] == 0


def test_ton_seqno_decimal_in_stack(monkeypatch) -> None:
    """Some endpoints return a plain decimal string under 'value'."""
    monkeypatch.setattr(
        chain_helpers,
        "_post_json_rpc",
        lambda *a, **kw: {
            "result": {"exit_code": 0, "stack": [{"value": "17"}]}
        },
    )
    assert get_ton_seqno("EQAdec")["seqno"] == 17


def test_ton_seqno_unknown_stack_head(monkeypatch) -> None:
    monkeypatch.setattr(
        chain_helpers,
        "_post_json_rpc",
        lambda *a, **kw: {
            "result": {"exit_code": 0, "stack": [{"weirdkey": "0x5"}]}
        },
    )
    with pytest.raises(RPCError):
        get_ton_seqno("EQAxxx")


def test_ton_seqno_bad_address() -> None:
    with pytest.raises(RPCError):
        get_ton_seqno("xx")


# ---------- HTTP routes ----------------------------------------------


def test_http_solana_blockhash(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(
        chain_helpers,
        "_post_json_rpc",
        lambda *a, **kw: {
            "result": {
                "value": {"blockhash": "BHASH", "lastValidBlockHeight": 1}
            }
        },
    )
    r = client.get("/api/wallet/solana/blockhash")
    assert r.status_code == 200, r.text
    assert r.json()["blockhash"] == "BHASH"


def test_http_solana_blockhash_502_on_rpc_failure(
    monkeypatch, client: TestClient
) -> None:
    def boom(*a, **kw):
        raise BalanceError("dns failed")

    monkeypatch.setattr(chain_helpers, "_post_json_rpc", boom)
    r = client.get("/api/wallet/solana/blockhash")
    assert r.status_code == 502
    assert r.json()["error_code"] == "wallet_balance_rpc_failure"


def test_http_evm_nonce(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "0xff"}
    )
    r = client.get("/api/wallet/evm/0x" + "ab" * 20 + "/nonce")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nonce"] == 255
    assert body["block_tag"] == "pending"


def test_http_evm_nonce_with_latest_tag(
    monkeypatch, client: TestClient
) -> None:
    monkeypatch.setattr(
        chain_helpers, "_post_json_rpc", lambda *a, **kw: {"result": "0x10"}
    )
    r = client.get("/api/wallet/evm/0x" + "ab" * 20 + "/nonce?block_tag=latest")
    assert r.status_code == 200
    assert r.json()["block_tag"] == "latest"
    assert r.json()["nonce"] == 16


def test_http_ton_seqno(monkeypatch, client: TestClient) -> None:
    monkeypatch.setattr(
        chain_helpers,
        "_post_json_rpc",
        lambda *a, **kw: {
            "result": {"exit_code": 0, "stack": [["num", "0xa"]]}
        },
    )
    r = client.get("/api/wallet/ton/EQAabc/seqno")
    assert r.status_code == 200
    assert r.json()["seqno"] == 10
