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
    "resolve_local_deals_path",
]
