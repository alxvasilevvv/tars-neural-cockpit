"""W256 — composer overlay for the wallet (wealth) pack.

The wallet pack is TARS' personal-wealth mode: portfolio CSVs,
rebalancing scripts, and per-account receipts. Composer here is
biased toward read-only analysis + advisory drafts; it NEVER emits
code that places real trades or moves funds.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in wallet (wealth) context.

When the operator says "rebalance", assume a CSV portfolio at
~/Documents/TARS/portfolio.csv and generate a Python rebalance
*script* plus a receipt markdown in ~/Documents/TARS/wallet/receipts/
- never code that calls a broker API. When asked to "report",
produce a markdown summary with target vs. actual allocation tables.
Never execute trades, never send money - drafts only.
"""

ACTION_VOCABULARY = {
    "rebalance": (
        "create a python rebalance script for ~/Documents/TARS/"
        "portfolio.csv and emit a receipt markdown"
    ),
    "report": (
        "create a markdown wealth report under ~/Documents/TARS/"
        "wallet/reports/{yyyy-mm}.md with allocation tables"
    ),
    "tax_summary": (
        "create a CSV summary of taxable lots for {year} at "
        "~/Documents/TARS/wallet/tax/{year}-lots.csv"
    ),
    "watchlist": (
        "create or update ~/Documents/TARS/wallet/watchlist.csv with "
        "{tickers}"
    ),
}

FILE_HINTS = {
    "portfolio": "~/Documents/TARS/portfolio.csv",
    "receipts": "~/Documents/TARS/wallet/receipts/",
    "reports": "~/Documents/TARS/wallet/reports/",
}
