"""Tests for the policy gate (Phase D)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.core.policy import (
    GateDecision,
    PolicyGate,
    PolicyMode,
    PolicyStore,
    resolve_mode,
)


def _store(tmp_path: Path) -> PolicyStore:
    return PolicyStore(str(tmp_path / "policy.sqlite"))


def test_resolve_mode_priority_arg_over_header_over_env(monkeypatch) -> None:
    monkeypatch.setenv("TARS_POLICY_MODE", "autopilot")
    assert resolve_mode() is PolicyMode.AUTOPILOT
    assert resolve_mode(header="dry_run") is PolicyMode.DRY_RUN
    assert resolve_mode(header="dry_run", request_arg="confirm") is PolicyMode.CONFIRM


def test_resolve_mode_falls_back_to_confirm() -> None:
    assert resolve_mode() is PolicyMode.CONFIRM


def test_resolve_mode_ignores_unknown_strings() -> None:
    assert resolve_mode(header="quad") is PolicyMode.CONFIRM


def test_gate_passes_through_non_destructive() -> None:
    gate = PolicyGate()

    async def run() -> GateDecision:
        return await gate.check(
            slug="business",
            action_id="kpi_snapshot",
            args={},
            destructive=False,
            mode=PolicyMode.CONFIRM,
        )

    out = asyncio.run(run())
    assert out.allowed is True
    assert out.reason == "not_destructive"


def test_gate_passes_through_autopilot() -> None:
    gate = PolicyGate()

    async def run() -> GateDecision:
        return await gate.check(
            slug="traders",
            action_id="place_alert",
            args={"ticker": "BTC"},
            destructive=True,
            mode=PolicyMode.AUTOPILOT,
        )

    out = asyncio.run(run())
    assert out.allowed is True
    assert out.reason == "autopilot"


def test_gate_dry_run_returns_preview_no_token() -> None:
    gate = PolicyGate()

    async def run() -> GateDecision:
        return await gate.check(
            slug="traders",
            action_id="place_alert",
            args={"ticker": "BTC"},
            destructive=True,
            mode=PolicyMode.DRY_RUN,
        )

    out = asyncio.run(run())
    assert out.allowed is False
    assert out.reason == "dry_run_preview_only"
    assert out.confirmation_token is None
    assert out.preview is not None


def test_gate_confirm_creates_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MEEET_STORE_PATH", str(tmp_path / "meeet.sqlite"))
    from backend.core.policy import reset_policy_store
    reset_policy_store()
    gate = PolicyGate()

    async def run() -> tuple[GateDecision, list]:
        decision = await gate.check(
            slug="business",
            action_id="draft_email",
            args={"to": "x@y.z"},
            destructive=True,
            mode=PolicyMode.CONFIRM,
        )
        from backend.core.policy import get_policy_store
        pending = await get_policy_store().list_pending()
        return decision, pending

    out, pending = asyncio.run(run())
    assert out.allowed is False
    assert out.reason == "awaiting_confirmation"
    assert out.confirmation_token and out.confirmation_token.startswith("cfm_")
    assert any(p.token == out.confirmation_token for p in pending)


def test_store_resolve_idempotent(tmp_path) -> None:
    store = _store(tmp_path)

    async def run():
        token = await store.create(
            slug="x", action_id="y", args={"a": 1}
        )
        first = await store.resolve(token, status="confirmed", result={"r": 1})
        assert first is not None
        assert first.status == "confirmed"
        # Second resolve on same token should be a no-op (returns None).
        second = await store.resolve(token, status="cancelled")
        assert second is None

    asyncio.run(run())


def test_store_expire_stale(tmp_path) -> None:
    store = _store(tmp_path)

    async def run():
        await store.create(
            slug="x", action_id="y", args={}, ttl_s=-10
        )
        n = await store.expire_stale()
        assert n == 1
        recent = await store.list_recent()
        assert recent and recent[0].status == "expired"

    asyncio.run(run())


def test_action_specs_marked_destructive() -> None:
    from backend.core.domains import packs as _packs  # noqa: F401
    from backend.core.domains.registry import get_pack

    expected = {
        ("traders", "place_alert"),
        ("traders", "cancel_alert"),
        ("business", "draft_email"),
        ("business", "log_deal"),
        ("business", "update_deal"),
        ("mlm", "generate_post"),
        ("mlm", "add_member"),
        ("mlm", "log_activity"),
    }
    found: set[tuple[str, str]] = set()
    for slug in ("traders", "business", "mlm", "science"):
        pack = get_pack(slug)
        assert pack is not None
        for spec in pack.actions():
            if spec.destructive:
                found.add((slug, spec.id))
    assert found == expected
