# Cursor algotrade audit — Wave 100 (2026-05-10)

Auditor: Claude · branch `claude/wave-87-onwards` (HEAD `4803215`).
Scope: every cursor branch tagged `algotrade-w*` against the spec
that landed in Wave 80 + the Wave 81-A SYNC entry.

## Branch landscape

| Branch                                           | On main? | Adds                                                                                |
|--------------------------------------------------|----------|-------------------------------------------------------------------------------------|
| `cursor/algotrade-w1-recovery` (= `W1`)          | yes      | strategy/ir.py, strategy/registry.py, backtest/{harness,indicators,metrics,data}.py |
| `cursor/algotrade-w1b-pack`                      | yes      | domains/packs/algotrade/{actions,pack,manifest,prompts,awareness}.py                |
| `cursor/algotrade-w2-paper-exec`                 | NO       | exec/{base,paper,positions,risk,router,sessions,runtime}.py                         |
| `cursor/algotrade-w3-analytics` (PR1)            | NO       | exec/analytics.py (PnLAttribution / SlippageReport / SessionMetrics)                |
| `cursor/algotrade-w3-pr2-session-report`         | partial  | exec/report.py only (already on this branch — landed standalone)                    |
| `cursor/algotrade-w3-pr3-council`                | NO       | exec/voices.py + domains/packs/algotrade/exec_actions.py                            |
| `cursor/algotrade-w4-workshop-pack`              | yes (PR1)| playbooks/_workshop/algotrade/                                                      |

The cursor branches were forked from a snapshot **before** Waves 90-99
landed (cohort, connectors, scheduler, receipts, outreach, org). Merging
any of them as-is would delete that work. Use cherry-pick / file copy.

For this audit I file-copied the W2 + W3 + W3-pr3 exec tree
(`exec/{analytics,base,paper,positions,risk,router,runtime,sessions,voices}.py`)
into the working tree so smoke tests can run against the real surface.
The files import cleanly (`from backend.core.algotrade.exec import ...` → OK).

## Per-phase shipped status

### W1 — Strategy IR + registry + backtest (LANDED)

- `strategy/ir.py` (477 LoC). Closed-world enums for Operator /
  Side / Timeframe; recursive `Condition` tree with comparison +
  boolean ops + `crosses_above` / `crosses_below`; SizingRule
  with `fixed_qty` / `fixed_notional` / `risk_pct`; canonical
  JSON + sha256 fingerprint; full validate().
- `strategy/registry.py` (300 LoC). File-backed (`by-fingerprint/`,
  `by-name/`, `index.jsonl`); idempotent put on fingerprint;
  versioning per slug; `get_registry()` singleton.
- `backtest/harness.py` (508 LoC). No-look-ahead event loop, fills
  at next-bar open by default, intra-bar stop / TP / trailing
  stops, slippage models `none|fixed_bp|atr_pct`, single-position
  v1 with `max_positions` IR field reserved.
- `backtest/indicators.py` (434 LoC). SMA, EMA, RSI, ATR,
  Bollinger lower/middle/upper. Incremental update API.
- `backtest/metrics.py` (190 LoC). total_return, cagr, sharpe,
  sortino, max_drawdown, win_rate, loss_rate, profit_factor,
  expectancy, trades, avg_trade_pct, exposure. **All 12 spec
  metrics present.**
- `recipes/`: `ma_cross`, `bollinger_reversion`, `rsi_oversold`,
  `trailing_runner` (4 starter strategies).

### W1b — Domain pack (LANDED)

- `actions.py` (558 LoC) — 8 actions:
  `list_recipes`, `load_recipe`, `parse_strategy`,
  `list_strategies`, `get_strategy`, `register_strategy`*,
  `fork_strategy`*, `backtest`. (* = destructive → routes
  through policy gate.)
- `pack.py` registers via `domains.registry.register()`.
- Exposed via existing `POST /api/domains/algotrade/actions/{id}`
  envelope in `web_extras/routers/domains.py`. **No dedicated
  `/api/algotrade/*` router** — Wave 81-A SYNC proposal does NOT
  match reality.

### W2 — Paper exec + risk gate + audit (NOT MERGED on main)

- `exec/base.py` — OrderIntent / Order / Fill / Position /
  AuditEvent / Side(BUY/SELL) / OrderType(MARKET/LIMIT) /
  OrderStatus / `OrderIntent.make()` factory generating
  `intent_id`.
- `exec/paper.py` — PaperAdapter; market orders fill at next bar
  open + slippage_bps, limit orders fill when bar.high/low crosses
  price. Async `submit/cancel/status/on_bar`.
- `exec/positions.py` — PositionStore with realised + unrealised
  PnL.
- `exec/risk.py` — RiskGate + RiskPolicy with **all spec'd fields**:
  `kill_switch`, `max_order_qty`, `max_position_notional`,
  `max_open_positions`, `max_daily_loss`, `allow_short`,
  `allowed_instruments`. Gate emits GateVerdict with
  `triggered_rules`.
- `exec/router.py` — OrderRouter wires intent → audit (intent
  event) → gate.evaluate (verdict event) → adapter.submit (order
  event) → fill listener (fill event). Idempotency via
  `OrderedDict` LRU keyed on `intent_id`. AuditLog is JSONL
  per-session.
- `exec/sessions.py` — SessionStore with status enum
  (PENDING / RUNNING / PAUSED / STOPPED / ERRORED / COMPLETED),
  `create / get / filter / update_status`. Persists to JSONL.
- `exec/runtime.py` — module-level singleton hookups for FastAPI.

### W3 — Analytics + report + council (NOT MERGED)

- `exec/analytics.py` (728 LoC) — PnLAttribution, RoundTrip,
  SlippageReport, SessionMetrics. Computed from audit log.
- `exec/report.py` (422 LoC) — markdown SessionReport renderer.
  **(This file IS on the current branch standalone.)**
- `exec/voices.py` (484 LoC) — trading council (3 voices).

### W4 — Workshop pack (PR1 LANDED)

- `playbooks/_workshop/algotrade/` — quant playbooks + recursive
  loader. 5 playbook files. Already on main.

## Spec-vs-reality gap matrix

| Spec item                           | Reality                                                     |
|-------------------------------------|-------------------------------------------------------------|
| Strategy IR with closed-world enums | DONE                                                        |
| Indicators SMA/EMA/RSI/ATR/BB       | DONE (5/5)                                                  |
| Backtest metrics 8+                 | DONE (12: all spec'd + cagr/exposure/avg_trade_pct/loss)    |
| Recipe gallery 4                    | DONE                                                        |
| Pack actions for read/register/bt   | DONE (8 actions via `/api/domains/algotrade/actions/*`)     |
| Paper exec + idempotency            | SHIPPED in W2 branch, **NOT on main**                       |
| Risk gate (all 7 policy fields)     | SHIPPED in W2, **NOT on main**                              |
| Audit log persisted JSONL           | SHIPPED in W2, **NOT on main**                              |
| Sessions start/stop/status          | SHIPPED in W2, **NOT on main**                              |
| Pack actions for exec               | SHIPPED in W3-pr3 (`exec_actions.py`), **NOT on main**      |
| PnL attribution / slippage report   | SHIPPED in W3-PR1, **NOT on main**                          |
| Markdown session report             | LANDED standalone (`exec/report.py`)                        |
| W3 analytics: Sharpe-over-time / DD chart / trade dist | NOT FOUND — analytics.py has counts, not time series |
| Workshop quant playbooks            | DONE (W4-PR1 landed)                                        |

## API contract reality vs Wave 81-A proposal

Wave 81-A proposed dedicated routes; reality uses the generic pack
envelope. Existing route surface (already shipped):

- `POST /api/domains/algotrade/actions/list_recipes`
- `POST /api/domains/algotrade/actions/load_recipe` `{name}`
- `POST /api/domains/algotrade/actions/parse_strategy` `{ir}`
- `POST /api/domains/algotrade/actions/list_strategies`
- `POST /api/domains/algotrade/actions/get_strategy` `{fingerprint}`
- `POST /api/domains/algotrade/actions/register_strategy` `{ir|recipe|fingerprint, ...}`
- `POST /api/domains/algotrade/actions/fork_strategy`
- `POST /api/domains/algotrade/actions/backtest` `{ir|fingerprint|recipe, bars|csv_path|binance, config?}`

Once Cursor merges W2/W3 → 6 more action ids appear (start_session,
submit_intent, stop_session, get_session, get_audit, set_policy)
on the same envelope.

**FE BacktestPanel.tsx misalignment:** the panel POSTs to
`/api/agents/{id}/backtest` with multipart CSV + SSE stream. That
route is NOT in `web_extras/routers/`. The panel falls back to a
deterministic mock when it 404s — which is what's happening today.

### FE adapter recommendation (no Cursor refactor needed)

Add a tiny adapter in `experiments/neural-showcase-v3/src/lib/algotrade.ts`:

```ts
export async function backtest(strategy: { ir?: object; recipe?: string; fingerprint?: string },
                                bars: Bar[]) {
  const r = await fetch(`${API_BASE}/api/domains/algotrade/actions/backtest`, {
    method: 'POST',
    headers: {'content-type':'application/json'},
    body: JSON.stringify({ ...strategy, bars: bars.map(b => ({ts: b.ts, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume })) })
  });
  return r.json();  // {ok, result: {...}}
}
```

BacktestPanel.tsx today is a CSV-agreement evaluator (input/expected
columns), not a Strategy IR backtest. Keep its existing FE-only flow
(it's a different feature). The new algotrade backtest belongs on
`/workshop/lab` or as a new panel — not retrofitted into BacktestPanel.

## Bugs / risks found

1. **Side enum mismatch**: backtest uses `Side.LONG/SHORT`; exec
   uses `Side.BUY/SELL`. Two enums named `Side` live in the same
   `algotrade` namespace. Risk: confusion during W3 voice
   integration (which translates strategy signals → exec intents).
   Recommend: keep both but rename exec's to `OrderSide` OR add an
   explicit translator in `OrderIntent.from_signal(side, …)`.
2. **`exec/__init__.py` imports `report.py` twice** (line 41 + 42 in
   the file copy). Harmless but flag it for cleanup.
3. Cursor branches are **forked pre-Wave 90**. Merging any cursor
   branch via `git merge` would delete cohort/connectors/scheduler/
   receipts/outreach/org modules. Use file-by-file cherry-pick
   instead.
4. W3 analytics ship counts + PnL attribution but **no time-series
   metrics** (Sharpe-over-time, drawdown curve over time, trade
   distribution histogram). Workshop FE will need these for the
   analytics tab.

## Tests added

`tests/test_algotrade_integration.py` — 3 stdlib-only test cases:

1. `StrategyToBacktestIT.test_recipe_register_backtest_metrics` —
   recipe → register (idempotent) → backtest 220 bars → assert all
   12 metric keys present + JSON-serialisable. PASS.
2. `PaperExecAuditIT.test_idempotent_submit_and_cap_reject` —
   create paper session, submit intent, replay same intent_id
   (idempotent), submit over-cap order (gate rejects), submit
   disallowed-instrument order (gate rejects), assert audit log
   has ≥4 entries. PASS.
3. `PackActionContractIT.test_actions_complete` — assert 8 action
   ids registered, both destructive flags set, every handler is
   `iscoroutinefunction`, every schema is a `type: object` JSON
   schema. SKIPPED in sandbox (`nacl` missing) — runs on a normal
   env.

```
$ python3 -m unittest tests.test_algotrade_integration -v
...
Ran 3 tests in 0.005s
OK (skipped=1)
```

## Punch list for Cursor

- [ ] **Land W2** on main (cherry-pick the 9 exec/*.py files +
      tests/test_algotrade_exec.py) without reverting Waves 90-99.
- [ ] **Land W3-PR1 analytics** (`exec/analytics.py` +
      `tests/test_algotrade_analytics.py`).
- [ ] **Land W3-PR3 council + exec actions** (`exec/voices.py` +
      `domains/packs/algotrade/exec_actions.py` — exposes
      `start_session/submit_intent/stop_session/get_audit/set_policy`
      via the same `/api/domains/algotrade/actions/*` envelope).
- [ ] Add **time-series analytics**: rolling Sharpe (window=30),
      drawdown series, trade-PnL histogram bins. Surface as a new
      action `session_timeseries`.
- [ ] Decide on `Side` enum: rename exec's to `OrderSide` to avoid
      shadowing, OR centralise in `algotrade/types.py`.
- [ ] Fix duplicate `from .report import …` line in
      `exec/__init__.py`.
- [ ] Pick up `test_algotrade_integration.py` (this audit) — it's
      the cross-module contract guard.

