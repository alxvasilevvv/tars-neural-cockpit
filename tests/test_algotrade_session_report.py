"""Tests for the W3-PR2 markdown session report renderer.

The renderer turns the W3-PR1 dataclasses into a fixed-structure
Markdown document an attendee can drop straight into a brief.
We assert that:

- Every section heading is present (search-stable for downstream
  consumers).
- PnL / slippage / metrics numbers are reflected in the rendered
  text.
- The structured ``payload`` mirrors every section so the
  cockpit's chart layer doesn't need to re-parse markdown.
- The renderer is deterministic: same inputs → same bytes.
- Empty sessions render gracefully (no division-by-zero, no
  crashes on the trade ledger).
- The ASCII sparkline lives only when there's at least 2 PnL
  curve samples.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.algotrade.exec import (
    AuditLog,
    OrderIntent,
    OrderRouter,
    OrderType,
    PaperAdapter,
    PaperConfig,
    PositionStore,
    RiskGate,
    RiskPolicy,
    Session,
    SessionStatus,
    Side,
    compute_attribution,
    compute_session_metrics,
    compute_slippage,
    render_session_report,
)


def _bar(ts: float, o: float, h: float, lo: float, c: float) -> dict:
    return {
        "instrument": "BINANCE:BTCUSDT",
        "ts": ts,
        "open": o,
        "high": h,
        "low": lo,
        "close": c,
        "volume": 1.0,
    }


def _intent(*, side: Side, qty: float = 1.0) -> OrderIntent:
    return OrderIntent.make(
        strategy_fingerprint="fp_test",
        instrument="BINANCE:BTCUSDT",
        side=side,
        qty=qty,
        type=OrderType.MARKET,
    )


def _wire(tmp_path: Path):
    adapter = PaperAdapter(PaperConfig(slippage_bps=5.0, commission_bps=1.0))
    positions = PositionStore()
    audit = AuditLog(tmp_path / "audit.jsonl")
    gate = RiskGate(RiskPolicy(max_order_qty=10.0, allow_short=True))
    router = OrderRouter(
        adapter=adapter,
        gate=gate,
        positions=positions,
        audit=audit,
        session_id="sess_test",
    )
    return adapter, positions, audit, router, gate


def _session_obj(sid: str = "sess_test") -> Session:
    return Session(
        session_id=sid,
        mode="paper",
        strategy_fingerprint="sha256:abcdef0123456789abcdef0123456789",
        instrument="BINANCE:BTCUSDT",
        adapter="paper",
        sandbox_id="cresco-day1",
        started_at=1700000000.0,
        status=SessionStatus.RUNNING,
        notes="cresco workshop, day 1",
    )


def _build_full_report(tmp_path: Path):
    adapter, positions, audit, router, gate = _wire(tmp_path)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(2, 110, 110, 110, 110))
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(3, 105, 105, 105, 105))
        await router.submit(_intent(side=Side.SELL, qty=1.0))
        await adapter.on_bar(_bar(4, 100, 100, 100, 100))

    asyncio.run(run())

    events = audit.read_all()
    attribution = compute_attribution(events)
    slippage = compute_slippage(events)
    metrics = compute_session_metrics(
        events,
        open_positions=positions.open_count(),
        realized_pnl=positions.total_realized(),
        unrealized_pnl=positions.total_unrealized(),
    )
    report = render_session_report(
        session=_session_obj(),
        policy=gate.policy,
        metrics=metrics,
        attribution=attribution,
        slippage=slippage,
        open_positions=[p.to_dict() for p in positions.all() if not p.is_flat()],
    )
    return report, attribution, slippage, metrics


def test_report_contains_all_required_sections(tmp_path: Path) -> None:
    report, *_ = _build_full_report(tmp_path)
    md = report.markdown
    for section in (
        "## Session",
        "## Headline metrics",
        "## PnL attribution",
        "## Top trades",
        "## Slippage",
        "## Risk policy",
    ):
        assert section in md, f"missing section header: {section}"


def test_report_uses_default_title_when_none_provided(tmp_path: Path) -> None:
    report, *_ = _build_full_report(tmp_path)
    assert report.markdown.startswith("# Session sess_test — sha256:abcdef012")


def test_report_respects_custom_title(tmp_path: Path) -> None:
    adapter, positions, audit, router, gate = _wire(tmp_path)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))

    asyncio.run(run())
    events = audit.read_all()
    metrics = compute_session_metrics(events)
    report = render_session_report(
        session=_session_obj(),
        policy=gate.policy,
        metrics=metrics,
        attribution=compute_attribution(events),
        slippage=compute_slippage(events),
        title="Cresco Day 1 — fp_alpha",
    )
    assert report.markdown.startswith("# Cresco Day 1 — fp_alpha")


def test_payload_mirrors_inputs(tmp_path: Path) -> None:
    report, attribution, slippage, metrics = _build_full_report(tmp_path)
    payload = report.payload

    assert payload["title"].startswith("Session sess_test")
    assert payload["session"]["session_id"] == "sess_test"
    assert payload["metrics"] == metrics.to_dict()
    assert payload["attribution"] == attribution.to_dict()
    assert payload["slippage"] == slippage.to_dict()
    assert payload["policy"]["allow_short"] is True
    assert isinstance(payload["sparkline"], str)


def test_report_includes_pnl_and_slippage_numbers(tmp_path: Path) -> None:
    report, attribution, slippage, metrics = _build_full_report(tmp_path)
    md = report.markdown
    assert "Realised PnL" in md
    assert "Slippage cost" in md
    assert "By instrument" in md
    assert "BINANCE:BTCUSDT" in md


def test_report_is_deterministic(tmp_path: Path) -> None:
    report1, *_ = _build_full_report(tmp_path)
    audit = AuditLog(tmp_path / "audit.jsonl")
    events = audit.read_all()
    report2_md = render_session_report(
        session=_session_obj(),
        policy=RiskPolicy(max_order_qty=10.0, allow_short=True),
        metrics=compute_session_metrics(events),
        attribution=compute_attribution(events),
        slippage=compute_slippage(events),
    ).markdown

    section_pairs = [
        ("## Session", "## Headline metrics"),
        ("## Headline metrics", "## PnL attribution"),
        ("## PnL attribution", "## Top trades"),
        ("## Top trades", "## Slippage"),
        ("## Slippage", "## Risk policy"),
    ]
    for start, end in section_pairs:
        a = _section(report1.markdown, start, end)
        b = _section(report2_md, start, end)
        assert a == b, f"section {start} drifted between renders"


def _section(md: str, start: str, end: str) -> str:
    s = md.index(start)
    e = md.index(end, s)
    return md[s:e]


def test_report_empty_session_does_not_crash(tmp_path: Path) -> None:
    metrics = compute_session_metrics([])
    attribution = compute_attribution([])
    slippage = compute_slippage([])
    report = render_session_report(
        session=_session_obj(),
        policy=RiskPolicy(),
        metrics=metrics,
        attribution=attribution,
        slippage=slippage,
    )
    assert "## Session" in report.markdown
    assert "_No closed trades in this session._" in report.markdown


def test_report_open_positions_section_only_when_present(tmp_path: Path) -> None:
    adapter, positions, audit, router, gate = _wire(tmp_path)

    async def run() -> None:
        await router.submit(_intent(side=Side.BUY, qty=1.0))
        await adapter.on_bar(_bar(1, 100, 100, 100, 100))

    asyncio.run(run())
    events = audit.read_all()
    metrics = compute_session_metrics(
        events,
        open_positions=positions.open_count(),
        realized_pnl=positions.total_realized(),
        unrealized_pnl=positions.total_unrealized(),
    )
    open_positions = [p.to_dict() for p in positions.all() if not p.is_flat()]

    report_with = render_session_report(
        session=_session_obj(),
        policy=gate.policy,
        metrics=metrics,
        attribution=compute_attribution(events),
        slippage=compute_slippage(events),
        open_positions=open_positions,
    )
    assert "## Open positions" in report_with.markdown

    report_without = render_session_report(
        session=_session_obj(),
        policy=gate.policy,
        metrics=metrics,
        attribution=compute_attribution(events),
        slippage=compute_slippage(events),
        open_positions=[],
    )
    assert "## Open positions" not in report_without.markdown


def test_sparkline_renders_when_curve_has_samples(tmp_path: Path) -> None:
    report, attribution, *_ = _build_full_report(tmp_path)
    assert len(attribution.pnl_curve) >= 2
    assert "Cumulative PnL curve" in report.markdown
    assert report.payload["sparkline"] != "—"


def test_sparkline_is_dash_when_curve_empty() -> None:
    metrics = compute_session_metrics([])
    attribution = compute_attribution([])
    slippage = compute_slippage([])
    report = render_session_report(
        session=_session_obj(),
        policy=RiskPolicy(),
        metrics=metrics,
        attribution=attribution,
        slippage=slippage,
    )
    assert report.payload["sparkline"] == "—"
    assert "Cumulative PnL curve" not in report.markdown


def test_session_report_action_returns_markdown_and_payload() -> None:
    """End-to-end through the action handler so the cockpit's
    contract stays honest."""

    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["TARS_ALGOTRADE_HOME"] = tmpdir
        from backend.core.algotrade.exec import reset_runtime
        reset_runtime()
        from backend.core.algotrade import get_registry
        from backend.core.algotrade.recipes import list_recipes, load_recipe
        from backend.core.domains.packs.algotrade.exec_actions import (
            start_paper_session_action,
            submit_intent_action,
            feed_bar_action,
            session_report_action,
        )

        name = list_recipes()[0]
        fp = get_registry().put(load_recipe(name)).fingerprint

        async def run():
            s = await start_paper_session_action({
                "fingerprint": fp,
                "instrument": "BINANCE:BTCUSDT",
                "config": {"slippage_bps": 2.0, "commission_bps": 0.5},
            })
            sid = s["session"]["session_id"]
            await submit_intent_action({"session_id": sid, "side": "buy", "qty": 1.0})
            await feed_bar_action({
                "session_id": sid,
                "bar": {"ts": 1, "open": 100, "high": 100, "low": 100, "close": 100, "instrument": "BINANCE:BTCUSDT"},
            })
            await submit_intent_action({"session_id": sid, "side": "sell", "qty": 1.0})
            await feed_bar_action({
                "session_id": sid,
                "bar": {"ts": 2, "open": 110, "high": 110, "low": 110, "close": 110, "instrument": "BINANCE:BTCUSDT"},
            })
            return await session_report_action({"session_id": sid, "top_n_trades": 3})

        result = asyncio.run(run())
        assert result["ok"] is True
        assert result["markdown"].startswith("# Session ")
        assert "## Headline metrics" in result["markdown"]
        assert "## Top trades" in result["markdown"]
        assert "## Slippage" in result["markdown"]
        assert "payload" in result
        assert result["payload"]["metrics"]["intents_total"] == 2
        assert result["payload"]["metrics"]["fills_total"] == 2
        assert result["payload"]["metrics"]["realized_pnl"] > 0
