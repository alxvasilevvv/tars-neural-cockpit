# Algotrade module — Phase W1 + W2-PR1 reference

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
5. **(W2-PR1)** A **paper-trading execution layer**
   (`algotrade.exec`): order router → risk gate → adapter → audit
   log → position book → session manager. Same dataclasses the
   live Binance adapter (W2-PR2) will plug into; same `Bar` type
   the backtest engine consumes.

W2-PR2 will add the Binance live adapter behind a vault key. W3
brings PnL attribution and the trading council. W4 the
workshop-lab multi-attendee mode.

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

## 6. Execution layer (W2-PR1)

```python
from backend.core.algotrade.exec import (
    OrderIntent, OrderType, Side,
    PaperAdapter, PaperConfig,
    PositionStore, RiskGate, RiskPolicy,
    AuditLog, OrderRouter,
    SessionStore, get_runtime,
)
```

The execution layer turns "my backtest looks great" into "send
a real order" with **zero translation surface** — the same `Bar`
the backtest harness consumes is what `PaperAdapter.on_bar`
takes, and the `Strategy` IR fingerprint is the audit anchor for
every intent.

### Building blocks

- `OrderIntent` — what the strategy / operator WANTS, pre-gate.
  Carries an `intent_id` the router de-dupes on (idempotent
  retries are safe).
- `RiskGate(policy=RiskPolicy(...), positions=...)` — pre-trade
  policy enforcement. Workshop-grade explicit rules: kill-switch,
  per-order qty cap, position-notional cap, max open positions,
  daily-loss kill-switch, no-short toggle, instrument allowlist.
  Returns a `GateVerdict` (accepted / reason / triggered_rules).
- `PaperAdapter(PaperConfig(commission_bps=…, slippage_bps=…))` —
  market orders fill at next bar's open with configured
  slippage; limit orders fill when the bar's range crosses
  the price.
- `PositionStore` — instrument-keyed open position book. Realises
  PnL on closing legs; rolls residual qty on long↔short flips.
  Backed by a JSON file so worker restarts pick up cleanly.
- `OrderRouter(adapter=…, gate=…, positions=…, audit=…)` — the
  one funnel every order goes through:
  `intent → verdict → order → fill`. Everything is appended to
  the per-session JSONL `AuditLog`.
- `SessionStore` — `(session_id, mode, strategy_fingerprint,
  status, sandbox_id, started_at)` rows persisted as JSONL so
  the cockpit can list them across worker restarts.
- `get_runtime()` — process-singleton that owns
  `session_id → (router, adapter, positions, audit, gate)` and
  rehydrates from disk on cold start.

### Domain pack actions (W2-PR1)

The `algotrade` domain pack now exposes the full paper cycle as
HTTP-addressable actions (under
`/api/domains/algotrade/actions/<id>/invoke`):

| Action                  | Destructive | Purpose                                                  |
| ----------------------- | ----------- | -------------------------------------------------------- |
| `start_paper_session`   | ✓           | Spin up a session bound to a registered strategy.        |
| `stop_session`          | ✓           | Close a session — no more intents accepted.              |
| `list_sessions`         |             | Filter by `mode` / `sandbox_id`.                         |
| `get_session`           |             | Snapshot: session, policy, positions, open orders, audit.|
| `submit_intent`         | ✓           | Operator-issued intent; goes through the gate.           |
| `cancel_order`          | ✓           | Cancel an open order.                                    |
| `feed_bar`              |             | Advance the paper clock by one OHLCV bar.                |
| `get_policy`            |             | Read the active risk policy.                             |
| `set_policy`            | ✓           | Replace the risk policy (kill-switch, caps, allowlist).  |
| `audit_tail`            |             | Last N audit events (intent / verdict / order / fill).   |

The `live_sessions` awareness source is the cockpit-facing
read-only roll-up (id, status, position count, realised +
unrealised PnL totals, kill-switch state) so the dashboard
doesn't spam `get_session` per row.

## 7. Tests

`tests/test_algotrade_strategy_ir.py` (24) ·
`tests/test_algotrade_registry.py` (10) ·
`tests/test_algotrade_indicators.py` (15) ·
`tests/test_algotrade_backtest.py` (15) ·
`tests/test_algotrade_pack.py` (26) ·
`tests/test_algotrade_exec.py` (32) ·
`tests/test_algotrade_exec_actions.py` (18) — **140 assertions,
0 network**, deterministic.

Run them as:

```
.venv/bin/python -m pytest tests/test_algotrade_*.py -q
```

## 8. Roadmap (Phase W)

| Phase   | What lands                                                                                  | Status                            |
| ------- | ------------------------------------------------------------------------------------------- | --------------------------------- |
| **W1a** | Strategy IR + registry + backtest + indicators + recipes                                    | shipped (PR #165)                 |
| **W1b** | `algotrade` domain pack — `parse`, `register`, `fork`, `backtest`, recipe + registry verbs  | shipped (PR #165)                 |
| **W2-PR1** | Paper executor + risk gate + order router + position store + session manager + 10 HTTP actions | this PR                           |
| **W2-PR2** | Live Binance adapter behind vault key + market-data poller                              | follow-up                         |
| **W3-PR1** | PnL attribution (by-instrument + by-strategy + trade ledger + curve) + slippage ledger + session metrics | this PR                |
| **W3-PR2** | Markdown session report (assemble + render to attendee handout)                         | follow-up                         |
| **W3-PR3** | Trading council voices (RiskAnalyst / ExecutionTrader / PnLAuditor commentary)          | follow-up                         |
| **W4-PR1** | Workshop quant playbooks + recursive playbook loader (5 quant recipes, derived-pack chain) | shipped (PR #167)              |
| **W4-PR2** | Workshop lab mode (multi-attendee sandbox + leaderboard) + cockpit handbook              | follow-up                         |

See [SYNC issue #163](https://github.com/alxvasilevvv/tars-neural-cockpit/issues/163) for the lane split with Claude.

## 9. Analytics layer (W3-PR1)

The W2-PR1 audit log is append-only JSONL of every intent /
verdict / order / fill. The analytics module
(`backend/core/algotrade/exec/analytics.py`) replays it offline
to produce three immutable dataclasses, all stdlib-only,
JSON-roundtrippable, and zero-look-ahead:

| Dataclass            | Surfaces                                                                                                    |
| -------------------- | ----------------------------------------------------------------------------------------------------------- |
| `PnLAttribution`     | `realized_total`, `unrealized_total`, `fees_total`, `by_instrument`, `by_strategy`, `trades` (`RoundTrip[]`), `pnl_curve` |
| `SlippageReport`     | per-fill `SlippageEntry[]`, `fills_total / with_reference / missing_reference`, `total_slippage_cost`, `avg / p50 / p95 / worst` bps, `by_instrument` |
| `SessionMetrics`     | `intents_total / accepted / rejected`, `orders_total`, `fills_total`, `cancels_total`, `realized_pnl`, `unrealized_pnl`, `fees_total`, `total_slippage_cost`, `open_positions`, `duration_seconds`, `acceptance_rate` |

Trade-matching mirrors the position store's weighted-average
entry exactly: a `RoundTrip` is emitted on every closing leg
(reduce / flip), with the closing leg's realised PnL net of
fees. Pyramiding (long → long add) updates the running average
without emitting a trip, exactly like the live book.

Slippage requires `Fill.reference_price` (bar.open for market,
limit price for limit). The paper adapter populates it
automatically. Live adapters that don't fill it are silently
skipped from the bps stats but still counted in
`fills_missing_reference` so the cockpit can warn "live adapter
without reference prices".

Three new domain-pack actions invoke the analyser:

| Action ID         | What it returns                                                                                                  |
| ----------------- | ---------------------------------------------------------------------------------------------------------------- |
| `pnl_report`      | `PnLAttribution.to_dict()` for the session, with optional `trades_limit` to trim the round-trip list.            |
| `slippage_report` | `SlippageReport.to_dict()`, with optional `entries_limit` to trim per-fill entries.                              |
| `session_summary` | Full snapshot: session row + active risk policy + `SessionMetrics.to_dict()` + open positions.                   |

These three are read-only (no `destructive=True`) so playbooks
can poll them as often as needed without going through the risk
gate.

Example end-to-end (paper session, 5 bps slippage, 1 bp
commission, buy 1 @ 100, sell 1 @ 110):

```
session_summary →
  intents=2, accepted=2, rejected=0, fills=2, open_positions=0
  realized_pnl=9.895, fees_total=0.021, total_slippage_cost=0.105
slippage_report →
  fills_with_reference=2, avg_slippage_bps=5.0, total_slippage_cost=0.105
pnl_report →
  trades_count=1, realized_total=9.895, by_strategy={fp_test: {realized:9.895,...}}
```

## 10. Workshop quant playbooks (W4-PR1)

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
