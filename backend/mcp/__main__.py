"""``python -m backend.mcp`` entry point.

Boots the stdio MCP server. Logging goes to stderr (MCP
hosts treat it as an out-of-band log channel).

Useful environment variables:

- ``TARS_MCP_LOG_LEVEL`` — set to ``DEBUG`` / ``INFO`` /
  ``WARNING`` / ``ERROR`` (default ``INFO``).
- All ``TARS_*`` env vars the underlying packs honour
  (``TARS_HOME``, ``TARS_ALGOTRADE_HOME``, etc.) propagate
  unchanged because the MCP server hosts the same packs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys


def _configure_logging() -> None:
    level_name = (os.environ.get("TARS_MCP_LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        stream=sys.stderr,
        level=level,
        format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    _configure_logging()
    from .server import McpServer
    from .stdio import serve_stdio

    server = McpServer()
    try:
        return asyncio.run(serve_stdio(server))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
