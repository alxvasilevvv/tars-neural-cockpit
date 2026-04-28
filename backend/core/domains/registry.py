"""Domain pack registry.

Packs register themselves at import time by calling :func:`register`. The
registry is a simple in-process mapping; nothing here implies how the host
app discovers packs (the app should ``import backend.core.domains.packs``).
"""

from __future__ import annotations

from typing import Iterable

from .base import DomainPack

_REGISTRY: dict[str, DomainPack] = {}


def register(pack: DomainPack) -> None:
    """Register a pack instance under its manifest slug.

    Re-registration with the same slug overwrites the previous entry. Tests
    rely on this for monkey-patching; production should not need it.
    """

    slug = pack.manifest.slug
    if not slug:
        raise ValueError("DomainPack manifest.slug must be non-empty")
    _REGISTRY[slug] = pack


def get_pack(slug: str) -> DomainPack | None:
    """Return the pack registered under ``slug`` or ``None``."""

    return _REGISTRY.get(slug)


def all_packs() -> Iterable[DomainPack]:
    """Return all registered packs in insertion order."""

    return tuple(_REGISTRY.values())


def clear() -> None:
    """Remove every registered pack. Test helper, not for production."""

    _REGISTRY.clear()
