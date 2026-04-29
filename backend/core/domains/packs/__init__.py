"""Built-in domain packs.

Importing this module triggers registration of every shipped pack. The host
application should import this once at startup so the registry is populated
before any router is mounted.

Composite packs are registered after the leaf packs so they can cleanly
reference the leaves through the registry.
"""

from . import business, entrepreneur, mlm, science, traders, wallet  # noqa: F401
from .composites import register_default_composites

register_default_composites()

__all__ = [
    "business",
    "entrepreneur",
    "mlm",
    "science",
    "traders",
    "wallet",
    "register_default_composites",
]
