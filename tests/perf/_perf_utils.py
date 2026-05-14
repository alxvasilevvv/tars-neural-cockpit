"""W266 — shared utilities for the five TARS performance benchmarks.

Each ``bench_*.py`` file imports two helpers from here:

* :func:`record_result` writes ``{name, samples, p50_ms, p95_ms,
  p99_ms, slo_ms, throughput_per_s, passed, slo_violations}`` to
  ``tests/perf/.results/<name>.json`` so the suite runner can render
  ``docs/PERF_REPORT_v10.0.md`` without re-running anything.
* :func:`percentiles` is a tiny dependency-free p50/p95/p99 helper —
  ``numpy``/``scipy`` are intentionally not imported because the perf
  suite has to run on stripped-down on-prem images that ship only the
  ``requirements.txt`` core.

The two helpers are deliberately ``pytest-benchmark``-agnostic: when
the plugin is installed we still write the same JSON shape so the
report is identical either way.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Iterable

# Tests/perf/.results/<name>.json — one row per benchmark. Cleaned on
# every RUN-PERF-SUITE invocation so we never report stale numbers.
RESULTS_DIR = Path(__file__).parent / ".results"


def percentiles(samples_ms: Iterable[float]) -> tuple[float, float, float]:
    """Return (p50, p95, p99) for a sequence of millisecond samples.

    Linear-interpolated; matches what most ops teams expect from a
    Grafana / Prometheus quantile query. Empty input is a programming
    error and raises ValueError so we never silently report 0ms.
    """

    xs = sorted(float(v) for v in samples_ms)
    if not xs:
        raise ValueError("percentiles() needs at least one sample")

    def q(p: float) -> float:
        if len(xs) == 1:
            return xs[0]
        idx = p * (len(xs) - 1)
        lo = math.floor(idx)
        hi = math.ceil(idx)
        if lo == hi:
            return xs[int(idx)]
        frac = idx - lo
        return xs[lo] * (1 - frac) + xs[hi] * frac

    return q(0.50), q(0.95), q(0.99)


def record_result(
    *,
    name: str,
    samples_ms: list[float],
    slo_ms: float,
    extra: dict | None = None,
) -> dict:
    """Persist a benchmark's results and return the rendered row.

    ``passed`` is computed against ``p95_ms <= slo_ms`` because that's
    the rule the rest of the suite (``RUN-PERF-SUITE.command`` +
    ``PERF_REPORT_v10.0.md``) reads.
    """

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    p50, p95, p99 = percentiles(samples_ms)
    row = {
        "name": name,
        "samples": len(samples_ms),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max(samples_ms), 2),
        "slo_ms": slo_ms,
        "passed": p95 <= slo_ms,
        "slo_kind": "p95_latency",
    }
    if extra:
        row.update(extra)

    # Pretty so a human can `cat` it without piping through jq.
    (RESULTS_DIR / f"{name}.json").write_text(
        json.dumps(row, indent=2, sort_keys=True), encoding="utf-8"
    )
    return row


def isolate_tars_home(monkeypatch, tmp_path) -> Path:
    """Point every TARS sqlite / receipt / chat path at ``tmp_path``.

    Mirrors the fixture used in `tests/test_composer.py` so each perf
    bench is hermetic and doesn't pollute the real ``~/.tars/`` tree
    on the host running the suite.
    """

    home = tmp_path / "tars-home"
    home.mkdir()
    monkeypatch.setenv("TARS_HOME", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TARS_CHAT_DB_PATH", str(home / "chat.sqlite"))
    monkeypatch.setenv("TARS_EVENTS_DB_PATH", str(home / "events.sqlite"))
    monkeypatch.setenv("TARS_RECEIPT_DIR", str(home / "receipts"))
    monkeypatch.setenv("TARS_RECEIPT_DB_PATH", str(home / "receipts.sqlite"))
    monkeypatch.setenv(
        "TARS_RECEIPT_HOST_KEY_PATH", str(home / "host-key.json")
    )
    monkeypatch.setenv("TARS_COMPOSER_DB", str(home / "composer.sqlite"))
    monkeypatch.setenv(
        "TARS_COMPOSER_BACKUP_DIR", str(home / "composer-backups")
    )
    # Strip cloud-LLM keys so any benchmark that touches the chat /
    # composer / voice paths exercises the deterministic fallback,
    # not a paid API. The perf suite must not cost money to run.
    for k in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "TARS_ANTHROPIC_API_KEY",
        "TARS_OPENAI_API_KEY",
        "TARS_OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    return home


__all__ = [
    "RESULTS_DIR",
    "percentiles",
    "record_result",
    "isolate_tars_home",
]
