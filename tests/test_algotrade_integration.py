"""End-to-end integration tests for the algotrade stack — Wave 100.

Glues W1 (Strategy IR + registry + backtest) through W2 (paper exec
+ risk gate + audit) using the real public API of every module.
Stdlib-only — no pytest dependency, runnable via:

    python3 -m unittest tests.test_algotrade_integration

The exec layer (W2) lives on cursor branches that have not yet been
merged onto main; tests that touch it are guarded with skipUnless so
the file imports cleanly today and starts exercising the real surface
the moment Cursor lands W2/W3.
"""

from __future__ import annotations

import asyncio
import math
import tempfile
import unittest
from pathlib import Path

from backend.core.algotrade.backtest.harness import (
    Bar,
    BacktestConfig,
    run_backtest,
)
from backend.core.algotrade.recipes import load_recipe
from backend.core.algotrade.strategy.registry import StrategyRegistry

# Cursor's W2 paper exec is on `cursor/algotrade-w2-paper-exec` and
# not yet merged onto main. Try-import so the rest of the suite still
# loads when those files aren't present.
try:
    from backend.core.algotrade.exec import (
        AuditLog,
        OrderRouter,
        PaperAdapter,
        PaperConfig,
        PositionStore,
        RiskGate,
        RiskPolicy,
        SessionStore,
    )
    from backend.core.algotrade.exec.base import (
        OrderIntent,
        OrderType,
        Side as ExecSide,
    )
    EXEC_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    EXEC_AVAILABLE = False
# NOTE: exec uses Side.BUY / Side.SELL; backtest uses Side.LONG /
# Side.SHORT. Two enums named `Side` in the same package — flagged in
# the Wave 100 audit (docs/audit/CURSOR_ALGOTRADE_AUDIT_2026-05-10.md).


def _sine_bars(n: int = 200, base: float = 100.0, amp: float = 8.0) -> list[Bar]:
    out: list[Bar] = []
    for i in range(n):
        px = base + amp * math.sin(i / 7.0)
        out.append(
            Bar(
                ts=1_700_000_000 + i * 3600,
                open=px,
                high=px * 1.004,
                low=px * 0.996,
                close=px,
                volume=1000.0,
            )
        )
    return out


class StrategyToBacktestIT(unittest.TestCase):
    """W1: load recipe → register → fingerprint roundtrip → backtest."""

    def test_recipe_register_backtest_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = StrategyRegistry(root=Path(tmp))
            strategy = load_recipe("ma_cross")
            row = reg.put(strategy, author="claude_w100")

            self.assertEqual(row.version, 1)
            fetched = reg.get(row.fingerprint)
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.fingerprint, strategy.fingerprint())

            # Idempotent put — same IR, same row.
            again = reg.put(strategy, author="claude_w100")
            self.assertEqual(again.fingerprint, row.fingerprint)
            self.assertEqual(again.version, row.version)

            cfg = BacktestConfig(initial_equity=10_000.0, commission_bp=5.0)
            result = run_backtest(strategy, _sine_bars(220), config=cfg)

            self.assertEqual(result.bars, 220)
            self.assertGreater(result.final_equity, 0)

            # Spec-mandated headline metrics — Wave 80 algotrade spec.
            for key in (
                "total_return", "cagr", "sharpe", "sortino",
                "max_drawdown", "win_rate", "loss_rate", "profit_factor",
                "expectancy", "trades", "avg_trade_pct", "exposure",
            ):
                self.assertIn(key, result.metrics, f"missing metric {key!r}")

            # Result is JSON-serialisable end-to-end.
            d = result.to_dict()
            self.assertEqual(d["strategy_fingerprint"], strategy.fingerprint())
            self.assertIsInstance(d["trades"], list)
            self.assertIsInstance(d["metrics"], dict)


@unittest.skipUnless(EXEC_AVAILABLE, "Cursor W2 paper exec branch not yet merged on main")
class PaperExecAuditIT(unittest.TestCase):
    """W2: intent → gate → adapter → audit, plus idempotency + caps."""

    def test_idempotent_submit_and_cap_reject(self) -> None:
        async def go() -> dict:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                positions = PositionStore()
                audit = AuditLog(path=root / "audit.jsonl")
                adapter = PaperAdapter(config=PaperConfig(starting_cash=100_000))
                gate = RiskGate(
                    policy=RiskPolicy(
                        max_order_qty=10.0,
                        max_open_positions=1,
                        allow_short=True,
                        kill_switch=False,
                        allowed_instruments=("BINANCE:BTCUSDT",),
                    ),
                    positions=positions,
                )
                sessions = SessionStore(path=root / "sessions.jsonl")
                sess = sessions.create(
                    mode="paper",
                    strategy_fingerprint="sha256:test",
                    instrument="BINANCE:BTCUSDT",
                    adapter="paper",
                )
                router = OrderRouter(
                    adapter=adapter,
                    gate=gate,
                    positions=positions,
                    audit=audit,
                    session_id=sess.session_id,
                )

                intent = OrderIntent.make(
                    strategy_fingerprint="sha256:test",
                    instrument="BINANCE:BTCUSDT",
                    side=ExecSide.BUY,
                    qty=1.0,
                    type=OrderType.MARKET,
                )

                v1, o1 = await router.submit(intent)
                v2, o2 = await router.submit(intent)  # idempotent replay

                # Over-cap order — gate must block.
                big = OrderIntent.make(
                    strategy_fingerprint="sha256:test",
                    instrument="BINANCE:BTCUSDT",
                    side=ExecSide.BUY,
                    qty=999.0,
                    type=OrderType.MARKET,
                )
                v3, _ = await router.submit(big)

                # Disallowed instrument — gate must block.
                bad = OrderIntent.make(
                    strategy_fingerprint="sha256:test",
                    instrument="BINANCE:DOGEUSDT",
                    side=ExecSide.BUY,
                    qty=1.0,
                    type=OrderType.MARKET,
                )
                v4, _ = await router.submit(bad)

                return {
                    "v1_accepted": v1.accepted,
                    "v2_reason": v2.reason,
                    "same_order": (
                        o1 is not None and o2 is not None
                        and o1.order_id == o2.order_id
                    ),
                    "v3_blocked": (not v3.accepted),
                    "v4_blocked": (not v4.accepted),
                    "audit_lines": _count_audit_lines(root / "audit.jsonl"),
                }

        out = asyncio.run(go())
        self.assertTrue(out["v1_accepted"])
        self.assertIn("idempotent", out["v2_reason"])
        self.assertTrue(out["same_order"])
        self.assertTrue(out["v3_blocked"])
        self.assertTrue(out["v4_blocked"])
        self.assertGreaterEqual(out["audit_lines"], 4)


def _count_audit_lines(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text().splitlines() if line.strip())
    except FileNotFoundError:
        return 0


class PackActionContractIT(unittest.TestCase):
    """W1b pack: every action ships a JSON schema and an async handler."""

    def test_actions_complete(self) -> None:
        try:
            from backend.core.domains.packs.algotrade import actions as pack_actions
        except ModuleNotFoundError as exc:
            self.skipTest(f"domain pack deps missing: {exc.name}")

        ids = {spec.id for spec in pack_actions.ACTIONS}
        for required in (
            "list_recipes", "load_recipe", "parse_strategy",
            "list_strategies", "get_strategy", "register_strategy",
            "fork_strategy", "backtest",
        ):
            self.assertIn(required, ids, f"pack missing action {required!r}")

        destructive = {s.id for s in pack_actions.ACTIONS if s.destructive}
        self.assertIn("register_strategy", destructive)
        self.assertIn("fork_strategy", destructive)

        import inspect
        for spec in pack_actions.ACTIONS:
            self.assertTrue(
                inspect.iscoroutinefunction(spec.handler),
                f"{spec.id} handler not async",
            )
            self.assertIsInstance(spec.schema, dict)
            self.assertEqual(spec.schema.get("type"), "object")


if __name__ == "__main__":
    unittest.main()
