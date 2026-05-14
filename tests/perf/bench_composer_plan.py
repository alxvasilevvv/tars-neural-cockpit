"""W266 — perf bench: 20 concurrent Composer plan generations.

**SLO:** p95 < 4s.

``plan_from_transcript`` is the entry point for the voice-driven
Composer (W253). With ``allow_llm=False`` it runs the deterministic
stub planner, which is what every cockpit user without cloud creds
hits — the SLO target is for that path.

20 concurrent runs models the worst realistic case: an operator
voice-batches a refactor across 20 files. Anything slower than 4s p95
means the cockpit can't keep up with a real voice session.
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.perf._perf_utils import isolate_tars_home, record_result

CONCURRENCY = int(os.getenv("TARS_PERF_COMPOSER_N", "20"))
SLO_MS = 4000.0


@pytest.mark.perf
def test_composer_plan_20_concurrent_p95_under_slo(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """20 concurrent composer plan generations → assert p95 < 4s."""

    isolate_tars_home(monkeypatch, tmp_path)

    # Project fixture — small repo, but enough files that the planner
    # has to scan a non-trivial set. Mirrors test_composer.py shape.
    project = tmp_path / "project"
    project.mkdir()
    (project / "models.py").write_text(
        "class Customer:\n    name: str\n    def greet(self):\n"
        "        return 'Hi ' + self.name\n",
        encoding="utf-8",
    )
    (project / "views.py").write_text(
        "from models import Customer\n\n"
        "def list_customers():\n    return [Customer()]\n",
        encoding="utf-8",
    )
    (project / "readme.md").write_text(
        "# App\n\nCustomer model docs.\n", encoding="utf-8"
    )
    (project / "utils.py").write_text(
        "def normalize_customer(c): return c\n", encoding="utf-8"
    )

    from backend.core.composer import plan_from_transcript, reset_store

    reset_store()

    transcripts = [
        "rename Customer to Account",
        "add type hints to greet",
        "extract list_customers to its own module",
        "fix import in views.py",
    ]

    def one_plan(i: int) -> float:
        transcript = transcripts[i % len(transcripts)]
        t0 = time.perf_counter()
        plan = plan_from_transcript(transcript, project, allow_llm=False)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert plan is not None
        assert plan.plan_id.startswith("cmp_"), f"unexpected plan: {plan!r}"
        return elapsed_ms

    with ThreadPoolExecutor(max_workers=min(CONCURRENCY, 8)) as pool:
        samples = list(pool.map(one_plan, range(CONCURRENCY)))

    row = record_result(
        name="bench_composer_plan",
        samples_ms=samples,
        slo_ms=SLO_MS,
        extra={
            "concurrency": CONCURRENCY,
            "path": "composer.plan_from_transcript()",
            "description": "20 concurrent composer plan generations (stub planner)",
        },
    )
    assert row["passed"], (
        f"REGRESSION: composer_plan p95={row['p95_ms']}ms exceeds SLO "
        f"{SLO_MS}ms; suggested fix: cache the project scan inside "
        f"backend/core/composer/planner.py — the file-walk is the "
        f"hottest thing in the stub planner today."
    )
