"""Action handlers for the MLM pack.

Real-ish adapters backed by an SQLite downline DB
(``~/.tars/downline.sqlite``) that self-seeds from the legacy
``data/mlm_network.csv`` on first run. Override the DB path with
``MLM_DB_PATH``; override the seed CSV with ``MLM_NETWORK_PATH``.

``score_recruit`` is a deterministic scorer over the local downline
DB (see ``scoring.py``); falls back to a stable SHA-256-derived
score for unknown handles. ``generate_post`` is a deterministic
multi-channel / multi-language drafter (see ``post_drafter.py``).
``tg_outreach_draft`` is a deterministic Telegram drafter (see
``tg_outreach.py``).
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...base import ActionSpec
from ....meeet import get_client
from .db import get_downline_db
from .post_drafter import (
    KNOWN_CHANNELS as POST_CHANNELS,
    KNOWN_FORMATS as POST_FORMATS,
    KNOWN_LANGUAGES as POST_LANGUAGES,
    KNOWN_TONES as POST_TONES,
    draft_post,
)
from .scoring import (
    compose_score,
    score_for_unknown_handle,
    signals_for_member,
)
from .tg_outreach import (
    KNOWN_INTENTS as TG_OUTREACH_INTENTS,
    KNOWN_LANGUAGES as TG_OUTREACH_LANGUAGES,
    KNOWN_TONES as TG_OUTREACH_TONES,
    tg_outreach_draft,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_NETWORK_PATH = _REPO_ROOT / "data" / "mlm_network.csv"


def _resolve(path_arg: str | None) -> Path:
    if path_arg:
        return Path(path_arg).expanduser()
    env = os.getenv("MLM_NETWORK_PATH")
    if env:
        return Path(env).expanduser()
    return _DEFAULT_NETWORK_PATH


def _parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Final fallback: ``fromisoformat`` handles microseconds + offsets.
    try:
        # Python <3.11 doesn't accept "Z"; replace with +00:00.
        cleaned = s.replace("Z", "+00:00")
        out = datetime.fromisoformat(cleaned)
        if out.tzinfo is None:
            out = out.replace(tzinfo=timezone.utc)
        return out
    except ValueError:
        return None


def _load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


def _depth_of(handle: str, parent_of: dict[str, str], cap: int = 32) -> int:
    """Depth of ``handle`` from a root (no sponsor). Returns 0 for roots."""
    depth = 0
    cur = handle
    seen: set[str] = set()
    while True:
        sponsor = (parent_of.get(cur) or "").strip()
        if not sponsor:
            return depth
        if sponsor in seen or depth > cap:
            return depth
        seen.add(sponsor)
        depth += 1
        cur = sponsor


async def _load_rows_from_db_or_csv(
    args: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]] | dict[str, Any]:
    """Try the SQLite DB first; fall back to CSV.

    Returns ``(rows, source_meta)`` on success, or a structured error
    dict on failure (the caller forwards it as the action response).
    """

    explicit_csv_arg = bool(args.get("path"))
    if not explicit_csv_arg:
        try:
            db = get_downline_db()
            await db.ensure_seeded()
            members = await db.list_members()
        except Exception as exc:
            return {
                "ok": False,
                "error": "downline_db_error",
                "detail": str(exc),
            }
        if members:
            rows = [
                {
                    "handle": m.handle,
                    "sponsor": m.sponsor or "",
                    "joined_at": m.joined_at or "",
                    "last_active_at": m.last_active_at or "",
                    "rank": m.rank or "",
                    "volume_usd": str(m.volume_usd or 0),
                }
                for m in members
            ]
            return rows, {"source": "sqlite", "path": db.db_path}

    # CSV fallback (or explicit per-call path).
    path = _resolve(str(args.get("path") or "") or None)
    if not path.exists():
        return {
            "ok": False,
            "error": "network_file_missing",
            "path": str(path),
            "hint": (
                "drop a CSV at data/mlm_network.csv, set MLM_NETWORK_PATH, "
                "or seed the SQLite DB at ~/.tars/downline.sqlite"
            ),
        }
    try:
        rows = _load(path)
    except Exception as exc:
        return {"ok": False, "error": "network_parse_error", "detail": str(exc)}
    return rows, {"source": "csv", "path": str(path)}


async def downline_snapshot(args: Mapping[str, Any]) -> Mapping[str, Any]:
    requested_depth = int(args.get("depth") or 12)
    requested_depth = max(1, min(requested_depth, 32))
    active_window_days = int(args.get("active_window_days") or 14)

    loaded = await _load_rows_from_db_or_csv(args)
    if isinstance(loaded, dict):
        return loaded
    rows, source_meta = loaded

    parent_of = {r.get("handle", ""): r.get("sponsor", "") for r in rows}
    now = datetime.now(timezone.utc)

    by_rank: dict[str, int] = defaultdict(int)
    by_depth: dict[int, int] = defaultdict(int)
    active = 0
    dormant = 0
    volume_total = 0.0
    members: list[dict[str, Any]] = []

    for r in rows:
        handle = (r.get("handle") or "").strip()
        if not handle:
            continue
        depth = _depth_of(handle, parent_of)
        if depth > requested_depth:
            continue
        rank = (r.get("rank") or "starter").strip().lower()
        try:
            volume = float(r.get("volume_usd") or 0)
        except ValueError:
            volume = 0.0
        last_active = _parse_date(r.get("last_active_at") or "")
        is_active = bool(
            last_active
            and (now - last_active).days <= active_window_days
        )
        if is_active:
            active += 1
        else:
            dormant += 1

        volume_total += volume
        by_rank[rank] += 1
        by_depth[depth] += 1

        members.append(
            {
                "handle": handle,
                "sponsor": (r.get("sponsor") or "").strip() or None,
                "depth": depth,
                "rank": rank,
                "volume_usd": volume,
                "last_active_at": (
                    last_active.isoformat() if last_active else None
                ),
                "active": is_active,
            }
        )

    return {
        "ok": True,
        "depth": requested_depth,
        "active_window_days": active_window_days,
        "total": len(members),
        "active": active,
        "dormant": dormant,
        "volume_usd": round(volume_total, 2),
        "ranks": dict(sorted(by_rank.items(), key=lambda kv: -kv[1])),
        "by_depth": {str(k): v for k, v in sorted(by_depth.items())},
        "members": members,
        "source": source_meta["source"],
        "path": source_meta["path"],
    }


_UPDATABLE_MEMBER_FIELDS: tuple[str, ...] = (
    "sponsor",
    "rank",
    "joined_at",
    "last_active_at",
    "volume_usd",
    "notes",
)


async def update_member(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Patch an existing member by handle.

    Args:
      ``handle``: required.
      Any of ``sponsor / rank / joined_at / last_active_at / volume_usd
      / notes``: passed through after coercion. Pass ``""`` for an
      optional string to clear it; omit a field to leave it untouched.
      ``handle`` itself cannot be patched.

    Returns ``{ok: True, handle, member, unchanged, changed_fields,
    db_path}`` on success, or ``{ok: False, error}`` with one of:
    ``handle_required``, ``no_updates``, ``volume_invalid``,
    ``member_not_found``, ``invalid_ts``.
    """

    handle = args.get("handle")
    if not isinstance(handle, str) or not handle.strip():
        return {"ok": False, "error": "handle_required"}

    updates: dict[str, Any] = {}
    for f in _UPDATABLE_MEMBER_FIELDS:
        if f in args:
            updates[f] = args[f]
    if not updates:
        return {"ok": False, "error": "no_updates"}

    for ts_field in ("joined_at", "last_active_at"):
        if ts_field in updates:
            value = updates[ts_field]
            if isinstance(value, str) and value.strip():
                if _parse_date(value) is None:
                    return {
                        "ok": False,
                        "error": "invalid_ts",
                        "field": ts_field,
                        "ts": value,
                    }

    db = get_downline_db()
    await db.ensure_seeded()
    try:
        member, changed = await db.update_member(handle, updates)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if member is None:
        return {
            "ok": False,
            "error": "member_not_found",
            "handle": handle.strip(),
        }

    if changed:
        client = get_client()
        await client.emit(
            "mlm.member_updated",
            {
                "handle": member.handle,
                "changed_fields": list(changed),
                "rank": member.rank,
                "db_path": db.db_path,
            },
        )

    return {
        "ok": True,
        "handle": handle.strip(),
        "member": member.to_dict(),
        "unchanged": not changed,
        "changed_fields": list(changed),
        "db_path": db.db_path,
    }


async def list_members(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read members from the downline DB with optional filters.

    Args:
      ``sponsor``: optional case-insensitive equality filter.
      ``rank``: optional case-insensitive equality filter.
      ``recent_days``: optional positive int. Keeps only members
        with ``last_active_at`` within this many days of "now".
      ``limit``: optional positive int (cap at 1000).

    Returns ``{ok, count, members, db_path, filters, summary}``.
    The ``summary`` block carries `by_rank` and `total_volume_usd`
    rollups so the cockpit can render a sidecar without a second
    pass.
    """

    db = get_downline_db()
    await db.ensure_seeded()

    sponsor_arg = args.get("sponsor")
    sponsor = (
        sponsor_arg.strip()
        if isinstance(sponsor_arg, str) and sponsor_arg.strip()
        else None
    )
    rank_arg = args.get("rank")
    rank = (
        rank_arg.strip()
        if isinstance(rank_arg, str) and rank_arg.strip()
        else None
    )

    recent_arg = args.get("recent_days")
    if isinstance(recent_arg, bool):
        recent_days: int | None = None
    elif isinstance(recent_arg, int) and recent_arg > 0:
        recent_days = recent_arg
    else:
        recent_days = None

    limit_arg = args.get("limit")
    if isinstance(limit_arg, bool):
        limit: int | None = None
    elif isinstance(limit_arg, int) and limit_arg > 0:
        limit = min(limit_arg, 1000)
    else:
        limit = None

    members = await db.list_members(
        sponsor=sponsor,
        rank=rank,
        recent_days=recent_days,
        limit=limit,
    )

    by_rank: dict[str, int] = {}
    total_volume = 0.0
    for m in members:
        rk = (m.rank or "").lower()
        if rk:
            by_rank[rk] = by_rank.get(rk, 0) + 1
        try:
            total_volume += float(m.volume_usd or 0.0)
        except (TypeError, ValueError):
            pass

    return {
        "ok": True,
        "count": len(members),
        "members": [m.to_dict() for m in members],
        "db_path": db.db_path,
        "filters": {
            "sponsor": sponsor.lower() if sponsor else None,
            "rank": rank.lower() if rank else None,
            "recent_days": recent_days,
            "limit": limit,
        },
        "summary": {
            "by_rank": by_rank,
            "total_volume_usd": round(total_volume, 2),
        },
    }


async def add_member(args: Mapping[str, Any]) -> Mapping[str, Any]:
    handle = str(args.get("handle") or "").strip()
    if not handle:
        return {"ok": False, "error": "handle_required"}
    sponsor = str(args.get("sponsor") or "").strip() or None
    rank = str(args.get("rank") or "starter").strip().lower() or "starter"
    joined_at = str(args.get("joined_at") or "").strip() or datetime.now(
        timezone.utc
    ).date().isoformat()
    notes = str(args.get("notes") or "").strip() or None
    try:
        volume = float(args.get("volume_usd") or 0.0)
    except (TypeError, ValueError):
        volume = 0.0

    db = get_downline_db()
    await db.ensure_seeded()
    if sponsor:
        existing_sponsor = await db.get(sponsor)
        if existing_sponsor is None:
            return {
                "ok": False,
                "error": "sponsor_not_found",
                "sponsor": sponsor,
            }

    outcome = await db.upsert(
        {
            "handle": handle,
            "sponsor": sponsor,
            "rank": rank,
            "joined_at": joined_at,
            "last_active_at": joined_at,
            "volume_usd": volume,
            "notes": notes,
        },
        conflict_strategy=str(args.get("on_conflict") or "update"),
    )
    member = await db.get(handle)
    return {
        "ok": True,
        "outcome": outcome,
        "member": member.to_dict() if member else None,
        "db_path": db.db_path,
    }


async def log_activity(args: Mapping[str, Any]) -> Mapping[str, Any]:
    handle = str(args.get("handle") or "").strip()
    if not handle:
        return {"ok": False, "error": "handle_required"}
    ts_arg = str(args.get("ts") or "").strip() or None
    if ts_arg:
        if _parse_date(ts_arg) is None:
            return {"ok": False, "error": "invalid_ts", "ts": ts_arg}
    try:
        volume_delta = float(args.get("volume_delta") or 0.0)
    except (TypeError, ValueError):
        volume_delta = 0.0

    db = get_downline_db()
    await db.ensure_seeded()
    updated = await db.log_activity(
        handle, ts=ts_arg, volume_delta=volume_delta
    )
    if updated is None:
        return {"ok": False, "error": "member_not_found", "handle": handle}
    return {
        "ok": True,
        "handle": handle,
        "ts": updated.last_active_at,
        "volume_usd": updated.volume_usd,
        "member": updated.to_dict(),
        "db_path": db.db_path,
    }


async def score_recruit(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Score a candidate against the local downline.

    When ``handle`` exists in the downline DB the score is the
    weighted composition of recency / volume / rank / tenure
    signals (``model="downline-v1"``). When the handle is unknown
    we fall back to a stable SHA-256 hash mapped onto ``[0.40,
    0.95]`` (``model="heuristic-v1"``) so the cockpit gets a
    deterministic number across machines and process restarts.

    See :mod:`backend.core.domains.packs.mlm.scoring` for the
    arithmetic. The action surface stays stable: ``score`` is the
    composite, ``fit_signals`` / ``risk_signals`` are short
    operator-facing strings derived from the components.
    """

    handle = str(args.get("handle", "")).strip()
    if not handle:
        return {"ok": False, "error": "handle_required"}

    db = get_downline_db()
    try:
        await db.ensure_seeded()
    except Exception:
        # Seed failures shouldn't break scoring — we'll just take
        # the unknown-handle branch.
        pass

    member = None
    try:
        member = await db.get(handle)
    except Exception:
        member = None

    if member is not None:
        signals = signals_for_member(member)
        score = compose_score(signals)
        return {
            "ok": True,
            "handle": handle,
            "score": score,
            "fit_signals": list(signals.fit),
            "risk_signals": list(signals.risk),
            "signals": signals.to_dict(),
            "model": "downline-v1",
            "source": "downline_db",
            "rank": signals.rank_label,
            "volume_usd": signals.volume_usd,
            "days_silent": signals.days_silent,
        }

    signals = score_for_unknown_handle(handle)
    score = compose_score(signals)
    return {
        "ok": True,
        "handle": handle,
        "score": score,
        "fit_signals": list(signals.fit),
        "risk_signals": list(signals.risk),
        "signals": signals.to_dict(),
        "model": "heuristic-v1",
        "source": "stable_hash",
        "hint": (
            "handle not found in local downline — score is a stable "
            "SHA-256-derived placeholder. Add the member via "
            "mlm.add_member to get real signals."
        ),
    }


async def generate_post(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Draft a channel-appropriate piece of content for the operator.

    Backed by :mod:`backend.core.domains.packs.mlm.post_drafter`.
    All knobs are optional (channel / format / tone / language /
    topic / cta) and unknown enum values fall back to defaults so
    existing playbooks ride through unchanged. Output includes
    ``draft``, ``cta``, ``hashtags``, ``char_count``,
    ``word_count`` so the cockpit can preview length budgets per
    platform.

    Validation: explicit but unknown ``channel`` strings still
    return ``{ok=False, error="unsupported_channel"}`` to keep the
    pre-existing cockpit safety net (the playbook YAML schema also
    pins it).
    """

    channel_arg = args.get("channel")
    if channel_arg is not None:
        channel_str = str(channel_arg).strip().lower()
        if channel_str and channel_str not in POST_CHANNELS:
            return {
                "ok": False,
                "error": "unsupported_channel",
                "channel": channel_str,
                "supported": list(POST_CHANNELS),
            }

    draft = draft_post(args)

    client = get_client()
    await client.emit(
        "mlm.post_drafted",
        {
            "channel": draft.channel,
            "format": draft.format,
            "tone": draft.tone,
            "language": draft.language,
            "topic": draft.topic,
            "char_count": draft.char_count,
            "word_count": draft.word_count,
        },
    )

    payload: dict[str, Any] = {
        "ok": True,
        **draft.to_dict(),
    }
    return payload


async def retention_alert(args: Mapping[str, Any]) -> Mapping[str, Any]:
    threshold_days = int(args.get("threshold_days") or 30)
    loaded = await _load_rows_from_db_or_csv(args)
    if isinstance(loaded, dict):
        return loaded
    rows, source_meta = loaded

    now = datetime.now(timezone.utc)
    at_risk: list[dict[str, Any]] = []
    for r in rows:
        last_active = _parse_date(r.get("last_active_at") or "")
        if last_active is None:
            continue
        days = (now - last_active).days
        if days >= threshold_days:
            at_risk.append(
                {
                    "handle": (r.get("handle") or "").strip(),
                    "sponsor": (r.get("sponsor") or "").strip() or None,
                    "rank": (r.get("rank") or "").strip(),
                    "last_active_at": last_active.isoformat(),
                    "days_silent": days,
                    "reason": "no activity in window",
                }
            )
    at_risk.sort(key=lambda d: d.get("days_silent", 0), reverse=True)
    return {
        "ok": True,
        "threshold_days": threshold_days,
        "at_risk": at_risk,
        "checked_at": now.isoformat(),
        "source": source_meta["source"],
        "path": source_meta["path"],
    }


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="downline_snapshot",
        name="Downline snapshot",
        description="Snapshot of network depth, activity and ranks from the local CSV.",
        handler=downline_snapshot,
        schema={
            "type": "object",
            "properties": {
                "depth": {"type": "integer", "minimum": 1, "maximum": 32},
                "active_window_days": {"type": "integer", "minimum": 1, "maximum": 365},
                "path": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="score_recruit",
        name="Score recruit",
        description="Score the fit of a candidate by public profile signals.",
        handler=score_recruit,
        schema={
            "type": "object",
            "properties": {"handle": {"type": "string"}},
            "required": ["handle"],
        },
    ),
    ActionSpec(
        id="generate_post",
        name="Generate post",
        description=(
            "Draft a channel-appropriate piece of content. "
            "Deterministic: same args always render the same draft. "
            "Supports ig / tg / wa / linkedin × post / story / reel "
            "/ dm × warm / professional / urgent / celebratory × "
            "en / ru / es. Emits 'mlm.post_drafted' on every call."
        ),
        handler=generate_post,
        schema={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": list(POST_CHANNELS),
                },
                "format": {
                    "type": "string",
                    "enum": list(POST_FORMATS),
                },
                "tone": {
                    "type": "string",
                    "enum": list(POST_TONES),
                },
                "language": {
                    "type": "string",
                    "enum": list(POST_LANGUAGES),
                },
                "topic": {"type": "string"},
                "cta": {
                    "type": "string",
                    "description": (
                        "Optional explicit call-to-action; falls back "
                        "to a tone-appropriate default."
                    ),
                },
            },
            "required": ["channel"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="retention_alert",
        name="Retention alert",
        description="Find members going quiet beyond the threshold and explain.",
        handler=retention_alert,
        schema={
            "type": "object",
            "properties": {
                "threshold_days": {"type": "integer", "minimum": 1, "maximum": 365},
                "path": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="add_member",
        name="Add downline member",
        description=(
            "Insert a new member into the SQLite downline DB. The "
            "sponsor must already exist."
        ),
        handler=add_member,
        schema={
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "sponsor": {"type": "string"},
                "rank": {
                    "type": "string",
                    "enum": ["starter", "bronze", "silver", "gold", "platinum"],
                },
                "joined_at": {"type": "string", "format": "date"},
                "volume_usd": {"type": "number", "minimum": 0},
                "notes": {"type": "string"},
                "on_conflict": {
                    "type": "string",
                    "enum": ["update", "skip"],
                },
            },
            "required": ["handle"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="log_activity",
        name="Log activity",
        description="Stamp a member's last_active_at and add to volume.",
        handler=log_activity,
        schema={
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "ts": {"type": "string"},
                "volume_delta": {"type": "number"},
            },
            "required": ["handle"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="update_member",
        name="Update downline member",
        description=(
            "Patch a previously-added member by handle. Pass any subset "
            "of sponsor / rank / joined_at / last_active_at / volume_usd "
            "/ notes; omitted fields are untouched. Pass an empty string "
            "for an optional string field to clear it. handle itself is "
            "never patchable. Idempotent: a no-op patch returns "
            "unchanged=True and emits no event. Stamps updated_at on "
            "every change. Emits an mlm.member_updated meeet event "
            "listing changed_fields. Marked destructive so the policy "
            "gate routes the call through confirmation."
        ),
        handler=update_member,
        schema={
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "sponsor": {"type": "string"},
                "rank": {
                    "type": "string",
                    "enum": ["starter", "bronze", "silver", "gold", "platinum"],
                },
                "joined_at": {"type": "string"},
                "last_active_at": {"type": "string"},
                "volume_usd": {"type": "number", "minimum": 0},
                "notes": {"type": "string"},
            },
            "required": ["handle"],
        },
        destructive=True,
    ),
    ActionSpec(
        id="list_members",
        name="List downline members",
        description=(
            "Read members from the SQLite downline DB with optional "
            "filters (sponsor / rank / recent_days / limit) and "
            "pre-computed rollups (by_rank, total_volume_usd) so the "
            "cockpit can render a sidecar without a second pass. "
            "Read-only; no policy gate required."
        ),
        handler=list_members,
        schema={
            "type": "object",
            "properties": {
                "sponsor": {"type": "string"},
                "rank": {
                    "type": "string",
                    "enum": ["starter", "bronze", "silver", "gold", "platinum"],
                },
                "recent_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3650,
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
        },
    ),
    ActionSpec(
        id="tg_outreach_draft",
        name="Telegram outreach draft",
        description=(
            "Deterministic Telegram outreach drafter. Generates a "
            "markdown + plain-text draft for an intent (welcome, "
            "checkin, winback, recruit, celebrate, upsell), tone, "
            "and language. Never auto-sends; preview only."
        ),
        handler=tg_outreach_draft,
        schema={
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": list(TG_OUTREACH_INTENTS),
                },
                "name": {"type": "string"},
                "tone": {
                    "type": "string",
                    "enum": list(TG_OUTREACH_TONES),
                },
                "language": {
                    "type": "string",
                    "enum": list(TG_OUTREACH_LANGUAGES),
                },
                "cta": {"type": "string"},
                "signature": {"type": "string"},
            },
            "required": ["intent"],
        },
    ),
)
