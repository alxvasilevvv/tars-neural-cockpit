"""Local-first persistence for ``traders.place_alert``.

The cockpit operator configures a price alert; ``place_alert`` used to
return a hardcoded ``stub-0001`` and forget it on the next request.
That broke the audit trail and made the destructive-action policy gate
look like theatre — there was nothing on the other side of the
confirmation step.

This module persists each alert into a local JSON store so the operator
gets a durable receipt and a future ``list_alerts`` action can read
them back. Storage path defaults to ``~/.tars/traders_alerts.json``,
overridable via ``TARS_LOCAL_ALERTS_PATH`` or the ``path`` kwarg.

File contract
-------------

The store is a list of dicts shaped like::

    {
      "id": "local-alert-0007",
      "ticker": "BTC",
      "price": 65000.0,
      "direction": "above",        # one of above|below|cross_above|cross_below
      "note": "...",                # optional operator note
      "source": "manual",           # manual / playbook / external
      "created_at": "2026-05-01T12:34:56Z",
      "active": true                # always true on creation; future
                                    # ack/cancel flow will flip this
    }

Concurrency
-----------

Process-local lock + tmp+rename atomic write. Single-user / single-host
is the model TARS targets; multiple processes sharing the same home
dir will race but the atomic write keeps the file readable.

Events
------

Every successful append emits a ``traders.alert_placed`` meeet event so
the cost ledger / audit timeline picks it up.
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


log = logging.getLogger("tars.traders.local_alerts")


DEFAULT_LOCAL_ALERTS_PATH = "~/.tars/traders_alerts.json"
LOCAL_ALERTS_ENV_VAR = "TARS_LOCAL_ALERTS_PATH"
LOCAL_ID_PREFIX = "local-alert-"
_LOCAL_ID_RE = re.compile(r"^local-alert-(\d+)$")
_MAX_NUMERIC_ID = 9_999_999

VALID_DIRECTIONS: frozenset[str] = frozenset(
    {"above", "below", "cross_above", "cross_below"}
)
VALID_SOURCES: frozenset[str] = frozenset({"manual", "playbook", "external"})


_lock = threading.Lock()


@dataclass(frozen=True)
class LocalAlertRecord:
    """One row in the local alerts store."""

    id: str
    ticker: str
    price: float
    direction: str
    note: str | None = None
    source: str = "manual"
    created_at: str = ""
    active: bool = True
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "ticker": self.ticker,
            "price": self.price,
            "direction": self.direction,
            "source": self.source,
            "created_at": self.created_at,
            "active": self.active,
        }
        if self.note is not None:
            out["note"] = self.note
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


def resolve_local_alerts_path(override: str | os.PathLike[str] | None = None) -> Path:
    """Return the resolved on-disk path for the local alerts store."""

    if override:
        return Path(os.path.expanduser(str(override)))
    env = os.getenv(LOCAL_ALERTS_ENV_VAR)
    if env:
        return Path(os.path.expanduser(env))
    return Path(os.path.expanduser(DEFAULT_LOCAL_ALERTS_PATH))


def _read_existing(path: Path) -> list[dict[str, Any]]:
    """Load existing rows. Tolerates missing file or corrupted JSON."""

    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("local alerts store unreadable at %s: %s", path, exc)
        return []
    if not isinstance(raw, list):
        log.warning("local alerts store at %s is not a list; resetting", path)
        return []
    return [row for row in raw if isinstance(row, dict)]


def _atomic_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex[:8]}")
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.write("\n")
    os.replace(tmp, path)


def _next_local_id(rows: list[dict[str, Any]]) -> str:
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


def _coerce_ticker(ticker: Any) -> str:
    if not isinstance(ticker, str):
        raise ValueError("ticker_required")
    s = ticker.strip().upper()
    if not s:
        raise ValueError("ticker_required")
    return s


def _coerce_price(price: Any) -> float:
    try:
        val = float(price)
    except (TypeError, ValueError) as exc:
        raise ValueError("price_invalid") from exc
    if val <= 0 or val != val:  # reject 0, negative, NaN
        raise ValueError("price_invalid")
    return val


def _coerce_direction(direction: Any) -> str:
    if not isinstance(direction, str):
        raise ValueError("direction_invalid")
    s = direction.strip().lower()
    if s not in VALID_DIRECTIONS:
        raise ValueError("direction_invalid")
    return s


def _coerce_source(source: Any) -> str:
    if not isinstance(source, str):
        return "manual"
    s = source.strip().lower()
    if s in VALID_SOURCES:
        return s
    return "manual"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def append_local_alert(
    *,
    ticker: Any,
    price: Any,
    direction: Any,
    note: str | None = None,
    source: Any = "manual",
    path: str | os.PathLike[str] | None = None,
    now: str | None = None,
) -> LocalAlertRecord:
    """Append an alert to the local JSON store and return its record.

    Validation is strict: ``ticker`` must be non-empty, ``price`` must
    be a positive finite number, ``direction`` must be one of
    :data:`VALID_DIRECTIONS`. Validation errors raise :class:`ValueError`
    with a stable error code (``ticker_required``, ``price_invalid``,
    ``direction_invalid``) so callers can map them into HTTP envelopes.
    """

    tk = _coerce_ticker(ticker)
    pr = _coerce_price(price)
    dr = _coerce_direction(direction)
    src = _coerce_source(source)
    nt = note.strip() if isinstance(note, str) and note.strip() else None
    created_at = now or _utc_now_iso()

    target = resolve_local_alerts_path(path)

    with _lock:
        rows = _read_existing(target)
        new_id = _next_local_id(rows)
        record = LocalAlertRecord(
            id=new_id,
            ticker=tk,
            price=pr,
            direction=dr,
            note=nt,
            source=src,
            created_at=created_at,
            active=True,
        )
        rows.append(record.to_dict())
        _atomic_write(target, rows)

    client = get_client()
    await client.emit(
        "traders.alert_placed",
        {
            "id": record.id,
            "ticker": record.ticker,
            "price": record.price,
            "direction": record.direction,
            "source": record.source,
            "store_path": str(target),
        },
    )

    return record


def read_local_alerts(
    path: str | os.PathLike[str] | None = None,
    *,
    active_only: bool = False,
    ticker: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read alerts from the local store with optional filters.

    ``active_only`` filters out alerts whose ``active`` flag is
    explicitly ``False``. ``ticker`` filters case-insensitively.
    ``limit`` truncates to the most recent N entries (rows are
    appended chronologically so we slice from the tail).
    """

    target = resolve_local_alerts_path(path)
    rows = _read_existing(target)
    out = list(rows)
    if active_only:
        out = [r for r in out if r.get("active") is not False]
    if ticker:
        wanted = ticker.strip().upper()
        if wanted:
            out = [r for r in out if str(r.get("ticker", "")).upper() == wanted]
    if isinstance(limit, int) and limit > 0:
        out = out[-limit:]
    return out


__all__ = [
    "DEFAULT_LOCAL_ALERTS_PATH",
    "LOCAL_ALERTS_ENV_VAR",
    "LOCAL_ID_PREFIX",
    "VALID_DIRECTIONS",
    "VALID_SOURCES",
    "LocalAlertRecord",
    "append_local_alert",
    "read_local_alerts",
    "resolve_local_alerts_path",
]
