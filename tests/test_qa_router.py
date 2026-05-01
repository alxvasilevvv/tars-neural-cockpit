"""Tests for the /api/qa router (qa-suite reports surface).

These tests exercise the FastAPI endpoints in isolation by:
- pointing ``QA_REPORT_PATH`` at a tmp_path file,
- spinning up the app via the FastAPI ``TestClient``,
- asserting the absent / present / failing scenarios.

The endpoints stay a no-op when no report file exists, so we can
deploy them without depending on the qa-suite ever running.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web_extras.app import app


@pytest.fixture
def client_with_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    report_path = tmp_path / "qa-report.json"
    monkeypatch.setenv("QA_REPORT_PATH", str(report_path))
    return TestClient(app), report_path


def _sample_report(*, fail_count: int = 0) -> dict:
    probes = [
        {
            "name": "route./",
            "category": "navigation",
            "status": "pass",
            "details": "OK",
            "ts": "2026-05-01T18:00:00Z",
        },
        {
            "name": "i18n.default-en./",
            "category": "i18n",
            "status": "pass",
            "details": "cyrillic=0",
            "ts": "2026-05-01T18:00:01Z",
        },
    ]
    for i in range(fail_count):
        probes.append(
            {
                "name": f"failing.probe.{i}",
                "category": "functional",
                "status": "fail",
                "details": f"synthetic failure {i}",
                "ts": "2026-05-01T18:00:02Z",
            }
        )
    return {
        "version": "qa-report/1.0.0",
        "started_at": "2026-05-01T18:00:00Z",
        "finished_at": "2026-05-01T18:01:30Z",
        "trace_id": "qa-test-1234",
        "base_url": "http://127.0.0.1:4173",
        "probes": probes,
    }


def test_health_returns_absent_when_no_report(client_with_report: tuple[TestClient, Path]) -> None:
    client, _ = client_with_report
    resp = client.get("/api/qa/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "absent"
    assert body["summary"] == {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    assert body["failing_probes"] == []
    assert "trace_id" in body


def test_health_returns_pass_for_clean_report(client_with_report: tuple[TestClient, Path]) -> None:
    client, report_path = client_with_report
    report_path.write_text(json.dumps(_sample_report()), encoding="utf-8")

    resp = client.get("/api/qa/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pass"
    assert body["summary"]["pass"] == 2
    assert body["summary"]["fail"] == 0
    assert body["base_url"] == "http://127.0.0.1:4173"
    assert body["report_trace"] == "qa-test-1234"
    assert body["failing_probes"] == []


def test_health_returns_fail_when_probes_failed(client_with_report: tuple[TestClient, Path]) -> None:
    client, report_path = client_with_report
    report_path.write_text(json.dumps(_sample_report(fail_count=2)), encoding="utf-8")

    resp = client.get("/api/qa/health")
    body = resp.json()
    assert body["status"] == "fail"
    assert body["summary"]["fail"] == 2
    assert len(body["failing_probes"]) == 2
    assert body["failing_probes"][0]["category"] == "functional"


def test_report_endpoint_paginates(client_with_report: tuple[TestClient, Path]) -> None:
    client, report_path = client_with_report
    report_path.write_text(json.dumps(_sample_report(fail_count=3)), encoding="utf-8")

    resp = client.get("/api/qa/report", params={"limit": 2, "offset": 1})
    body = resp.json()
    assert body["total_probes"] == 5
    assert body["page"]["count"] == 2
    assert body["page"]["limit"] == 2
    assert body["page"]["offset"] == 1


def test_post_report_writes_file(client_with_report: tuple[TestClient, Path]) -> None:
    client, report_path = client_with_report
    payload = _sample_report(fail_count=1)
    resp = client.post("/api/qa/report", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["report_trace"] == "qa-test-1234"
    assert body["summary"]["fail"] == 1
    assert report_path.is_file()
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["trace_id"] == "qa-test-1234"


def test_post_report_rejects_bad_version(client_with_report: tuple[TestClient, Path]) -> None:
    client, _ = client_with_report
    resp = client.post("/api/qa/report", json={"version": "not-qa-report", "probes": []})
    assert resp.status_code == 400
    assert "qa-report/" in resp.text


def test_post_report_requires_token_when_set(
    client_with_report: tuple[TestClient, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = client_with_report
    monkeypatch.setenv("QA_INGEST_TOKEN", "secret-1")

    payload = _sample_report()
    resp = client.post("/api/qa/report", json=payload)
    assert resp.status_code == 401

    resp = client.post(
        "/api/qa/report",
        json=payload,
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 403

    resp = client.post(
        "/api/qa/report",
        json=payload,
        headers={"Authorization": "Bearer secret-1"},
    )
    assert resp.status_code == 200
