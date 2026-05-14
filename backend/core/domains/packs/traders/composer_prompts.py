"""W256 — composer overlay for the traders pack.

Traders is the day-trading / signals / alerts pack. Composer here
favours strategy notebooks, alert config files, and backtest scripts
- always paper-trading first, never live execution.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in traders context.

When the operator asks for "an alert" or "a signal", emit a YAML
config under ~/Documents/TARS/traders/alerts/ - never wire up an
exchange order endpoint. When asked for "a backtest" or "a strategy",
produce a Python script that reads local OHLCV CSVs and writes a
results markdown. All trading code is paper-only; any reference to
real execution must be commented out with a refusal note.
"""

ACTION_VOCABULARY = {
    "alert": (
        "create a YAML alert config at ~/Documents/TARS/traders/"
        "alerts/{symbol}-{rule}.yaml"
    ),
    "backtest": (
        "create a python backtest script for {strategy} reading "
        "~/Documents/TARS/traders/data/{symbol}.csv"
    ),
    "journal": (
        "append a trade-journal entry to ~/Documents/TARS/traders/"
        "journal/{yyyy-mm-dd}.md with reasoning and outcome"
    ),
    "watchlist": (
        "create or update ~/Documents/TARS/traders/watchlist.csv "
        "with {tickers}"
    ),
}

FILE_HINTS = {
    "alerts": "~/Documents/TARS/traders/alerts/",
    "data": "~/Documents/TARS/traders/data/",
    "journal": "~/Documents/TARS/traders/journal/",
}
