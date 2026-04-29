"""Cost & token rollups derived from the meeet event store."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

from backend.core.meeet import StoredEvent, get_store


@dataclass(frozen=True)
class PriceEntry:
    """USD per million tokens for a single model."""

    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True)
class PriceTable:
    """Approximate pricing.

    Prices are USD-per-million-tokens; the ledger is happy to carry
    None for unknown models.
    """

    entries: Mapping[str, PriceEntry]

    def lookup(self, model: str) -> PriceEntry | None:
        if not model:
            return None
        if model in self.entries:
            return self.entries[model]
        # Allow "anthropic/claude-..." short prefix lookup.
        for k, v in self.entries.items():
            if model.startswith(k):
                return v
        return None

    def cost_usd(
        self, model: str, tokens_in: int, tokens_out: int
    ) -> float | None:
        entry = self.lookup(model)
        if entry is None:
            return None
        return round(
            (tokens_in / 1_000_000.0) * entry.input_per_mtok
            + (tokens_out / 1_000_000.0) * entry.output_per_mtok,
            6,
        )


# Sane defaults — easy to override via env or by passing a custom table.
_DEFAULT_ENTRIES: dict[str, PriceEntry] = {
    "anthropic/claude-3-5-sonnet-20241022": PriceEntry(3.0, 15.0),
    "anthropic/claude-3-5-haiku": PriceEntry(0.8, 4.0),
    "anthropic/claude-3-opus": PriceEntry(15.0, 75.0),
    "openai/gpt-4o-mini": PriceEntry(0.15, 0.60),
    "openai/gpt-4o": PriceEntry(2.5, 10.0),
    "openai/gpt-4.1": PriceEntry(2.0, 8.0),
    "openai/gpt-4.1-mini": PriceEntry(0.4, 1.6),
    # Local voices have zero direct API cost; tracked anyway so dashboards
    # show the deterministic vs paid split.
    "tars-local-v1": PriceEntry(0.0, 0.0),
    "tars-mock-cloud-v1": PriceEntry(0.0, 0.0),
    "tars-local-chat-v1": PriceEntry(0.0, 0.0),
}


def default_price_table() -> PriceTable:
    return PriceTable(entries=dict(_DEFAULT_ENTRIES))


@dataclass(frozen=True)
class UsageLine:
    """A single ``usage.tokens`` data point pulled from the event store."""

    ts: float
    trace_id: str | None
    session_id: str | None
    route: str | None
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float | None
    kind: str  # source event kind, usually "usage.tokens" or "sampler.decision"


@dataclass(frozen=True)
class UsageRollup:
    """Aggregated usage for the dashboard."""

    total_calls: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_route: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_session: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "by_model": self.by_model,
            "by_route": self.by_route,
            "by_session": self.by_session,
        }


class UsageLedger:
    """Derives token + cost rollups from the meeet event store.

    No DB of its own. Stateless aside from the price table.
    """

    USAGE_KIND = "usage.tokens"

    def __init__(self, price_table: PriceTable | None = None, *, store=None) -> None:
        self.prices = price_table or default_price_table()
        self.store = store if store is not None else get_store()

    async def list_lines(
        self,
        *,
        limit: int = 500,
        since: float | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[UsageLine]:
        events = await self.store.list_events(
            limit=limit,
            since=since,
            kind=self.USAGE_KIND,
            session_id=session_id,
            trace_id=trace_id,
        )
        return [self._line_from_event(ev) for ev in events]

    async def rollup(
        self,
        *,
        limit: int = 1000,
        since: float | None = None,
        session_id: str | None = None,
    ) -> UsageRollup:
        lines = await self.list_lines(
            limit=limit, since=since, session_id=session_id
        )
        return self._rollup(lines)

    # -- internals -------------------------------------------------------

    def _line_from_event(self, ev: StoredEvent) -> UsageLine:
        payload = ev.payload or {}
        model = str(payload.get("model") or "")
        tokens_in = int(payload.get("tokens_in") or 0)
        tokens_out = int(payload.get("tokens_out") or 0)
        latency_ms = float(payload.get("latency_ms") or 0.0)
        cost = payload.get("cost_usd")
        if cost is None:
            cost = self.prices.cost_usd(model, tokens_in, tokens_out)
        return UsageLine(
            ts=ev.ts,
            trace_id=ev.trace_id,
            session_id=ev.session_id,
            route=ev.route,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            kind=ev.kind,
        )

    @staticmethod
    def _rollup(lines: Iterable[UsageLine]) -> UsageRollup:
        total_calls = 0
        total_in = 0
        total_out = 0
        total_cost = 0.0
        by_model: dict[str, dict[str, Any]] = {}
        by_route: dict[str, dict[str, Any]] = {}
        by_session: dict[str, dict[str, Any]] = {}

        def _bucket(d: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
            if not key:
                key = "(unset)"
            cur = d.get(key)
            if cur is None:
                cur = {
                    "calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": 0.0,
                    "latency_ms_total": 0.0,
                }
                d[key] = cur
            return cur

        for ln in lines:
            total_calls += 1
            total_in += ln.tokens_in
            total_out += ln.tokens_out
            cost_value = ln.cost_usd or 0.0
            total_cost += cost_value
            for bucket_dict, key in (
                (by_model, ln.model or "(unknown)"),
                (by_route, ln.route or "(unset)"),
                (by_session, ln.session_id or "(unset)"),
            ):
                b = _bucket(bucket_dict, key)
                b["calls"] += 1
                b["tokens_in"] += ln.tokens_in
                b["tokens_out"] += ln.tokens_out
                b["cost_usd"] = round(b["cost_usd"] + cost_value, 6)
                b["latency_ms_total"] = round(
                    b["latency_ms_total"] + ln.latency_ms, 3
                )

        return UsageRollup(
            total_calls=total_calls,
            total_tokens_in=total_in,
            total_tokens_out=total_out,
            total_cost_usd=round(total_cost, 6),
            by_model=by_model,
            by_route=by_route,
            by_session=by_session,
        )


_SINGLETON: Optional[UsageLedger] = None


def get_ledger() -> UsageLedger:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = UsageLedger()
    return _SINGLETON


def reset_ledger() -> None:
    """Test helper: drop the cached singleton."""

    global _SINGLETON
    _SINGLETON = None


# Allow operators to override the global price table from a JSON file
# or env var (e.g. real production prices vs published list prices).
# This is opt-in to keep the default deterministic for tests.
def _maybe_load_env_prices() -> dict[str, PriceEntry]:
    raw = os.getenv("TARS_PRICE_OVERRIDES_JSON", "").strip()
    if not raw:
        return {}
    try:
        import json

        data = json.loads(raw)
        out: dict[str, PriceEntry] = {}
        if isinstance(data, dict):
            for model, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                try:
                    out[model] = PriceEntry(
                        float(entry.get("input_per_mtok") or 0.0),
                        float(entry.get("output_per_mtok") or 0.0),
                    )
                except (TypeError, ValueError):
                    continue
        return out
    except Exception:
        return {}


_overrides = _maybe_load_env_prices()
if _overrides:
    _DEFAULT_ENTRIES.update(_overrides)
