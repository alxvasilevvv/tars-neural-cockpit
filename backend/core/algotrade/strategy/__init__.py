"""Strategy DSL — JSON IR, parser, registry.

Why an IR (intermediate representation): the council operates on
structured strategy objects (\"now invert it\", \"add a trailing
stop\") and so does every analytics surface. Operators see Python
code in the cockpit, but TARS reasons in IR. The two are kept in
sync by a deterministic codegen pass.
"""

from .ir import (
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
from .registry import StoredStrategy, StrategyRegistry, get_registry

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
