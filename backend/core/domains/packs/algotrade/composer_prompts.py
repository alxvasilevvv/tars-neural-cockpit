"""W256 — composer overlay for the algotrade pack.

Algotrade is the institutional-leaning strategy + IR + paper-trading
pack. Composer here favours strategy IR files, signal definitions,
and backtest harnesses - never live order entry.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in algotrade context.

When the operator asks for "a strategy" or "an IR", produce a JSON
strategy IR file under ~/Documents/TARS/algotrade/strategies/. When
asked for "a backtest run", scaffold a Python entrypoint that loads
the IR and emits a results JSON + a markdown digest. Live order
entry is out of scope - paper-trading only.
"""

ACTION_VOCABULARY = {
    "ir": (
        "create a strategy IR JSON at ~/Documents/TARS/algotrade/"
        "strategies/{slug}.json"
    ),
    "backtest": (
        "scaffold a backtest entrypoint at ~/Documents/TARS/"
        "algotrade/backtests/{slug}/run.py + results digest"
    ),
    "signal": (
        "create a signal definition YAML at ~/Documents/TARS/"
        "algotrade/signals/{name}.yaml"
    ),
    "report": (
        "create a markdown performance report under ~/Documents/"
        "TARS/algotrade/reports/{yyyy-mm-dd}.md"
    ),
}

FILE_HINTS = {
    "strategies": "~/Documents/TARS/algotrade/strategies/",
    "backtests": "~/Documents/TARS/algotrade/backtests/",
    "reports": "~/Documents/TARS/algotrade/reports/",
}
