"""Regression tests for vault status_for_keys, pack auth to_dict, RSS
news parsing, CRM log_deal stubs.
"""

from __future__ import annotations

import asyncio

from backend.core.domains.packs.traders import awareness as traders_aware
from backend.core.domains.packs.business import actions as business_actions
from backend.core.domains.registry import get_pack
from backend.core.vault import status_for_keys


def test_status_for_keys_preserves_order_and_dedup(monkeypatch) -> None:
    monkeypatch.setenv("HUBSPOT_API_KEY", "x")
    refs = status_for_keys(
        ("PIPEDRIVE_API_KEY", "HUBSPOT_API_KEY", "PIPEDRIVE_API_KEY")
    )
    assert [r.key for r in refs] == ["PIPEDRIVE_API_KEY", "HUBSPOT_API_KEY"]
    by = {r.key: r for r in refs}
    assert by["HUBSPOT_API_KEY"].available is True
    assert by["HUBSPOT_API_KEY"].source == "env"


def test_pack_to_dict_includes_auth() -> None:
    b = get_pack("business")
    assert b is not None
    d = b.to_dict()
    assert "auth" in d and "keys" in d["auth"]
    keys = [k["key"] for k in d["auth"]["keys"]]
    assert "HUBSPOT_API_KEY" in keys and "PIPEDRIVE_API_KEY" in keys


def test_parse_rss_atom_minimal() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>BTC rally on ETF inflow</title><link>https://example.com/a</link><pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate></item>
  <item><title>Market crash fears</title><link>https://example.com/b</link></item>
</channel></rss>"""
    items = traders_aware._parse_rss_atom(xml)
    assert len(items) == 2
    tones = {it["title"]: it["tone"] for it in items}
    assert tones["BTC rally on ETF inflow"] == "bullish"
    assert tones["Market crash fears"] == "bearish"




def test_log_deal_stub_without_crm_keys(monkeypatch) -> None:
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    out = asyncio.run(
        business_actions.log_deal(
            {"name": "Acme", "amount": 1200, "stage": "discovery"}
        )
    )
    assert out["ok"] is True
    assert out.get("crm_pushed") is False
    assert out.get("deal_id") == "stub-deal-0001"


def test_log_deal_hubspot_when_key_and_api_ok(monkeypatch) -> None:
    monkeypatch.setenv("HUBSPOT_API_KEY", "pat-test")
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)

    async def fake_post(url, body=None, *, headers=None, timeout=6.0):
        assert "hubapi.com" in url
        return (201, {"id": "deal-77", "properties": {}})

    monkeypatch.setattr(
        "backend.core.domains.packs.business.actions.post_json",
        fake_post,
    )
    out = asyncio.run(business_actions.log_deal({"name": "Zebra", "amount": 500}))
    assert out["crm_pushed"] is True
    assert out["crm"] == "hubspot"
    assert out["deal_id"] == "deal-77"
