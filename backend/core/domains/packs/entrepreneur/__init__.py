"""Entrepreneur pack — Phase M / P6 canonical replacement for ``mlm``.

The MLM pack stays in the registry as a deprecated alias resolving to
this pack until 2026-07-29. Cockpit state, saved agents, and third-
party API clients that pinned ``pack_slug=mlm`` keep working; new code
should use ``entrepreneur``.
"""

from .pack import EntrepreneurPack

__all__ = ["EntrepreneurPack"]
