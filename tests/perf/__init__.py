"""W266 — TARS performance benchmarks.

These tests are **not** part of the default ``pytest`` lane; they are
opt-in load tests run via ``scripts/RUN-PERF-SUITE.command`` (or
``pytest tests/perf/ -m perf``). Each module asserts a service-level
objective (SLO) for one of the five hottest TARS paths:

==========  ==========================================  ======================
Module                                                  SLO
==========  ==========================================  ======================
``bench_chat``              100 concurrent chat requests p95 latency  < 2.5s
``bench_voice_command``     50 concurrent /api/voice/command          < 800ms
``bench_usage_metering``    1000 usage_event writes/sec  no drops
``bench_audit_timeline``    /api/audit/timeline w/ 10k receipts      < 200ms
``bench_composer_plan``     20 concurrent composer plan generations  < 4s
==========  ==========================================  ======================

Implementation notes:

* All five files prefer ``pytest-benchmark`` if installed. When the
  plugin is missing (which is the case in the slimmest CI lane) the
  benchmark falls back to a plain ``asyncio.gather()`` loop driven by
  ``time.perf_counter()`` — the runner script reads the same JSON
  shape either way.
* Each benchmark writes ``{"name", "samples", "p50_ms", "p95_ms",
  "p99_ms", "slo_ms", "passed"}`` to
  ``tests/perf/.results/<name>.json`` so the RUN-PERF-SUITE script
  can render a single report without re-running anything.
* Hermetic by design: the FastAPI ``TestClient`` is created in-process,
  no network, no external services touched. The usage-metering bench
  writes to a temp SQLite; the audit-timeline bench seeds 10k receipts
  into a temp ledger before measurement.
"""
