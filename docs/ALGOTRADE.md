# Algotrade module — Phase W1 + W2 + W3 + W4-PR1 reference

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
   live Binance adapter (W2-PR2) plugs into; same `Bar` type the
   backtest engine consumes.
6. **(W2-PR2)** A **Binance Spot REST adapter**
   (`algotrade.exec.binance`) wired into the same router /
   audit / position pipeline. Defaults to Spot Testnet so
   workshop attendees never risk real funds; real-money mode
   requires kill_switch=OFF flip after manual verification.
7. **(W3-PR1 → W3-PR3)** PnL attribution + slippage ledger +
   session metrics + Markdown session report + trading council
   voices — all stdlib-only, deterministic, no LLM calls in the
   audit path.
8. **(W4-PR1)** Workshop quant playbooks + recursive
   playbook loader (5 quant recipes covering paper-trading,
   backtest comparison, morning PnL, risk review, strategy lab).

W4-PR2 is next: workshop lab mode (multi-attendee sandbox +
leaderboard) + cockpit handbook.

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
| **W2-PR1** | Paper executor + risk gate + order router + position store + session manager + 10 HTTP actions | shipped (PR #166)                |
| **W2-PR2** | Binance Spot REST adapter (testnet by default; live behind kill_switch=ON) + `start_live_session` action | this PR        |
| **W3-PR1** | PnL attribution (by-instrument + by-strategy + trade ledger + curve) + slippage ledger + session metrics | shipped (PR #168)      |
| **W3-PR2** | Markdown session report renderer (`session_report` action, ASCII PnL sparkline)         | shipped (PR #169)                 |
| **W3-PR3** | Trading council voices (RiskAnalyst / ExecutionTrader / PnLAuditor commentary)          | this PR                           |
| **W4-PR1** | Workshop quant playbooks + recursive playbook loader (5 quant recipes, derived-pack chain) | shipped (PR #167)              |
| **W4-PR2** | Workshop lab mode (multi-attendee sandbox + leaderboard) + cockpit handbook              | this PR                           |

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

## 10. Markdown session report (W3-PR2)

`backend/core/algotrade/exec/report.py` turns the W3-PR1
dataclasses into a self-contained Markdown handout — the
artefact a workshop attendee paste into Notion, e-mails to
their PM, or renders to PDF. `render_session_report(...)`
takes plain dataclasses (not a runtime handle) so a saved
JSONL audit can produce a report long after the session is
gone. Pure stdlib, deterministic.

Sections (fixed headings, search-stable):

1. `## Session` — id / mode / status / strategy fingerprint /
   instrument / started + closed timestamps / sandbox / notes.
2. `## Headline metrics` — realised + unrealised PnL, fees,
   slippage cost, avg slippage, intents accepted/total +
   acceptance rate, intents rejected, orders / fills /
   cancels, bars consumed, open positions, duration.
3. `## PnL attribution` — totals + cumulative PnL sparkline +
   by-instrument table + by-strategy table.
4. `## Top trades` — top-N winners + top-N detractors from
   the round-trip ledger.
5. `## Slippage` — total cost + avg / p50 / p95 / worst bps +
   coverage line + by-instrument table.
6. `## Risk policy` — kill switch, allow_short, all caps, and
   the allowlist.
7. `## Open positions` — only when present (otherwise omitted).

The action handler `algotrade.session_report` returns both the
rendered `markdown` and a structured `payload` (mirror of
every section), so the cockpit's chart layer + W3-PR3 council
voices reason over the same numbers without re-parsing
markdown.

The PnL sparkline uses Unicode block characters
(``▁▂▃▄▅▆▇█``) so it embeds safely in Markdown, Slack, and
e-mail; the cockpit can re-render the same data as a proper
chart from `PnLAttribution.pnl_curve`.

## 11. Trading council voices (W3-PR3)

Three deterministic, stdlib-only "agents" read the W3-PR1
analytics + W3-PR2 report payload and emit structured
commentary the cockpit can render alongside the markdown
report. **No LLM call** — workshops are reproducible (same
audit log → same verdicts) and transparent (every bullet is
explained by the rule that fired, with a `metrics_consulted`
audit trail of which numbers drove the verdict).

| Voice                | What it judges                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------- |
| `risk_analyst`       | Kill-switch state, daily-loss-limit proximity, verdict rejection rate, slippage cost vs realised PnL.           |
| `execution_trader`   | Avg / worst slippage bps, reference-price coverage, intent acceptance rate, cancel ratio.                       |
| `pnl_auditor`        | Win-rate, win/loss ratio, biggest contributor / detractor, fees-as-share-of-realised, by-strategy concentration. |

Each voice returns a `Voice` dataclass with:
- `severity ∈ {info, warn, alert}` — colour for the cockpit banner.
- `headline` — one-line summary for the voice's card.
- `bullets` — rationale list; cockpit renders as `- bullet`.
- `metrics_consulted` — which payload numbers drove the
  verdict. Useful when an attendee asks "where did this come
  from?".

`run_council(...)` invokes all three and returns a
`CouncilReview` whose `consensus` is the worst severity any
voice raised (cockpit colours the review banner off this).

The action `algotrade.council_review` exposes the same review
to playbooks / cockpit / external MCP clients.

## 12. Workshop quant playbooks (W4-PR1)

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

## 13. Live Binance adapter (W2-PR2)

Closes the workshop's "paper → testnet → live" cycle. Stdlib
only — `urllib.request` for HTTP, `hmac` + `hashlib` for
SHA-256 signing — so deploying live trading on a Cresco
workstation needs no new dependency, no docker network, no key
service. Three pieces:

```text
backend/core/algotrade/exec/binance.py
├─ BinanceConfig    # api_key, api_secret, testnet, recv_window_ms
├─ BinanceClient    # signed REST wrapper (server_time, account, new_order, query_order, cancel_order)
└─ BinanceAdapter   # ExecAdapter — submit / cancel / status, fills via response + status polling
```

### Testnet vs production

`BinanceConfig.testnet` defaults to **True**. Workshop attendees
mint a free key at https://testnet.binance.vision/ and the
adapter swings to `https://testnet.binance.vision`. The endpoint
shape is identical to production, so the same playbooks and
strategies that work on testnet translate to live with a single
flag.

| `testnet` | Base URL                          | Default policy on `start_live_session`               |
| --------- | --------------------------------- | ---------------------------------------------------- |
| `True`    | `https://testnet.binance.vision`  | `RiskPolicy(allow_short=False)` — runnable as-is     |
| `False`   | `https://api.binance.com`         | `RiskPolicy(kill_switch=True, allow_short=False)` — gate blocks every intent until the operator explicitly disables `kill_switch` via `set_policy` after manual verification |

### Wire contract (same as paper)

The adapter implements the same `ExecAdapter` ABC the paper
adapter does, so the router / risk gate / position book / audit
log / analytics / council voices all see live sessions exactly
like paper sessions. The only differences are:

- Fills are derived from Binance's `payload.fills` array on
  market orders (instant fills) and synthesised from
  `executedQty` + `cummulativeQuoteQty` if the response carries
  execution but no `fills` array. On open limit orders, the
  next `status()` poll observes the executed quantity and emits
  the gap as a single fill. The router's `order.fills` loop
  handles submit-time fills; the adapter pushes status-time
  fills directly to `on_fill`.
- `Fill.reference_price` is set to `intent.price` for limit
  orders and `None` for market orders (Binance doesn't surface
  a "would-have-been" price). This means the W3-PR1 slippage
  ledger reports `fills_missing_reference > 0` for every market
  order — the cockpit / council voices already handle this case.

### Action: `start_live_session`

```jsonc
{
  "action": "algotrade.start_live_session",
  "args": {
    "fingerprint": "sha256:…",         // strategy registry fingerprint
    "instrument": "BINANCE:BTCUSDT",   // optional override
    "binance": {
      "api_key": "<testnet or production key>",
      "api_secret": "<testnet or production secret>",
      "testnet": true                  // DEFAULT — never sends real money
    },
    "policy": { "max_position_qty": 1.0 }  // optional; overrides defaults
  }
}
```

Response includes:

```jsonc
{
  "ok": true,
  "session": { "session_id": "sess_…", "mode": "live", "adapter": "binance", … },
  "policy":  { "kill_switch": true, "allow_short": false, … },
  "binance": {
    "name": "binance",
    "testnet": false,
    "base_url": "https://api.binance.com",
    "api_key_prefix": "abcdef",        // never the secret
    "recv_window_ms": 5000,
    "timeout_seconds": 10.0
  },
  "warning": "Live mode wired with kill_switch=ON by default…"  // null on testnet
}
```

### Security posture

- API key + secret are kept **in-memory only** for the lifetime
  of the worker. They are **never** written to
  `sessions.jsonl`, `audit/`, or `policies/`.
- `metadata.binance` on the persisted session row uses the
  `to_safe_dict()` projection — base URL, key prefix, testnet
  flag, recv_window. The cockpit can render
  `binance:abcdef…(testnet)` without touching the secret.
- After a worker restart, `ExecRuntime.get(session_id)` returns
  `None` for any live session — the historical row stays in
  `sessions.jsonl` for audit / council replay, but the operator
  must call `start_live_session` again to re-authenticate.
  Paper sessions still rehydrate transparently from disk.
- Real-money mode boots with `kill_switch=ON`. The operator has
  to issue an explicit `set_policy` call to disable it. The
  recommended workflow is:
  1. Start live session (kill switch ON, no orders flow).
  2. Use `submit_intent` with a tiny test quantity; observe the
     `verdict.rejected` reason.
  3. `set_policy` with `kill_switch=False` AND a tight
     `max_notional_per_intent` cap.
  4. Re-submit the test intent; verify the order reaches Binance
     and `status` returns FILLED.
  5. Loosen caps as you build confidence.

## 14. Workshop lab mode (W4-PR2)

The W4-PR2 lab gives a facilitator the plumbing to run a
30-person room without bespoke ops. **No new sub-API** — the
lab reuses the existing `sandbox_id` field on every session,
so attendees use the same algotrade verbs they already know.

### Architecture

```text
backend/core/algotrade/lab/
├─ Workshop          # id, name, facilitator, status, attendee_ids
├─ Attendee          # id, display_name, sandbox_id, workshop_id
├─ LabStore          # one JSON doc per workshop on disk
└─ Leaderboard       # fans W3-PR1 metrics across attendee sandboxes
```

`LabStore` persists at
`$TARS_HOME/algotrade/lab/<workshop_id>/roster.json` — pure
JSON, no sqlite, no migrations. A facilitator can `cat` the
file mid-workshop to audit who's enrolled and which
`sandbox_id` they got.

### Sandbox minting

When `lab_enroll_attendee` runs, the lab mints:

```
sandbox_id = lab:<workshop_id>:<attendee_id>
```

Every downstream verb (`start_paper_session`,
`start_live_session`, `submit_intent`, `feed_bar`,
`session_report`, `council_review`) accepts a `sandbox_id`
arg already, so the lab integration is opt-in: the attendee
just passes the lab-minted id to their normal flow.

### Leaderboard

`compute_leaderboard(workshop_id)` walks every attendee in the
workshop, lists every session that carries their `sandbox_id`,
replays the W2-PR1 audit log via the W3-PR1
`compute_session_metrics` for each session, sums the totals,
and ranks by net edge:

```
score = realized_pnl - fees_total - slippage_cost
```

Tie-breakers (in order):
1. Higher `acceptance_rate` — well-formed intents > spam.
2. More fills — more activity = more learning.
3. Earlier `joined_at` — stable, deterministic.

The leaderboard is **always recomputed from disk** — no
caching. Restart the worker mid-workshop and the next
`lab_leaderboard` call returns the same ranking that matches
every attendee's audit log byte-for-byte. This is the same
property the W3-PR3 trading council voices rely on, so the
lab + council pair perfectly for post-workshop debriefs.

### Actions

| Action ID                     | What it does                                                                                       |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| `lab_create_workshop`         | Mint a workshop bucket. Persists roster.json on disk.                                              |
| `lab_list_workshops`          | List workshops (newest first). Optional `status` filter.                                           |
| `lab_set_workshop_status`     | Pause / close a workshop. Closed workshops reject new enrollments.                                 |
| `lab_enroll_attendee`         | Mint an attendee + their `sandbox_id`. Returns a `usage_hint` the cockpit can copy-paste.          |
| `lab_list_attendees`          | List attendees in a workshop, in join order.                                                       |
| `lab_leaderboard`             | Compute the ranking. Pure stdlib, deterministic, no caching.                                       |
| `lab_attendee_snapshot`       | Per-attendee handout: workshop + attendee + sessions + rank.                                       |

### Facilitator workflow

See `docs/COCKPIT_HANDBOOK.md` for the full operator runbook.
TL;DR:

1. `lab_create_workshop` → save `workshop_id`.
2. For each attendee: `lab_enroll_attendee` → hand them the
   minted `sandbox_id` + the
   `_workshop.quant.recipe_to_paper` playbook.
3. Attendees run their normal algotrade flow with their
   `sandbox_id`.
4. `lab_leaderboard` whenever you want to publish standings.
5. `lab_attendee_snapshot` per attendee for the post-workshop
   debrief.
6. `lab_set_workshop_status({status: "closed"})` to archive.

### Bundled playbook

`playbooks/_workshop/quant/lab_kickoff.json` — three steps
(`lab_create_workshop` → `lab_enroll_attendee` →
`lab_leaderboard`) parameterised by `WORKSHOP_NAME` /
`WORKSHOP_FACILITATOR` / `ATTENDEE_NAME` env vars so a shell
loop can fan it across a roster.

## 15. Workshop debrief bundle (W4-PR3)

`render_workshop_debrief(workshop_id)` stitches the W3-PR1
analytics, the W3-PR2 session report, the W3-PR3 council
voices, and the W4-PR2 leaderboard into a **single Markdown
document** the facilitator can email out at the end of the
session. No more chasing 15 individual report URLs — one
action, one page, one consistent visual identity.

### Layout

```text
# Workshop debrief — {workshop name}

## Workshop
- workshop_id, status, facilitator, started_at, attendees, …

## Leaderboard
| Rank | Attendee | Sessions | Realised PnL | Fees | Slippage | Score | Accept rate |

## Per-attendee debrief
### {Attendee} — rank #N
- attendee metadata, sandbox_id, score, council consensus
#### Session {session_id} — sha256:…   ← W3-PR2 report, headings pushed +3
##### Headline metrics
##### PnL attribution
##### Top trades
##### Slippage
…

---
_Generated by TARS algotrade — workshop {id} at {timestamp}._
```

### Action

`algotrade.lab_workshop_debrief`:

```jsonc
{
  "workshop_id": "ws_cresco-may-12-cohort_…",
  "include_session_reports": true   // default
}
```

Returns `WorkshopDebrief.to_dict()`:

```jsonc
{
  "ok": true,
  "debrief": {
    "workshop": { … Workshop.to_dict() … },
    "leaderboard": { … Leaderboard.to_dict() … },
    "attendees": [
      {
        "attendee": { … Attendee.to_dict() … },
        "rank": { … LeaderboardEntry.to_dict() … },
        "sessions_markdown": [ "# Session sess_… …", … ],
        "council_consensus": "warn"
      },
      …
    ],
    "markdown": "# Workshop debrief — Cresco…\n…",
    "rendered_at": 1715050000.0
  }
}
```

### Modes

- **Full bundle** (`include_session_reports=true`) — the
  email-ready document, ~5–10 KB per attendee per session.
- **Headlines only** (`include_session_reports=false`) — just
  the leaderboard + per-attendee summaries (rank, sandbox,
  council consensus). What the cockpit lab summary panel
  renders.

### Determinism

Same audit logs always produce the same bundle, byte-for-byte
modulo the `rendered_at` timestamp. This means a facilitator
can re-render the debrief at any point post-workshop and get
the same result — useful for shipping a "v1.0 of the workshop"
artifact then a "v1.1 with one bug-fix on the leaderboard" two
weeks later, both reproducible from the raw audit logs.
