"""Tests for the W2-PR2 Binance Spot REST adapter.

The adapter never hits the network in tests: a fake
``urlopen``-shaped callable is injected into
:class:`BinanceClient` and records every signed request so we
can assert on:

- The HMAC-SHA256 signature is present and computed against
  the canonical query string (sorted by insertion order with
  Binance's own query semantics).
- The right HTTP verb / path / params reach the wire.
- Adapter state transitions (`OPEN` → `FILLED`) on the
  response payload.
- Position store + audit log update via the router exactly
  like the paper adapter.
- Idempotent re-submit returns the cached order.
- 4xx responses mark the order REJECTED with the Binance
  error message.

No real Binance credentials are involved.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import json
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from backend.core.algotrade.exec import (
    AuditLog,
    BinanceAdapter,
    BinanceAPIError,
    BinanceClient,
    BinanceConfig,
    BinanceTransportError,
    OrderIntent,
    OrderRouter,
    OrderStatus,
    OrderType,
    PositionStore,
    RiskGate,
    RiskPolicy,
    Side,
    reset_runtime,
)


# --------------------------------------------------------- fake transport


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeOpener:
    """Records every Request and returns a queued response."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._queue: list[Any] = []

    def queue(self, status: int, body: dict | str | bytes) -> None:
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self._queue.append(_FakeResponse(status, body))

    def queue_error(self, status: int, body: dict) -> None:
        from urllib.error import HTTPError

        self._queue.append(
            HTTPError(
                url="https://test", code=status, msg="err",
                hdrs=None, fp=io.BytesIO(json.dumps(body).encode("utf-8")),
            )
        )

    def __call__(self, request, timeout: float = 10.0):
        url = request.full_url
        method = request.get_method()
        data = request.data.decode("utf-8") if request.data else ""
        self.calls.append({
            "url": url,
            "method": method,
            "headers": dict(request.headers),
            "data": data,
            "timeout": timeout,
        })
        if not self._queue:
            raise AssertionError(f"unexpected call: {method} {url}")
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _config(testnet: bool = True) -> BinanceConfig:
    return BinanceConfig(
        api_key="abc123",
        api_secret="secret",
        testnet=testnet,
    )


def _intent(
    *,
    side: Side = Side.BUY,
    qty: float = 1.0,
    type: OrderType = OrderType.MARKET,
    price: float | None = None,
) -> OrderIntent:
    return OrderIntent.make(
        strategy_fingerprint="fp_test",
        instrument="BINANCE:BTCUSDT",
        side=side,
        qty=qty,
        type=type,
        price=price,
    )


# --------------------------------------------------------- client signing


def test_client_uses_testnet_base_url_by_default() -> None:
    config = _config(testnet=True)
    assert config.base_url == "https://testnet.binance.vision"


def test_client_uses_live_base_url_when_testnet_off() -> None:
    config = _config(testnet=False)
    assert config.base_url == "https://api.binance.com"


def test_client_signs_request_with_hmac_sha256() -> None:
    fake = _FakeOpener()
    fake.queue(200, {"serverTime": 1700000000000})
    client = BinanceClient(_config(), opener=fake)

    client._request("GET", "/api/v3/account", {}, signed=True)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    parsed = urllib.parse.urlparse(call["url"])
    qs = urllib.parse.parse_qs(parsed.query)
    assert "timestamp" in qs
    assert "signature" in qs
    assert qs["recvWindow"] == ["5000"]

    canonical = parsed.query.rsplit("&signature=", 1)[0]
    expected = hmac.new(b"secret", canonical.encode(), hashlib.sha256).hexdigest()
    assert qs["signature"][0] == expected


def test_client_passes_api_key_header() -> None:
    fake = _FakeOpener()
    fake.queue(200, {"serverTime": 0})
    client = BinanceClient(_config(), opener=fake)

    client.server_time()

    headers = fake.calls[0]["headers"]
    # urllib stores headers with capitalised keys
    assert headers.get("X-mbx-apikey") == "abc123" or headers.get("X-MBX-APIKEY") == "abc123"


def test_client_raises_typed_api_error_on_4xx() -> None:
    fake = _FakeOpener()
    fake.queue_error(400, {"code": -1013, "msg": "Filter failure"})
    client = BinanceClient(_config(), opener=fake)

    with pytest.raises(BinanceAPIError) as excinfo:
        client.account()
    assert excinfo.value.code == -1013
    assert "Filter failure" in str(excinfo.value)


def test_client_raises_transport_error_on_url_error() -> None:
    from urllib.error import URLError

    fake = _FakeOpener()
    fake._queue.append(URLError("nodename nor servname"))
    client = BinanceClient(_config(), opener=fake)

    with pytest.raises(BinanceTransportError):
        client.account()


# --------------------------------------------------------- adapter


def test_adapter_market_buy_emits_fills_from_response() -> None:
    fake = _FakeOpener()
    fake.queue(200, {
        "orderId": 12345,
        "status": "FILLED",
        "executedQty": "1.0",
        "cummulativeQuoteQty": "100.0",
        "transactTime": 1700000000000,
        "fills": [
            {"tradeId": 999, "price": "100.0", "qty": "1.0", "commission": "0.001"},
        ],
    })
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    order = asyncio.run(adapter.submit(_intent()))

    assert order.status == OrderStatus.FILLED
    assert len(order.fills) == 1
    fill = order.fills[0]
    assert fill.qty == 1.0
    assert fill.price == 100.0
    assert fill.fee == pytest.approx(0.001)
    assert fill.fill_id == "999"
    # Reference price comes from intent.price (None for market).
    assert fill.reference_price is None


def test_adapter_synthesises_fill_when_response_lacks_fills_array() -> None:
    """Some responses don't include `fills`; we synthesise from
    executedQty + cummulativeQuoteQty so the position book stays
    consistent."""

    fake = _FakeOpener()
    fake.queue(200, {
        "orderId": 22,
        "status": "FILLED",
        "executedQty": "2.0",
        "cummulativeQuoteQty": "210.0",
        "transactTime": 1700000000000,
    })
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    order = asyncio.run(adapter.submit(_intent(qty=2.0)))

    assert order.status == OrderStatus.FILLED
    assert len(order.fills) == 1
    fill = order.fills[0]
    assert fill.qty == pytest.approx(2.0)
    assert fill.price == pytest.approx(105.0)


def test_adapter_idempotent_resubmit_returns_cached_order() -> None:
    fake = _FakeOpener()
    fake.queue(200, {"orderId": 1, "status": "FILLED", "executedQty": "1.0",
                     "cummulativeQuoteQty": "100.0", "transactTime": 0})
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    intent = _intent()
    o1 = asyncio.run(adapter.submit(intent))
    o2 = asyncio.run(adapter.submit(intent))
    assert o1 is o2
    # No second HTTP call.
    assert len(fake.calls) == 1


def test_adapter_marks_order_rejected_on_binance_api_error() -> None:
    fake = _FakeOpener()
    fake.queue_error(400, {"code": -2010, "msg": "Account has insufficient balance"})
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    order = asyncio.run(adapter.submit(_intent(qty=999.0)))

    assert order.status == OrderStatus.REJECTED
    assert "insufficient" in (order.rejection_reason or "").lower()


def test_adapter_status_polls_and_updates_open_order() -> None:
    fake = _FakeOpener()
    # First the submit returns OPEN with no fills.
    fake.queue(200, {
        "orderId": 7,
        "status": "NEW",
        "executedQty": "0",
        "cummulativeQuoteQty": "0",
        "transactTime": 0,
    })
    # Then a status poll returns FILLED.
    fake.queue(200, {
        "orderId": 7,
        "status": "FILLED",
        "executedQty": "1.0",
        "cummulativeQuoteQty": "100.0",
        "transactTime": 1700000001000,
    })
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    order = asyncio.run(adapter.submit(_intent(type=OrderType.LIMIT, price=100.0)))
    assert order.status == OrderStatus.OPEN

    polled = asyncio.run(adapter.status(order.order_id))
    assert polled is not None
    assert polled.status == OrderStatus.FILLED
    assert len(polled.fills) == 1


def test_adapter_cancel_marks_canceled_and_closes() -> None:
    fake = _FakeOpener()
    fake.queue(200, {"orderId": 9, "status": "NEW", "executedQty": "0",
                     "cummulativeQuoteQty": "0", "transactTime": 0})
    fake.queue(200, {"orderId": 9, "status": "CANCELED",
                     "executedQty": "0", "cummulativeQuoteQty": "0"})
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    order = asyncio.run(adapter.submit(_intent(type=OrderType.LIMIT, price=99.0)))
    canceled = asyncio.run(adapter.cancel(order.order_id))
    assert canceled.status == OrderStatus.CANCELED
    assert canceled.closed_at is not None


# --------------------------------------------------------- router integration


def test_adapter_drives_router_audit_and_positions(tmp_path: Path) -> None:
    fake = _FakeOpener()
    fake.queue(200, {
        "orderId": 1, "status": "FILLED", "executedQty": "1.0",
        "cummulativeQuoteQty": "100.0", "transactTime": 1700000000000,
        "fills": [{"tradeId": 11, "price": "100.0", "qty": "1.0", "commission": "0.0"}],
    })
    client = BinanceClient(_config(), opener=fake)
    adapter = BinanceAdapter(_config(), client=client)

    positions = PositionStore()
    audit = AuditLog(tmp_path / "audit.jsonl")
    gate = RiskGate(RiskPolicy(allow_short=False))
    router = OrderRouter(
        adapter=adapter,
        gate=gate,
        positions=positions,
        audit=audit,
        session_id="sess_live",
    )

    verdict, order = asyncio.run(router.submit(_intent()))
    assert verdict.accepted is True
    assert order is not None
    assert order.status == OrderStatus.FILLED

    pos = positions.get("BINANCE:BTCUSDT")
    assert pos is not None
    assert pos.qty == 1.0
    assert pos.avg_price == 100.0

    # Audit log must contain intent → verdict → order → fill.
    kinds = [e.kind for e in audit.read_all()]
    assert kinds[:4] == ["intent", "verdict", "order", "fill"]


# --------------------------------------------------------- runtime + action


def test_runtime_start_live_session_uses_kill_switch_on_real_money(tmp_path: Path) -> None:
    """Live (testnet=False) sessions must wire kill_switch=ON by
    default — operator has to explicitly disable via set_policy."""

    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.algotrade.exec import get_runtime, BinanceConfig

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint
        runtime = get_runtime()

        live_config = BinanceConfig(
            api_key="key", api_secret="sec", testnet=False
        )
        # We pass client=None; the runtime never calls the client
        # because no order has been submitted yet.
        wiring = runtime.start_live_session(
            strategy_fingerprint=fp,
            instrument="BINANCE:BTCUSDT",
            binance_config=live_config,
            client=BinanceClient(live_config, opener=_FakeOpener()),
        )
        assert wiring.gate.policy.kill_switch is True
        assert wiring.gate.policy.allow_short is False
        assert wiring.session.mode == "live"
        assert wiring.session.adapter == "binance"
        # Metadata must NEVER include the secret.
        assert "binance" in wiring.session.metadata
        assert "api_secret" not in wiring.session.metadata["binance"]
        assert wiring.session.metadata["binance"]["testnet"] is False


def test_runtime_start_live_session_testnet_no_kill_switch(tmp_path: Path) -> None:
    """Testnet sessions don't need the kill switch — workshops
    have to be runnable out of the box."""

    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.algotrade.exec import get_runtime, BinanceConfig

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint
        runtime = get_runtime()

        testnet_config = BinanceConfig(
            api_key="key", api_secret="sec", testnet=True
        )
        wiring = runtime.start_live_session(
            strategy_fingerprint=fp,
            instrument="BINANCE:BTCUSDT",
            binance_config=testnet_config,
            client=BinanceClient(testnet_config, opener=_FakeOpener()),
        )
        assert wiring.gate.policy.kill_switch is False
        assert wiring.session.metadata["binance"]["testnet"] is True


def test_runtime_does_not_rehydrate_live_sessions(tmp_path: Path) -> None:
    """A live session row stays in sessions.jsonl after stop, but
    `get` returns None until the operator re-authenticates."""

    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.algotrade.exec import get_runtime, BinanceConfig

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint
        runtime = get_runtime()

        cfg = BinanceConfig(api_key="k", api_secret="s", testnet=True)
        wiring = runtime.start_live_session(
            strategy_fingerprint=fp,
            instrument="BINANCE:BTCUSDT",
            binance_config=cfg,
            client=BinanceClient(cfg, opener=_FakeOpener()),
        )
        sid = wiring.session.session_id

        # Forget the in-memory wiring (simulates worker restart).
        runtime._wirings.clear()

        rehydrated = runtime.get(sid)
        assert rehydrated is None

        # The session row still exists.
        assert runtime.session_store().get(sid) is not None


def test_start_live_session_action_requires_credentials() -> None:
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.domains.packs.algotrade.exec_actions import (
            start_live_session_action,
        )

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint

        result = asyncio.run(start_live_session_action({
            "fingerprint": fp,
            "binance": {},
        }))
        assert result["ok"] is False
        assert result["error"] == "missing_binance_credentials"


def test_start_live_session_action_returns_safe_binance_block() -> None:
    """The action's response includes a safe binance dict
    (api_key prefix, testnet, base_url) but NEVER the secret."""

    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.domains.packs.algotrade.exec_actions import (
            start_live_session_action,
        )

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint

        result = asyncio.run(start_live_session_action({
            "fingerprint": fp,
            "instrument": "BINANCE:BTCUSDT",
            "binance": {
                "api_key": "abcdef1234567890",
                "api_secret": "verysecret",
                "testnet": True,
            },
        }))
        assert result["ok"] is True
        assert result["session"]["mode"] == "live"
        assert result["session"]["adapter"] == "binance"
        # Safe block: no secret, prefixed key.
        assert "api_secret" not in result["binance"]
        assert result["binance"]["api_key_prefix"] == "abcdef"
        assert result["binance"]["testnet"] is True
        assert result["binance"]["base_url"] == "https://testnet.binance.vision"
        assert result["warning"] is None  # testnet → no warning


def test_start_live_session_action_warns_on_real_money() -> None:
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.domains.packs.algotrade.exec_actions import (
            start_live_session_action,
        )

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint

        result = asyncio.run(start_live_session_action({
            "fingerprint": fp,
            "instrument": "BINANCE:BTCUSDT",
            "binance": {
                "api_key": "abcdef1234567890",
                "api_secret": "verysecret",
                "testnet": False,
            },
        }))
        assert result["ok"] is True
        assert result["binance"]["testnet"] is False
        assert result["binance"]["base_url"] == "https://api.binance.com"
        assert result["warning"] is not None
        assert "kill_switch" in result["warning"].lower()
        # Live mode: kill switch on by default.
        assert result["policy"]["kill_switch"] is True
