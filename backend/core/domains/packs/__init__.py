"""Built-in domain packs.

Importing this module triggers registration of every shipped pack. The host
application should import this once at startup so the registry is populated
before any router is mounted.

Composite packs are registered after the leaf packs so they can cleanly
reference the leaves through the registry.
"""

from . import (  # noqa: F401
    algotrade,
    business,
    civic,           # W204 — public-records pack, free for all tiers
    entrepreneur,
    mlm,
    science,
    traders,
    wallet,
    web_search,
)
from .composites import register_default_composites

register_default_composites()

__all__ = [
    "algotrade",
    "business",
    "civic",
    "entrepreneur",
    "mlm",
    "science",
    "traders",
    "wallet",
    "web_search",
    "register_default_composites",
]
