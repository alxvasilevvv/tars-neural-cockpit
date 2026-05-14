"""W266 — perf bench: ``/api/audit/timeline`` against 10k receipts.

**SLO:** p95 < 200ms for a 10k-receipt ledger.

The receipt store query is hash-chained SQLite + day-Merkle root
lookups. As the ledger grows the audit explorer UI fans out a
timeline request whenever the user changes a filter — the regression
risk is that a missing index or an N+1 day-root lookup ships and
shows up as a 2s spinner in the cockpit's Audit tab.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from tests.perf._perf_utils import isolate_tars_home, record_result

SEED_COUNT = int(os.getenv("TARS_PERF_AUDIT_SEED", "10000"))
QUERY_RUNS = int(os.getenv("TARS_PERF_AUDIT_RUNS", "100"))
SLO_MS = 200.0


@pytest.mark.perf
def test_audit_timeline_10k_receipts_p95_under_slo(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seed 10k receipts → fire 100 /api/audit/timeline queries → assert p95 < 200ms."""

    isolate_tars_home(monkeypatch, tmp_path)

    import backend.core.receipts.store as rs_mod
    from backend.core.receipts.store import ReceiptStore

    monkeypatch.setenv("TARS_RECEIPT_STORE", "enabled")
    monkeypatch.setattr(rs_mod, "_STORE", None, raising=False)

    store = ReceiptStore()
    monkeypatch.setattr(rs_mod, "_STORE", store, raising=False)

    # ── seed 10k receipts ───────────────────────────────────────
    async def seed() -> None:
        # Spread receipts over 14 days so day-Merkle root lookups
        # have to hit multiple cache slots.
        now = time.time()
        kinds = ["composer.apply", "voice.command", "agent.run", "chat.message"]
        for i in range(SEED_COUNT):
            ts = now - (i % 14) * 86400 - (i % 3600)
            await store.append(
                type=kinds[i % len(kinds)],
                actor=f"user_{i % 50}",
                resource=f"file_{i % 200}.py",
                payload={"index": i, "summary": f"row {i}"},
                ts=ts,
            )

    asyncio.run(seed())

    # ── HTTP layer (TestClient) ─────────────────────────────────
    from fastapi.testclient import TestClient
    from web_extras.app import app

    client = TestClient(app)

    # Mix of filters: type-only, q-text, only_anchored, plain.
    queries = [
        "/api/audit/timeline?limit=100",
        "/api/audit/timeline?kind=composer.apply&limit=100",
        "/api/audit/timeline?q=row&limit=100",
        "/api/audit/timeline?only_anchored=false&limit=100",
        "/api/audit/timeline?kind=voice.command&q=42&limit=50",
    ]

    samples: list[float] = []
    for i in range(QUERY_RUNS):
        url = queries[i % len(queries)]
        t0 = time.perf_counter()
        res = client.get(url)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # 503 happens only if receipts module is disabled — perf bench
        # treats it as a wiring bug, not a soft skip.
        assert res.status_code == 200, (
            f"audit timeline {url} returned {res.status_code}: {res.text[:200]}"
        )
        samples.append(elapsed_ms)

    row = record_result(
        name="bench_audit_timeline",
        samples_ms=samples,
        slo_ms=SLO_MS,
        extra={
            "seed_count": SEED_COUNT,
            "query_runs": QUERY_RUNS,
            "path": "/api/audit/timeline",
            "description": "Audit timeline query against 10k seeded receipts",
        },
    )
    assert row["passed"], (
        f"REGRESSION: audit/timeline p95={row['p95_ms']}ms exceeds SLO "
        f"{SLO_MS}ms on a {SEED_COUNT}-receipt ledger; suggested fix: "
        f"add a (ts DESC, type) covering index in "
        f"backend/core/receipts/store.py and cache the day-Merkle-root "
        f"lookup per request — see _summarise hot loop in audit.py."
    )
