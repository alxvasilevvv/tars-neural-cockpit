"""``tars version`` — describe the installed CLI + packs."""

from __future__ import annotations

import argparse
import os
import platform
import sys
from typing import Any


CLI_VERSION = "0.1.0"


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "version", help="Print CLI + pack versions + system info."
    )
    p.add_argument(
        "--check-packs",
        action="store_true",
        help="Skip listing packs (faster startup, no domain imports).",
    )


def handle(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": CLI_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tars_home": os.environ.get(
            "TARS_HOME",
            os.environ.get("TARS_ALGOTRADE_HOME", str(os.path.expanduser("~/.tars"))),
        ),
    }

    if not args.check_packs:
        payload["packs"] = _list_packs()
    return {"ok": True, **payload}


def _list_packs() -> list[dict[str, Any]]:
    """Best-effort pack inventory. ``DomainManifest`` itself
    does not carry version/phase (those live in the JSON
    manifest file next to each pack), so we load the JSON
    manifest opportunistically and merge."""

    import importlib
    import json
    from pathlib import Path

    out: list[dict[str, Any]] = []
    try:
        importlib.import_module(
            "backend.core.domains.packs.algotrade.pack"
        )
        from backend.core.domains.registry import all_packs
    except Exception as exc:  # noqa: BLE001 — best-effort
        return [{"slug": "?", "error": str(exc)}]

    for pack in all_packs():
        manifest = pack.manifest
        version_str = "?"
        phase = "?"
        try:
            mod = importlib.import_module(pack.__class__.__module__)
            mod_path = Path(getattr(mod, "__file__", "") or "").parent
            mf_path = mod_path / "manifest.json"
            if mf_path.exists():
                raw = json.loads(mf_path.read_text())
                version_str = str(raw.get("version") or "?")
                phase = str(raw.get("phase") or "?")
        except Exception:  # noqa: BLE001 — best-effort
            pass
        out.append(
            {
                "slug": manifest.slug,
                "name": manifest.name,
                "version": version_str,
                "phase": phase,
            }
        )
    return out
