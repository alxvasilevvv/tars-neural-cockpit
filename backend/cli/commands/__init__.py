"""CLI subcommand modules.

Each module exports an ``add_parser(subparsers)`` function that
registers its subcommand tree on the top-level parser, and a
``handle(args, ctx)`` function the dispatcher routes to.
"""

from . import algotrade, lab, playbooks, version

__all__ = ["algotrade", "lab", "playbooks", "version"]
