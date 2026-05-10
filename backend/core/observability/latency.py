"""In-process latency recorder for the perf dashboard (Wave 108).

Tiny ring-buffer keyed by operation name (``council``, ``backtest``,
``webhook``, ``connector``, ...). Each ``record(op, duration_ms)``
appends a sample with a wallclock timestamp; queries compute P50 /
P95 / P99 / Max + a coarse histogram on demand.

Why not OTel directly: OTel is OPT-IN (Wave 73) and exports to a
remote OTLP backend. The perf dashboard needs local data even when
no operator has wired up Tempo/Honeycomb/Datadog. This module is the
local mirror; OTel still receives spans separately when configured.

Storage is a per-operation ``collections.deque`` capped at
``LATENCY_BUFFER_SIZE`` (default 2048 samples) so memory is bounded
under churn. The whole module is dependency-free + thread-safe via
a single ``threading.Lock``.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Iterable


LATENCY_BUFFER_SIZE = 2048


_lock = threading.Lock()
_samples: dict[str, deque[tuple[float, float]]] = defaultdict(
    lambda: deque(maxlen=LATENCY_BUFFER_SIZE)
)


def record(op: str, duration_ms: float, *, at: float | None = None) -> None:
    """Append a single sample.

    ``op`` should be a short canonical name. Negative or NaN values
    are ignored. ``at`` defaults to ``time.time()``.
    """

    if not op or not isinstance(op, str):
        return
    try:
        ms = float(duration_ms)
    except (TypeError, ValueError):
        return
    if ms < 0 or ms != ms:  # NaN check
        return
    ts = float(at) if at is not None else time.time()
    with _lock:
        _samples[op].append((ts, ms))


def recent(op: str, *, window_s: float | None = None) -> list[float]:
    """Return durations in milliseconds for ``op`` in the time window.

    ``window_s=None`` returns the full ring buffer; pass e.g.
    ``86400`` for the last 24h.
    """

    with _lock:
        buf = list(_samples.get(op, ()))
    if not buf:
        return []
    if window_s is None or window_s <= 0:
        return [ms for _, ms in buf]
    cutoff = time.time() - float(window_s)
    return [ms for ts, ms in buf if ts >= cutoff]


def reset(op: str | None = None) -> None:
    """Clear samples for ``op`` (or all when ``None``)."""

    with _lock:
        if op is None:
            _samples.clear()
        else:
            _samples.pop(op, None)


def known_ops() -> list[str]:
    with _lock:
        return sorted(_samples.keys())


def percentile(samples: list[float], p: float) -> float | None:
    """Linear-interpolation percentile (no numpy)."""

    if not samples:
        return None
    if p <= 0:
        return min(samples)
    if p >= 100:
        return max(samples)
    sorted_s = sorted(samples)
    rank = (p / 100.0) * (len(sorted_s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_s) - 1)
    frac = rank - lo
    return sorted_s[lo] * (1 - frac) + sorted_s[hi] * frac


def summary(op: str, *, window_s: float | None = None) -> dict[str, float | int | None]:
    """Compact stats for a single operation."""

    s = recent(op, window_s=window_s)
    if not s:
        return {
            "op": op,
            "count": 0,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
            "avg": None,
        }
    return {
        "op": op,
        "count": len(s),
        "p50": round(percentile(s, 50) or 0, 2),
        "p95": round(percentile(s, 95) or 0, 2),
        "p99": round(percentile(s, 99) or 0, 2),
        "max": round(max(s), 2),
        "avg": round(sum(s) / len(s), 2),
    }


def histogram(
    op: str,
    *,
    window_s: float | None = None,
    buckets: Iterable[float] | None = None,
) -> dict[str, object]:
    """Bucketed counts (default buckets cover 1 ms .. 30 s).

    Buckets are upper-inclusive: a sample at exactly 100ms goes into
    the ``<=100`` bucket. Anything bigger than the last bucket goes
    into the synthetic ``+inf`` bucket.
    """

    if buckets is None:
        bs = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000]
    else:
        bs = sorted(float(b) for b in buckets if b > 0)
    samples = recent(op, window_s=window_s)
    counts = [0] * (len(bs) + 1)
    for ms in samples:
        placed = False
        for i, edge in enumerate(bs):
            if ms <= edge:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    labels = [f"<={int(e)}ms" for e in bs] + ["+inf"]
    return {
        "op": op,
        "window_s": window_s,
        "total": len(samples),
        "buckets": [{"label": labels[i], "count": counts[i]} for i in range(len(counts))],
    }


__all__ = [
    "LATENCY_BUFFER_SIZE",
    "record",
    "recent",
    "reset",
    "known_ops",
    "percentile",
    "summary",
    "histogram",
]
