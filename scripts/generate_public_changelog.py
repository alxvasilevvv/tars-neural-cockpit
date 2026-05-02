#!/usr/bin/env python3
"""Generate a trimmed public changelog from the full agent log.

The full ``docs/CHANGELOG_AGENTS.md`` is the per-edit log every
agent appends to and currently weighs ~550 KB across 170+ entries.
The cockpit's `/changelog` page bundles it as a raw import which
balloons the chunk to ~560 KB raw / 188 KB gzip — bigger than the
entire cockpit shell.

This script splits the source on ``## `` headers, keeps the most
recent ``--limit`` entries (60 by default — roughly the last
two months of work), and writes the result to
``docs/CHANGELOG_PUBLIC.md``. The cockpit imports the public file
instead, so the chunk stays small without losing fidelity for the
operator (the full log is still on GitHub).

Usage::

    python3 scripts/generate_public_changelog.py
    python3 scripts/generate_public_changelog.py --limit 100
    python3 scripts/generate_public_changelog.py --check  # CI guard
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "CHANGELOG_AGENTS.md"
DST = ROOT / "docs" / "CHANGELOG_PUBLIC.md"

DEFAULT_LIMIT = 60

_HEADER_RE = re.compile(r"^## ", re.MULTILINE)


def _front_matter(source: str) -> str:
    """Return the markdown content before the first ``## ``
    header (title, intro paragraph). Empty string when none."""

    m = _HEADER_RE.search(source)
    if m is None:
        return ""
    return source[: m.start()].rstrip() + "\n\n"


def _entries(source: str) -> list[str]:
    """Split the source into entry strings keyed on ``## `` headers.

    Each entry includes its own ``## `` line. Order matches the
    source (newest-first by convention).
    """

    parts = _HEADER_RE.split(source)
    # parts[0] is the front-matter; entries start at index 1.
    return [f"## {p.lstrip()}" for p in parts[1:] if p.strip()]


def build_public(source: str, *, limit: int) -> str:
    """Compose the public changelog: front-matter + first
    ``limit`` entries + GitHub link footer."""

    front = _front_matter(source)
    entries = _entries(source)
    kept = entries[:limit]
    body = "\n".join(e.rstrip() + "\n" for e in kept)
    footer = (
        "\n---\n\n"
        f"_Showing the most recent {len(kept)} of "
        f"{len(entries)} entries. Full per-edit log: "
        "[`docs/CHANGELOG_AGENTS.md` on GitHub]"
        "(https://github.com/alxvasilevvv/tars-neural-cockpit/"
        "blob/main/docs/CHANGELOG_AGENTS.md)._\n"
    )
    return front + body + footer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of recent entries to keep (default {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the destination file is stale "
        "(used by CI to guard against forgotten regenerations).",
    )
    args = parser.parse_args()

    if not SRC.exists():
        print(f"ERROR: source not found: {SRC}", file=sys.stderr)
        return 1

    source = SRC.read_text(encoding="utf-8")
    public = build_public(source, limit=args.limit)

    if args.check:
        existing = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if existing != public:
            print(
                f"ERROR: {DST.relative_to(ROOT)} is stale; run "
                "`python3 scripts/generate_public_changelog.py` "
                "and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {DST.relative_to(ROOT)} is up to date.")
        return 0

    DST.write_text(public, encoding="utf-8")
    print(
        f"wrote {DST.relative_to(ROOT)} "
        f"({len(public):,} bytes, kept {min(args.limit, len(_entries(source)))} "
        f"of {len(_entries(source))} entries)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
