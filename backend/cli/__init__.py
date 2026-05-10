"""TARS command-line interface (Wave M2).

Stdlib-only argparse wrapper around the same action handlers
the HTTP / domain-router layer drives. The CLI is **not** a
re-implementation — every verb routes to the canonical async
handler under ``backend.core.domains.packs.*.actions`` so the
audit log, risk gate, and council voices behave identically
whether the operator drives them from the cockpit, an external
MCP client, or the terminal.

Entry point: ``python -m backend.cli`` (and a shell shim at
``bin/tars`` once the package is installed).
"""

from .main import build_parser, main

__all__ = ["build_parser", "main"]
