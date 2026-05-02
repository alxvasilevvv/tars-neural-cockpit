"""TARS HTTP middleware package.

Currently houses the :mod:`expensive_routes_rate_limit` middleware
(Bug #4 fix from ``docs/SYSTEM_AUDIT_2026-05-02.md``).
"""

from web_extras.middleware.expensive_routes_rate_limit import (
    ExpensiveRoutesRateLimitMiddleware,
    install_expensive_routes_rate_limit,
)

__all__ = [
    "ExpensiveRoutesRateLimitMiddleware",
    "install_expensive_routes_rate_limit",
]
