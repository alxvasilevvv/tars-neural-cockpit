"""Tests for the ``business.hubspot_pull_pipeline`` adapter.

Covers argument validation, vault-key resolution, HTTP error
handling, payload parsing, derived rollups (active / won / lost
counts, pipeline_amount), client-side pipeline filtering, paging
cursors, action wiring, and the
``integration.hubspot.deals_list`` meeet event emission.

The HTTP boundary is mocked so the suite is hermetic and never
touches the real HubSpot API.
"""

from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _sample_deal(
    deal_id: str,
    *,
    name: str,
    amount: str | None = "1000",
    stage: str = "qualifiedtobuy",
    pipeline: str | None = "default",
    close_date: str | None = "2026-12-31",
    created_at: str | None = "2026-01-01T00:00:00Z",
    updated_at: str | None = "2026-04-30T00:00:00Z",
) -> dict[str, Any]:
    """Build a HubSpot-shaped deal row."""

    props: dict[str, Any] = {
        "dealname": name,
        "dealstage": stage,
    }
    if amount is not None:
        props["amount"] = amount
    if pipeline is not None:
        props["pipeline"] = pipeline
    if close_date is not None:
        props["closedate"] = close_date
    return {
        "id": deal_id,
        "properties": props,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def _sample_ok_payload(*, with_cursor: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "results": [
            _sample_deal("1001", name="Acme Corp", amount="50000"),
            _sample_deal(
                "1002",
                name="Globex",
                amount="15000",
                stage="contractsent",
            ),
            _sample_deal(
                "1003",
                name="Initech",
                amount="9000",
                stage="closedwon",
            ),
            _sample_deal(
                "1004",
                name="Hooli",
                amount="3000",
                stage="closedlost",
            ),
        ],
    }
    if with_cursor:
        body["paging"] = {"next": {"after": "next-page-token-xyz"}}
    return body


@pytest.fixture
def patched_http(monkeypatch):
    """Replace ``hubspot.get_json`` with a controllable stub."""

    state: dict[str, Any] = {
        "calls": [],
        "status": 200,
        "payload": _sample_ok_payload(),
        "raise": None,
    }

    async def fake_get_json(url, *, params=None, headers=None, timeout=None):
        state["calls"].append(
            {
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
            }
        )
        if state["raise"]:
            raise state["raise"]
        return state["status"], state["payload"]

    from backend.core.domains.packs.business import hubspot as hubspot_mod

    monkeypatch.setattr(hubspot_mod, "get_json", fake_get_json)
    return state


@pytest.fixture(autouse=True)
def _isolated_meeet_store(tmp_path, monkeypatch):
    """Isolate the meeet store so emitted events don't accumulate
    across the rest of the suite.
    """

    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    monkeypatch.setenv("MEEET_INGEST_URL", "")
    import backend.core.meeet.client as client_mod
    import backend.core.meeet.store as store_mod

    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]
    yield
    client_mod._SINGLETON = None  # type: ignore[attr-defined]
    store_mod._SINGLETON = None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------
# Unit: parsers / helpers
# ---------------------------------------------------------------------


def test_parse_amount_handles_strings_floats_and_blanks():
    from backend.core.domains.packs.business.hubspot import _parse_amount

    assert _parse_amount("12345.67") == pytest.approx(12345.67)
    assert _parse_amount(42) == 42.0
    assert _parse_amount(None) is None
    assert _parse_amount("") is None
    assert _parse_amount("not-a-number") is None


def test_stage_label_returns_human_label_or_raw_id():
    from backend.core.domains.packs.business.hubspot import _stage_label_for

    assert _stage_label_for("closedwon") == "Closed won"
    assert _stage_label_for("contractsent") == "Contract sent"
    assert _stage_label_for("custom_stage_x") == "custom_stage_x"
    assert _stage_label_for("") == ""


def test_normalise_properties_accepts_list_string_and_blank():
    from backend.core.domains.packs.business.hubspot import (
        DEFAULT_PROPERTIES,
        _normalise_properties,
    )

    assert _normalise_properties(["dealname", "amount"]) == ("dealname", "amount")
    assert _normalise_properties("dealname,amount,closedate") == (
        "dealname",
        "amount",
        "closedate",
    )
    assert _normalise_properties(None) == DEFAULT_PROPERTIES
    assert _normalise_properties("") == DEFAULT_PROPERTIES
    assert _normalise_properties([]) == DEFAULT_PROPERTIES
    assert _normalise_properties(123) == DEFAULT_PROPERTIES


def test_parse_deal_row_handles_missing_optional_props():
    from backend.core.domains.packs.business.hubspot import _parse_deal_row

    row = {"id": "9999", "properties": {}}
    parsed = _parse_deal_row(row)
    assert parsed is not None
    assert parsed.id == "9999"
    assert parsed.name == "(unnamed)"
    assert parsed.amount is None
    assert parsed.stage_id == ""
    assert parsed.stage_label == ""


def test_parse_deal_row_returns_none_for_missing_id_or_bad_shape():
    from backend.core.domains.packs.business.hubspot import _parse_deal_row

    assert _parse_deal_row(None) is None
    assert _parse_deal_row("not a dict") is None
    assert _parse_deal_row({"properties": {"dealname": "no id"}}) is None


def test_next_cursor_extracts_after_value():
    from backend.core.domains.packs.business.hubspot import _next_cursor_from

    assert _next_cursor_from({"paging": {"next": {"after": "abc"}}}) == "abc"
    assert _next_cursor_from({}) is None
    assert _next_cursor_from({"paging": {}}) is None
    assert _next_cursor_from({"paging": {"next": {}}}) is None


# ---------------------------------------------------------------------
# Unit: validation paths
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_limit_string_returns_error():
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"limit": "many", "api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "invalid_limit"


@pytest.mark.asyncio
async def test_invalid_limit_too_high_returns_error():
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"limit": 999, "api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "invalid_limit"
    assert "1..100" in res["detail"]


@pytest.mark.asyncio
async def test_invalid_limit_zero_returns_error():
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"limit": 0, "api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "invalid_limit"


@pytest.mark.asyncio
async def test_missing_api_key_returns_auth_missing(monkeypatch):
    from backend.core.domains.packs.business import hubspot as hubspot_mod

    monkeypatch.setattr(hubspot_mod, "get_secret", lambda _key: None)
    res = await hubspot_mod.pull_pipeline({})
    assert res["ok"] is False
    assert res["error"] == "auth_missing"
    assert "HUBSPOT_API_KEY" in res["detail"]


@pytest.mark.asyncio
async def test_api_key_from_args_overrides_vault(monkeypatch, patched_http):
    from backend.core.domains.packs.business import hubspot as hubspot_mod

    monkeypatch.setattr(hubspot_mod, "get_secret", lambda _key: None)
    res = await hubspot_mod.pull_pipeline({"api_key": "explicit-tok"})
    assert res["ok"] is True
    auth = patched_http["calls"][0]["headers"].get("Authorization")
    assert auth == "Bearer explicit-tok"


# ---------------------------------------------------------------------
# Unit: HTTP path / payload parsing
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_limit_is_25_and_url_is_correct(patched_http):
    from backend.core.domains.packs.business.hubspot import (
        DEALS_URL,
        pull_pipeline,
    )

    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is True
    assert patched_http["calls"][0]["url"] == DEALS_URL
    assert patched_http["calls"][0]["params"]["limit"] == 25
    assert patched_http["calls"][0]["params"]["archived"] == "false"


@pytest.mark.asyncio
async def test_custom_limit_passes_through(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    await pull_pipeline({"api_key": "tok", "limit": 7})
    assert patched_http["calls"][0]["params"]["limit"] == 7


@pytest.mark.asyncio
async def test_after_cursor_threads_into_request(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    await pull_pipeline({"api_key": "tok", "after": "page-2"})
    assert patched_http["calls"][0]["params"]["after"] == "page-2"


@pytest.mark.asyncio
async def test_after_cursor_omitted_when_blank(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    await pull_pipeline({"api_key": "tok", "after": "  "})
    assert "after" not in patched_http["calls"][0]["params"]


@pytest.mark.asyncio
async def test_properties_arg_serialised_as_csv(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    await pull_pipeline(
        {"api_key": "tok", "properties": ["dealname", "amount"]}
    )
    sent = patched_http["calls"][0]["params"]["properties"]
    assert sent == "dealname,amount"


@pytest.mark.asyncio
async def test_default_properties_used_when_none_passed(patched_http):
    from backend.core.domains.packs.business.hubspot import (
        DEFAULT_PROPERTIES,
        pull_pipeline,
    )

    await pull_pipeline({"api_key": "tok"})
    sent = patched_http["calls"][0]["params"]["properties"]
    assert sent == ",".join(DEFAULT_PROPERTIES)


@pytest.mark.asyncio
async def test_authorization_header_uses_bearer_token(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    await pull_pipeline({"api_key": "secret-token"})
    assert (
        patched_http["calls"][0]["headers"]["Authorization"]
        == "Bearer secret-token"
    )


@pytest.mark.asyncio
async def test_happy_path_normalises_deals_with_derived_rollups(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"api_key": "tok"})

    assert res["ok"] is True
    assert res["count"] == 4
    assert {d["id"] for d in res["deals"]} == {"1001", "1002", "1003", "1004"}
    # 1001 (qualifiedtobuy) + 1002 (contractsent) are active.
    assert res["active_count"] == 2
    assert res["won_count"] == 1
    assert res["lost_count"] == 1
    # 50000 + 15000 = 65000
    assert res["pipeline_amount"] == pytest.approx(65000.0)
    # Each row carries normalised fields.
    by_id = {d["id"]: d for d in res["deals"]}
    assert by_id["1001"]["name"] == "Acme Corp"
    assert by_id["1001"]["stage_label"] == "Qualified to buy"
    assert by_id["1003"]["stage_label"] == "Closed won"


@pytest.mark.asyncio
async def test_next_cursor_propagated(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["payload"] = _sample_ok_payload(with_cursor=True)
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is True
    assert res["next_cursor"] == "next-page-token-xyz"


@pytest.mark.asyncio
async def test_no_next_cursor_when_paging_absent(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"api_key": "tok"})
    assert res["next_cursor"] is None


@pytest.mark.asyncio
async def test_pipeline_filter_drops_unrelated_deals(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["payload"] = {
        "results": [
            _sample_deal("1", name="A", pipeline="default"),
            _sample_deal("2", name="B", pipeline="enterprise"),
            _sample_deal("3", name="C", pipeline="default"),
        ]
    }
    res = await pull_pipeline({"api_key": "tok", "pipeline": "default"})
    assert res["ok"] is True
    assert {d["id"] for d in res["deals"]} == {"1", "3"}


@pytest.mark.asyncio
async def test_pipeline_filter_blank_treated_as_unset(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"api_key": "tok", "pipeline": "  "})
    assert res["ok"] is True
    assert res["count"] == 4


@pytest.mark.asyncio
async def test_include_raw_attaches_original_row(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"api_key": "tok", "include_raw": True})
    assert res["deals"][0]["raw"]["properties"]["dealname"] == "Acme Corp"


@pytest.mark.asyncio
async def test_include_raw_default_false_omits_raw(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    res = await pull_pipeline({"api_key": "tok"})
    assert "raw" not in res["deals"][0]


# ---------------------------------------------------------------------
# Unit: error paths
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_error_returned_structurally(patched_http):
    from backend.core.domains._http import NetworkError
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["raise"] = NetworkError("dns failure")
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "network_error"
    assert "dns failure" in res["detail"]


@pytest.mark.asyncio
async def test_401_returned_as_auth_invalid(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["status"] = 401
    patched_http["payload"] = {"message": "expired token"}
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "auth_invalid"
    assert res["status"] == 401


@pytest.mark.asyncio
async def test_500_returned_as_upstream_status_with_detail(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["status"] = 502
    patched_http["payload"] = {"message": "bad gateway"}
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "upstream_status"
    assert res["status"] == 502
    assert res["detail"] == "bad gateway"


@pytest.mark.asyncio
async def test_non_object_payload_rejected(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["payload"] = ["unexpected", "list"]
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is False
    assert res["error"] == "upstream_payload_invalid"


@pytest.mark.asyncio
async def test_empty_results_returns_ok_with_zero_count(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["payload"] = {"results": []}
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is True
    assert res["count"] == 0
    assert "active_count" not in res  # rollups only emitted when deals present


@pytest.mark.asyncio
async def test_malformed_results_skipped(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline

    patched_http["payload"] = {
        "results": [
            "garbage",
            {"properties": {"dealname": "no id"}},
            _sample_deal("1001", name="Valid"),
        ]
    }
    res = await pull_pipeline({"api_key": "tok"})
    assert res["ok"] is True
    assert res["count"] == 1
    assert res["deals"][0]["id"] == "1001"


# ---------------------------------------------------------------------
# Action wiring
# ---------------------------------------------------------------------


def test_action_registered_in_business_pack():
    from backend.core.domains.registry import get_pack

    pack = get_pack("business")
    assert pack is not None
    actions = {a.id for a in pack.actions()}
    assert "hubspot_pull_pipeline" in actions


def test_action_is_not_destructive():
    from backend.core.domains.registry import get_pack

    pack = get_pack("business")
    spec = next(a for a in pack.actions() if a.id == "hubspot_pull_pipeline")
    assert spec.destructive is False


# ---------------------------------------------------------------------
# Meeet event emission
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_and_completed_events_emitted(patched_http):
    from backend.core.domains.packs.business.hubspot import pull_pipeline
    from backend.core.meeet.store import get_store

    await pull_pipeline({"api_key": "tok", "limit": 5})

    events = await get_store().list_events(limit=200)
    kinds = [e.kind for e in events]
    phases = [
        e.payload.get("phase")
        for e in events
        if e.kind == "integration.hubspot.deals_list"
    ]
    assert "integration.hubspot.deals_list" in kinds
    assert "request" in phases
    assert "completed" in phases


@pytest.mark.asyncio
async def test_error_event_emitted_on_network_failure(patched_http):
    from backend.core.domains._http import NetworkError
    from backend.core.domains.packs.business.hubspot import pull_pipeline
    from backend.core.meeet.store import get_store

    patched_http["raise"] = NetworkError("offline")
    await pull_pipeline({"api_key": "tok"})

    events = await get_store().list_events(limit=200)
    error_events = [
        e
        for e in events
        if e.kind == "integration.hubspot.deals_list"
        and e.payload.get("phase") == "error"
        and e.payload.get("error") == "network_error"
    ]
    assert error_events, "expected one error event"
