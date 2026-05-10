"""Strategy recipes — JSON IR templates the workshop attendees fork.

Each recipe is a complete, validatable :class:`Strategy` IR
serialised to JSON. The attendees will use them as starting points
in the vibe-coding pipeline (``algotrade.fork`` → tweak via
``algotrade.refine`` → backtest).

The catalogue is intentionally small (5 recipes) and each one
covers a different mental model:

- ``ma_cross``         — trend-following classic.
- ``bollinger_reversion`` — mean-reversion against bands.
- ``rsi_oversold``     — momentum exhaustion long.
- ``donchian_breakout`` *(coming W2)* — breakout playbook.
- ``trailing_runner``  — let winners run with a trailing stop.

The :func:`list_recipes` and :func:`load_recipe` helpers are the
only public surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..strategy.ir import Strategy

_RECIPES_DIR = Path(__file__).resolve().parent


def list_recipes() -> list[str]:
    return sorted(p.stem for p in _RECIPES_DIR.glob("*.json"))


def load_recipe(name: str) -> Strategy:
    """Load a recipe by stem (``"ma_cross"``)."""
    path = _RECIPES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"no recipe named {name!r}")
    payload: dict[str, Any] = json.loads(path.read_text())
    return Strategy.from_dict(payload)


__all__ = ["list_recipes", "load_recipe"]
