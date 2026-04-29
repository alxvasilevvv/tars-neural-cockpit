"""Wallet balance reader contract tests.

Mocks ``urllib.request.urlopen`` rather than hitting real RPCs so the
suite stays offline. Pins:

- Solana balance decoding (lamports → SOL display, 9 decimals).
- EVM balance decoding (0x-hex wei → ETH display, 18 decimals).
- TON balance decoding (nano → TON display, 9 decimals).
- RPC error path returns a structured ``BalanceError``.
- Wallet pack ``wallet.balance`` action plumbs through to the same code.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.domains.registry import get_pack
from backend.core.wallet import (
    BalanceError,
    WalletChain,
    fetch_balance,
    fetch_evm_balance,
    fetch_solana_balance,
    fetch_ton_balance,
    get_wallet_service,
    reset_wallet_service_for_tests,
)
from backend.core.wallet.balance import EVM_DEFAULT_RPC, SOLANA_DEFAULT_RPC


def _fake_resp(payload: dict[str, Any]) -> "object":
    body = json.dumps(payload).encode("utf-8")

    class _Stream:
        def read(self) -> bytes:
            return body

        def __enter__(self) -> "_Stream":
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

    return _Stream()


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch) -> Iterator[None]:
    tmp = tempfile.mkdtemp(prefix="tars_wallet_balance_")
    monkeypatch.setenv("TARS_WALLETS_DB_PATH", os.path.join(tmp, "wallets.sqlite"))
    monkeypatch.setenv(
        "TARS_WALLETS_SECRETS_PATH", os.path.join(tmp, "wallet_secrets.json")
    )
    reset_wallet_service_for_tests()
    yield
    reset_wallet_service_for_tests()


# ---------- direct readers ----------------------------------------------


def test_solana_balance_decodes_lamports() -> None:
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 2_500_000_000}})
    with patch("urllib.request.urlopen", return_value=fake) as opener:
        bal = fetch_solana_balance("Sendr111")
    assert opener.call_count == 1
    assert bal.chain is WalletChain.SOLANA
    assert bal.raw == 2_500_000_000
    assert bal.decimals == 9
    assert bal.symbol == "SOL"
    assert bal.display == "2.5"
    assert bal.rpc_url == SOLANA_DEFAULT_RPC


def test_evm_balance_decodes_hex_wei() -> None:
    # 0xde0b6b3a7640000 == 1e18 wei == 1 ETH
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": "0xde0b6b3a7640000"})
    with patch("urllib.request.urlopen", return_value=fake):
        bal = fetch_evm_balance("0xabc")
    assert bal.raw == 10**18
    assert bal.decimals == 18
    assert bal.symbol == "ETH"
    assert bal.display == "1"
    assert bal.rpc_url == EVM_DEFAULT_RPC


def test_ton_balance_decodes_nano() -> None:
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": "1500000000"})
    with patch("urllib.request.urlopen", return_value=fake):
        bal = fetch_ton_balance("EQ123")
    assert bal.raw == 1_500_000_000
    assert bal.decimals == 9
    assert bal.symbol == "TON"
    assert bal.display == "1.5"


def test_zero_balance_displays_as_zero() -> None:
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 0}})
    with patch("urllib.request.urlopen", return_value=fake):
        bal = fetch_solana_balance("Sendr111")
    assert bal.display == "0"


def test_rpc_error_message_raises_balance_error() -> None:
    fake = _fake_resp(
        {"jsonrpc": "2.0", "id": 1, "error": {"code": -32700, "message": "Parse error"}}
    )
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(BalanceError) as exc:
            fetch_solana_balance("Sendr111")
    assert "Parse error" in str(exc.value)


def test_rpc_unparsable_response_raises() -> None:
    class _Stream:
        def read(self) -> bytes:
            return b"<html>nope</html>"

        def __enter__(self) -> "_Stream":
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=_Stream()):
        with pytest.raises(BalanceError):
            fetch_solana_balance("Sendr111")


def test_rpc_value_not_int_raises() -> None:
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": "garbage"}})
    with patch("urllib.request.urlopen", return_value=fake):
        with pytest.raises(BalanceError):
            fetch_solana_balance("Sendr111")


def test_fetch_balance_dispatches_per_chain() -> None:
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 1}})
    with patch("urllib.request.urlopen", return_value=fake):
        b = fetch_balance(chain=WalletChain.SOLANA, address="X")
    assert b.chain is WalletChain.SOLANA


def test_rpc_url_override_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("TARS_SOLANA_RPC_URL", "https://env.example.com")
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 0}})
    captured: dict[str, Any] = {}

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return fake

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        bal = fetch_solana_balance("X", rpc_url="https://override.example.com")
    assert captured["url"] == "https://override.example.com"
    assert bal.rpc_url == "https://override.example.com"


def test_rpc_url_env_used_when_no_override(monkeypatch) -> None:
    monkeypatch.setenv("TARS_SOLANA_RPC_URL", "https://env.example.com")
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 0}})
    captured: dict[str, Any] = {}

    def _fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return fake

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        bal = fetch_solana_balance("X")
    assert captured["url"] == "https://env.example.com"
    assert bal.rpc_url == "https://env.example.com"


# ---------- HTTP route -------------------------------------------------


@pytest.fixture
def client() -> "object":
    from fastapi.testclient import TestClient

    from web_extras.app import app

    return TestClient(app)


def test_balance_endpoint_round_trips(client: Any) -> None:
    create = client.post(
        "/api/wallet", json={"label": "x", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 7_000_000_000}})
    with patch("urllib.request.urlopen", return_value=fake):
        r = client.get(f"/api/wallet/{wid}/balance").json()
    assert r["ok"] is True
    bal = r["balance"]
    assert bal["chain"] == "solana"
    assert bal["display"] == "7"


def test_balance_endpoint_returns_unknown_wallet_404(client: Any) -> None:
    r = client.get("/api/wallet/wlt_deadbeef/balance")
    assert r.status_code == 404


def test_balance_endpoint_returns_ok_false_on_rpc_error(client: Any) -> None:
    create = client.post(
        "/api/wallet", json={"label": "x", "chain": "solana"}
    ).json()
    wid = create["wallet"]["id"]

    def _broken(req, timeout):
        raise OSError("boom")

    with patch("urllib.request.urlopen", side_effect=_broken):
        r = client.get(f"/api/wallet/{wid}/balance").json()
    # The endpoint never 500s on RPC failure — it returns ok=false so
    # the cockpit can show a friendly retry pill.
    assert r["ok"] is False
    assert "error" in r


# ---------- pack action ------------------------------------------------


@pytest.mark.asyncio
async def test_wallet_balance_action_uses_service() -> None:
    svc = get_wallet_service()
    wallet, _ = await svc.create_wallet(label="x", chain=WalletChain.SOLANA)
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    fake = _fake_resp({"jsonrpc": "2.0", "id": 1, "result": {"value": 1_000_000_000}})
    with patch("urllib.request.urlopen", return_value=fake):
        out = await by_id["balance"].handler({"wallet_id": wallet.id})
    assert out["ok"] is True
    assert out["balance"]["display"] == "1"


def test_wallet_balance_action_is_non_destructive() -> None:
    pack = get_pack("wallet")
    by_id = {a.id: a for a in pack.actions()}
    assert by_id["balance"].destructive is False
