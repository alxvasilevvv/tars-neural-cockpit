"""TARS domain packs.

Each pack adapts the neural core to a specific audience: traders, business,
MLM, science. A pack contributes:

- ``actions``: domain-specific operations the agent can invoke.
- ``awareness``: data sources / streams the pack listens to.
- ``system_prompt``: voice and constraints for the council in this mode.

The :mod:`backend.core.domains.packs` subpackage registers all built-in packs
on import. Anything that wants to use the registry should ``import`` either
this module or :mod:`backend.core.domains.packs`.
"""

from .base import (
    ActionSpec,
    AwarenessSource,
    DomainManifest,
    DomainPack,
)
from .registry import all_packs, get_pack, register

__all__ = [
    "ActionSpec",
    "AwarenessSource",
    "DomainManifest",
    "DomainPack",
    "all_packs",
    "get_pack",
    "register",
]
