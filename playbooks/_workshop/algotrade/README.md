# Algotrade vertical — workshop starter pack

Five playbooks built for the **Cresco Capital "Algorithmic Edge"
workshop** (CARF / 3V / Crypto Fund quant teams). Together they cover
the full quant loop: design a Strategy IR, backtest, gate through risk
review, paper trade, and promote to live with a human approval.

## Coming from QuantConnect / Zipline / Backtrader?

If you've shipped strategies on QuantConnect, Zipline, or Backtrader,
here's the TARS analog and what's different:

| Concept | QC / Zipline / Backtrader | TARS |
| ------- | ------------------------- | ---- |
| Strategy code | `class Algorithm(QCAlgorithm)` / `initialize()` + `handle_data()` / `Strategy` subclass | **Strategy IR** — declarative JSON params + pack action `algotrade.strategy.compose`. Re-runnable, fingerprint-addressable, anchorable on Solana. |
| Backtest | `lean backtest` / `zipline run` / `bt.Backtest().run()` | `algotrade.backtest.run` — same args (instrument, range, capital), report shape ≈ `{sharpe, sortino, max_drawdown, win_rate, expectancy, cagr}`. |
| Live broker adapter | IB / Tradier / Alpaca / CCXT | Binance v9.2 mock today — vault-key + multi-sig confirm + daily caps before any real order is placed. |
| Risk policy | hand-rolled `RiskManagement` model | First-class `RiskPolicy`: `kill_switch`, `max_position_usd`, `daily_loss_cap_usd`, `max_open_positions`, `allowed_instruments`. |
| Audit log | print + LEAN log files | JSONL receipts under `~/.tars/algotrade/sessions/*.jsonl`, weekly aggregate playbook included. |
| Paper trading | LEAN paper / Zipline `LiveTradingAlgorithm` | `algotrade.session.start` with `mode: "paper"`, schedulable monitor. |

What's actually different at the seam: every action TARS takes against
your strategy emits a signed **AuditEvent** that is replayable,
queryable, and (optionally) Merkle-rooted on-chain via
`wallet.anchor_memo`. So your weekly compliance report is not "we
trust the logs" — it's "here is the Solana memo, verify it
yourself".

## Playbooks

| File | Teaches | Phase |
| ---- | ------- | ----- |
| `mean_reversion_strategy.json` | Compose a mean-reversion Strategy IR (SMA + RSI), backtest 2024 BTC/USDT, gate, then paper for 7 days. | design |
| `momentum_breakout_strategy.json` | Compose a Bollinger-band breakout with EMA(50) trend filter, same backtest → gate → 7-day paper flow. | design |
| `live_paper_session.json` | Start a paper session under a strict risk policy (kill_switch, $1k position, $50 daily loss cap) and schedule a 15-minute health monitor. | test |
| `backtest_to_live_pipeline.json` | End-to-end promotion: registry pick → re-backtest → Sharpe>1.5 gate → 30-day paper → human approval → live (Binance v9.2 mock). | deploy |
| `risk_audit_weekly.json` | Friday 18:00: aggregate every algotrade audit log for the past week, email compliance, anchor the summary on Solana. | deploy |

## Fork instructions

1. Copy a file out of `_workshop/algotrade/` into your own pack
   directory, e.g. `playbooks/cresco/mean_reversion_strategy.json`.
2. Replace the `id` prefix with your fund slug
   (e.g. `cresco.mean_reversion_strategy`).
3. Adjust strategy params (SMA / RSI / Bollinger periods) and the
   backtest range to match your asset universe.
4. Replace placeholder env keys (`COMPLIANCE_EMAIL`,
   `HEAD_OF_TRADING_EMAIL`) with real values in `.env`.
5. Validate the file:
   `python3 -c "import json; json.load(open('<path>'))"`.
6. Reload playbooks from the cockpit (Settings → Playbooks → Reload)
   or restart the backend.

## Suggested workshop order (Day 1)

1. **Open with `mean_reversion_strategy.json`** (design phase) — every
   quant has built mean reversion before; lets the room see the full
   IR → backtest → gate → paper loop in 4 minutes.
2. **Build `momentum_breakout_strategy.json`** with attendees so they
   internalise that strategies are *parameter records*, not Python
   subclasses.
3. **Deploy `live_paper_session.json`** so each attendee leaves Day 1
   with a live paper session and a scheduled monitor running on their
   machine.
4. **Walk `backtest_to_live_pipeline.json` as the headline demo** —
   this is the slide they'll bring to their CIO. Don't actually run
   the live step in the room (the Binance v9.2 adapter is mock today).
5. **Schedule `risk_audit_weekly.json`** as homework. Friday 18:00
   the compliance officer gets their first auto-audit.

## Risk emphasis (read this to the room)

Every promotion to live trading goes through:
- **Risk gate** (Sharpe > 1.5, max drawdown < 20% on the most recent
  6 months of data — configurable per fund).
- **30-day paper observation** before live is even considered.
- **Human approval gate** (HIL) — your Head of Trading gets the email
  and clicks approve / reject.
- **Vault-key + multi-sig confirm** at the adapter layer (Binance
  v9.2 won't accept an order without it).
- **Daily caps** (`max_position_usd`, `daily_loss_cap_usd`,
  `kill_switch`) enforced *inside* the session loop, not in a wrapper.

If any of those five gates flips red, the session refuses to escalate.
That's the contract Cresco compliance signed off on.
