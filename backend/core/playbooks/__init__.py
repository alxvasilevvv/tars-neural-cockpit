"""TARS playbooks — declarative multi-step action chains.

A playbook is a JSON file under ``playbooks/<pack>/<name>.json`` with
this shape:

    {
      "id": "traders.morning_check",
      "name": "Morning trading check",
      "description": "...",
      "steps": [
        {"id": "market", "action": "traders.summarize_market",
         "args": {"basket": ["BTC","ETH"]},
         "store_as": "market"},
        {"id": "news",   "action": "traders.awareness.news_feed.snapshot",
         "store_as": "news"}
      ]
    }

The runner threads each step's result back into the context and runs
arg templating with simple ``${steps.<id>.path.to.value}`` and
``${context.<key>}`` substitutions. Destructive steps still flow
through the policy gate.
"""

from .loader import (
    PLAYBOOKS_DIR,
    Playbook,
    PlaybookStep,
    discover,
    get_playbook,
    list_playbooks,
    reset_loader_cache,
)
from .runner import PlaybookRunner, StepResult, run_playbook

__all__ = [
    "PLAYBOOKS_DIR",
    "Playbook",
    "PlaybookRunner",
    "PlaybookStep",
    "StepResult",
    "discover",
    "get_playbook",
    "list_playbooks",
    "reset_loader_cache",
    "run_playbook",
]
