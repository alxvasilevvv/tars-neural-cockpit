# Algotrade module — Phase W1 reference

> Foundations for the **Cresco workshop** (\"The Algorithmic Edge\").
> See `docs/CRESCO_WORKSHOP.md` (operator) for the audience-facing
> guide and SYNC issue **#163** for the full Phase W plan.

The `backend/core/algotrade/` module gives TARS:

1. A **JSON IR** for trading strategies (`algotrade.strategy.ir`).
2. A **versioned, file-backed registry** (`algotrade.strategy.registry`).
3. A **deterministic, stdlib-only backtest engine**
   (`algotrade.backtest`) with incremental indicators (SMA / EMA /
   RSI / ATR / Bollinger).
4. A **recipe gallery** (`algotrade.recipes`) — 4 starter
   strategies operators fork from in the workshop's vibe-coding
   step.

W2 will add the live execution layer (paper + Binance), risk gate
and order router. W3 brings PnL attribution and the trading
council. W4 the workshop-lab multi-attendee mode.

## 1. Strategy IR

The IR is the **single source of truth** for every strategy. The
backtest engine, the live executor, the risk gate, the council
voices, and the cockpit visualiser all consume the same dataclass.
There is no second representation.

```python
from backend.core.algotrade import (
    Condition, Indicator, Operator, Side, SizingRule,
    Strategy, Timeframe,
)

s = Strategy(
    name="BB Reversion 4h BTC",
    description="long when close < lower 2σ band; exit at SMA",
    instrument="BINANCE:BTCUSDT",
    timeframe=Timeframe.H4,
    side=Side.LONG,
    entry=Condition(op=Operator.LT, args=[
        Indicator(name="close"),
        Indicator(name="bb_lower", params={"period": 20, "k": 2}),
    ]),
    exit=Condition(op=Operator.GT, args=[
        Indicator(name="close"),
        Indicator(name="sma", params={"period": 20}),
    ]),
    sizing=SizingRule(kind="risk_pct", risk_pct=0.01),
    stop_loss_pct=0.03,
)
s.validate()         # raises StrategyError if anything is off
fp = s.fingerprint() # "sha256:…", deterministic, sorted-JSON hash
```

Hard guarantees:

- **Round-trippable.** `Strategy.from_dict(s.to_dict()).fingerprint()
  == s.fingerprint()`. Field order doesn't matter.
- **Closed-world enums.** Indicator / operator / sizing names are
  enums — typos fail at parse time.
- **Stop / TP / trailing pcts** are open intervals `(0, 1)`. A 100 %
  stop is rejected.
- **`risk_pct` sizing** requires a `stop_loss_pct` (so risk per
  trade is computable).
- **No imperative escape hatch.** The IR is data. To extend the
  language: add an enum value + a handler.

### Indicator catalogue

| Name        | Params                     | Notes                          |
| ----------- | -------------------------- | ------------------------------ |
| `open`      | —                          | bar field                      |
| `high`      | —                          | bar field                      |
| `low`       | —                          | bar field                      |
| `close`     | —                          | bar field                      |
| `volume`    | —                          | bar field                      |
| `sma`       | `period: int`              | simple MA                      |
| `ema`       | `period: int`              | exponential MA (SMA-seeded)    |
| `rsi`       | `period: int`              | Wilder RSI                     |
| `atr`       | `period: int`              | Wilder ATR                     |
| `bb_mid`    | `period: int`, `k: float`  | Bollinger middle (= SMA)       |
| `bb_upper`  | `period: int`, `k: float`  | Bollinger upper band           |
| `bb_lower`  | `period: int`, `k: float`  | Bollinger lower band           |

Adding one: see `backend/core/algotrade/backtest/indicators.py`
(register in `INDICATORS` dict + add a class with
`update(bar) -> float | None`).

### Operators

`lt`, `le`, `gt`, `ge`, `eq`, `and`, `or`, `not`, `crosses_above`,
`crosses_below`. The `crosses_*` operators read indicator state from
the previous bar; without two bars of warm-up they degrade
gracefully to plain `gt` / `lt`.

### Sizing modes

- `fixed_qty` — `qty: 0.01` → always send 0.01 units.
- `fixed_notional` — `notional: 1000` → send `notional / fill_price`.
- `risk_pct` — size so the implied loss to `stop_loss_pct` equals
  `risk_pct * equity`. Requires `stop_loss_pct`.

## 2. Strategy registry

File-backed, JSONL on disk under `$TARS_HOME/algotrade/strategies/`
(default `~/.tars/algotrade/strategies/`):

```text
strategies/
├── by-fingerprint/sha256/<full-hash>.json    canonical IR
├── by-name/<slug>.jsonl                      version history
└── index.jsonl                               append-only index
```

Why a flat file: every workshop attendee runs TARS locally and
deserves a registry they can `cat` and `git diff`. Sqlite backend
behind the same `StrategyRegistry` interface lands later if scale
demands it.

```python
from backend.core.algotrade import get_registry

reg = get_registry()
row = reg.put(s, author="op", parent_fingerprint=None)
# row.fingerprint, row.version, row.created_at, row.author, row.metadata

# Idempotent: re-putting the same fingerprint returns the existing row.
same = reg.put(s)
assert same.version == row.version

# Versions list: every put with a new fingerprint bumps the version.
reg.versions("BB Reversion 4h BTC")  # → [v1, v2, …]
reg.latest("BB Reversion 4h BTC")    # → v_n
reg.search(tag="mean_reversion")
reg.search(instrument="BINANCE:BTCUSDT")
```

Concurrency: `threading.Lock` per process. Cross-process locking
is **not** implemented yet because workshop attendees each run
their own backend. We'll add `fcntl.flock` on the index when
the workshop scales to a shared server.

## 3. Backtest engine

Stdlib-only event loop, bar by bar. Honest by design:

- **No look-ahead.** Conditions evaluated at bar `t`'s close fill
  at bar `t+1`'s open. The first trade in any test that uses
  `crosses_above` is verified against this rule.
- **Realistic costs.** Per-side commission (default 10 bp) plus a
  configurable slippage model:
  - `none` — debug only.
  - `fixed_bp` — `bps * fill_price` offset (default 1 bp).
  - `atr_pct` — `atr * pct/100` offset (uses live ATR if
    referenced).
- **Single position v1.** `max_positions=1` is enforced; the IR
  field exists so a v2 multi-position scheduler can land
  without an IR change.
- **Deterministic.** Same `(strategy_fingerprint, bars)` →
  bit-identical equity curve, trades, metrics. Backtest cache key
  reuses the strategy fingerprint.

```python
from backend.core.algotrade.backtest.harness import (
    BacktestConfig, run_backtest,
)
from backend.core.algotrade.backtest.data import load_csv

bars = load_csv("path/to/btcusdt_1h.csv")
res = run_backtest(s, bars, config=BacktestConfig(
    initial_equity=10_000.0,
    commission_bp=10.0,
    slippage_model="fixed_bp",
    slippage_bp=1.0,
))
print(res.metrics["sharpe"], res.metrics["max_drawdown"])
print([t.exit_reason for t in res.trades])
```

`res.to_dict()` is fully JSON-serialisable: drop into the cockpit's
`/api/algotrade/backtest` SSE stream as-is.

### Metrics surfaced

`total_return` · `cagr` · `sharpe` · `sortino` · `max_drawdown` ·
`win_rate` · `loss_rate` · `profit_factor` · `expectancy` ·
`trades` · `avg_trade_pct` · `exposure`. All annualised against the
average bar interval inferred from the equity curve.

## 4. Data loaders

```python
from backend.core.algotrade.backtest.data import (
    load_csv,            # local CSV (ts,open,high,low,close,volume)
    load_binance_klines, # Binance spot, async, 1k bar limit per call
)

bars = await load_binance_klines("BTCUSDT", interval="4h", limit=500)
```

CSV header MUST be `ts,open,high,low,close,volume`. `ts` is epoch
seconds (close time).

## 5. Recipes

```python
from backend.core.algotrade.recipes import list_recipes, load_recipe

list_recipes()
# → ['bollinger_reversion', 'ma_cross', 'rsi_oversold', 'trailing_runner']

s = load_recipe("ma_cross")
# Fully validated Strategy IR ready to backtest or fork.
```

The 4 starter recipes are intentionally diverse:

| Recipe                | Mental model         | Sizing       | Stops               |
| --------------------- | -------------------- | ------------ | ------------------- |
| `ma_cross`            | trend-following      | risk_pct=1 % | stop_loss=3 %       |
| `bollinger_reversion` | mean-reversion       | risk_pct=1 % | stop_loss=3 %       |
| `rsi_oversold`        | momentum exhaustion  | fixed_qty    | stop=2 % / TP=5 %   |
| `trailing_runner`     | trend + let it run   | risk_pct=1 % | stop=4 % / trail=5 %|

Forking flow (W1-PR2 wires this into the `algotrade` domain pack):

```text
fork(recipe="ma_cross") → Strategy v1
↓
refine("instrument BINANCE:ETHUSDT, timeframe 4h, period 20/50") → v2
↓
backtest(v2, bars=load_binance_klines("ETHUSDT", "4h", 500)) → metrics
↓
register(v2)
↓
deploy(v2, mode="paper")  ← W2
```

## 6. Tests

`tests/test_algotrade_strategy_ir.py` (24) ·
`tests/test_algotrade_registry.py` (10) ·
`tests/test_algotrade_indicators.py` (15) ·
`tests/test_algotrade_backtest.py` (15) — **64 assertions, 0
network**, deterministic.

Run them as:

```
.venv/bin/python -m pytest tests/test_algotrade_*.py -q
```

## 7. Roadmap (Phase W)

| Phase   | What lands                                                                                  | PR                                |
| ------- | ------------------------------------------------------------------------------------------- | --------------------------------- |
| **W1a** | Strategy IR + registry + backtest + indicators + recipes                                    | this PR                           |
| **W1b** | `algotrade` domain pack — `generate_strategy`, `backtest`, `register`, `fork`, `refine`     | next                              |
| **W2**  | Paper executor + Binance live adapter + risk gate + order router + position store           | follow-up                         |
| **W3**  | PnL attribution + slippage ledger + session report + trading council voices                 | follow-up                         |
| **W4-PR1** | Workshop quant playbooks + recursive playbook loader (5 quant recipes, derived-pack chain) | this PR                          |
| **W4-PR2** | Workshop lab mode (multi-attendee sandbox + leaderboard) + cockpit handbook              | follow-up                         |

See [SYNC issue #163](https://github.com/alxvasilevvv/tars-neural-cockpit/issues/163) for the lane split with Claude.

## 9. Workshop quant playbooks (W4-PR1)

The 10 W2-PR1 execution actions (`start_paper_session`,
`submit_intent`, `feed_bar`, `set_policy`, `audit_tail`, …) are
composed into 5 runnable recipes for the Cresco workshop, living
under `playbooks/_workshop/quant/` and discovered automatically by
the recursive `discover()` loader. Run via the playbooks runner
(`backend/core/playbooks/runner.py`) or the cockpit's lab mode.

| Playbook id                            | What it does                                                                                  | Pack       |
| -------------------------------------- | --------------------------------------------------------------------------------------------- | ---------- |
| `_workshop.quant.recipe_to_paper`      | Pick a recipe → backtest → start paper session → seed bars → tail audit. The "first day" loop. | `algotrade` |
| `_workshop.quant.backtest_compare`     | Run two recipes against the same bar series; surface metrics for council debate.              | `algotrade` |
| `_workshop.quant.morning_pnl`          | Daily ops: list sessions → snapshot → audit_tail → log to memory.                             | `algotrade` |
| `_workshop.quant.risk_review`          | Pull current `RiskPolicy`, summarise audit breaches, propose tightened policy (no auto-apply).| `algotrade` |
| `_workshop.quant.strategy_lab`         | Design / mutate a `Strategy` IR, re-register, immediately backtest. Drives the lab UI loop.   | `algotrade` |

The recursive loader derives the `pack` field from the directory
chain (`_workshop.quant`) but the JSON's own `pack` field still
wins, so existing playbooks like
`_workshop/fund/portfolio_monitoring.json` — which declares
`"pack": "workshop"` — keep their explicit binding. New workshop
verticals can drop a `playbooks/_workshop/<vertical>/*.json`
directory in and get picked up on next `reset_loader_cache()`
without code changes.
