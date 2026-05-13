"""``python -m backend.core.doctor`` — run all checks + print results.

Flags:
  --json        machine-readable output, no terminal colors
  --quiet       only print problems (status != ok)
  --check SLUG  run a single check by slug
  --timeout S   per-check soft timeout (default 5)

Exit codes:
  0  — all checks ok or skip
  1  — at least one warn
  2  — at least one fail
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .checks import REGISTRY, CheckResult, run_all, run_check
from .fixers import FIX_REGISTRY, FixResult, run_all_fixes, run_fix


# ANSI colors — disabled when stdout isn't a TTY or NO_COLOR is set.
def _supports_color() -> bool:
    import os
    if os.getenv("NO_COLOR"):
        return False
    return sys.stdout.isatty()


_COLOR = {
    "ok": "\033[32m",     # green
    "warn": "\033[33m",   # yellow
    "fail": "\033[31m",   # red
    "skip": "\033[90m",   # bright black
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def _c(s: str, key: str) -> str:
    if not _supports_color():
        return s
    return f"{_COLOR.get(key, '')}{s}{_COLOR['reset']}"


_STATUS_GLYPH = {
    "ok": "✓",
    "warn": "⚠",
    "fail": "✗",
    "skip": "·",
}


def _format_human(results: Sequence[CheckResult], *, quiet: bool) -> str:
    rows: list[str] = []
    rows.append(_c("TARS doctor — health check (Wave 154)", "bold"))
    rows.append("")
    max_label = max((len(r.label) for r in results), default=0)
    for r in results:
        if quiet and r.status == "ok":
            continue
        glyph = _STATUS_GLYPH.get(r.status, "?")
        line = (
            f"  {_c(glyph, r.status)}  "
            f"{r.label.ljust(max_label)}  "
            f"{_c(r.status.upper().ljust(4), r.status)}  "
            f"{r.summary}"
        )
        rows.append(line)
        if r.suggestion and r.status != "ok":
            rows.append(f"      → {r.suggestion}")
    # Summary line
    totals: dict[str, int] = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for r in results:
        totals[r.status] = totals.get(r.status, 0) + 1
    rows.append("")
    rows.append(
        "  Summary: "
        f"{_c(str(totals['ok']), 'ok')} ok · "
        f"{_c(str(totals['warn']), 'warn')} warn · "
        f"{_c(str(totals['fail']), 'fail')} fail · "
        f"{_c(str(totals['skip']), 'skip')} skip"
    )
    return "\n".join(rows) + "\n"


def _exit_code(results: Sequence[CheckResult]) -> int:
    if any(r.status == "fail" for r in results):
        return 2
    if any(r.status == "warn" for r in results):
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m backend.core.doctor",
        description="Unified TARS health check (Wave 154).",
    )
    p.add_argument(
        "--json", action="store_true",
        help="machine-readable output",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="suppress 'ok' rows in human output",
    )
    p.add_argument(
        "--check", metavar="SLUG", default=None,
        help="run a single check by slug (e.g. daemon, mcp, clone)",
    )
    p.add_argument(
        "--timeout", type=float, default=5.0,
        help="per-check soft timeout in seconds (default 5)",
    )
    p.add_argument(
        "--list", action="store_true",
        help="print available check slugs and exit",
    )
    p.add_argument(
        "--fix", nargs="?", const="__ALL__", metavar="SLUG",
        help="apply safe auto-remediation. With no arg: every registered fixer. With SLUG: one.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list:
        for slug, fn in REGISTRY:
            doc = (fn.__doc__ or "").strip().splitlines()
            short = doc[0] if doc else ""
            has_fix = " [fixer]" if slug in FIX_REGISTRY else ""
            sys.stdout.write(f"{slug:12s}  {short}{has_fix}\n")
        return 0

    if args.fix:
        if args.fix == "__ALL__":
            fix_results = run_all_fixes()
        else:
            fix_results = [run_fix(args.fix)]
        if args.json:
            _print_json([r.to_dict() for r in fix_results])
        else:
            sys.stdout.write("TARS doctor — fix run\n\n")
            for r in fix_results:
                if r.applied:
                    glyph = "✓"
                    line = f"  {glyph} {r.slug:12s} {r.before_status} → {r.after_status or '?'}  {r.detail}"
                elif r.skipped:
                    glyph = "·"
                    line = f"  {glyph} {r.slug:12s} SKIP ({r.reason})  {r.detail}"
                else:
                    glyph = "✗"
                    line = f"  {glyph} {r.slug:12s} FAIL ({r.reason})  {r.detail}"
                sys.stdout.write(line + "\n")
            applied = sum(1 for r in fix_results if r.applied)
            skipped = sum(1 for r in fix_results if r.skipped)
            failed = sum(1 for r in fix_results if not r.applied and not r.skipped)
            sys.stdout.write(
                f"\n  Summary: {applied} applied · {skipped} skipped · {failed} failed\n"
            )
        return 0 if not any(
            (not r.applied and not r.skipped) for r in fix_results
        ) else 2

    if args.check:
        results = [run_check(args.check, timeout_s=args.timeout)]
    else:
        results = run_all(timeout_s=args.timeout)

    if args.json:
        sys.stdout.write(
            json.dumps([r.to_dict() for r in results], indent=2, default=str) + "\n"
        )
    else:
        sys.stdout.write(_format_human(results, quiet=args.quiet))

    return _exit_code(results)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
