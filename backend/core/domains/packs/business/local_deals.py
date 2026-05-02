"""Local-first persistence for ``business.log_deal``.

When neither HubSpot nor Pipedrive credentials are available the
``business.log_deal`` action used to return a hardcoded stub id and
forget the deal. That breaks the closed loop with ``daily_brief``,
which reads operator deals from a JSON file on disk.

This module persists logged deals into a local JSON store so the
brief can pick them up the next morning, and so the operator has a
durable record before plugging in a real CRM.

File contract
-------------

The store is a list of dicts compatible with the existing
``data/business_deals.json`` shape (`id`, `name`, `amount`, `stage`,
`owner`, `next_step`, `due` …). New rows are appended; existing rows
are never rewritten in place so a simultaneous reader from
``daily_brief`` cannot see torn writes.

Default path: ``~/.tars/business_deals.json`` (override via
``TARS_LOCAL_DEALS_PATH`` env var or the ``path`` kwarg on
``append_local_deal``).

Concurrency
-----------

We use a process-local lock + atomic tmp+rename. That's enough for
the single-user / single-host model TARS targets today; if multiple
TARS processes share a home dir they'll race, but the tmp+rename
keeps the file readable at all times.

Events
------

Every successful append emits a ``business.deal_logged`` meeet event
(see the cross-cutting `meeet × TARS` adapter rule) so the cost
ledger and audit timeline get a row.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ....meeet import get_client


log = logging.getLogger("tars.business.local_deals")


DEFAULT_LOCAL_DEALS_PATH = "~/.tars/business_deals.json"
LOCAL_DEALS_ENV_VAR = "TARS_LOCAL_DEALS_PATH"
LOCAL_ID_PREFIX = "local-"
_LOCAL_ID_RE = re.compile(r"^local-(\d+)$")
_MAX_NUMERIC_ID = 9_999_999

_VALID_STAGES: frozenset[str] = frozenset(
    {
        "discovery",
        "qualification",
        "proposal",
        "negotiation",
        "won",
        "lost",
    }
)


_lock = threading.Lock()


@dataclass(frozen=True)
class LocalDealRecord:
    """One row in the local deals store."""

    id: str
    name: str
    amount: float
    stage: str
    owner: str | None = None
    next_step: str | None = None
    due: str | None = None
    notes: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "stage": self.stage,
        }
        if self.owner is not None:
            out["owner"] = self.owner
        if self.next_step is not None:
            out["next_step"] = self.next_step
        if self.due is not None:
            out["due"] = self.due
        if self.notes is not None:
            out["notes"] = self.notes
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


def resolve_local_deals_path(override: str | os.PathLike[str] | None = None) -> Path:
    """Return the resolved on-disk path for the local deals store.

    Priority order: ``override`` arg > ``TARS_LOCAL_DEALS_PATH`` env
    var > ``~/.tars/business_deals.json``. ``~`` is always expanded.
    """

    if override:
        return Path(os.path.expanduser(str(override)))
    env = os.getenv(LOCAL_DEALS_ENV_VAR)
    if env:
        return Path(os.path.expanduser(env))
    return Path(os.path.expanduser(DEFAULT_LOCAL_DEALS_PATH))


def _read_existing(path: Path) -> list[dict[str, Any]]:
    """Load the existing deals list. Tolerates a missing file or
    corrupted JSON by treating both as 'empty'.
    """

    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("local deals store unreadable at %s: %s", path, exc)
        return []
    if not isinstance(raw, list):
        log.warning("local deals store at %s is not a list; resetting", path)
        return []
    return [row for row in raw if isinstance(row, dict)]


def _atomic_write(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write ``rows`` to ``path`` via tmp+rename.

    A simultaneous reader (``daily_brief``) sees either the old
    file or the new file but never a half-written one.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex[:8]}")
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.write("\n")
    os.replace(tmp, path)


def _next_local_id(rows: list[dict[str, Any]]) -> str:
    """Mint the next ``local-NNNN`` id, monotone over existing rows.

    Existing CRM ids (``deal-77``, ``d-7012``, …) are ignored — only
    rows whose id matches ``local-<digits>`` participate. The result
    is zero-padded to 4 digits for sort stability up to 9999, then
    grows naturally.
    """

    highest = 0
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, str):
            continue
        m = _LOCAL_ID_RE.match(rid)
        if not m:
            continue
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if n > highest:
            highest = n
    nxt = min(highest + 1, _MAX_NUMERIC_ID)
    return f"{LOCAL_ID_PREFIX}{nxt:04d}"


def _coerce_amount(amount: Any) -> float:
    if amount is None:
        return 0.0
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return 0.0
    if val < 0:
        return 0.0
    return val


def _coerce_stage(stage: Any) -> str:
    if not isinstance(stage, str):
        return "discovery"
    s = stage.strip().lower()
    if s in _VALID_STAGES:
        return s
    return "discovery"


_UPDATABLE_FIELDS: tuple[str, ...] = (
    "name",
    "amount",
    "stage",
    "owner",
    "next_step",
    "due",
    "notes",
)


def _coerce_update_value(field_name: str, value: Any) -> Any:
    """Coerce a user-supplied update value to its canonical shape.

    Returns ``...`` (Ellipsis) when the field should be left untouched
    (e.g. caller passed ``None`` for a non-stage / non-amount field
    that's still optional). Returns ``None`` to explicitly clear a
    field; returns the coerced value otherwise.
    """

    if field_name == "name":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name_required")
        return value.strip()
    if field_name == "amount":
        return _coerce_amount(value)
    if field_name == "stage":
        return _coerce_stage(value)
    # Optional string fields: blank/None means "don't touch".
    if value is None:
        return ...
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return value


async def update_local_deal(
    deal_id: str,
    *,
    updates: Mapping[str, Any] | None = None,
    path: str | os.PathLike[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Apply patch-style updates to an existing local deal row.

    Only fields in :data:`_UPDATABLE_FIELDS` may be patched. Values
    outside the schema are silently ignored — the cockpit must use
    the action contract. Returns the updated row as a dict on
    success, or raises :class:`KeyError` (``deal_not_found``) /
    :class:`ValueError` (``deal_id_required``, ``no_updates``,
    ``name_required``).

    Stamps ``updated_at`` (UTC ISO Z) on every change. If no field
    actually changes, the row is returned with ``unchanged=True``
    and *no* meeet event is emitted (idempotent).
    """

    if not isinstance(deal_id, str) or not deal_id.strip():
        raise ValueError("deal_id_required")
    aid = deal_id.strip()

    if not isinstance(updates, Mapping) or not updates:
        raise ValueError("no_updates")

    coerced: dict[str, Any] = {}
    for field_name in _UPDATABLE_FIELDS:
        if field_name not in updates:
            continue
        value = _coerce_update_value(field_name, updates[field_name])
        if value is ...:
            continue
        coerced[field_name] = value
    if not coerced:
        raise ValueError("no_updates")

    when = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    target = resolve_local_deals_path(path)

    changed_fields: list[str] = []
    updated_row: dict[str, Any]
    with _lock:
        rows = _read_existing(target)
        idx: int | None = None
        for i, row in enumerate(rows):
            if str(row.get("id") or "") == aid:
                idx = i
                break
        if idx is None:
            raise KeyError("deal_not_found")
        current = dict(rows[idx])
        for field_name, value in coerced.items():
            if current.get(field_name) != value:
                changed_fields.append(field_name)
                if value is None:
                    current.pop(field_name, None)
                else:
                    current[field_name] = value
        if changed_fields:
            current["updated_at"] = when
            rows[idx] = current
            _atomic_write(target, rows)
        updated_row = current

    if changed_fields:
        client = get_client()
        await client.emit(
            "business.deal_updated",
            {
                "id": aid,
                "name": updated_row.get("name"),
                "stage": updated_row.get("stage"),
                "changed_fields": list(changed_fields),
                "store_path": str(target),
            },
        )

    out = dict(updated_row)
    out["unchanged"] = not changed_fields
    out["changed_fields"] = list(changed_fields)
    return out


_TERMINAL_STAGES: frozenset[str] = frozenset({"won", "lost"})


def read_local_deals(
    path: str | os.PathLike[str] | None = None,
    *,
    active_only: bool = False,
    stage: str | None = None,
    owner: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read deals from the local store with optional filters.

    ``active_only`` excludes rows whose ``stage`` is in
    ``{"won", "lost"}``. ``stage`` filters to a single stage value
    (case-insensitive, coerced via :func:`_coerce_stage`). ``owner``
    filters case-insensitively on the row's ``owner`` field.
    ``limit`` slices the most recent N entries (rows are appended
    chronologically).
    """

    target = resolve_local_deals_path(path)
    rows = _read_existing(target)
    out = list(rows)
    if active_only:
        out = [
            r
            for r in out
            if str(r.get("stage") or "").lower() not in _TERMINAL_STAGES
        ]
    if stage:
        wanted_stage = _coerce_stage(stage)
        out = [r for r in out if str(r.get("stage") or "").lower() == wanted_stage]
    if owner:
        wanted_owner = owner.strip().lower()
        if wanted_owner:
            out = [
                r
                for r in out
                if isinstance(r.get("owner"), str)
                and r["owner"].strip().lower() == wanted_owner
            ]
    if isinstance(limit, int) and limit > 0:
        out = out[-limit:]
    return out


async def append_local_deal(
    *,
    name: str,
    amount: Any = 0.0,
    stage: Any = "discovery",
    owner: str | None = None,
    next_step: str | None = None,
    due: str | None = None,
    notes: str | None = None,
    path: str | os.PathLike[str] | None = None,
) -> LocalDealRecord:
    """Append a deal to the local JSON store and return its record.

    ``name`` is required and must be non-empty after stripping.
    ``amount`` is coerced to float (negative values clamp to 0).
    ``stage`` falls back to ``discovery`` when unrecognised so we
    never crash on operator typos. The returned record carries the
    minted ``local-NNNN`` id.
    """

    nm = str(name or "").strip()
    if not nm:
        raise ValueError("name_required")

    record = LocalDealRecord(
        id="",
        name=nm,
        amount=_coerce_amount(amount),
        stage=_coerce_stage(stage),
        owner=owner.strip() if isinstance(owner, str) and owner.strip() else None,
        next_step=(
            next_step.strip()
            if isinstance(next_step, str) and next_step.strip()
            else None
        ),
        due=due.strip() if isinstance(due, str) and due.strip() else None,
        notes=notes.strip() if isinstance(notes, str) and notes.strip() else None,
    )

    target = resolve_local_deals_path(path)

    with _lock:
        rows = _read_existing(target)
        new_id = _next_local_id(rows)
        record = LocalDealRecord(
            id=new_id,
            name=record.name,
            amount=record.amount,
            stage=record.stage,
            owner=record.owner,
            next_step=record.next_step,
            due=record.due,
            notes=record.notes,
        )
        rows.append(record.to_dict())
        _atomic_write(target, rows)

    client = get_client()
    await client.emit(
        "business.deal_logged",
        {
            "id": record.id,
            "name": record.name,
            "amount": record.amount,
            "stage": record.stage,
            "store_path": str(target),
            "crm_pushed": False,
        },
    )

    return record


__all__ = [
    "DEFAULT_LOCAL_DEALS_PATH",
    "LOCAL_DEALS_ENV_VAR",
    "LOCAL_ID_PREFIX",
    "LocalDealRecord",
    "append_local_deal",
    "read_local_deals",
    "resolve_local_deals_path",
    "update_local_deal",
]
