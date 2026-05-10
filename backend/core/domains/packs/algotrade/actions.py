"""Algotrade actions — the W1b action surface.

All handlers follow the standard TARS action contract: accept a
mapping, return a mapping, never raise for ordinary user input
(structured ``ok=False`` envelope instead).

Backtest data sources (in priority order):

1. ``bars`` (inline list of OHLCV dicts) — fastest, no network.
2. ``csv_path`` — local file, ``ts,open,high,low,close,volume``.
3. ``binance`` — ``{"symbol": "BTCUSDT", "interval": "1h",
   "limit": 500}`` — fetches via the algotrade data loader.

The handler validates exactly one source is provided.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from ...base import ActionSpec
from backend.core.algotrade import (
    Strategy,
    StrategyError,
    get_registry,
)
from backend.core.algotrade.backtest.data import (
    DataError,
    load_binance_klines,
    load_csv,
)
from backend.core.algotrade.backtest.harness import (
    Bar,
    BacktestConfig,
    BacktestError,
    run_backtest,
)
from backend.core.algotrade.recipes import list_recipes, load_recipe


# --------------------------------------------------------- helpers


def _err(error: str, **detail: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error": error}
    payload.update(detail)
    return payload


def _ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


def _strategy_from_args(args: Mapping[str, Any]) -> tuple[Strategy | None, dict[str, Any] | None]:
    """Resolve a strategy from one of: ``ir`` (inline IR dict),
    ``fingerprint`` (registry lookup), or ``recipe`` (starter pack)."""

    if "ir" in args and args["ir"] is not None:
        try:
            return Strategy.from_dict(args["ir"]), None
        except StrategyError as exc:
            return None, _err("invalid_ir", detail=str(exc))

    fingerprint = args.get("fingerprint")
    if fingerprint:
        row = get_registry().get(str(fingerprint))
        if row is None:
            return None, _err("strategy_not_found", fingerprint=fingerprint)
        return row.strategy, None

    recipe = args.get("recipe")
    if recipe:
        try:
            return load_recipe(str(recipe)), None
        except FileNotFoundError as exc:
            return None, _err("recipe_not_found", detail=str(exc))
        except StrategyError as exc:
            return None, _err("recipe_invalid", detail=str(exc))

    return None, _err(
        "missing_strategy_source",
        detail="provide one of: ir, fingerprint, recipe",
    )


# --------------------------------------------------------- recipe verbs


async def list_recipes_action(_args: Mapping[str, Any]) -> dict[str, Any]:
    return _ok(recipes=list_recipes())


async def load_recipe_action(args: Mapping[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    if not name:
        return _err("missing_name", detail="`name` is required (see list_recipes)")
    try:
        s = load_recipe(str(name))
    except FileNotFoundError:
        return _err("recipe_not_found", name=name)
    except StrategyError as exc:
        return _err("recipe_invalid", detail=str(exc))
    return _ok(name=name, strategy=s.to_dict(), fingerprint=s.fingerprint())


# --------------------------------------------------------- IR verbs


async def parse_strategy_action(args: Mapping[str, Any]) -> dict[str, Any]:
    raw = args.get("ir")
    if raw is None:
        return _err("missing_ir", detail="`ir` (object) is required")
    try:
        s = Strategy.from_dict(raw)
    except StrategyError as exc:
        return _err("invalid_ir", detail=str(exc))
    return _ok(strategy=s.to_dict(), fingerprint=s.fingerprint())


# --------------------------------------------------------- registry verbs


async def register_strategy_action(args: Mapping[str, Any]) -> dict[str, Any]:
    strategy, err = _strategy_from_args(args)
    if err is not None:
        return err
    assert strategy is not None  # for type checkers

    author = str(args.get("author") or "operator")
    parent_fp = args.get("parent_fingerprint")
    metadata = args.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return _err("invalid_metadata", detail="`metadata` must be an object")
    try:
        row = get_registry().put(
            strategy,
            author=author,
            parent_fingerprint=str(parent_fp) if parent_fp else None,
            metadata=dict(metadata),
        )
    except StrategyError as exc:
        return _err("registry_rejected", detail=str(exc))

    return _ok(
        slug=row.slug,
        version=row.version,
        fingerprint=row.fingerprint,
        author=row.author,
        parent_fingerprint=row.parent_fingerprint,
        created_at=row.created_at,
    )


async def list_strategies_action(args: Mapping[str, Any]) -> dict[str, Any]:
    reg = get_registry()
    tag = args.get("tag")
    instrument = args.get("instrument")
    author = args.get("author")
    rows = reg.search(
        tag=str(tag) if tag else None,
        author=str(author) if author else None,
        instrument=str(instrument) if instrument else None,
    )
    by_slug: dict[str, Any] = {}
    for r in rows:
        if r.slug not in by_slug or r.version > by_slug[r.slug]["version"]:
            by_slug[r.slug] = {
                "slug": r.slug,
                "name": r.strategy.name,
                "version": r.version,
                "fingerprint": r.fingerprint,
                "instrument": r.strategy.instrument,
                "timeframe": r.strategy.timeframe.value,
                "side": r.strategy.side.value,
                "tags": list(r.strategy.tags),
                "author": r.author,
                "created_at": r.created_at,
            }
    out = sorted(by_slug.values(), key=lambda x: x["name"])
    return _ok(count=len(out), strategies=out)


async def get_strategy_action(args: Mapping[str, Any]) -> dict[str, Any]:
    fp = args.get("fingerprint")
    if not fp:
        return _err("missing_fingerprint")
    row = get_registry().get(str(fp))
    if row is None:
        return _err("strategy_not_found", fingerprint=fp)
    return _ok(
        slug=row.slug,
        version=row.version,
        fingerprint=row.fingerprint,
        author=row.author,
        parent_fingerprint=row.parent_fingerprint,
        created_at=row.created_at,
        metadata=dict(row.metadata),
        strategy=row.strategy.to_dict(),
    )


async def fork_strategy_action(args: Mapping[str, Any]) -> dict[str, Any]:
    fp = args.get("fingerprint")
    if not fp:
        return _err(
            "missing_fingerprint",
            detail="`fingerprint` of the parent strategy is required",
        )
    row = get_registry().get(str(fp))
    if row is None:
        return _err("strategy_not_found", fingerprint=fp)

    new_name = args.get("new_name") or f"{row.strategy.name} (fork)"
    description = args.get("description") or row.strategy.description

    payload = row.strategy.to_dict()
    payload["name"] = new_name
    payload["description"] = description
    overrides = args.get("overrides") or {}
    if not isinstance(overrides, Mapping):
        return _err("invalid_overrides", detail="`overrides` must be an object")
    payload.update(dict(overrides))

    try:
        new_strategy = Strategy.from_dict(payload)
    except StrategyError as exc:
        return _err("fork_invalid", detail=str(exc))

    author = str(args.get("author") or "operator")
    persisted = get_registry().put(
        new_strategy,
        author=author,
        parent_fingerprint=row.fingerprint,
        metadata={"forked_from": row.fingerprint, "forked_at": time.time()},
    )
    return _ok(
        slug=persisted.slug,
        version=persisted.version,
        fingerprint=persisted.fingerprint,
        parent_fingerprint=persisted.parent_fingerprint,
        strategy=persisted.strategy.to_dict(),
    )


# --------------------------------------------------------- backtest verb


async def backtest_action(args: Mapping[str, Any]) -> dict[str, Any]:
    strategy, err = _strategy_from_args(args)
    if err is not None:
        return err
    assert strategy is not None

    bars, err = await _resolve_bars(args)
    if err is not None:
        return err
    assert bars is not None

    cfg = _resolve_config(args.get("config") or {})
    if isinstance(cfg, dict):
        return cfg  # error envelope

    try:
        result = run_backtest(strategy, bars, config=cfg)
    except BacktestError as exc:
        return _err("backtest_rejected", detail=str(exc))
    except StrategyError as exc:
        return _err("strategy_invalid", detail=str(exc))

    payload = result.to_dict()

    down_sample = args.get("equity_down_sample")
    if down_sample:
        try:
            n = int(down_sample)
        except (TypeError, ValueError):
            n = 0
        if n > 0 and len(payload["equity_curve"]) > n:
            payload["equity_curve"] = _down_sample_curve(payload["equity_curve"], n)
            payload["equity_curve_down_sampled"] = True
            payload["equity_curve_target_points"] = n

    return _ok(**payload)


def _resolve_config(raw: Mapping[str, Any]) -> BacktestConfig | dict[str, Any]:
    if not isinstance(raw, Mapping):
        return _err("invalid_config", detail="`config` must be an object")
    try:
        return BacktestConfig(
            initial_equity=float(raw.get("initial_equity", 10_000.0)),
            commission_bp=float(raw.get("commission_bp", 10.0)),
            slippage_model=str(raw.get("slippage_model", "fixed_bp")),
            slippage_bp=float(raw.get("slippage_bp", 1.0)),
            slippage_atr_pct=float(raw.get("slippage_atr_pct", 0.1)),
            seed=int(raw.get("seed", 42)),
            fill_at=str(raw.get("fill_at", "next_open")),
        )
    except (TypeError, ValueError) as exc:
        return _err("invalid_config", detail=str(exc))


async def _resolve_bars(args: Mapping[str, Any]) -> tuple[list[Bar] | None, dict[str, Any] | None]:
    sources = [k for k in ("bars", "csv_path", "binance") if args.get(k) is not None]
    if not sources:
        return None, _err(
            "missing_data",
            detail="provide one of: bars (inline), csv_path, binance",
        )
    if len(sources) > 1:
        return None, _err(
            "ambiguous_data",
            detail=f"provide exactly one of: bars / csv_path / binance, got {sources}",
        )

    if "bars" in args and args["bars"] is not None:
        raw = args["bars"]
        if not isinstance(raw, list):
            return None, _err("invalid_bars", detail="`bars` must be a list of objects")
        out: list[Bar] = []
        for i, row in enumerate(raw):
            try:
                out.append(
                    Bar(
                        ts=int(row["ts"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0.0)),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                return None, _err(
                    "invalid_bar",
                    index=i,
                    detail=str(exc),
                )
        return out, None

    if "csv_path" in args and args["csv_path"]:
        try:
            return load_csv(str(args["csv_path"])), None
        except DataError as exc:
            return None, _err("csv_failed", detail=str(exc))

    spec = args.get("binance") or {}
    if not isinstance(spec, Mapping):
        return None, _err("invalid_binance_spec", detail="`binance` must be an object")
    symbol = str(spec.get("symbol") or "")
    if not symbol:
        return None, _err("missing_binance_symbol", detail="`binance.symbol` required")
    interval = str(spec.get("interval") or "1h")
    limit = int(spec.get("limit") or 500)
    try:
        bars = await load_binance_klines(symbol, interval=interval, limit=limit)
    except DataError as exc:
        return None, _err("binance_failed", detail=str(exc))
    return bars, None


def _down_sample_curve(
    curve: list[Mapping[str, Any]], target: int
) -> list[Mapping[str, Any]]:
    """Bucket a dense equity curve down to ~``target`` points by
    averaging within evenly-spaced index windows. Anchor first +
    last points so the chart never lies about endpoints."""

    n = len(curve)
    if n <= target:
        return list(curve)
    bucket = n / target
    out: list[dict[str, Any]] = []
    for i in range(target):
        lo = int(i * bucket)
        hi = int((i + 1) * bucket)
        window = curve[lo:hi]
        if not window:
            continue
        avg_eq = sum(p["equity"] for p in window) / len(window)
        out.append({"ts": window[-1]["ts"], "equity": avg_eq})
    out[0] = dict(curve[0])
    out[-1] = dict(curve[-1])
    return out


# --------------------------------------------------------- specs


# Schemas (JSON Schema-ish — same shape used by every other pack)


_IR_SCHEMA = {
    "type": "object",
    "description": "Strategy IR — see backend/core/algotrade/strategy/ir.py",
}


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="list_recipes",
        name="List recipes",
        description=(
            "Catalogue of starter strategies. Each name resolves to a "
            "complete validated Strategy IR via load_recipe."
        ),
        handler=list_recipes_action,
        schema={"type": "object", "properties": {}},
    ),
    ActionSpec(
        id="load_recipe",
        name="Load recipe",
        description=(
            "Fetch a starter strategy by name (e.g. 'ma_cross', "
            "'bollinger_reversion', 'rsi_oversold', 'trailing_runner')."
        ),
        handler=load_recipe_action,
        schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    ),
    ActionSpec(
        id="parse_strategy",
        name="Parse strategy IR",
        description=(
            "Validate and canonicalise a Strategy IR. Returns the "
            "canonical dict + sha256 fingerprint."
        ),
        handler=parse_strategy_action,
        schema={
            "type": "object",
            "properties": {"ir": _IR_SCHEMA},
            "required": ["ir"],
        },
    ),
    ActionSpec(
        id="list_strategies",
        name="List stored strategies",
        description=(
            "Inventory of strategies in the local registry. Optional "
            "filters by tag / instrument / author."
        ),
        handler=list_strategies_action,
        schema={
            "type": "object",
            "properties": {
                "tag": {"type": "string"},
                "instrument": {"type": "string"},
                "author": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="get_strategy",
        name="Get stored strategy",
        description=(
            "Fetch a stored strategy by sha256 fingerprint. Returns "
            "the full row (IR + version + author + parent + metadata)."
        ),
        handler=get_strategy_action,
        schema={
            "type": "object",
            "properties": {"fingerprint": {"type": "string"}},
            "required": ["fingerprint"],
        },
    ),
    ActionSpec(
        id="register_strategy",
        name="Register strategy",
        description=(
            "Persist a strategy in the local registry. Idempotent on "
            "fingerprint. Provide one of: ir, fingerprint (re-stamp), "
            "recipe."
        ),
        handler=register_strategy_action,
        schema={
            "type": "object",
            "properties": {
                "ir": _IR_SCHEMA,
                "fingerprint": {"type": "string"},
                "recipe": {"type": "string"},
                "author": {"type": "string"},
                "parent_fingerprint": {"type": "string"},
                "metadata": {"type": "object"},
            },
        },
        destructive=True,
    ),
    ActionSpec(
        id="fork_strategy",
        name="Fork strategy",
        description=(
            "Duplicate a stored strategy as a new draft. Optionally "
            "overrides individual IR fields (instrument, sizing, "
            "stop_loss_pct, etc.). Persists the fork with parent_"
            "fingerprint set."
        ),
        handler=fork_strategy_action,
        schema={
            "type": "object",
            "properties": {
                "fingerprint": {"type": "string"},
                "new_name": {"type": "string"},
                "description": {"type": "string"},
                "overrides": {"type": "object"},
                "author": {"type": "string"},
            },
            "required": ["fingerprint"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="backtest",
        name="Backtest strategy",
        description=(
            "Run a backtest. Strategy via ir/fingerprint/recipe. Data "
            "via bars (inline) / csv_path / binance "
            "({symbol, interval, limit}). Optional config overrides "
            "and equity_down_sample for chart-friendly output."
        ),
        handler=backtest_action,
        schema={
            "type": "object",
            "properties": {
                "ir": _IR_SCHEMA,
                "fingerprint": {"type": "string"},
                "recipe": {"type": "string"},
                "bars": {"type": "array"},
                "csv_path": {"type": "string"},
                "binance": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "interval": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["symbol"],
                },
                "config": {
                    "type": "object",
                    "properties": {
                        "initial_equity": {"type": "number"},
                        "commission_bp": {"type": "number"},
                        "slippage_model": {"type": "string"},
                        "slippage_bp": {"type": "number"},
                        "slippage_atr_pct": {"type": "number"},
                        "seed": {"type": "integer"},
                        "fill_at": {"type": "string"},
                    },
                },
                "equity_down_sample": {"type": "integer"},
            },
        },
    ),
)
