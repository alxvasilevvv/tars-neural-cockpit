"""Civic pack actions — public-records lookups.

Three thin adapters over keyless public APIs. Each one returns a
structured ``{ok, ...}`` mapping so the council can chain them without
exception handling.

APIs used:
- OpenStates  https://v3.openstates.org/people  (free tier — 500 req/day, no key required for low volume)
- CourtListener https://www.courtlistener.com/api/rest/v3/search/  (free, generous rate limit)

All HTTP calls go through ``backend.core.domains._http.get_json`` so they
share the project's timeout, retry, and observability behavior.
"""

from __future__ import annotations

from typing import Any, Mapping

from ...base import ActionSpec
from ..._http import get_json


# ─── OpenStates: lookup legislator by name or zip ─────────────────────────
async def _lookup_legislator(args: Mapping[str, Any]) -> dict[str, Any]:
    name = (args.get("name") or "").strip()
    zip_code = (args.get("zip") or args.get("zip_code") or "").strip()
    state = (args.get("state") or "").strip().lower()

    if not name and not zip_code:
        return {"ok": False, "error": "missing_query", "hint": "pass {name} or {zip}"}

    params: dict[str, str] = {"per_page": "10"}
    if name:
        params["name"] = name
    if state:
        params["jurisdiction"] = state
    if zip_code:
        # OpenStates uses geo /people.geo, but the simple ?name= flow is
        # what the council usually wants. Keep it light.
        params["location"] = zip_code

    try:
        data = await get_json(
            "https://v3.openstates.org/people",
            params=params,
            timeout_s=15.0,
        )
    except Exception as exc:
        return {"ok": False, "error": "upstream_failed", "message": str(exc)}

    results = data.get("results") or []
    out = []
    for p in results[:10]:
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "party": p.get("party"),
            "state": (p.get("jurisdiction") or {}).get("name"),
            "current_role": (p.get("current_role") or {}).get("title"),
            "district": (p.get("current_role") or {}).get("district"),
            "image": p.get("image"),
            "openstates_url": p.get("openstates_url"),
        })
    return {"ok": True, "count": len(out), "results": out}


# ─── OpenStates: recent votes for a legislator ────────────────────────────
async def _recent_votes(args: Mapping[str, Any]) -> dict[str, Any]:
    person_id = (args.get("openstates_id") or args.get("id") or "").strip()
    if not person_id:
        return {"ok": False, "error": "missing_openstates_id"}

    try:
        data = await get_json(
            f"https://v3.openstates.org/people/{person_id}",
            params={"include": "votes"},
            timeout_s=15.0,
        )
    except Exception as exc:
        return {"ok": False, "error": "upstream_failed", "message": str(exc)}

    votes = data.get("votes") or []
    out = []
    for v in votes[:25]:
        out.append({
            "bill": (v.get("bill") or {}).get("identifier"),
            "title": (v.get("bill") or {}).get("title"),
            "date": v.get("start_date"),
            "result": v.get("result"),
            "option": v.get("option"),
            "url": v.get("sources", [{}])[0].get("url") if v.get("sources") else None,
        })
    return {"ok": True, "person_id": person_id, "count": len(out), "votes": out}


# ─── CourtListener: search federal court records ──────────────────────────
async def _court_case_search(args: Mapping[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or args.get("q") or "").strip()
    court = (args.get("court") or "").strip().lower()
    if not query:
        return {"ok": False, "error": "missing_query"}

    params = {"q": query, "type": "o"}  # 'o' = opinions
    if court:
        params["court"] = court

    try:
        data = await get_json(
            "https://www.courtlistener.com/api/rest/v3/search/",
            params=params,
            timeout_s=15.0,
        )
    except Exception as exc:
        return {"ok": False, "error": "upstream_failed", "message": str(exc)}

    results = data.get("results") or []
    out = []
    for r in results[:10]:
        out.append({
            "case_name": r.get("caseName"),
            "court": r.get("court"),
            "date_filed": r.get("dateFiled"),
            "docket_number": r.get("docketNumber"),
            "citation": r.get("citation"),
            "url": "https://www.courtlistener.com" + (r.get("absolute_url") or ""),
            "snippet": (r.get("snippet") or "")[:200],
        })
    return {"ok": True, "query": query, "count": len(out), "results": out}


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        id="lookup_legislator",
        name="Lookup legislator",
        description="Find a US legislator by name, state, or zip (OpenStates).",
        handler=_lookup_legislator,
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "state": {"type": "string", "description": "2-letter code"},
                "zip": {"type": "string"},
            },
        },
    ),
    ActionSpec(
        id="recent_votes",
        name="Recent votes",
        description="Pull the last 25 votes for a legislator (by OpenStates ID).",
        handler=_recent_votes,
        schema={
            "type": "object",
            "properties": {
                "openstates_id": {"type": "string"},
            },
            "required": ["openstates_id"],
        },
    ),
    ActionSpec(
        id="court_case_search",
        name="Search federal court records",
        description="Search US federal opinions (CourtListener).",
        handler=_court_case_search,
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "court": {"type": "string", "description": "e.g. scotus, ca9, dcd"},
            },
            "required": ["query"],
        },
    ),
)
