"""Built-in domain packs.

Importing this module triggers registration of every shipped pack. The host
application should import this once at startup so the registry is populated
before any router is mounted.
"""

from . import business, mlm, science, traders  # noqa: F401

__all__ = ["business", "mlm", "science", "traders"]
