"""MCP session pool facade (Wave M6+M7 consolidated rewrite)."""

from __future__ import annotations

from .bridge_pkg.pool import SessionPool, get_default_pool, reset_default_pool

__all__ = ["SessionPool", "get_default_pool", "reset_default_pool"]
