"""Algotrade domain pack — exposes the W1a foundations as actions.

Cresco workshop ("The Algorithmic Edge", CARF / 3V / Crypto Fund
quant teams) — Phase W1b.

The pack wraps :mod:`backend.core.algotrade` (Strategy IR, registry,
backtest engine, recipe gallery) into the standard TARS domain
contract so the cockpit, the council, the playbook scheduler, the
CLI (Wave M2), and the MCP server (Wave M4) all reach the same
verbs through ``POST /api/domains/algotrade/actions/<id>/invoke``.

W1b ships:

- ``list_recipes`` — catalogue of starter strategies.
- ``load_recipe`` — fetch a recipe by name (returns full IR).
- ``parse_strategy`` — accept a JSON IR, validate, return canonical.
- ``register_strategy`` — persist an IR (idempotent on fingerprint).
- ``fork_strategy`` — duplicate a stored strategy as a new draft.
- ``list_strategies`` — registry inventory (slug + latest version).
- ``get_strategy`` — fetch a stored strategy by fingerprint.
- ``backtest`` — run a strategy against bars (CSV / Binance klines /
  inline). Returns the full :class:`BacktestResult` payload.

W2 will add ``paper_session_start`` / ``paper_session_stop`` and the
live Binance executor; the policy gate guards them then.
"""

from .pack import AlgotradePack

__all__ = ["AlgotradePack"]
