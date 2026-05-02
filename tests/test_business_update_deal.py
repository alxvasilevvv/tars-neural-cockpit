"""Tests for ``business.update_deal`` and ``update_local_deal``.

Closes the deal lifecycle: ``log_deal`` writes, ``daily_brief`` reads,
``update_deal`` patches stage / amount / next_step / etc. on a
previously-logged local row. Covers idempotency, validation, audit
metadata, meeet event emission, and integration with ``daily_brief``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from backend.core.domains.packs.business.actions import (
    daily_brief,
    log_deal,
    update_deal,
)
from backend.core.domains.packs.business.actions import ACTIONS as BUSINESS_ACTIONS
from backend.core.domains.packs.business.local_deals import (
    LOCAL_DEALS_ENV_VAR,
    _coerce_update_value,
    update_local_deal,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    target = tmp_path / "business_deals.json"
    monkeypatch.setenv(LOCAL_DEALS_ENV_VAR, str(target))
    monkeypatch.delenv("HUBSPOT_API_KEY", raising=False)
    monkeypatch.delenv("PIPEDRIVE_API_KEY", raising=False)
    return target


@pytest.fixture(autouse=True)
def _spy_meeet(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    captured: list[tuple[str, dict[str, Any]]] = []

    class _Spy:
        async def emit(self, kind: str, payload: dict[str, Any]) -> None:
            captured.append((kind, dict(payload)))

    monkeypatch.setattr(
        "backend.core.domains.packs.business.local_deals.get_client",
        lambda: _Spy(),
    )
    return captured


@pytest.fixture(autouse=True)
def _stub_council(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable the council so daily_brief stays fast and offline."""

    monkeypatch.setattr(
        "backend.core.domains.packs.business.actions.get_council",
        lambda: _NoCouncil(),
    )


class _NoCouncil:
    async def deliberate(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("council should be disabled in tests")


def _run(coro):
    return asyncio.run(coro)


def _seed_deal(**overrides: Any) -> str:
    base = {
        "name": "Acme Q3",
        "amount": 12_000,
        "stage": "discovery",
        "council": False,
    }
    base.update(overrides)
    out = _run(log_deal(base))
    assert out["ok"] is True
    return out["deal_id"]


# ---------------------------------------------------------------- _coerce_update_value

def test_coerce_update_value_name_required() -> None:
    with pytest.raises(ValueError, match="name_required"):
        _coerce_update_value("name", "")
    with pytest.raises(ValueError, match="name_required"):
        _coerce_update_value("name", "   ")


def test_coerce_update_value_name_strips() -> None:
    assert _coerce_update_value("name", "  Acme  ") == "Acme"


def test_coerce_update_value_amount_clamps_negative() -> None:
    assert _coerce_update_value("amount", -5) == 0.0


def test_coerce_update_value_amount_falls_back_on_garbage() -> None:
    assert _coerce_update_value("amount", "abc") == 0.0


def test_coerce_update_value_stage_falls_back() -> None:
    assert _coerce_update_value("stage", "Won") == "won"
    assert _coerce_update_value("stage", "totally invalid") == "discovery"


def test_coerce_update_value_optional_string_blank_clears_to_none() -> None:
    assert _coerce_update_value("owner", "") is None


def test_coerce_update_value_optional_string_none_means_skip() -> None:
    assert _coerce_update_value("notes", None) is ...


def test_coerce_update_value_optional_string_strips_value() -> None:
    assert _coerce_update_value("next_step", "  call back  ") == "call back"


# ---------------------------------------------------------------- update_local_deal

def test_update_local_deal_changes_stage_and_emits(
    _isolated_env: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    aid = _seed_deal()
    _spy_meeet.clear()

    out = _run(
        update_local_deal(
            aid,
            updates={"stage": "won"},
            now="2030-01-02T03:04:05Z",
        )
    )
    assert out["stage"] == "won"
    assert out["updated_at"] == "2030-01-02T03:04:05Z"
    assert out["unchanged"] is False
    assert out["changed_fields"] == ["stage"]

    on_disk = json.loads(_isolated_env.read_text(encoding="utf-8"))
    assert on_disk[0]["stage"] == "won"
    assert on_disk[0]["updated_at"] == "2030-01-02T03:04:05Z"

    assert _spy_meeet, "expected business.deal_updated event"
    kind, payload = _spy_meeet[-1]
    assert kind == "business.deal_updated"
    assert payload["id"] == aid
    assert payload["stage"] == "won"
    assert payload["changed_fields"] == ["stage"]
    assert payload["store_path"] == str(_isolated_env)


def test_update_local_deal_idempotent_no_event(
    _isolated_env: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    aid = _seed_deal()
    _spy_meeet.clear()
    out = _run(update_local_deal(aid, updates={"stage": "discovery"}))
    assert out["unchanged"] is True
    assert out["changed_fields"] == []
    assert "updated_at" not in out
    assert _spy_meeet == []


def test_update_local_deal_blank_optional_string_clears_field(
    _isolated_env: Path,
) -> None:
    aid = _seed_deal(owner="Sam")
    out = _run(update_local_deal(aid, updates={"owner": ""}))
    assert "owner" not in out
    assert out["changed_fields"] == ["owner"]


def test_update_local_deal_none_skips_optional_string(
    _isolated_env: Path,
) -> None:
    aid = _seed_deal(owner="Sam", next_step="call back")
    out = _run(update_local_deal(aid, updates={"owner": None, "stage": "won"}))
    assert out.get("owner") == "Sam"
    assert out["stage"] == "won"
    assert out["changed_fields"] == ["stage"]


def test_update_local_deal_unknown_id_raises(_isolated_env: Path) -> None:
    _seed_deal()
    with pytest.raises(KeyError, match="deal_not_found"):
        _run(update_local_deal("local-9999", updates={"stage": "won"}))


def test_update_local_deal_blank_id_raises(_isolated_env: Path) -> None:
    with pytest.raises(ValueError, match="deal_id_required"):
        _run(update_local_deal("   ", updates={"stage": "won"}))


def test_update_local_deal_no_updates_raises(_isolated_env: Path) -> None:
    aid = _seed_deal()
    with pytest.raises(ValueError, match="no_updates"):
        _run(update_local_deal(aid, updates={}))


def test_update_local_deal_blank_name_raises(_isolated_env: Path) -> None:
    aid = _seed_deal()
    with pytest.raises(ValueError, match="name_required"):
        _run(update_local_deal(aid, updates={"name": "   "}))


def test_update_local_deal_only_listed_fields_apply(_isolated_env: Path) -> None:
    aid = _seed_deal()
    out = _run(
        update_local_deal(
            aid,
            updates={"stage": "won", "should_be_ignored": "yes"},
        )
    )
    assert out["stage"] == "won"
    assert "should_be_ignored" not in out
    assert out["changed_fields"] == ["stage"]


# ---------------------------------------------------------------- update_deal action

def test_update_deal_action_happy_path(
    _isolated_env: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    aid = _seed_deal()
    _spy_meeet.clear()

    out = _run(
        update_deal(
            {
                "deal_id": aid,
                "stage": "won",
                "amount": 18_500,
                "next_step": "send invoice",
            }
        )
    )
    assert out["ok"] is True
    assert out["deal_id"] == aid
    assert out["unchanged"] is False
    assert set(out["changed_fields"]) == {"stage", "amount", "next_step"}
    deal = out["deal"]
    assert deal["stage"] == "won"
    assert deal["amount"] == 18_500
    assert deal["next_step"] == "send invoice"
    assert "unchanged" not in deal
    assert "changed_fields" not in deal
    assert out["store"] == "local"
    assert out["store_path"] == str(_isolated_env)
    assert _spy_meeet[-1][0] == "business.deal_updated"


def test_update_deal_action_missing_id() -> None:
    out = _run(update_deal({}))
    assert out == {"ok": False, "error": "deal_id_required"}


def test_update_deal_action_blank_id() -> None:
    out = _run(update_deal({"deal_id": "   ", "stage": "won"}))
    assert out == {"ok": False, "error": "deal_id_required"}


def test_update_deal_action_no_updates(_isolated_env: Path) -> None:
    aid = _seed_deal()
    out = _run(update_deal({"deal_id": aid}))
    assert out == {"ok": False, "error": "no_updates"}


def test_update_deal_action_unknown_id(_isolated_env: Path) -> None:
    _seed_deal()
    out = _run(update_deal({"deal_id": "local-9999", "stage": "won"}))
    assert out == {"ok": False, "error": "deal_not_found", "deal_id": "local-9999"}


def test_update_deal_action_idempotent_no_event(
    _isolated_env: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    aid = _seed_deal()
    _run(update_deal({"deal_id": aid, "stage": "won"}))
    _spy_meeet.clear()
    out = _run(update_deal({"deal_id": aid, "stage": "won"}))
    assert out["ok"] is True
    assert out["unchanged"] is True
    assert out["changed_fields"] == []
    assert _spy_meeet == []


def test_update_deal_action_validation_error_no_event(
    _isolated_env: Path,
    _spy_meeet: list[tuple[str, dict[str, Any]]],
) -> None:
    aid = _seed_deal()
    _spy_meeet.clear()
    out = _run(update_deal({"deal_id": aid, "name": "   "}))
    assert out == {"ok": False, "error": "name_required"}
    assert _spy_meeet == []


def test_update_deal_action_path_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(LOCAL_DEALS_ENV_VAR, raising=False)
    target = tmp_path / "explicit.json"
    log_resp = _run(
        log_deal(
            {
                "name": "Acme",
                "amount": 1,
                "stage": "discovery",
                "council": False,
                "store_path": str(target),
            }
        )
    )
    aid = log_resp["deal_id"]
    out = _run(
        update_deal(
            {
                "deal_id": aid,
                "stage": "won",
                "store_path": str(target),
            }
        )
    )
    assert out["ok"] is True
    assert out["store_path"] == str(target)
    rows = json.loads(target.read_text(encoding="utf-8"))
    assert rows[0]["stage"] == "won"


def test_update_deal_action_store_unwritable(
    monkeypatch: pytest.MonkeyPatch, _isolated_env: Path
) -> None:
    aid = _seed_deal()

    def _boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "backend.core.domains.packs.business.local_deals._atomic_write",
        _boom,
    )
    out = _run(update_deal({"deal_id": aid, "stage": "won"}))
    assert out["ok"] is False
    assert out["error"] == "local_store_unwritable"
    assert "disk full" in out["detail"]


def test_update_deal_action_clearing_optional_string(_isolated_env: Path) -> None:
    aid = _seed_deal(owner="Sam")
    out = _run(update_deal({"deal_id": aid, "owner": ""}))
    assert out["ok"] is True
    assert "owner" not in out["deal"]
    assert out["changed_fields"] == ["owner"]


# ---------------------------------------------------------------- daily_brief integration

def test_update_deal_then_daily_brief_reflects_won_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _isolated_env: Path
) -> None:
    monkeypatch.setenv("BUSINESS_DEALS_PATH", str(tmp_path / "missing_bundled.json"))
    monkeypatch.setenv("BUSINESS_KPI_PATH", str(tmp_path / "missing_kpi.json"))
    monkeypatch.setenv("CALENDAR_PATH", str(tmp_path / "missing_cal.json"))

    a = _seed_deal(name="Acme A", amount=1)
    b = _seed_deal(name="Acme B", amount=2)
    _run(update_deal({"deal_id": a, "stage": "won"}))

    out = _run(daily_brief({"council": False}))
    assert out["ok"] is True
    assert out["deals_total"] == 2
    assert out["deals_active"] == 1  # 'a' is now won
    assert out["deals_local_logged"] == 2
    action_ids = {step["deal_id"] for step in out["actions"]}
    assert b in action_ids
    assert a not in action_ids


# ---------------------------------------------------------------- ActionSpec wiring

def _spec_by_id(action_id: str):
    return next(spec for spec in BUSINESS_ACTIONS if spec.id == action_id)


def test_update_deal_spec_is_destructive_and_requires_id() -> None:
    spec = _spec_by_id("update_deal")
    assert spec.destructive is True
    assert spec.schema["required"] == ["deal_id"]
    assert "stage" in spec.schema["properties"]
    assert "amount" in spec.schema["properties"]
    assert (
        spec.schema["properties"]["stage"]["enum"]
        == [
            "discovery",
            "qualification",
            "proposal",
            "negotiation",
            "won",
            "lost",
        ]
    )
