"""``tars algotrade ...`` subcommands.

Routes every verb to the canonical async action handler in
``backend.core.domains.packs.algotrade``. The CLI never
re-implements business logic — same handler the HTTP layer
calls, same audit trail.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Mapping


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "algotrade",
        help="Strategy IR / backtest / paper + live executor verbs.",
    )
    sub = p.add_subparsers(dest="algotrade_cmd", metavar="<verb>")

    _add_list_recipes(sub)
    _add_load_recipe(sub)
    _add_list_strategies(sub)
    _add_get_strategy(sub)
    _add_register_strategy(sub)
    _add_backtest(sub)
    _add_list_sessions(sub)
    _add_get_session(sub)
    _add_session_report(sub)
    _add_council_review(sub)


# ----------------------------------------------------- subparsers


def _add_list_recipes(sub) -> None:
    sub.add_parser("list-recipes", help="List bundled starter strategies.")


def _add_load_recipe(sub) -> None:
    p = sub.add_parser("load-recipe", help="Fetch a recipe by name.")
    p.add_argument("name")


def _add_list_strategies(sub) -> None:
    p = sub.add_parser(
        "list-strategies",
        help="Inventory of strategies in the local registry.",
    )
    p.add_argument("--tag")
    p.add_argument("--instrument")
    p.add_argument("--author")


def _add_get_strategy(sub) -> None:
    p = sub.add_parser("get-strategy", help="Fetch a stored strategy by fingerprint.")
    p.add_argument("fingerprint")


def _add_register_strategy(sub) -> None:
    p = sub.add_parser(
        "register-strategy",
        help="Register a strategy from one of: --recipe, --ir-file.",
    )
    p.add_argument("--recipe", help="Recipe name (e.g. ma_cross).")
    p.add_argument("--ir-file", help="Path to a Strategy IR JSON file.")
    p.add_argument("--author", default="cli")


def _add_backtest(sub) -> None:
    p = sub.add_parser("backtest", help="Run a backtest against bars from a CSV.")
    p.add_argument("--recipe", help="Use a starter recipe by name.")
    p.add_argument("--fingerprint", help="Use a registered strategy by fingerprint.")
    p.add_argument("--ir-file", help="Path to a Strategy IR JSON file.")
    p.add_argument("--csv-path", help="Local CSV: ts,open,high,low,close,volume.")
    p.add_argument(
        "--binance",
        help=(
            "Binance public klines source: SYMBOL[:INTERVAL[:LIMIT]] "
            "(default 1h, 500). Example: BTCUSDT:1h:500."
        ),
    )
    p.add_argument(
        "--equity-down-sample",
        type=int,
        help="Trim the equity curve to ~N points for chart-friendly output.",
    )


def _add_list_sessions(sub) -> None:
    p = sub.add_parser("list-sessions", help="List paper / live sessions.")
    p.add_argument("--mode", choices=["paper", "live"])
    p.add_argument("--status", choices=["pending", "running", "paused", "stopped", "errored", "completed"])
    p.add_argument("--sandbox-id", help="Filter by sandbox (e.g. lab attendee).")


def _add_get_session(sub) -> None:
    p = sub.add_parser("get-session", help="Full snapshot of one session.")
    p.add_argument("session_id")


def _add_session_report(sub) -> None:
    p = sub.add_parser(
        "session-report",
        help="Render the W3-PR2 markdown report for a session.",
    )
    p.add_argument("session_id")
    p.add_argument(
        "--top-n-trades", type=int, default=5, help="Top winners + detractors."
    )


def _add_council_review(sub) -> None:
    p = sub.add_parser(
        "council-review",
        help="Run the W3-PR3 trading council for a session.",
    )
    p.add_argument("session_id")


# ----------------------------------------------------- dispatch


def handle(args: argparse.Namespace) -> dict[str, Any]:
    cmd = args.algotrade_cmd
    if cmd is None:
        return {
            "ok": False,
            "error": "missing_subcommand",
            "detail": "Try `tars algotrade --help` for the verb list.",
        }

    handlers = {
        "list-recipes": _do_list_recipes,
        "load-recipe": _do_load_recipe,
        "list-strategies": _do_list_strategies,
        "get-strategy": _do_get_strategy,
        "register-strategy": _do_register_strategy,
        "backtest": _do_backtest,
        "list-sessions": _do_list_sessions,
        "get-session": _do_get_session,
        "session-report": _do_session_report,
        "council-review": _do_council_review,
    }
    fn = handlers.get(cmd)
    if fn is None:
        return {"ok": False, "error": "unknown_subcommand", "detail": cmd}
    return fn(args)


def _run(coro):
    return asyncio.run(coro)


def _load_ir_file(path: str) -> dict[str, Any] | None:
    p = Path(path).expanduser()
    if not p.exists():
        return None
    return json.loads(p.read_text())


# ----------------------------------------------------- handlers


def _do_list_recipes(_args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.actions import (
        list_recipes_action,
    )

    return _run(list_recipes_action({}))


def _do_load_recipe(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.actions import (
        load_recipe_action,
    )

    return _run(load_recipe_action({"name": args.name}))


def _do_list_strategies(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.actions import (
        list_strategies_action,
    )

    payload: dict[str, Any] = {}
    for k in ("tag", "instrument", "author"):
        v = getattr(args, k, None)
        if v:
            payload[k] = v
    return _run(list_strategies_action(payload))


def _do_get_strategy(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.actions import (
        get_strategy_action,
    )

    return _run(get_strategy_action({"fingerprint": args.fingerprint}))


def _do_register_strategy(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.actions import (
        register_strategy_action,
    )

    payload: dict[str, Any] = {"author": args.author}
    if args.recipe:
        payload["recipe"] = args.recipe
    elif args.ir_file:
        ir = _load_ir_file(args.ir_file)
        if ir is None:
            return {"ok": False, "error": "ir_file_not_found", "detail": args.ir_file}
        payload["ir"] = ir
    else:
        return {
            "ok": False,
            "error": "missing_source",
            "detail": "provide one of --recipe, --ir-file",
        }
    return _run(register_strategy_action(payload))


def _do_backtest(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.actions import backtest_action

    payload: dict[str, Any] = {}
    if args.recipe:
        payload["recipe"] = args.recipe
    elif args.fingerprint:
        payload["fingerprint"] = args.fingerprint
    elif args.ir_file:
        ir = _load_ir_file(args.ir_file)
        if ir is None:
            return {"ok": False, "error": "ir_file_not_found", "detail": args.ir_file}
        payload["ir"] = ir
    else:
        return {
            "ok": False,
            "error": "missing_strategy_source",
            "detail": "provide one of --recipe, --fingerprint, --ir-file",
        }

    if args.csv_path:
        payload["csv_path"] = args.csv_path
    elif args.binance:
        spec = args.binance.split(":")
        binance: dict[str, Any] = {"symbol": spec[0]}
        if len(spec) > 1 and spec[1]:
            binance["interval"] = spec[1]
        if len(spec) > 2 and spec[2]:
            try:
                binance["limit"] = int(spec[2])
            except ValueError:
                pass
        payload["binance"] = binance
    else:
        return {
            "ok": False,
            "error": "missing_data",
            "detail": "provide one of --csv-path, --binance",
        }
    if args.equity_down_sample:
        payload["equity_down_sample"] = args.equity_down_sample
    return _run(backtest_action(payload))


def _do_list_sessions(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.exec_actions import (
        list_sessions_action,
    )

    payload: dict[str, Any] = {}
    if args.mode:
        payload["mode"] = args.mode
    if args.status:
        payload["status"] = args.status
    if args.sandbox_id:
        payload["sandbox_id"] = args.sandbox_id
    return _run(list_sessions_action(payload))


def _do_get_session(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.exec_actions import (
        get_session_action,
    )

    return _run(get_session_action({"session_id": args.session_id}))


def _do_session_report(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.exec_actions import (
        session_report_action,
    )

    return _run(
        session_report_action(
            {
                "session_id": args.session_id,
                "top_n_trades": args.top_n_trades,
            }
        )
    )


def _do_council_review(args: argparse.Namespace) -> dict[str, Any]:
    from backend.core.domains.packs.algotrade.exec_actions import (
        council_review_action,
    )

    return _run(council_review_action({"session_id": args.session_id}))
