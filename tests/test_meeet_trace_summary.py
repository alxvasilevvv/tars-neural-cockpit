"""Materialised ``trace_summary`` view + HTTP surface.

The events table is the source of truth; the rollup is recomputed on
demand (and from the lifespan loop every ``TARS_TRACE_SUMMARY_INTERVAL_S``
seconds in production). These tests pin both the rollup math and the
read-side endpoints.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from backend.core.meeet import (
    MeeetStore,
    TraceSummaryStore,
    reset_client,
    reset_store,
    reset_trace_summary_store,
)


def _seed_store(store: MeeetStore, events: list[dict]) -> None:
    """Insert a fixed list of events so we can assert deterministic rollups."""

    async def run() -> None:
        for ev in events:
            await store.insert(ev)

    asyncio.run(run())


def _ts(offset: float) -> float:
    return 1_700_000_000.0 + offset


@pytest.fixture()
def isolated_meeet(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.delenv("MEEET_INGEST_URL", raising=False)
    monkeypatch.delenv("MEEET_LOCAL_LOG", raising=False)
    reset_store()
    reset_client()
    reset_trace_summary_store()
    try:
        yield
    finally:
        reset_store()
        reset_client()
        reset_trace_summary_store()


def _store(tmp_path) -> MeeetStore:
    return MeeetStore(str(tmp_path / "isolated.sqlite"))


def test_rebuild_returns_zero_when_empty(tmp_path) -> None:
    store = _store(tmp_path)
    summary_store = TraceSummaryStore(events_store=store)
    out = asyncio.run(summary_store.rebuild())
    assert out["ok"] is True
    assert out["scanned_events"] == 0
    assert out["traces"] == 0


def test_rebuild_aggregates_events_per_trace(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": "trc_A",
                "kind": "domain.action.invoked",
                "payload": {},
                "session_id": "ses_morning",
                "route": "edge",
            },
            {
                "ts": _ts(2),
                "trace_id": "trc_A",
                "kind": "usage.tokens",
                "payload": {
                    "tokens_in": 100,
                    "tokens_out": 50,
                    "cost_usd": 0.0021,
                },
                "session_id": "ses_morning",
                "route": "cloud",
            },
            {
                "ts": _ts(4),
                "trace_id": "trc_A",
                "kind": "sampler.decision",
                "payload": {"contradictions": 2},
                "session_id": "ses_morning",
                "route": "cloud",
            },
            {
                "ts": _ts(0),
                "trace_id": "trc_B",
                "kind": "domain.action.invoked",
                "payload": {},
                "route": "edge",
            },
        ],
    )

    summary_store = TraceSummaryStore(events_store=store)
    out = asyncio.run(summary_store.rebuild())
    assert out["scanned_events"] == 4
    assert out["traces"] == 2

    a = asyncio.run(summary_store.get("trc_A"))
    assert a is not None
    assert a.event_count == 3
    assert a.kinds == [
        "domain.action.invoked",
        "sampler.decision",
        "usage.tokens",
    ]
    assert a.routes == ["cloud", "edge"]
    assert a.primary_route == "mixed"
    assert a.tokens_in == 100
    assert a.tokens_out == 50
    assert a.total_cost_usd == pytest.approx(0.0021, rel=1e-6)
    assert a.contradictions == 2
    assert a.last_session_id == "ses_morning"
    assert a.started_at == _ts(0)
    assert a.ended_at == _ts(4)
    assert a.duration_ms == 4000

    b = asyncio.run(summary_store.get("trc_B"))
    assert b is not None
    assert b.event_count == 1
    assert b.routes == ["edge"]
    assert b.primary_route == "edge"
    assert b.duration_ms == 0


def test_rebuild_is_idempotent(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": "trc_idem",
                "kind": "x.evt",
                "payload": {},
                "route": "edge",
            }
        ],
    )
    summary_store = TraceSummaryStore(events_store=store)
    a = asyncio.run(summary_store.rebuild())
    b = asyncio.run(summary_store.rebuild())
    assert a["traces"] == 1
    assert b["traces"] == 1
    summaries = asyncio.run(summary_store.list_summaries())
    assert len(summaries) == 1


def test_rebuild_skips_events_without_trace_id(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": None,
                "kind": "rogue.evt",
                "payload": {},
            },
            {
                "ts": _ts(0),
                "trace_id": "trc_keep",
                "kind": "kept.evt",
                "payload": {},
            },
        ],
    )
    summary_store = TraceSummaryStore(events_store=store)
    out = asyncio.run(summary_store.rebuild())
    assert out["traces"] == 1
    summaries = asyncio.run(summary_store.list_summaries())
    assert [s.trace_id for s in summaries] == ["trc_keep"]


def test_classify_route_picks_fallback_over_mixed(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": "trc_fb",
                "kind": "x",
                "payload": {},
                "route": "edge",
            },
            {
                "ts": _ts(1),
                "trace_id": "trc_fb",
                "kind": "x",
                "payload": {},
                "route": "fallback",
            },
        ],
    )
    summary_store = TraceSummaryStore(events_store=store)
    asyncio.run(summary_store.rebuild())
    s = asyncio.run(summary_store.get("trc_fb"))
    assert s is not None
    assert s.primary_route == "fallback"
    assert sorted(s.routes) == ["edge", "fallback"]


def test_error_count_picks_up_failed_kinds(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": "trc_err",
                "kind": "domain.action.invoked",
                "payload": {},
            },
            {
                "ts": _ts(1),
                "trace_id": "trc_err",
                "kind": "domain.action.failed",
                "payload": {"reason": "bad"},
            },
        ],
    )
    summary_store = TraceSummaryStore(events_store=store)
    asyncio.run(summary_store.rebuild())
    s = asyncio.run(summary_store.get("trc_err"))
    assert s is not None
    assert s.error_count == 1


def test_list_summaries_filters_and_orders(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": "trc_old",
                "kind": "x",
                "payload": {},
                "route": "edge",
                "session_id": "ses_night",
            },
            {
                "ts": _ts(120),
                "trace_id": "trc_new",
                "kind": "x",
                "payload": {},
                "route": "cloud",
                "session_id": "ses_morning",
            },
            {
                "ts": _ts(60),
                "trace_id": "trc_mid",
                "kind": "x",
                "payload": {},
                "route": "edge",
                "session_id": "ses_morning",
            },
        ],
    )
    summary_store = TraceSummaryStore(events_store=store)
    asyncio.run(summary_store.rebuild())

    rows = asyncio.run(summary_store.list_summaries(limit=10))
    assert [r.trace_id for r in rows] == ["trc_new", "trc_mid", "trc_old"]

    rows_route = asyncio.run(
        summary_store.list_summaries(primary_route="edge")
    )
    assert {r.trace_id for r in rows_route} == {"trc_old", "trc_mid"}

    rows_session = asyncio.run(
        summary_store.list_summaries(session_id="ses_morning")
    )
    assert {r.trace_id for r in rows_session} == {"trc_new", "trc_mid"}

    rows_since = asyncio.run(summary_store.list_summaries(since=_ts(100)))
    assert [r.trace_id for r in rows_since] == ["trc_new"]


def test_to_dict_roundtrips_clean(tmp_path) -> None:
    store = _store(tmp_path)
    _seed_store(
        store,
        [
            {
                "ts": _ts(0),
                "trace_id": "trc_dict",
                "kind": "usage.tokens",
                "payload": {
                    "tokens_in": 10,
                    "tokens_out": 5,
                    "cost_usd": 0.0001,
                },
                "route": "cloud",
            }
        ],
    )
    summary_store = TraceSummaryStore(events_store=store)
    asyncio.run(summary_store.rebuild())
    s = asyncio.run(summary_store.get("trc_dict"))
    assert s is not None
    body = s.to_dict()
    assert body["trace_id"] == "trc_dict"
    assert body["primary_route"] == "cloud"
    assert body["total_cost_usd"] == pytest.approx(0.0001, rel=1e-6)
    assert body["kinds"] == ["usage.tokens"]
    assert isinstance(body["updated_at"], float)


def test_disabled_store_short_circuits(tmp_path) -> None:
    disabled = MeeetStore(str(tmp_path / "noop.sqlite"), enabled=False)
    summary_store = TraceSummaryStore(events_store=disabled)
    out = asyncio.run(summary_store.rebuild())
    assert out == {"ok": False, "reason": "store_disabled"}
    assert asyncio.run(summary_store.list_summaries()) == []
    assert asyncio.run(summary_store.get("anything")) is None


# ---------------------------------------------------------------------- HTTP


@pytest.fixture()
def http_app(isolated_meeet):
    from web_extras.app import app

    with TestClient(app) as client:
        yield client


def test_traces_endpoint_returns_rollup(http_app: TestClient) -> None:
    from backend.core.meeet import get_store, get_trace_summary_store

    store = get_store()
    asyncio.run(
        store.insert(
            {
                "ts": _ts(0),
                "trace_id": "trc_http",
                "kind": "domain.action.invoked",
                "payload": {},
                "route": "edge",
                "session_id": "ses_z",
            }
        )
    )
    asyncio.run(get_trace_summary_store().rebuild())

    resp = http_app.get("/api/meeet/traces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert body["traces"][0]["trace_id"] == "trc_http"
    assert body["traces"][0]["primary_route"] == "edge"

    detail = http_app.get("/api/meeet/traces/trc_http")
    assert detail.status_code == 200
    assert detail.json()["trace"]["trace_id"] == "trc_http"

    missing = http_app.get("/api/meeet/traces/trc_does_not_exist")
    assert missing.status_code == 404


def test_traces_refresh_endpoint_runs_rebuild(http_app: TestClient) -> None:
    from backend.core.meeet import get_store

    store = get_store()
    asyncio.run(
        store.insert(
            {
                "ts": _ts(0),
                "trace_id": "trc_refresh",
                "kind": "x.evt",
                "payload": {},
                "route": "edge",
            }
        )
    )
    resp = http_app.post("/api/meeet/traces/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["traces"] >= 1
    assert body["scanned_events"] >= 1


def test_traces_endpoint_filters(http_app: TestClient) -> None:
    from backend.core.meeet import get_store, get_trace_summary_store

    store = get_store()
    asyncio.run(
        store.insert(
            {
                "ts": _ts(0),
                "trace_id": "trc_e",
                "kind": "x",
                "payload": {},
                "route": "edge",
                "session_id": "ses_a",
            }
        )
    )
    asyncio.run(
        store.insert(
            {
                "ts": _ts(1),
                "trace_id": "trc_c",
                "kind": "x",
                "payload": {},
                "route": "cloud",
                "session_id": "ses_b",
            }
        )
    )
    asyncio.run(get_trace_summary_store().rebuild())

    resp = http_app.get("/api/meeet/traces", params={"primary_route": "cloud"})
    assert resp.status_code == 200
    rows = resp.json()["traces"]
    assert {r["trace_id"] for r in rows} == {"trc_c"}

    resp_session = http_app.get(
        "/api/meeet/traces", params={"session_id": "ses_a"}
    )
    rows_s = resp_session.json()["traces"]
    assert {r["trace_id"] for r in rows_s} == {"trc_e"}
