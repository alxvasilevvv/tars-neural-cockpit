"""Remote billing usage POST + mirror from ``usage.tokens`` (see TARS_MEEET_BILLING.md)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.core.meeet.client import get_client, reset_client
from backend.core.meeet_billing import mirror_usage
from backend.core.meeet_billing.client import clear_operator_cache, post_operator_usage_delta


@pytest.fixture(autouse=True)
def _clear_billing_cache():
    clear_operator_cache()
    yield
    clear_operator_cache()
    reset_client()


@pytest.mark.asyncio
async def test_post_operator_usage_delta_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/billing")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {
                    "ok": True,
                    "spent_usd_24h": 0.01,
                    "allowed_cloud": True,
                }
            ).encode()

    with patch("urllib.request.urlopen", return_value=_Resp()) as m:
        out = await post_operator_usage_delta(0.01, trace_id="trc_test_xyz")
    assert out["ok"] is True
    assert m.call_count == 1
    req = m.call_args[0][0]
    assert req.full_url == "https://meeet.example/billing/operator/usage"
    assert req.get_method() == "POST"
    sent = json.loads(req.data.decode("utf-8"))
    assert sent["delta_usd"] == 0.01
    assert sent["trace_id"] == "trc_test_xyz"


@pytest.mark.asyncio
async def test_mirror_skips_when_not_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARS_BILLING_SOURCE", raising=False)
    mock = AsyncMock()
    with patch("backend.core.meeet_billing.mirror_usage.post_operator_usage_delta", mock):
        await mirror_usage.after_usage_tokens_emitted(
            route="cloud",
            payload={"cost_usd": 0.5},
        )
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_mirror_skips_when_route_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    mock = AsyncMock()
    with patch("backend.core.meeet_billing.mirror_usage.post_operator_usage_delta", mock):
        await mirror_usage.after_usage_tokens_emitted(
            route="edge",
            payload={"cost_usd": 0.5},
        )
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_mirror_posts_when_cloud_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    mock = AsyncMock(return_value={"ok": True})
    with patch("backend.core.meeet_billing.mirror_usage.post_operator_usage_delta", mock):
        await mirror_usage.after_usage_tokens_emitted(
            route="cloud",
            payload={"cost_usd": 0.25},
            trace_id="trc_outer",
        )
    mock.assert_called_once()
    assert mock.call_args[0][0] == 0.25
    assert mock.call_args.kwargs.get("trace_id") == "trc_outer"


@pytest.mark.asyncio
async def test_post_usage_retries_on_transient_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.error

    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/billing")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")
    monkeypatch.setenv("MEEET_BILLING_USAGE_RETRIES", "4")

    class _Ok:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"ok": True}).encode()

    calls: list[int] = []

    def side_effect(req, timeout=None):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(
                req.full_url, 503, "unavailable", hdrs=None, fp=None
            )
        return _Ok()

    with patch("urllib.request.urlopen", side_effect=side_effect):
        out = await post_operator_usage_delta(0.01)
    assert out["ok"] is True
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_post_operator_usage_retry_exhausted(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import urllib.error

    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/billing")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")
    monkeypatch.setenv("MEEET_BILLING_USAGE_RETRIES", "3")

    def always_503(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 503, "unavailable", hdrs=None, fp=None
        )

    caplog.set_level("WARNING")
    with (
        patch("urllib.request.urlopen", side_effect=always_503),
        patch(
            "backend.core.meeet_billing.client.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        out = await post_operator_usage_delta(0.02, trace_id="trc_exhaust")
    assert out.get("ok") is False
    assert out.get("error") == "http_503"
    exhausted = next(
        r for r in caplog.records if r.getMessage() == "meeet.mirror.usage.exhausted"
    )
    assert getattr(exhausted, "trace_id", None) == "trc_exhaust"
    assert getattr(exhausted, "attempts", None) == 3
    assert getattr(exhausted, "last_error", None) == "http_503"


@pytest.mark.asyncio
async def test_emit_usage_tokens_triggers_mirror_without_ingest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Billing mirror runs even when meeet ingest URL is unset (local-first)."""

    monkeypatch.setenv("TARS_BILLING_SOURCE", "remote")
    monkeypatch.setenv("MEEET_BILLING_BASE_URL", "https://meeet.example/billing")
    monkeypatch.setenv("MEEET_BILLING_API_KEY", "secret")
    monkeypatch.setenv("MEEET_INGEST_URL", "")

    mock = AsyncMock(return_value={"ok": True})
    with patch(
        "backend.core.meeet_billing.mirror_usage.after_usage_tokens_emitted",
        mock,
    ):
        reset_client()
        client = get_client()
        from backend.core.meeet.tracing import trace_scope

        with trace_scope(route="cloud"):
            await client.emit(
                "usage.tokens",
                {"model": "openai/gpt-4o", "tokens_in": 100, "tokens_out": 50, "cost_usd": 0.01},
            )
    mock.assert_called_once()
    assert mock.call_args.kwargs.get("trace_id")
