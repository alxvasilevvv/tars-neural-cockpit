"""
TARS QA Agent — autonomous end-to-end probe for tars.meeet.world + bridge.

Stdlib-only by design (no requests / no aiohttp / no pytest). Runs from
any Python 3.10+ environment that ships with macOS / Ubuntu by default,
which lets us drop it into GH Actions without `pip install`.
"""

__version__ = "1.0.0"
