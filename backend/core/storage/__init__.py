"""W231 — boot-time storage bootstrap.

The heavy-lifting lives in :mod:`backend.core.storage.bootstrap`.
Importing this package is cheap; the bootstrap routine itself is
called from ``web_extras/app.py``'s lifespan.
"""

from __future__ import annotations

from .bootstrap import (
    DEFAULT_TARS_DIR,
    BootstrapResult,
    init_all_databases,
    tars_dir,
)

__all__ = [
    "DEFAULT_TARS_DIR",
    "BootstrapResult",
    "init_all_databases",
    "tars_dir",
]
