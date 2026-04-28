"""Convenience runner for the TARS cockpit backend.

Usage:
    .venv/bin/python serve.py            # default 127.0.0.1:8765
    PORT=9000 HOST=0.0.0.0 python serve.py

Once running, browse:
    http://127.0.0.1:8765/docs           # OpenAPI
    http://127.0.0.1:8765/api/domains    # domain packs
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import uvicorn  # noqa: WPS433  (runtime guard)
    except ImportError:
        sys.stderr.write(
            "uvicorn is not installed. Run: pip install fastapi uvicorn\n"
        )
        return 2

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    reload = os.getenv("TARS_RELOAD", "0") == "1"

    uvicorn.run(
        "web_extras.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
