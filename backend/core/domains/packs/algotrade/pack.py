"""Algotrade domain pack.

Why this exists: W1a shipped the building blocks (Strategy IR,
registry, backtest engine, recipe gallery) but they live behind
plain Python imports. The cockpit, the playbook scheduler, the
CLI, and external MCP clients all reach domain capabilities
through the standard ``/api/domains/<slug>/actions/<id>/invoke``
HTTP envelope. Wrapping algotrade as a domain pack closes that
gap and makes every workshop attendee surface (UI / cron job /
council voice / external automation) talk to the same verbs.

Design choices:

- **Read-heavy actions are non-destructive.** ``list_recipes``,
  ``load_recipe``, ``parse_strategy``, ``list_strategies``,
  ``get_strategy``, and ``backtest`` are pure / idempotent and
  bypass the policy gate. ``register_strategy`` and
  ``fork_strategy`` mutate the on-disk registry — flagged
  ``destructive=True`` so they route through the gate (operator
  / agent confirmation).
- **No live execution in W1b.** Live order placement, paper
  trading sessions, and cancel verbs land in W2 where the risk
  gate is wired. W1b is intentionally read + persist only.
- **Schema-first.** Every action ships a JSON schema in its
  ``ActionSpec.schema`` so the cockpit can render parameter
  forms and external MCP clients can validate before sending.
"""

from __future__ import annotations

from ...base import DomainManifest, DomainPack
from ...registry import register
from .actions import ACTIONS
from .awareness import SOURCES
from .prompts import SYSTEM_PROMPT


class AlgotradePack(DomainPack):
    manifest = DomainManifest(
        slug="algotrade",
        name="Algotrade",
        short="Strategy IR + backtest + paper executor — Cresco workshop full cycle.",
        description=(
            "Algorithmic trading toolkit for quant teams. "
            "**W1** ships a JSON Strategy IR, versioned file-backed "
            "registry, deterministic stdlib-only backtest engine with "
            "incremental indicators (SMA/EMA/RSI/ATR/Bollinger), and a "
            "4-strategy starter recipe gallery. **W2-PR1** adds the "
            "paper-trading execution layer: order router with "
            "intent → verdict → order → fill audit, risk gate "
            "(per-order qty cap, position notional cap, max open "
            "positions, no-short toggle, daily-loss kill-switch, "
            "instrument allowlist), in-process session manager, and "
            "JSONL audit log per session. **W3-PR1** adds analytics "
            "on top of the audit log: PnL attribution by instrument "
            "and strategy_fingerprint with a round-trip ledger and "
            "cumulative PnL curve, slippage ledger (fill price vs "
            "intended reference in basis points + cost), and a "
            "session metrics summary. **W2-PR2** will add the live "
            "Binance adapter; **W3-PR2/3** session reports + trading "
            "council voices; **W4** workshop lab mode + quant "
            "playbooks (W4-PR1 shipped 5 quant playbooks + recursive "
            "loader)."
        ),
        color="#f97316",
        capabilities=(
            "strategy_ir",
            "strategy_registry",
            "backtest_deterministic",
            "indicators_sma_ema_rsi_atr_bollinger",
            "recipe_gallery",
            "binance_klines_data",
            "paper_executor",
            "risk_gate_policy",
            "order_router_audit",
            "position_pnl_book",
            "session_manager",
            "pnl_attribution",
            "slippage_ledger",
            "session_metrics",
        ),
        audience="quant traders, analysts, fund operators, workshop attendees",
    )

    def auth_vault_keys(self) -> tuple[str, ...]:
        # No keys needed for W1b. Binance public klines + local CSV
        # are the only data sources, both unauth. Keys re-enter the
        # story in W2 (live exchange execution).
        return ()

    def actions(self):
        return ACTIONS

    def awareness(self):
        return SOURCES

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT


register(AlgotradePack())
