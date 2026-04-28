"""Disk-backed playbook discovery.

Layout: ``playbooks/<pack>/<name>.json``. Each file is a single
:class:`Playbook` definition. Names must be unique. The loader caches
the result of a scan; call :func:`reset_loader_cache` to re-read.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


PLAYBOOKS_DIR = Path(__file__).resolve().parents[3] / "playbooks"


@dataclass(frozen=True)
class PlaybookStep:
    id: str
    action: str  # "<slug>.<action_id>" OR "<slug>.awareness.<source_id>.snapshot"
    args: dict[str, Any] = field(default_factory=dict)
    store_as: Optional[str] = None
    when: Optional[str] = None  # simple python boolean expression over context
    on_error: str = "stop"  # "stop" | "continue"


@dataclass(frozen=True)
class Playbook:
    id: str
    name: str
    description: str
    steps: tuple[PlaybookStep, ...]
    pack: Optional[str] = None
    tags: tuple[str, ...] = ()
    on_block: str = "stop"  # "stop" | "continue"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "pack": self.pack,
            "tags": list(self.tags),
            "on_block": self.on_block,
            "steps": [
                {
                    "id": s.id,
                    "action": s.action,
                    "args": dict(s.args),
                    "store_as": s.store_as,
                    "when": s.when,
                    "on_error": s.on_error,
                }
                for s in self.steps
            ],
        }


def _step_from_dict(d: Mapping[str, Any]) -> PlaybookStep:
    if "id" not in d or "action" not in d:
        raise ValueError(f"playbook step missing id/action: {dict(d)}")
    return PlaybookStep(
        id=str(d["id"]),
        action=str(d["action"]),
        args=dict(d.get("args") or {}),
        store_as=str(d["store_as"]) if d.get("store_as") else None,
        when=str(d["when"]) if d.get("when") else None,
        on_error=str(d.get("on_error") or "stop"),
    )


def _from_dict(blob: Mapping[str, Any], *, pack: str | None) -> Playbook:
    pid = str(blob.get("id") or "").strip()
    if not pid:
        raise ValueError("playbook missing id")
    steps = blob.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"playbook {pid} has no steps")
    return Playbook(
        id=pid,
        name=str(blob.get("name") or pid),
        description=str(blob.get("description") or ""),
        steps=tuple(_step_from_dict(s) for s in steps),
        pack=pack or (str(blob.get("pack")) if blob.get("pack") else None),
        tags=tuple(str(t) for t in (blob.get("tags") or [])),
        on_block=str(blob.get("on_block") or "stop"),
    )


_CACHE: dict[str, Playbook] | None = None


def discover(root: Path | str | None = None) -> dict[str, Playbook]:
    """Scan disk and return a fresh ``{id: Playbook}`` mapping.

    Reads from ``$TARS_PLAYBOOKS_DIR`` first if set, else the project-
    relative ``playbooks/`` directory.
    """

    if root is None:
        root_env = os.getenv("TARS_PLAYBOOKS_DIR")
        root = Path(root_env) if root_env else PLAYBOOKS_DIR
    root = Path(root)
    out: dict[str, Playbook] = {}
    if not root.exists():
        return out
    for pack_dir in sorted(root.iterdir()):
        if not pack_dir.is_dir():
            continue
        for path in sorted(pack_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as fh:
                    blob = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid json in {path}: {exc}") from exc
            try:
                pb = _from_dict(blob, pack=pack_dir.name)
            except ValueError as exc:
                raise ValueError(f"invalid playbook in {path}: {exc}") from exc
            if pb.id in out:
                raise ValueError(
                    f"duplicate playbook id {pb.id!r} (existing: {path})"
                )
            out[pb.id] = pb
    return out


def list_playbooks(refresh: bool = False) -> Iterable[Playbook]:
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = discover()
    return list(_CACHE.values())


def get_playbook(playbook_id: str, refresh: bool = False) -> Optional[Playbook]:
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = discover()
    return _CACHE.get(playbook_id)


def reset_loader_cache() -> None:
    global _CACHE
    _CACHE = None
