"""W256 - domain-pack-aware composer helpers.

The composer planner consults this module to figure out which pack
the operator is currently in and to fetch that pack's prompt overlay
+ action vocabulary + file hints.

Active pack is persisted to ``~/.tars/active_pack.json`` with shape::

    {"pack": "<slug>", "updated_at": "<iso8601>"}

When the file is missing or malformed, we fall back to the default
``web_search`` pack. The default is deliberately the safest pack
(read-only outbound search) - if no pack has been chosen yet, the
composer behaves like a research scratchpad.

Supported packs (W256 spec):

    web_search, business, civic, entrepreneur, wallet, traders,
    science, algotrade

Each pack ships a ``composer_prompts.py`` with three top-level
attributes:

    - ``SYSTEM_PROMPT_OVERLAY``  -> str, appended to base composer prompt
    - ``ACTION_VOCABULARY``      -> dict[str, str] shortcut -> template
    - ``FILE_HINTS``             -> dict[str, str] label -> path

This module never raises on a missing module; an empty overlay /
vocab / hints is returned instead so the composer always degrades
gracefully.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any


DEFAULT_PACK = "web_search"

# Slugs the composer recognizes. The list is closed on purpose - the
# /switch-pack endpoint validates against this set so a typo can't
# silently rebrand the composer into a bogus mode.
KNOWN_PACKS: tuple[str, ...] = (
    "web_search",
    "business",
    "civic",
    "entrepreneur",
    "wallet",
    "traders",
    "science",
    "algotrade",
)


def _active_pack_path() -> Path:
    raw = os.environ.get("TARS_ACTIVE_PACK_PATH") or "~/.tars/active_pack.json"
    return Path(os.path.expanduser(raw))


def get_active_pack() -> str:
    """Return the current active-pack slug, or ``DEFAULT_PACK``.

    Reads ``~/.tars/active_pack.json``. Tolerant of missing file,
    bad JSON, or unknown slugs (anything we don't recognize is
    treated as unset).
    """

    p = _active_pack_path()
    if not p.is_file():
        return DEFAULT_PACK
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_PACK
    pack = data.get("pack") if isinstance(data, dict) else None
    if not isinstance(pack, str):
        return DEFAULT_PACK
    pack = pack.strip()
    if pack not in KNOWN_PACKS:
        return DEFAULT_PACK
    return pack


def set_active_pack(pack: str) -> str:
    """Persist ``pack`` as the composer's active pack.

    Raises :class:`ValueError` on an unknown slug so callers can map
    to a 400. Creates ``~/.tars/`` on demand.
    """

    if not isinstance(pack, str) or pack.strip() not in KNOWN_PACKS:
        raise ValueError(
            f"unknown pack {pack!r}; expected one of {sorted(KNOWN_PACKS)}"
        )
    p = _active_pack_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pack": pack.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return pack.strip()


def _load_module(pack: str) -> Any | None:
    """Import ``backend.core.domains.packs.<pack>.composer_prompts``.

    Returns ``None`` if the module doesn't exist (so an out-of-tree
    pack that hasn't shipped the W256 overlay still works - it just
    runs against the base composer prompt).

    Uses ``spec_from_file_location`` so the import doesn't trigger
    the parent ``backend.core.domains.packs`` package ``__init__`` —
    that file pulls in heavy deps (``nacl`` for plugin signing, etc.)
    which we don't need for prompt overlays and which can fail in
    constrained test environments.
    """

    try:
        return import_module(
            f"backend.core.domains.packs.{pack}.composer_prompts"
        )
    except ModuleNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        pass

    # File-based loader — sidesteps the package __init__ chain.
    try:
        import importlib.util  # noqa: PLC0415
        from pathlib import Path as _Path  # noqa: PLC0415

        here = _Path(__file__).resolve()
        # backend/core/composer/packs.py -> backend/core/domains/packs/
        # parents[0]=composer, parents[1]=core -> sibling 'domains/packs'.
        repo_packs = here.parents[1] / "domains" / "packs"
        leaf = repo_packs / pack / "composer_prompts.py"
        if not leaf.is_file():
            return None
        spec = importlib.util.spec_from_file_location(
            f"_composer_pack_prompts_{pack}", str(leaf)
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001
        return None


def get_pack_overlay(pack: str | None = None) -> str:
    """Return the pack's ``SYSTEM_PROMPT_OVERLAY`` text, or ``""``."""

    slug = pack or get_active_pack()
    mod = _load_module(slug)
    if mod is None:
        return ""
    val = getattr(mod, "SYSTEM_PROMPT_OVERLAY", "")
    return str(val) if val else ""


def get_pack_action_vocabulary(pack: str | None = None) -> dict[str, str]:
    """Return the pack's ``ACTION_VOCABULARY`` dict, or empty dict."""

    slug = pack or get_active_pack()
    mod = _load_module(slug)
    if mod is None:
        return {}
    val = getattr(mod, "ACTION_VOCABULARY", {})
    if not isinstance(val, dict):
        return {}
    # Stringify defensively - operator-facing template strings only.
    return {str(k): str(v) for k, v in val.items()}


def get_pack_file_hints(pack: str | None = None) -> dict[str, str]:
    """Return the pack's ``FILE_HINTS`` dict, or empty dict."""

    slug = pack or get_active_pack()
    mod = _load_module(slug)
    if mod is None:
        return {}
    val = getattr(mod, "FILE_HINTS", {})
    if not isinstance(val, dict):
        return {}
    return {str(k): str(v) for k, v in val.items()}


def expand_action_shortcut(
    transcript: str, pack: str | None = None
) -> str:
    """Expand a leading ``ACTION_VOCABULARY`` shortcut in ``transcript``.

    Supports a few input styles:

    - ``"post about X"`` -> expands "post" with ``{topic}=about X``
    - ``"draft to alice about pricing"`` -> ``draft`` with ``contact=alice``
    - ``"rebalance"`` -> single-word shortcut, no params

    Unknown words pass through unchanged. The first whitespace-
    separated token is the candidate shortcut.
    """

    if not transcript:
        return transcript
    vocab = get_pack_action_vocabulary(pack)
    if not vocab:
        return transcript
    head, _, tail = transcript.strip().partition(" ")
    head_key = head.lower().strip(",.!?:;")
    template = vocab.get(head_key)
    if not template:
        return transcript
    rest = tail.strip()
    # Best-effort: substitute the remainder into the first placeholder.
    # If there are no placeholders, prepend the expansion to the rest.
    try:
        if "{" in template:
            # Replace any {x} with the rest verbatim; if no rest, drop
            # placeholders.
            import re as _re

            def _sub(_m: _re.Match[str]) -> str:
                return rest or ""

            expanded = _re.sub(r"\{[^}]+\}", _sub, template)
        else:
            expanded = template
    except Exception:  # noqa: BLE001
        expanded = template
    expanded = expanded.strip()
    if rest and "{" not in template:
        return f"{expanded} ({rest})"
    return expanded


def get_pack_info(pack: str | None = None) -> dict[str, Any]:
    """Return the full pack-info payload used by the HTTP router."""

    slug = pack or get_active_pack()
    return {
        "pack": slug,
        "default": slug == DEFAULT_PACK,
        "known_packs": list(KNOWN_PACKS),
        "system_prompt_overlay": get_pack_overlay(slug),
        "action_vocabulary": get_pack_action_vocabulary(slug),
        "file_hints": get_pack_file_hints(slug),
    }


__all__ = [
    "DEFAULT_PACK",
    "KNOWN_PACKS",
    "get_active_pack",
    "set_active_pack",
    "get_pack_overlay",
    "get_pack_action_vocabulary",
    "get_pack_file_hints",
    "expand_action_shortcut",
    "get_pack_info",
]
