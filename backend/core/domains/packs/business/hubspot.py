"""Read-only HubSpot CRM adapter.

Backs the ``business.hubspot_pull_pipeline`` action with a
deterministic GET against
``api.hubapi.com/crm/v3/objects/deals``. Returns a normalised
pipeline shape (one row per deal, derived ``stage_label`` /
``amount_usd``) plus an opaque ``next_cursor`` for HubSpot's
``after`` pagination.

Auth comes from the vault key ``HUBSPOT_API_KEY`` (a HubSpot
"private app" access token). When the key is missing we return
``{"ok": False, "error": "auth_missing", ...}`` — the action stays
non-destructive so the operator can preview the contract before
plugging in a real key.

We emit ``integration.hubspot.deals_list`` events
(``request`` / ``completed`` / ``error``) per the
``meeet × TARS`` adapter rule in IDEAS.md so the cost ledger and
observability layer see real-adapter calls.

The adapter is **stdlib-only** (uses
:mod:`backend.core.domains._http`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping

from backend.core.vault import get_secret

from ..._http import NetworkError, get_json
from ....meeet import get_client


log = logging.getLogger("tars.business.hubspot")


DEALS_URL = "https://api.hubapi.com/crm/v3/objects/deals"

DEFAULT_LIMIT = 25
MAX_LIMIT = 100  # HubSpot caps page size at 100 for the deals endpoint.

# Properties we care about. Anything else HubSpot returns is dropped on
# the floor — the action contract stays stable even if the operator
# enables extra columns inside HubSpot.
DEFAULT_PROPERTIES: tuple[str, ...] = (
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "closedate",
    "createdate",
    "hs_lastmodifieddate",
)

# HubSpot's built-in default pipeline labels. We keep this map small and
# explicit so unknown stage ids never mask data — they pass through as
# the raw id.
DEFAULT_STAGE_LABELS: Mapping[str, str] = {
    "appointmentscheduled": "Appointment scheduled",
    "qualifiedtobuy": "Qualified to buy",
    "presentationscheduled": "Presentation scheduled",
    "decisionmakerboughtin": "Decision-maker bought in",
    "contractsent": "Contract sent",
    "closedwon": "Closed won",
    "closedlost": "Closed lost",
}

ACTIVE_STAGE_IDS: frozenset[str] = frozenset(
    {
        "appointmentscheduled",
        "qualifiedtobuy",
        "presentationscheduled",
        "decisionmakerboughtin",
        "contractsent",
    }
)
LOST_STAGE_IDS: frozenset[str] = frozenset({"closedlost"})
WON_STAGE_IDS: frozenset[str] = frozenset({"closedwon"})


@dataclass(frozen=True)
class HubSpotDeal:
    """One pipeline row, normalised."""

    id: str
    name: str
    amount: float | None
    stage_id: str
    stage_label: str
    pipeline: str | None
    close_date: str | None
    created_at: str | None
    updated_at: str | None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "stage_id": self.stage_id,
            "stage_label": self.stage_label,
            "pipeline": self.pipeline,
            "close_date": self.close_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_raw:
            body["raw"] = dict(self.raw)
        return body


@dataclass(frozen=True)
class PipelineResult:
    ok: bool
    deals: tuple[HubSpotDeal, ...] = field(default_factory=tuple)
    next_cursor: str | None = None
    error: str | None = None
    detail: str | None = None
    status: int | None = None
    source: str = "hubspot"

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "ok": self.ok,
            "source": self.source,
            "count": len(self.deals),
            "deals": [d.to_dict(include_raw=include_raw) for d in self.deals],
            "next_cursor": self.next_cursor,
        }
        if self.error is not None:
            body["error"] = self.error
        if self.detail is not None:
            body["detail"] = self.detail
        if self.status is not None:
            body["status"] = self.status
        if self.deals:
            active = [
                d
                for d in self.deals
                if d.stage_id in ACTIVE_STAGE_IDS or d.stage_id == ""
            ]
            won = [d for d in self.deals if d.stage_id in WON_STAGE_IDS]
            lost = [d for d in self.deals if d.stage_id in LOST_STAGE_IDS]
            body["active_count"] = len(active)
            body["won_count"] = len(won)
            body["lost_count"] = len(lost)
            body["pipeline_amount"] = round(
                sum(d.amount for d in active if isinstance(d.amount, (int, float))),
                2,
            )
        return body


# ---------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------


def _parse_amount(raw: Any) -> float | None:
    """HubSpot returns ``amount`` as a string (``"12345.67"``); be
    defensive about empty / None / non-numeric cases."""

    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _stage_label_for(stage_id: str) -> str:
    if not stage_id:
        return ""
    return DEFAULT_STAGE_LABELS.get(stage_id, stage_id)


def _parse_deal_row(row: Any) -> HubSpotDeal | None:
    """HubSpot returns each deal as
    ``{"id": "...", "properties": {...}, "createdAt": "...", ...}``.
    Be defensive about missing keys."""

    if not isinstance(row, dict):
        return None
    deal_id = row.get("id")
    if not deal_id:
        return None
    props = row.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    name = str(props.get("dealname") or "").strip() or "(unnamed)"
    stage_id = str(props.get("dealstage") or "").strip()
    pipeline = props.get("pipeline")
    return HubSpotDeal(
        id=str(deal_id),
        name=name,
        amount=_parse_amount(props.get("amount")),
        stage_id=stage_id,
        stage_label=_stage_label_for(stage_id),
        pipeline=str(pipeline) if pipeline else None,
        close_date=props.get("closedate") or None,
        created_at=row.get("createdAt") or props.get("createdate") or None,
        updated_at=row.get("updatedAt") or props.get("hs_lastmodifieddate") or None,
        raw=row,
    )


def _normalise_properties(arg: Any) -> tuple[str, ...]:
    """Accept a list / tuple / comma-separated string, fall back to the
    default property set when blank or invalid.
    """

    if arg is None:
        return DEFAULT_PROPERTIES
    if isinstance(arg, str):
        items = [p.strip() for p in arg.split(",") if p.strip()]
        return tuple(items) if items else DEFAULT_PROPERTIES
    if isinstance(arg, (list, tuple)):
        items = [str(p).strip() for p in arg if str(p).strip()]
        return tuple(items) if items else DEFAULT_PROPERTIES
    return DEFAULT_PROPERTIES


def _next_cursor_from(payload: Mapping[str, Any]) -> str | None:
    """HubSpot puts cursor under ``paging.next.after``."""

    paging = payload.get("paging")
    if not isinstance(paging, dict):
        return None
    nxt = paging.get("next")
    if not isinstance(nxt, dict):
        return None
    cur = nxt.get("after")
    return str(cur) if cur else None


# ---------------------------------------------------------------------
# Action handler
# ---------------------------------------------------------------------


async def pull_pipeline(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read-only fetch of the HubSpot deals pipeline.

    Args
    ----
    limit : int (default 25, max 100).
    after : str (optional opaque cursor from a previous response).
    properties : list[str] | str (optional, default :data:`DEFAULT_PROPERTIES`).
    pipeline : str (optional pipeline id filter — applied **client-side**
        against the ``pipeline`` property since the public ``GET deals``
        endpoint does not accept a server-side filter without the search
        endpoint).
    include_raw : bool (default False) — if True, attach each deal's
        raw HubSpot row under ``raw``.
    api_key : str (optional; for tests / playbooks. Otherwise the vault
        key ``HUBSPOT_API_KEY`` is used).
    """

    raw_limit = args.get("limit", DEFAULT_LIMIT)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return PipelineResult(
            ok=False,
            error="invalid_limit",
            detail=f"limit must be a positive int, got {raw_limit!r}",
        ).to_dict()
    if limit < 1 or limit > MAX_LIMIT:
        return PipelineResult(
            ok=False,
            error="invalid_limit",
            detail=f"limit must be 1..{MAX_LIMIT}, got {limit}",
        ).to_dict()

    after_arg = args.get("after")
    after = str(after_arg).strip() if after_arg else None

    properties = _normalise_properties(args.get("properties"))
    pipeline_filter = args.get("pipeline")
    pipeline_filter = (
        str(pipeline_filter).strip() if isinstance(pipeline_filter, str) else None
    ) or None

    include_raw = bool(args.get("include_raw", False))

    api_key = args.get("api_key") or get_secret("HUBSPOT_API_KEY")
    if not api_key:
        return PipelineResult(
            ok=False,
            error="auth_missing",
            detail=(
                "set HUBSPOT_API_KEY in the vault (private-app access "
                "token) to enable pipeline pulls."
            ),
        ).to_dict()

    params: dict[str, Any] = {
        "limit": limit,
        "properties": ",".join(properties),
        "archived": "false",
    }
    if after:
        params["after"] = after

    client = get_client()
    await client.emit(
        "integration.hubspot.deals_list",
        {
            "phase": "request",
            "limit": limit,
            "after": after,
            "properties": list(properties),
            "pipeline_filter": pipeline_filter,
        },
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        status, payload = await get_json(
            DEALS_URL, params=params, headers=headers, timeout=10.0
        )
    except NetworkError as exc:
        await client.emit(
            "integration.hubspot.deals_list",
            {"phase": "error", "error": "network_error", "detail": str(exc)},
        )
        return PipelineResult(
            ok=False,
            error="network_error",
            detail=str(exc),
        ).to_dict()

    if status == 401:
        await client.emit(
            "integration.hubspot.deals_list",
            {"phase": "error", "error": "auth_invalid", "status": 401},
        )
        return PipelineResult(
            ok=False,
            error="auth_invalid",
            status=401,
            detail="HubSpot rejected the access token (401).",
        ).to_dict()

    if status != 200:
        await client.emit(
            "integration.hubspot.deals_list",
            {"phase": "error", "error": "upstream_status", "status": status},
        )
        detail: str | None = None
        if isinstance(payload, dict):
            msg = payload.get("message")
            if msg:
                detail = str(msg)
        return PipelineResult(
            ok=False,
            error="upstream_status",
            status=status,
            detail=detail,
        ).to_dict()

    if not isinstance(payload, dict):
        return PipelineResult(
            ok=False,
            error="upstream_payload_invalid",
            detail="expected JSON object",
        ).to_dict()

    raw_results = payload.get("results")
    rows: list[Any] = list(raw_results) if isinstance(raw_results, list) else []

    deals: list[HubSpotDeal] = []
    for row in rows:
        parsed = _parse_deal_row(row)
        if parsed is None:
            continue
        if pipeline_filter and parsed.pipeline != pipeline_filter:
            continue
        deals.append(parsed)

    next_cursor = _next_cursor_from(payload)

    await client.emit(
        "integration.hubspot.deals_list",
        {
            "phase": "completed",
            "count": len(deals),
            "has_next": bool(next_cursor),
        },
    )

    return PipelineResult(
        ok=True,
        deals=tuple(deals),
        next_cursor=next_cursor,
    ).to_dict(include_raw=include_raw)


__all__ = [
    "ACTIVE_STAGE_IDS",
    "DEALS_URL",
    "DEFAULT_LIMIT",
    "DEFAULT_PROPERTIES",
    "DEFAULT_STAGE_LABELS",
    "HubSpotDeal",
    "LOST_STAGE_IDS",
    "MAX_LIMIT",
    "PipelineResult",
    "WON_STAGE_IDS",
    "pull_pipeline",
]
