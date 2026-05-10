"""TARS algotrade — Strategy IR, backtest, registry.

Phase W (Cresco workshop). The submodules are deliberately
stdlib-only so a fresh `make bootstrap` machine can run a backtest
without an extra `pip install`. Numpy/pandas remain optional for
the heavy paths (vectorised metrics on huge bar sets); the default
loop is plain Python list iteration so the workshop attendees can
read every line in the call stack.
"""

from .strategy.ir import (
    Action,
    Condition,
    Constant,
    Indicator,
    Operator,
    Side,
    SizingRule,
    Strategy,
    StrategyError,
    Timeframe,
)
from .strategy.registry import (
    StoredStrategy,
    StrategyRegistry,
    get_registry,
)

__all__ = [
    "Action",
    "Condition",
    "Constant",
    "Indicator",
    "Operator",
    "Side",
    "SizingRule",
    "Strategy",
    "StrategyError",
    "Timeframe",
    "StoredStrategy",
    "StrategyRegistry",
    "get_registry",
]
