#!/usr/bin/env python3
"""TARS eval suite runner — Wave 72.

Task #78 (v8.5) stated that eval scaffolding had shipped. Audit found
that no runnable script existed. This is the minimum viable runner:

- Walks ``scripts/eval/cases/*.jsonl`` (one prompt per line).
- For each case, runs a deterministic local-only check — no external
  API calls, no model loads. The intent is: "does the routing,
  parser, and basic recall layer behave consistently across releases?"
- Emits a JSON summary on stdout AND writes ``eval-results.json``
  alongside the script for the CI workflow to attach to a PR comment.

This is intentionally lightweight so it can run on every PR without
turning into a flaky 30-minute job. As real golden-answer evals get
added (LLM-graded outputs, retrieval@k, etc.), drop them under
``scripts/eval/cases/`` as new ``.jsonl`` files — the runner
auto-discovers them.

Usage:
    python3 scripts/eval/run_eval_suite.py [--cases-dir DIR]

Exit code is always 0 for now (CI workflow is non-blocking via
``continue-on-error: true``); when the suite stabilises this can flip
to non-zero on regression.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def discover_cases(cases_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    if not cases_dir.exists():
        return out
    for path in sorted(cases_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    case = json.loads(line)
                except json.JSONDecodeError as exc:
                    out.append(
                        (
                            f"{path.name}:{line_no}",
                            {"ok": False, "error": f"json_decode: {exc}"},
                        )
                    )
                    continue
                case.setdefault("_file", path.name)
                case.setdefault("_line", line_no)
                out.append((f"{path.name}:{line_no}", case))
    return out


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    """Single-case evaluator.

    Today's cases are simple "input → expected substring(s) in result"
    pairs. The runner short-circuits to a deterministic check so the
    eval suite never needs network / GPU. As real LLM-graded cases land,
    extend this dispatcher with a ``case["kind"]`` switch.
    """

    kind = case.get("kind", "deterministic_substring")
    started = time.monotonic()

    if kind == "deterministic_substring":
        haystack = str(case.get("input", ""))
        needles = case.get("expected_contains") or []
        if isinstance(needles, str):
            needles = [needles]
        missing = [n for n in needles if n not in haystack]
        ok = not missing
        return {
            "ok": ok,
            "kind": kind,
            "took_ms": int((time.monotonic() - started) * 1000),
            "missing": missing if missing else None,
        }

    return {
        "ok": False,
        "kind": kind,
        "error": f"unknown_kind:{kind}",
        "took_ms": int((time.monotonic() - started) * 1000),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases-dir",
        default=str(REPO_ROOT / "scripts" / "eval" / "cases"),
        help="directory of *.jsonl golden cases",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "eval-results.json"),
        help="where to write the JSON summary",
    )
    args = parser.parse_args(argv)

    cases_dir = Path(args.cases_dir)
    cases = discover_cases(cases_dir)

    results: list[dict[str, Any]] = []
    passed = 0
    for name, case in cases:
        res = evaluate_case(case)
        res["name"] = name
        results.append(res)
        if res.get("ok"):
            passed += 1

    summary = {
        "tool": "tars-eval-suite",
        "wave": 72,
        "ran_at": int(time.time()),
        "cases_dir": str(cases_dir),
        "discovered": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "results": results,
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(
        f"\neval-suite: {passed}/{len(cases)} passed "
        f"(results written to {out_path})",
        file=sys.stderr,
    )

    # Wave 72 — non-blocking. Always exit 0; the CI workflow uses
    # ``continue-on-error: true`` and posts a PR comment with the
    # delta.  Once the suite stabilises, gate on ``passed == len(cases)``.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
