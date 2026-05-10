"""Binance Spot REST adapter (W2-PR2).

Talks to Binance's signed REST endpoints (Spot Testnet by
default; real endpoint behind an explicit ``testnet=False``).
Stdlib-only: ``urllib.request`` for HTTP, ``hmac`` + ``hashlib``
for HMAC-SHA256 signing, ``urllib.parse`` for query encoding.
No third-party dependency, no websocket — fills are derived
from polling order status on submit and on every explicit
``status()`` call.

Workshop default
----------------

`BinanceConfig.testnet=True` → base URL is
``https://testnet.binance.vision``. Cresco attendees mint a
free testnet API key from
https://testnet.binance.vision/, drop it into the action
schema, and trade against the same endpoint shape as
production without ever risking real funds. This is the
workshop's "feels-like-live" mode.

Production trading
------------------

Setting ``testnet=False`` swings the base URL to
``https://api.binance.com``. The risk gate is the *only* layer
that decides whether an intent reaches Binance — wire the gate
with `kill_switch=True` if you're not absolutely ready to send
real orders.

Idempotency
-----------

Binance accepts an optional ``newClientOrderId``. We pass the
intent's ``intent_id`` so that re-submitting an idempotent
intent (router-level dedup short-circuit happens first) would
collide on the exchange side too.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping
from urllib.error import HTTPError, URLError

from .base import (
    ExecAdapter,
    Fill,
    Order,
    OrderIntent,
    OrderStatus,
    OrderType,
    Side,
)


# ---------------------------------------------------------------------
# Config + transport
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class BinanceConfig:
    api_key: str
    api_secret: str
    testnet: bool = True
    """Default to Spot Testnet — workshop attendees never risk
    real funds. Set ``testnet=False`` for production trading."""
    recv_window_ms: int = 5_000
    """Binance ``recvWindow``: drops requests older than this."""
    timeout_seconds: float = 10.0
    name: str = "binance"

    @property
    def base_url(self) -> str:
        return (
            "https://testnet.binance.vision"
            if self.testnet
            else "https://api.binance.com"
        )

    def to_safe_dict(self) -> dict[str, Any]:
        """Like ``to_dict`` but never includes the secret. The
        public API key prefix (first 6 chars) is included so the
        cockpit can show ``binance:abc123...`` without ever
        rendering the secret."""

        return {
            "name": self.name,
            "testnet": bool(self.testnet),
            "base_url": self.base_url,
            "api_key_prefix": (self.api_key or "")[:6],
            "recv_window_ms": int(self.recv_window_ms),
            "timeout_seconds": float(self.timeout_seconds),
        }


class BinanceClient:
    """Minimal signed REST client. Synchronous under the hood
    (urllib has no async); :class:`BinanceAdapter` runs the
    blocking calls in a thread via :func:`asyncio.to_thread` so
    the event loop is never starved."""

    def __init__(self, config: BinanceConfig, *, opener: Any = None) -> None:
        self.config = config
        self._opener = opener  # tests inject a fake urlopen

    # ----------------------------------------------------- helpers

    def _sign(self, query: str) -> str:
        return hmac.new(
            self.config.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any],
        *,
        signed: bool,
    ) -> dict[str, Any]:
        clean = {k: v for k, v in params.items() if v is not None}
        if signed:
            clean["timestamp"] = int(time.time() * 1000)
            clean["recvWindow"] = self.config.recv_window_ms

        query = urllib.parse.urlencode(clean, doseq=True)
        if signed:
            query += f"&signature={self._sign(query)}"

        url = f"{self.config.base_url}{path}"
        if method.upper() in ("GET", "DELETE"):
            url = f"{url}?{query}"
            data = None
        else:
            data = query.encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=data,
            method=method.upper(),
            headers={
                "X-MBX-APIKEY": self.config.api_key,
                "User-Agent": "tars-algotrade/0.6 (+meeet.world)",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        opener = self._opener or urllib.request.urlopen
        try:
            with opener(request, timeout=self.config.timeout_seconds) as resp:
                body = resp.read()
        except HTTPError as exc:  # 4xx / 5xx
            body = exc.read()
            try:
                payload = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                payload = {"code": exc.code, "msg": str(exc.reason)}
            raise BinanceAPIError(
                code=int(payload.get("code", exc.code)),
                msg=str(payload.get("msg", exc.reason)),
                http_status=exc.code,
            ) from None
        except URLError as exc:
            raise BinanceTransportError(str(exc.reason)) from None

        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise BinanceTransportError(f"non-json body: {exc}") from None

    # ----------------------------------------------------- API

    def server_time(self) -> dict[str, Any]:
        return self._request("GET", "/api/v3/time", {}, signed=False)

    def account(self) -> dict[str, Any]:
        return self._request("GET", "/api/v3/account", {}, signed=True)

    def new_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        new_client_order_id: str | None = None,
        time_in_force: str = "GTC",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": _format_qty(quantity),
        }
        if order_type.upper() == "LIMIT":
            params["price"] = _format_price(price)
            params["timeInForce"] = time_in_force
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        return self._request(
            "POST", "/api/v3/order", params, signed=True
        )

    def query_order(
        self,
        *,
        symbol: str,
        order_id: int | None = None,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = int(order_id)
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request("GET", "/api/v3/order", params, signed=True)

    def cancel_order(
        self,
        *,
        symbol: str,
        order_id: int | None = None,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = int(order_id)
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        return self._request(
            "DELETE", "/api/v3/order", params, signed=True
        )


# ---------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------


def _binance_symbol(instrument: str) -> str:
    """Convert TARS instrument naming (``BINANCE:BTCUSDT``) to
    Binance's bare symbol (``BTCUSDT``)."""

    if ":" in instrument:
        return instrument.split(":", 1)[1]
    return instrument


def _binance_status_to_local(status: str) -> OrderStatus:
    return {
        "NEW": OrderStatus.OPEN,
        "PARTIALLY_FILLED": OrderStatus.PARTIAL,
        "FILLED": OrderStatus.FILLED,
        "CANCELED": OrderStatus.CANCELED,
        "REJECTED": OrderStatus.REJECTED,
        "EXPIRED": OrderStatus.CANCELED,
    }.get(status.upper(), OrderStatus.OPEN)


class BinanceAdapter(ExecAdapter):
    """Live (or testnet) Binance Spot adapter.

    Maintains an in-memory ``order_id → Order`` map indexed by
    Binance's ``orderId``. Fills are produced two ways:

    1. **On submit**: if the response carries ``fills`` (market
       orders typically fill instantly), we emit them
       immediately via the callback.
    2. **On status poll**: if the cached fill count is below the
       reported ``executedQty``, we synthesise the missing
       fills against the reported ``cummulativeQuoteQty`` /
       ``executedQty`` average so the position book stays in
       sync. Workshop attendees can call ``status`` from the
       cockpit to "pull" updates without a websocket.
    """

    def __init__(
        self,
        config: BinanceConfig,
        *,
        client: BinanceClient | None = None,
        on_fill: Callable[[Order, Fill], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config
        self.name = config.name
        self._client = client or BinanceClient(config)
        self._orders: dict[str, Order] = {}
        self._intent_to_order: dict[str, str] = {}
        self._exchange_id_to_local: dict[int, str] = {}
        self._symbol_for_order: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._on_fill = on_fill

    # ----------------------------------------------------- adapter API

    async def submit(self, intent: OrderIntent) -> Order:
        async with self._lock:
            if intent.intent_id in self._intent_to_order:
                return self._orders[self._intent_to_order[intent.intent_id]]

            symbol = _binance_symbol(intent.instrument)
            order = Order(
                order_id=f"binord_{uuid.uuid4().hex[:12]}",
                intent_id=intent.intent_id,
                strategy_fingerprint=intent.strategy_fingerprint,
                instrument=intent.instrument,
                side=intent.side,
                qty=float(intent.qty),
                type=intent.type,
                price=intent.price,
                status=OrderStatus.NEW,
                submitted_at=time.time(),
            )
            self._orders[order.order_id] = order
            self._intent_to_order[intent.intent_id] = order.order_id
            self._symbol_for_order[order.order_id] = symbol

        try:
            payload = await asyncio.to_thread(
                self._client.new_order,
                symbol=symbol,
                side=intent.side.value.upper(),
                order_type=intent.type.value.upper(),
                quantity=float(intent.qty),
                price=intent.price,
                new_client_order_id=intent.intent_id,
                time_in_force=intent.time_in_force,
            )
        except (BinanceAPIError, BinanceTransportError) as exc:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = str(exc)
            order.closed_at = time.time()
            return order

        # Submit-path: don't fire on_fill — the router iterates
        # ``order.fills`` after submit() returns and dispatches
        # them itself. Firing here would double-count.
        self._absorb_response(order, payload)
        return order

    async def cancel(self, order_id: str) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise KeyError(order_id)
            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.REJECTED,
            ):
                return order
            symbol = self._symbol_for_order.get(order_id) or _binance_symbol(
                order.instrument
            )
            exchange_id = self._exchange_id_for_local(order_id)

        try:
            await asyncio.to_thread(
                self._client.cancel_order,
                symbol=symbol,
                order_id=exchange_id,
                orig_client_order_id=(
                    order.intent_id if exchange_id is None else None
                ),
            )
        except BinanceAPIError as exc:
            # Already gone / unknown — treat as canceled.
            order.status = OrderStatus.CANCELED
            order.closed_at = time.time()
            order.rejection_reason = f"binance: {exc}"
            return order
        order.status = OrderStatus.CANCELED
        order.closed_at = time.time()
        return order

    async def status(self, order_id: str) -> Order | None:
        order = self._orders.get(order_id)
        if order is None:
            return None
        if order.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
        ):
            return order

        symbol = self._symbol_for_order.get(order_id) or _binance_symbol(
            order.instrument
        )
        exchange_id = self._exchange_id_for_local(order_id)
        try:
            payload = await asyncio.to_thread(
                self._client.query_order,
                symbol=symbol,
                order_id=exchange_id,
                orig_client_order_id=(
                    order.intent_id if exchange_id is None else None
                ),
            )
        except BinanceAPIError as exc:
            # Order vanished — mark canceled so the gate moves on.
            order.status = OrderStatus.CANCELED
            order.closed_at = time.time()
            order.rejection_reason = f"binance: {exc}"
            return order

        # Status-path: router doesn't iterate; we have to push
        # newly observed fills to the on_fill callback directly.
        new_fills = self._absorb_response(order, payload)
        if self._on_fill is not None:
            for fill in new_fills:
                await self._on_fill(order, fill)
        return order

    # ----------------------------------------------------- internals

    def _exchange_id_for_local(self, local_id: str) -> int | None:
        for ex_id, lid in self._exchange_id_to_local.items():
            if lid == local_id:
                return ex_id
        return None

    def _absorb_response(
        self, order: Order, payload: Mapping[str, Any]
    ) -> list[Fill]:
        """Mutate ``order`` in place from a Binance response and
        return the *new* fills observed (so the caller can decide
        whether to fan them out to ``on_fill``).
        """

        ex_id = payload.get("orderId")
        if isinstance(ex_id, (int, str)):
            try:
                ex_id_int = int(ex_id)
                self._exchange_id_to_local[ex_id_int] = order.order_id
            except (TypeError, ValueError):
                pass

        fills = payload.get("fills") or []
        new_fills: list[Fill] = []
        if isinstance(fills, list) and fills:
            already = {f.fill_id for f in order.fills}
            for raw in fills:
                fill_id = str(
                    raw.get("tradeId")
                    or raw.get("id")
                    or f"fil_{uuid.uuid4().hex[:12]}"
                )
                if fill_id in already:
                    continue
                qty = float(raw.get("qty", 0.0) or 0.0)
                if qty <= 0:
                    continue
                price = float(raw.get("price", 0.0) or 0.0)
                fee = float(raw.get("commission", 0.0) or 0.0)
                fill = Fill(
                    fill_id=fill_id,
                    order_id=order.order_id,
                    qty=qty,
                    price=price,
                    fee=fee,
                    ts=float(payload.get("transactTime", time.time() * 1000)) / 1000.0,
                    reference_price=order.price,
                )
                order.fills.append(fill)
                new_fills.append(fill)

        executed = float(payload.get("executedQty", 0.0) or 0.0)
        cumm_quote = float(payload.get("cummulativeQuoteQty", 0.0) or 0.0)
        already_filled = sum(f.qty for f in order.fills)
        gap = executed - already_filled
        if gap > 1e-12 and cumm_quote > 0 and executed > 0:
            avg_price = cumm_quote / executed
            ts = float(payload.get("transactTime", time.time() * 1000)) / 1000.0
            synth = Fill(
                fill_id=f"syn_{uuid.uuid4().hex[:12]}",
                order_id=order.order_id,
                qty=gap,
                price=avg_price,
                fee=0.0,
                ts=ts,
                reference_price=order.price,
            )
            order.fills.append(synth)
            new_fills.append(synth)

        status = str(payload.get("status") or "").upper()
        if status:
            order.status = _binance_status_to_local(status)
        if order.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
        ) and order.closed_at is None:
            order.closed_at = time.time()

        return new_fills

    # ----------------------------------------------------- introspection

    def all_orders(self) -> list[Order]:
        return list(self._orders.values())

    def open_orders(self) -> list[Order]:
        return [
            o
            for o in self._orders.values()
            if o.status not in (
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.REJECTED,
            )
        ]


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------


class BinanceAPIError(RuntimeError):
    """4xx / 5xx response from Binance — typed so the adapter
    can decide whether to mark the order rejected vs canceled."""

    def __init__(self, *, code: int, msg: str, http_status: int) -> None:
        super().__init__(f"binance {http_status}: {msg} (code={code})")
        self.code = code
        self.msg = msg
        self.http_status = http_status


class BinanceTransportError(RuntimeError):
    """Network / parsing failure before we got a structured
    response. Treated as transient by the adapter (caller may
    retry)."""


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _format_qty(qty: float) -> str:
    # Binance accepts decimal strings; trim trailing zeros to
    # avoid step-size mismatch warnings on testnet.
    s = f"{float(qty):.8f}".rstrip("0").rstrip(".")
    return s or "0"


def _format_price(price: float | None) -> str:
    if price is None:
        return "0"
    s = f"{float(price):.8f}".rstrip("0").rstrip(".")
    return s or "0"
