"""Tests for the local-first ``business.log_deal`` adapter.

Covers two layers:

- ``backend.core.domains.packs.business.local_deals`` — pure JSON
  store helpers (path resolution, monotonic ids, atomic write,
  defensive coercion of stage/amount).
- ``business.log_deal`` action — exercises the fallback path when
  no CRM credentials are configured, plus the meeet-event side
  effect.

Real CRM round-trip (HubSpot / Pipedrive) is already covered in
``test_batch2_adapters.py``; the new behaviour kicks in only on
the local fallback so we focus there.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.packs.business import actions as business_actions
from backend.core.domains.packs.business import local_deals as ld


# ---------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------


def test_resolve_path_default(monkeypatch):
    monkeypatch.delenv(ld.LOCAL_DEALS_ENV_VAR, raising=False)
    p = ld.resolve_local_deals_path()
    # Default lives under the operator home, not the repo.
    assert str(p).endswith("/.tars/business_deals.json")
    # Should be absolute (expanduser hit).
    assert p.is_absolute()


def test_resolve_path_env_override(monkeypatch, tmp_path):
    target = tmp_path / "custom-deals.json"
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(target))
    p = ld.resolve_local_deals_path()
    assert p == target


def test_resolve_path_explicit_arg_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(tmp_path / "from-env.json"))
    explicit = tmp_path / "from-arg.json"
    p = ld.resolve_local_deals_path(str(explicit))
    assert p == explicit


def test_resolve_path_expands_tilde(monkeypatch):
    monkeypatch.delenv(ld.LOCAL_DEALS_ENV_VAR, raising=False)
    p = ld.resolve_local_deals_path("~/.tars/elsewhere.json")
    assert "~" not in str(p)
    assert str(p).endswith("/.tars/elsewhere.json")


# ---------------------------------------------------------------------
# Read existing helper
# ---------------------------------------------------------------------


def test_read_existing_missing_file_returns_empty(tmp_path):
    p = tmp_path / "ghost.json"
    assert ld._read_existing(p) == []


def test_read_existing_corrupted_json_returns_empty(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("not valid json", encoding="utf-8")
    assert ld._read_existing(p) == []


def test_read_existing_non_list_returns_empty(tmp_path):
    p = tmp_path / "wrong-shape.json"
    p.write_text(json.dumps({"deals": []}), encoding="utf-8")
    assert ld._read_existing(p) == []


def test_read_existing_filters_non_dict_rows(tmp_path):
    p = tmp_path / "mixed.json"
    p.write_text(
        json.dumps([{"id": "a"}, "skip", 42, {"id": "b"}]),
        encoding="utf-8",
    )
    assert ld._read_existing(p) == [{"id": "a"}, {"id": "b"}]


# ---------------------------------------------------------------------
# Id minting
# ---------------------------------------------------------------------


def test_next_local_id_empty():
    assert ld._next_local_id([]) == "local-0001"


def test_next_local_id_continues_from_max():
    rows = [
        {"id": "local-0007"},
        {"id": "local-0003"},
        {"id": "deal-77"},
        {"id": "d-7012"},
    ]
    assert ld._next_local_id(rows) == "local-0008"


def test_next_local_id_ignores_unrelated_ids():
    rows = [{"id": "deal-99"}, {"id": "unknown"}, {"name": "no id"}]
    assert ld._next_local_id(rows) == "local-0001"


def test_next_local_id_handles_missing_id_field():
    rows = [{"name": "no id"}, {"id": None}]
    assert ld._next_local_id(rows) == "local-0001"


# ---------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "given,expected",
    [
        (None, 0.0),
        (0, 0.0),
        ("123", 123.0),
        (-50, 0.0),
        ("garbage", 0.0),
        (1234.5, 1234.5),
    ],
)
def test_coerce_amount(given, expected):
    assert ld._coerce_amount(given) == expected


@pytest.mark.parametrize(
    "given,expected",
    [
        (None, "discovery"),
        ("PROPOSAL", "proposal"),
        ("won", "won"),
        ("typo-stage", "discovery"),
        ("  Negotiation  ", "negotiation"),
    ],
)
def test_coerce_stage(given, expected):
    assert ld._coerce_stage(given) == expected


# ---------------------------------------------------------------------
# append_local_deal — happy path
# ---------------------------------------------------------------------


def test_append_local_deal_writes_to_disk(tmp_path):
    target = tmp_path / "deals.json"
    record = asyncio.run(
        ld.append_local_deal(
            name="Acme Co",
            amount=1200,
            stage="proposal",
            owner="you",
            next_step="send red-line",
            due="2026-05-12",
            path=str(target),
        )
    )
    assert record.id == "local-0001"
    assert record.name == "Acme Co"
    assert record.amount == 1200.0
    assert record.stage == "proposal"
    assert record.owner == "you"

    raw = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["id"] == "local-0001"
    assert raw[0]["name"] == "Acme Co"
    assert raw[0]["due"] == "2026-05-12"


def test_append_local_deal_increments_existing_ids(tmp_path):
    target = tmp_path / "deals.json"
    target.write_text(
        json.dumps(
            [
                {"id": "local-0001", "name": "Old", "amount": 0, "stage": "won"},
                {"id": "local-0002", "name": "Old2", "amount": 0, "stage": "won"},
            ]
        ),
        encoding="utf-8",
    )
    record = asyncio.run(
        ld.append_local_deal(name="Fresh", path=str(target))
    )
    assert record.id == "local-0003"

    rows = json.loads(target.read_text(encoding="utf-8"))
    assert len(rows) == 3
    assert rows[-1]["id"] == "local-0003"


def test_append_local_deal_preserves_unrelated_rows(tmp_path):
    """Existing CRM rows (e.g. d-7012) survive a local append."""

    target = tmp_path / "deals.json"
    target.write_text(
        json.dumps(
            [
                {
                    "id": "d-7012",
                    "name": "Northstar",
                    "amount": 84000,
                    "stage": "negotiation",
                }
            ]
        ),
        encoding="utf-8",
    )
    asyncio.run(ld.append_local_deal(name="New", path=str(target)))
    rows = json.loads(target.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0]["id"] == "d-7012"
    assert rows[1]["id"] == "local-0001"


def test_append_local_deal_creates_parent_dir(tmp_path):
    target = tmp_path / "nested" / "deeper" / "deals.json"
    asyncio.run(ld.append_local_deal(name="Deep", path=str(target)))
    assert target.exists()
    assert target.parent.is_dir()


def test_append_local_deal_strips_blank_optionals(tmp_path):
    target = tmp_path / "deals.json"
    record = asyncio.run(
        ld.append_local_deal(
            name="Quiet",
            owner="   ",
            next_step="",
            due=None,
            notes="",
            path=str(target),
        )
    )
    d = record.to_dict()
    assert "owner" not in d
    assert "next_step" not in d
    assert "due" not in d
    assert "notes" not in d


def test_append_local_deal_rejects_blank_name(tmp_path):
    target = tmp_path / "deals.json"
    with pytest.raises(ValueError, match="name_required"):
        asyncio.run(ld.append_local_deal(name="   ", path=str(target)))
    assert not target.exists()


def test_append_local_deal_recovers_from_corrupt_store(tmp_path):
    """A corrupted file should not block new writes — it should be
    treated as an empty list and overwritten with valid JSON."""

    target = tmp_path / "deals.json"
    target.write_text("definitely not json", encoding="utf-8")

    record = asyncio.run(ld.append_local_deal(name="Recovery", path=str(target)))

    rows = json.loads(target.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["id"] == record.id == "local-0001"


def test_append_local_deal_emits_meeet_event(tmp_path, monkeypatch):
    target = tmp_path / "deals.json"
    captured: list[tuple[str, dict[str, Any]]] = []

    class _CaptureClient:
        async def emit(self, kind: str, payload: dict[str, Any]) -> None:
            captured.append((kind, payload))

    monkeypatch.setattr(ld, "get_client", lambda: _CaptureClient())

    asyncio.run(
        ld.append_local_deal(
            name="MeeetTest",
            amount=999,
            stage="qualification",
            path=str(target),
        )
    )

    kinds = [k for k, _ in captured]
    assert "business.deal_logged" in kinds
    payload = next(p for k, p in captured if k == "business.deal_logged")
    assert payload["id"].startswith("local-")
    assert payload["name"] == "MeeetTest"
    assert payload["amount"] == 999.0
    assert payload["stage"] == "qualification"
    assert payload["crm_pushed"] is False
    assert payload["store_path"] == str(target)


# ---------------------------------------------------------------------
# Action handler — local fallback
# ---------------------------------------------------------------------


@pytest.fixture
def isolated_local_deals(tmp_path, monkeypatch):
    """Point the local store at a tmp file and clear CRM env vars
    so the action handler is forced down the local path."""

    target = tmp_path / "deals.json"
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(target))
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    return target


def test_log_deal_local_fallback_returns_minted_id(isolated_local_deals):
    out = asyncio.run(
        business_actions.log_deal(
            {"name": "LocalAcme", "amount": 1200, "stage": "discovery"}
        )
    )
    assert out["ok"] is True
    assert out["crm_pushed"] is False
    assert out["crm"] == "local"
    assert out["deal_id"] == "local-0001"
    assert out["store_path"] == str(isolated_local_deals)
    assert "deal" in out
    assert out["deal"]["id"] == "local-0001"
    assert out["deal"]["amount"] == 1200.0


def test_log_deal_local_fallback_persists_row(isolated_local_deals):
    asyncio.run(business_actions.log_deal({"name": "Persisted", "amount": 99}))
    rows = json.loads(isolated_local_deals.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["name"] == "Persisted"
    assert rows[0]["amount"] == 99.0
    assert rows[0]["id"] == "local-0001"


def test_log_deal_local_fallback_increments_across_calls(isolated_local_deals):
    for n in range(1, 4):
        out = asyncio.run(business_actions.log_deal({"name": f"Deal {n}"}))
        assert out["deal_id"] == f"local-{n:04d}"


def test_log_deal_explicit_store_path_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(tmp_path / "ignored.json"))
    explicit = tmp_path / "explicit.json"
    out = asyncio.run(
        business_actions.log_deal(
            {"name": "Override", "store_path": str(explicit)}
        )
    )
    assert out["store_path"] == str(explicit)
    assert explicit.exists()
    assert not (tmp_path / "ignored.json").exists()


def test_log_deal_blank_name_returns_validation_error(isolated_local_deals):
    out = asyncio.run(business_actions.log_deal({"name": "   "}))
    assert out["ok"] is False
    assert out["error"] == "name_required"
    # The store should not have been touched.
    assert not isolated_local_deals.exists()


def test_log_deal_invalid_amount_coerces_to_zero(isolated_local_deals):
    out = asyncio.run(
        business_actions.log_deal({"name": "Loose", "amount": "garbage"})
    )
    assert out["ok"] is True
    assert out["amount"] == 0.0
    assert out["deal"]["amount"] == 0.0


def test_log_deal_invalid_stage_falls_back_to_discovery(isolated_local_deals):
    out = asyncio.run(
        business_actions.log_deal({"name": "Loose", "stage": "moonshot"})
    )
    assert out["deal"]["stage"] == "discovery"


def test_log_deal_hubspot_short_circuits_local_store(tmp_path, monkeypatch):
    """When HubSpot succeeds the local store must NOT be touched."""

    target = tmp_path / "deals.json"
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(target))
    monkeypatch.setenv("HUBSPOT_API_KEY", "pat-test")
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)

    async def fake_post(url, body=None, *, headers=None, timeout=6.0):
        return (201, {"id": "deal-77", "properties": {}})

    monkeypatch.setattr(
        "backend.core.domains.packs.business.actions.post_json", fake_post
    )

    out = asyncio.run(business_actions.log_deal({"name": "Zebra", "amount": 500}))
    assert out["ok"] is True
    assert out["crm"] == "hubspot"
    assert out["deal_id"] == "deal-77"
    assert out["crm_pushed"] is True
    assert not target.exists()


def test_log_deal_pipedrive_short_circuits_local_store(tmp_path, monkeypatch):
    target = tmp_path / "deals.json"
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(target))
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.setenv("PIPEDRIVE_API_KEY", "pd-test")

    async def fake_post(url, body=None, *, headers=None, timeout=6.0):
        return (200, {"data": {"id": 42}})

    monkeypatch.setattr(
        "backend.core.domains.packs.business.actions.post_json", fake_post
    )

    out = asyncio.run(business_actions.log_deal({"name": "Lion", "amount": 1}))
    assert out["ok"] is True
    assert out["crm"] == "pipedrive"
    assert out["deal_id"] == "42"
    assert not target.exists()


# ---------------------------------------------------------------------
# Schema wiring
# ---------------------------------------------------------------------


def test_log_deal_action_schema_documents_local_store():
    spec = next(
        (a for a in business_actions.ACTIONS if a.id == "log_deal"), None
    )
    assert spec is not None
    props = spec.schema["properties"]
    assert "store_path" in props
    assert "stage" in props
    assert spec.destructive is True


def test_log_deal_action_stage_enum_in_schema():
    spec = next(
        (a for a in business_actions.ACTIONS if a.id == "log_deal"), None
    )
    assert spec is not None
    enum = spec.schema["properties"]["stage"]["enum"]
    assert "discovery" in enum
    assert "won" in enum
    assert "negotiation" in enum


# ---------------------------------------------------------------------
# Id format invariant
# ---------------------------------------------------------------------


def test_local_id_format_is_zero_padded_4_digits(tmp_path, monkeypatch):
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    monkeypatch.setenv(ld.LOCAL_DEALS_ENV_VAR, str(tmp_path / "deals.json"))
    out = asyncio.run(business_actions.log_deal({"name": "Pad"}))
    assert re.match(r"^local-\d{4,}$", out["deal_id"])
