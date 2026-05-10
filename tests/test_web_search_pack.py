"""Tests for the web-search domain pack.

Covers, end-to-end without network:

- Registration: pack appears in the registry, exposes the expected
  actions, and lists ``BRAVE_SEARCH_API_KEY`` as an auth key.
- Dispatcher: ``_planned_order`` walks Brave → SearXNG → DDG when
  configured, drops un-configured backends, and respects an explicit
  ``adapter`` pin.
- Adapters: each one is monkeypatched to return canned responses, so
  the parsers and error paths are exercised without hitting the
  internet (Brave JSON, DDG HTML, SearXNG JSON, network error,
  4xx upstream).
- Action surface: ``search`` returns the expected envelope, including
  ``tried`` per attempt; ``health`` is a pure no-network probe.
- Vault list: ``BRAVE_SEARCH_API_KEY`` is in ``KNOWN_KEYS`` so the
  cockpit's secrets panel renders it.

We avoid ``pytest-asyncio`` (not in the base requirements) and run
coroutines via ``asyncio.run`` like the rest of the suite.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from unittest import mock

import pytest

from backend.core.domains import packs as _packs  # noqa: F401 — registers
from backend.core.domains.packs.web_search import actions as ws_actions
from backend.core.domains.packs.web_search.adapters import (
    AdapterResult,
    SearchHit,
    dedupe,
    trim,
)
from backend.core.domains.packs.web_search.adapters import brave as brave_mod
from backend.core.domains.packs.web_search.adapters import ddg as ddg_mod
from backend.core.domains.packs.web_search.adapters import searxng as sx_mod
from backend.core.domains.registry import get_pack
from backend.core.vault.keychain import KNOWN_KEYS


# --------------------------------------------------------- registration


def test_pack_registers_under_web_search_slug() -> None:
    pack = get_pack("web_search")
    assert pack is not None
    assert pack.manifest.slug == "web_search"
    assert "web_search_brave" in pack.manifest.capabilities
    action_ids = {a.id for a in pack.actions()}
    assert {"search", "health"} <= action_ids


def test_brave_secret_listed_in_known_keys() -> None:
    assert "BRAVE_SEARCH_API_KEY" in KNOWN_KEYS


def test_to_dict_includes_pack_memory_actions() -> None:
    pack = get_pack("web_search")
    assert pack is not None
    ids = [a["id"] for a in pack.to_dict()["actions"]]
    # System-wide pack.memory.* must be injected for every pack so the
    # cockpit can scope memory per slug — regression fence.
    for sys_id in (
        "pack.memory.set",
        "pack.memory.get",
        "pack.memory.list",
        "pack.memory.delete",
    ):
        assert sys_id in ids, ids


# --------------------------------------------------------- dispatcher


def test_planned_order_keyless_falls_back_to_ddg() -> None:
    plan = ws_actions._planned_order(
        "auto", have_brave=False, have_searxng=False
    )
    assert plan == ("ddg",)


def test_planned_order_walks_full_chain_when_all_configured() -> None:
    plan = ws_actions._planned_order(
        "auto", have_brave=True, have_searxng=True
    )
    assert plan == ("brave", "searxng", "ddg")


def test_planned_order_skips_unconfigured_backends() -> None:
    assert ws_actions._planned_order(
        "auto", have_brave=True, have_searxng=False
    ) == ("brave", "ddg")
    assert ws_actions._planned_order(
        "auto", have_brave=False, have_searxng=True
    ) == ("searxng", "ddg")


def test_planned_order_pinned_adapter_overrides_chain() -> None:
    # Even if Brave isn't configured, an explicit pin must produce
    # exactly that one — the pin is "I want this backend, fail loud".
    plan = ws_actions._planned_order(
        "brave", have_brave=False, have_searxng=False
    )
    assert plan == ("brave",)


# --------------------------------------------------------- adapters: brave


_BRAVE_SAMPLE = json.dumps(
    {
        "web": {
            "results": [
                {
                    "title": "Pandas — official docs",
                    "url": "https://pandas.pydata.org",
                    "description": "pandas is a fast, powerful, "
                    "flexible and easy to use open source data "
                    "analysis and manipulation tool.",
                    "age": "2 weeks ago",
                    "language": "en",
                },
                {
                    "title": "pandas on PyPI",
                    "url": "https://pypi.org/project/pandas/",
                    "description": "Powerful data structures for "
                    "data analysis, time series, and statistics.",
                },
            ]
        }
    }
)


def test_brave_adapter_parses_canonical_response() -> None:
    async def fake_get_text(url, *, params=None, headers=None, timeout=8.0):
        assert "X-Subscription-Token" in headers
        assert headers["X-Subscription-Token"] == "test-key"
        return 200, _BRAVE_SAMPLE

    with mock.patch.object(brave_mod, "get_text", new=fake_get_text):
        result: AdapterResult = asyncio.run(
            brave_mod.search("pandas docs", limit=5, api_key="test-key")
        )
    assert result.ok is True
    assert result.adapter == "brave"
    assert len(result.hits) == 2
    assert result.hits[0].url == "https://pandas.pydata.org"
    assert result.hits[0].source == "brave"
    assert result.hits[0].extra.get("age") == "2 weeks ago"


def test_brave_adapter_missing_key_short_circuits() -> None:
    result = asyncio.run(brave_mod.search("x", limit=3, api_key=""))
    assert result.ok is False
    assert result.error == "api_key_missing"


def test_brave_adapter_handles_unauthorized() -> None:
    async def fake_get_text(url, *, params=None, headers=None, timeout=8.0):
        return 401, ""

    with mock.patch.object(brave_mod, "get_text", new=fake_get_text):
        result = asyncio.run(
            brave_mod.search("x", limit=3, api_key="bad")
        )
    assert result.ok is False
    assert result.error == "unauthorized"
    assert result.upstream_status == 401


def test_brave_adapter_handles_rate_limit() -> None:
    async def fake_get_text(url, *, params=None, headers=None, timeout=8.0):
        return 429, ""

    with mock.patch.object(brave_mod, "get_text", new=fake_get_text):
        result = asyncio.run(
            brave_mod.search("x", limit=3, api_key="ok")
        )
    assert result.ok is False
    assert result.error == "rate_limited"
    assert result.upstream_status == 429


def test_brave_adapter_handles_network_error() -> None:
    from backend.core.domains._http import NetworkError

    async def boom(*a: Any, **k: Any):
        raise NetworkError("dns fail")

    with mock.patch.object(brave_mod, "get_text", new=boom):
        result = asyncio.run(
            brave_mod.search("x", limit=3, api_key="ok")
        )
    assert result.ok is False
    assert result.error == "network_error"
    assert "dns fail" in (result.detail or "")


# --------------------------------------------------------- adapters: ddg


_DDG_SAMPLE = """
<html><body>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Ffoo">Example Foo</a>
  <a class="result__snippet" href="https://example.com/foo">A short summary about foo &amp; bar.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.org/bar">Example Bar</a>
  <a class="result__snippet" href="https://example.org/bar">Another snippet here.</a>
</div>
</body></html>
"""


def test_ddg_parser_unwraps_redirects_and_strips_html() -> None:
    hits = ddg_mod._parse(_DDG_SAMPLE, limit=5)
    assert len(hits) == 2
    assert hits[0].url == "https://example.com/foo"
    assert hits[0].title == "Example Foo"
    assert "&" in hits[0].snippet  # entity decoded
    assert hits[1].url == "https://example.org/bar"


def test_ddg_unwrap_handles_protocol_relative_and_real_urls() -> None:
    assert ddg_mod._unwrap(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fz.example%2Fa"
    ) == "https://z.example/a"
    assert ddg_mod._unwrap("https://plain.example/x") == (
        "https://plain.example/x"
    )


def test_ddg_adapter_anomaly_page_yields_rate_limit() -> None:
    anomaly = (
        "<html><head><title>DuckDuckGo Anomaly</title></head>"
        "<body>Anomaly: please verify…</body></html>"
    )

    async def fake_get_text(url, *, params=None, headers=None, timeout=8.0):
        return 200, anomaly

    with mock.patch.object(ddg_mod, "get_text", new=fake_get_text):
        result = asyncio.run(ddg_mod.search("x", limit=3))
    assert result.ok is False
    assert result.error == "rate_limited"


# --------------------------------------------------------- adapters: searxng


_SX_SAMPLE = json.dumps(
    {
        "results": [
            {
                "title": "Result A",
                "url": "https://a.example",
                "content": "Snippet for A.",
                "engine": "google",
            },
            {
                "title": "Result B",
                "url": "https://b.example",
                "content": "Snippet for B.",
                "engine": "ddg",
            },
        ]
    }
)


def test_searxng_adapter_parses_results_and_normalises_url() -> None:
    async def fake_get_text(url, *, params=None, headers=None, timeout=8.0):
        # base URL must end in /search after normalisation
        assert url.endswith("/search")
        return 200, _SX_SAMPLE

    with mock.patch.object(sx_mod, "get_text", new=fake_get_text):
        result = asyncio.run(
            sx_mod.search(
                "x", limit=5, base_url="http://127.0.0.1:8080"
            )
        )
    assert result.ok is True
    assert len(result.hits) == 2
    assert result.hits[0].extra.get("engine") == "google"


def test_searxng_adapter_missing_url_short_circuits() -> None:
    result = asyncio.run(sx_mod.search("x", limit=3, base_url=""))
    assert result.ok is False
    assert result.error == "base_url_missing"


def test_searxng_normalise_base_appends_trailing_slash() -> None:
    assert sx_mod._normalise_base("http://x") == "http://x/"
    assert sx_mod._normalise_base("http://x/") == "http://x/"
    assert sx_mod._normalise_base("") == ""


# --------------------------------------------------------- helpers


def test_trim_collapses_whitespace_and_truncates() -> None:
    assert trim("  hello   world  ") == "hello world"
    long = "x" * 500
    out = trim(long, max_chars=100)
    assert len(out) == 100
    assert out.endswith("…")


def test_dedupe_keeps_first_occurrence_by_url() -> None:
    h = (
        SearchHit(title="A", url="https://x.com/a"),
        SearchHit(title="A2", url="https://x.com/a/"),  # trailing slash
        SearchHit(title="B", url="https://x.com/b"),
    )
    out = dedupe(h)
    assert len(out) == 2
    assert out[0].title == "A"
    assert out[1].title == "B"


# --------------------------------------------------------- top-level action


def test_search_requires_query() -> None:
    out = asyncio.run(ws_actions.search({}))
    assert out["ok"] is False
    assert out["error"] == "query_required"


def test_search_default_uses_ddg_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Strip env so the dispatcher truly has no configured backend.
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("TARS_SEARXNG_URL", raising=False)

    async def fake_ddg_search(query, *, limit, timeout=8.0):
        return AdapterResult(
            ok=True,
            adapter="ddg",
            hits=(
                SearchHit(
                    title="Hello",
                    url="https://hello.example",
                    snippet="hi",
                    source="ddg",
                ),
            ),
        )

    monkeypatch.setattr(ws_actions.ddg_adapter, "search", fake_ddg_search)
    out = asyncio.run(ws_actions.search({"query": "hi"}))
    assert out["ok"] is True
    assert out["adapter"] == "ddg"
    assert out["count"] == 1
    assert out["results"][0]["url"] == "https://hello.example"
    assert any(t["adapter"] == "ddg" and t["ok"] for t in out["tried"])


def test_search_falls_through_failed_adapter_to_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "stub")
    monkeypatch.delenv("TARS_SEARXNG_URL", raising=False)

    async def fake_brave_search(query, *, limit, api_key, timeout=8.0):
        return AdapterResult(
            ok=False, adapter="brave", error="upstream_status",
            upstream_status=503,
        )

    async def fake_ddg_search(query, *, limit, timeout=8.0):
        return AdapterResult(
            ok=True,
            adapter="ddg",
            hits=(SearchHit(title="x", url="https://x.example"),),
        )

    monkeypatch.setattr(ws_actions.brave_adapter, "search", fake_brave_search)
    monkeypatch.setattr(ws_actions.ddg_adapter, "search", fake_ddg_search)

    out = asyncio.run(ws_actions.search({"query": "anything"}))
    assert out["ok"] is True
    assert out["adapter"] == "ddg"
    tried_adapters = [t["adapter"] for t in out["tried"]]
    assert tried_adapters == ["brave", "ddg"]


def test_search_all_adapters_fail_returns_actionable_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("TARS_SEARXNG_URL", raising=False)

    async def fake_ddg_search(query, *, limit, timeout=8.0):
        return AdapterResult(
            ok=False, adapter="ddg", error="rate_limited"
        )

    monkeypatch.setattr(ws_actions.ddg_adapter, "search", fake_ddg_search)

    out = asyncio.run(ws_actions.search({"query": "x"}))
    assert out["ok"] is False
    assert out["error"] == "all_adapters_failed"
    assert "BRAVE_SEARCH_API_KEY" in out["hint"]
    assert out["tried"][0]["adapter"] == "ddg"


def test_search_pinned_adapter_does_not_fall_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("TARS_SEARXNG_URL", raising=False)

    async def fake_brave_search(query, *, limit, api_key, timeout=8.0):
        return AdapterResult(
            ok=False, adapter="brave", error="api_key_missing"
        )

    monkeypatch.setattr(ws_actions.brave_adapter, "search", fake_brave_search)
    out = asyncio.run(
        ws_actions.search({"query": "x", "adapter": "brave"})
    )
    assert out["ok"] is False
    # Only Brave was tried — pin must not silently widen the chain.
    assert [t["adapter"] for t in out["tried"]] == ["brave"]


def test_search_limit_is_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("TARS_SEARXNG_URL", raising=False)

    seen_limits: list[int] = []

    async def fake_ddg_search(query, *, limit, timeout=8.0):
        seen_limits.append(limit)
        return AdapterResult(ok=True, adapter="ddg", hits=())

    monkeypatch.setattr(ws_actions.ddg_adapter, "search", fake_ddg_search)
    asyncio.run(ws_actions.search({"query": "x", "limit": 999}))
    asyncio.run(ws_actions.search({"query": "x", "limit": -5}))
    asyncio.run(ws_actions.search({"query": "x", "limit": "garbage"}))
    assert seen_limits == [
        ws_actions.MAX_LIMIT,
        1,
        ws_actions.DEFAULT_LIMIT,
    ]


def test_health_action_is_pure_no_network() -> None:
    out = asyncio.run(ws_actions.health({}))
    assert out["ok"] is True
    assert "ddg" in out["default_order"]
    assert out["adapters"]["ddg"]["configured"] is True
