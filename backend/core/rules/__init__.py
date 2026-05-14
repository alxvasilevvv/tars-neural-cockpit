"""W239 - Rules for TARS (Cursor "Rules for AI" equivalent).

A small, durable seam that lets the operator dictate coding/style/
behavior rules that get folded into the system prompt for every chat
turn. Mirrors Cursor's "Rules for AI" feature.

Storage
-------

Global rules live in ``~/.tars/rules.yml`` (overrideable via
``TARS_HOME`` env var). Per-domain-pack rules can ship at
``backend/core/domains/packs/<slug>/rules.yml`` - those are READ-ONLY
overlays, loaded only when that pack is active for the current
thread.

YAML schema (intentionally minimal)::

    rules:
      - id: r-1
        text: "Answer in the language the user wrote in"
        enabled: true
      - id: r-2
        text: "..."
        enabled: false

YAML parse errors are caught: a corrupt file degrades to an empty
list rather than crashing the chat path. Atomic writes keep the file
intact if the process dies mid-write.

Integration
-----------

:func:`inject_rules_into_prompt` is called from the chat orchestrator
right before the system prompt hits the voice. Wrapped in a
defensive try/except: rules are a nice-to-have, never a P0.
"""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal


# ---------------------------------------------------------------------------
# Default seed - first boot writes these to ~/.tars/rules.yml so the operator
# has something to edit/disable in the Settings panel.
# ---------------------------------------------------------------------------

DEFAULT_RULES_SEED: list[dict[str, Any]] = [
    {
        "id": "seed-language",
        "text": "Answer in the language the user wrote in.",
        "enabled": True,
    },
    {
        "id": "seed-no-hallucinate-paths",
        "text": (
            "Never make up file paths or URLs - say 'I don't have that' "
            "instead of inventing one."
        ),
        "enabled": True,
    },
    {
        "id": "seed-confirm-dangerous",
        "text": (
            "When asked to do something dangerous (rm -rf, delete data, "
            "wipe storage, force-push), confirm first before acting."
        ),
        "enabled": True,
    },
    {
        "id": "seed-concrete-examples",
        "text": (
            "Prefer concrete examples over abstract descriptions - show "
            "a snippet or a real value when you can."
        ),
        "enabled": True,
    },
    {
        "id": "seed-fewer-side-effects",
        "text": (
            "When unsure between two options, pick the one with fewer "
            "side effects."
        ),
        "enabled": True,
    },
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


Scope = Literal["global", "pack"]


@dataclass
class Rule:
    """One operator-defined rule injected into the system prompt."""

    id: str
    text: str
    enabled: bool = True
    scope: Scope = "global"
    pack: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "enabled": bool(self.enabled),
            "scope": self.scope,
            "pack": self.pack,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        scope: Scope = "global",
        pack: str | None = None,
    ) -> "Rule":
        rid = str(data.get("id") or f"rule-{uuid.uuid4().hex[:8]}")
        text = str(data.get("text") or "").strip()
        enabled = bool(data.get("enabled", True))
        return cls(id=rid, text=text, enabled=enabled, scope=scope, pack=pack)


# ---------------------------------------------------------------------------
# Filesystem paths
# ---------------------------------------------------------------------------


def _tars_home() -> Path:
    """Return ``~/.tars`` (or ``TARS_HOME`` override). Created on demand."""

    override = os.environ.get("TARS_HOME")
    if override:
        p = Path(override).expanduser()
    else:
        p = Path.home() / ".tars"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def global_rules_path() -> Path:
    """Return ``~/.tars/rules.yml`` (the global rule store)."""

    return _tars_home() / "rules.yml"


def _packs_dir() -> Path:
    """Return the on-disk parent of all domain packs."""

    here = Path(__file__).resolve()
    # backend/core/rules/__init__.py -> backend/core/domains/packs
    return here.parent.parent / "domains" / "packs"


def pack_rules_path(pack_slug: str) -> Path:
    """Return ``backend/core/domains/packs/<slug>/rules.yml``."""

    return _packs_dir() / pack_slug / "rules.yml"


# ---------------------------------------------------------------------------
# YAML helpers (defensive - never raises on parse error)
# ---------------------------------------------------------------------------


def _load_yaml_safe(path: Path) -> dict[str, Any]:
    """Read ``path`` as YAML. Returns ``{}`` on any failure."""

    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        # YAML parse error, IO error, encoding error - degrade silently.
        return {}


def _dump_yaml_atomic(path: Path, data: dict[str, Any]) -> None:
    """Atomic write of YAML to ``path`` with 0o600 perms."""

    import yaml  # type: ignore

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".rules-", suffix=".yml.tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            yaml.safe_dump(
                data,
                fh,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
            )
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


# ---------------------------------------------------------------------------
# Seed on first boot
# ---------------------------------------------------------------------------


def _ensure_seed() -> None:
    """Write the default seed file if ``~/.tars/rules.yml`` is missing."""

    path = global_rules_path()
    if path.exists():
        return
    try:
        _dump_yaml_atomic(
            path,
            {
                "version": 1,
                "created_ts": int(time.time()),
                "rules": [dict(r) for r in DEFAULT_RULES_SEED],
            },
        )
    except Exception:
        # If we can't seed, downstream loads return an empty list.
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _coerce_rules(
    items: Iterable[Any],
    *,
    scope: Scope,
    pack: str | None,
) -> list[Rule]:
    out: list[Rule] = []
    if not items:
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            r = Rule.from_dict(item, scope=scope, pack=pack)
        except Exception:
            continue
        if not r.text:
            continue
        out.append(r)
    return out


def load_global_rules() -> list[Rule]:
    """Read ~/.tars/rules.yml (seeding if absent). Always returns a list."""

    _ensure_seed()
    data = _load_yaml_safe(global_rules_path())
    return _coerce_rules(data.get("rules") or [], scope="global", pack=None)


def load_pack_rules(pack_slug: str | None) -> list[Rule]:
    """Read per-pack overlay rules. Returns ``[]`` if pack has no file."""

    if not pack_slug:
        return []
    data = _load_yaml_safe(pack_rules_path(pack_slug))
    return _coerce_rules(data.get("rules") or [], scope="pack", pack=pack_slug)


def load_active_rules(active_pack: str | None = None) -> list[Rule]:
    """Return flattened rules - enabled first, then disabled; global before pack.

    The returned list is the *visible* set (enabled + disabled both
    appear so the Settings UI can render them). Use
    :func:`inject_rules_into_prompt` for the LLM-injection path,
    which filters to enabled-only.
    """

    out: list[Rule] = []
    g = load_global_rules()
    p = load_pack_rules(active_pack)

    enabled_global = [r for r in g if r.enabled]
    disabled_global = [r for r in g if not r.enabled]
    enabled_pack = [r for r in p if r.enabled]
    disabled_pack = [r for r in p if not r.enabled]

    out.extend(enabled_global)
    out.extend(enabled_pack)
    out.extend(disabled_global)
    out.extend(disabled_pack)
    return out


def save_global_rules(rules: list[Rule]) -> None:
    """Persist the global rule list to ``~/.tars/rules.yml`` (atomic, 0o600).

    Pack-scope rules are silently dropped - pack overlays are
    read-only from the pack source.
    """

    payload: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rules:
        if r.scope == "pack":
            continue
        rid = r.id or f"rule-{uuid.uuid4().hex[:8]}"
        if rid in seen:
            continue
        seen.add(rid)
        payload.append(
            {
                "id": rid,
                "text": r.text,
                "enabled": bool(r.enabled),
            }
        )
    _dump_yaml_atomic(
        global_rules_path(),
        {
            "version": 1,
            "updated_ts": int(time.time()),
            "rules": payload,
        },
    )


def patch_global_rule(
    rule_id: str,
    *,
    text: str | None = None,
    enabled: bool | None = None,
) -> Rule | None:
    """Patch one rule's text/enabled. Returns updated Rule or None if missing."""

    rules = load_global_rules()
    found: Rule | None = None
    for r in rules:
        if r.id == rule_id:
            if text is not None:
                r.text = str(text).strip()
            if enabled is not None:
                r.enabled = bool(enabled)
            found = r
            break
    if found is None:
        return None
    save_global_rules(rules)
    return found


def delete_global_rule(rule_id: str) -> bool:
    """Remove a rule from the global store. Returns True if it existed."""

    rules = load_global_rules()
    keep = [r for r in rules if r.id != rule_id]
    if len(keep) == len(rules):
        return False
    save_global_rules(keep)
    return True


# ---------------------------------------------------------------------------
# Prompt injection
# ---------------------------------------------------------------------------


def _format_rules_block(rules: list[Rule]) -> str:
    """Render the ``## Rules`` block. Skips disabled and empty rules."""

    visible = [r for r in rules if r.enabled and r.text]
    if not visible:
        return ""
    lines: list[str] = ["## Rules", ""]
    lines.append(
        "The operator has set the following rules. Honor every one of them "
        "unless they conflict with safety or the operator's explicit request "
        "this turn."
    )
    lines.append("")
    for idx, r in enumerate(visible, start=1):
        suffix = (
            f"  _(from pack: {r.pack})_"
            if r.scope == "pack" and r.pack
            else ""
        )
        lines.append(f"{idx}. {r.text.strip()}{suffix}")
    lines.append("")
    return "\n".join(lines)


def inject_rules_into_prompt(
    system_prompt: str | None,
    active_pack: str | None = None,
) -> str:
    """Return ``system_prompt`` with a ``## Rules`` block prepended.

    Defensive: any failure (missing YAML lib, corrupt file, IO error)
    returns the original prompt unchanged.
    """

    base = system_prompt or ""
    try:
        rules = load_active_rules(active_pack)
        block = _format_rules_block(rules)
    except Exception:
        return base
    if not block:
        return base
    if not base.strip():
        return block.rstrip() + "\n"
    return block.rstrip() + "\n\n" + base


__all__ = [
    "Rule",
    "DEFAULT_RULES_SEED",
    "global_rules_path",
    "pack_rules_path",
    "load_global_rules",
    "load_pack_rules",
    "load_active_rules",
    "save_global_rules",
    "patch_global_rule",
    "delete_global_rule",
    "inject_rules_into_prompt",
]
