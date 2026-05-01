"""Saved-search alerting.

A *saved search* (``backend.core.chat.models.SavedSearch``) is a
persistent query the operator wants to revisit. The alert path turns
each saved search into a passive watcher:

1. ``poll_saved_search`` runs the saved search via the existing
   :func:`~backend.core.search.engine.search` family.
2. Each hit is mapped to a stable *fingerprint* (``chunk:<chunk_id>``
   / ``message:<msg_id>`` / ``trace:<event_id>``).
3. The current fingerprint set is diffed against
   ``SavedSearch.seen_hits`` (the snapshot persisted on the prior
   poll). The difference is the new-hit set.
4. When the new-hit set is non-empty *and* there was a prior baseline
   (``last_alert_at`` is not None **or** the saved search has been
   polled at least once before), :class:`MeeetClient` emits
   ``saved_search.new_hits`` with payload
   ``{search_id, label, scope, query, new_count, new_hits, total}``.
5. The fingerprint snapshot + ``last_run_at`` (and ``last_alert_at``
   when the alert fired) are persisted via
   :meth:`ChatStore.record_saved_search_alert`.

The first poll on a saved search seeds ``seen_hits`` without firing
an alert — operators don't want a flood of "everything is new" the
moment they create a saved search. Subsequent polls only fire when
genuinely new fingerprints appear.

Design choices kept deliberately small for the first slice:

- One poll = one HTTP call. Background scheduling lives a layer up
  (a follow-up can wire it into the lifespan loop the same way the
  ``trace_summary`` and ``message_embed`` loops do today).
- The fingerprint set is bounded by ``MAX_SEEN_HITS`` (default 1000)
  to keep the JSON payload sane on long-running watchers; the oldest
  entries roll off when the cap is hit.
- Trace hits use the ``event_id`` as the discriminator (so re-emitted
  events with a new ``event_id`` count as new hits even when the
  trace itself was seen before — exactly what an operator wants to
  flag fresh activity).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.chat.store import ChatStore, get_chat_store
from backend.core.meeet import get_client
from backend.core.search.engine import (
    SearchHit,
    SearchScope,
    search,
    search_chunks,
    search_messages,
    search_traces,
)


log = logging.getLogger("tars.search.alerts")


MAX_SEEN_HITS = 1000


def hit_fingerprint(hit: SearchHit) -> str:
    """Stable identifier the alert path diffs on.

    Prefers the most-specific ID per kind. Falls back to the kind
    label so unparseable hits still produce *some* fingerprint
    rather than crashing the diff.
    """

    ref = hit.ref or {}
    if hit.kind == "chunk":
        return f"chunk:{ref.get('chunk_id') or ''}"
    if hit.kind == "message":
        return f"message:{ref.get('msg_id') or ''}"
    if hit.kind == "trace":
        # event_id is more granular than trace_id; the operator wants
        # to know about *new* events even on a familiar trace.
        return f"trace:{ref.get('event_id') or ref.get('trace_id') or ''}"
    return f"{hit.kind}:?"


async def _run_saved_search(saved, *, top_k: int) -> list[SearchHit]:
    """Dispatch to the right scope-specific search function.

    Mirrors the ``run_saved_search`` HTTP endpoint logic so polling
    sees the same hits the operator would see in a manual run.
    """

    scope: SearchScope = saved.scope  # type: ignore[assignment]
    query = saved.query or ""
    filters = dict(saved.filters or {})

    def _kw(*keys: str) -> dict[str, Any]:
        return {k: filters[k] for k in keys if k in filters and filters[k] is not None}

    if scope == "chunks":
        return await search_chunks(
            query,
            top_k=top_k,
            **_kw("thread_id", "pack", "mime", "since", "until"),
        )
    if scope == "messages":
        return await search_messages(
            query,
            top_k=top_k,
            **_kw("thread_id", "role", "pack", "since", "until"),
        )
    if scope == "traces":
        return await search_traces(
            query,
            top_k=top_k,
            **_kw("kind", "trace_id", "since", "until"),
        )
    res = await search(query, scope="all", top_k=top_k)
    return list(res.hits)


async def poll_saved_search(
    search_id: str,
    *,
    chat: ChatStore | None = None,
    top_k: int = 25,
) -> dict[str, Any]:
    """Run a saved search, diff against the prior snapshot, alert.

    Returns a stats dict:
    ``{ok, search_id, label, scope, total, new_count, new_hits,
       alerted, first_poll}``.

    - ``ok=False`` only when the saved search isn't found or the chat
      store is disabled.
    - ``first_poll=True`` when no prior baseline existed; the snapshot
      is seeded but no event is emitted (operators don't want a flood
      of "everything is new" on day one).
    - ``alerted=True`` when ``saved_search.new_hits`` was emitted.
    """

    chat = chat or get_chat_store()
    if not chat.enabled:
        return {"ok": False, "reason": "chat_store_disabled"}
    saved = await chat.get_saved_search(search_id)
    if saved is None:
        return {"ok": False, "reason": "not_found"}

    hits = await _run_saved_search(saved, top_k=top_k)
    fingerprints: list[str] = []
    seen_in_run: set[str] = set()
    for hit in hits:
        fp = hit_fingerprint(hit)
        if not fp or fp in seen_in_run:
            continue
        seen_in_run.add(fp)
        fingerprints.append(fp)

    prior = set(saved.seen_hits or ())
    first_poll = saved.last_run_at is None and not prior

    new_hits = [fp for fp in fingerprints if fp not in prior]

    # Merge: keep the ordering of "current run first, then any prior
    # entries we still want to remember". Cap at MAX_SEEN_HITS.
    merged: list[str] = list(fingerprints)
    if len(merged) < MAX_SEEN_HITS:
        for fp in saved.seen_hits or ():
            if fp not in seen_in_run:
                merged.append(fp)
                seen_in_run.add(fp)
                if len(merged) >= MAX_SEEN_HITS:
                    break

    alerted = False
    snoozed = saved.is_snoozed()
    if new_hits and not first_poll and not snoozed:
        try:
            payload = {
                "search_id": saved.id,
                "label": saved.label,
                "scope": saved.scope,
                "query": saved.query,
                "filters": dict(saved.filters or {}),
                "new_count": len(new_hits),
                "new_hits": new_hits,
                "total": len(fingerprints),
            }
            await get_client().emit("saved_search.new_hits", payload)
            alerted = True
        except Exception as exc:  # never crash poll on a flaky bridge
            log.warning(
                "saved_search.new_hits emit failed for %s: %s",
                saved.id,
                exc,
            )

    await chat.record_saved_search_alert(
        saved.id,
        seen_hits=merged,
        had_new_hits=alerted,
    )

    return {
        "ok": True,
        "search_id": saved.id,
        "label": saved.label,
        "scope": saved.scope,
        "total": len(fingerprints),
        "new_count": len(new_hits),
        "new_hits": new_hits,
        "alerted": alerted,
        "first_poll": first_poll,
        "snoozed": snoozed,
        "snoozed_until": saved.snoozed_until,
    }


async def poll_all_saved_searches(
    *,
    chat: ChatStore | None = None,
    top_k: int = 25,
    limit: int = 100,
) -> dict[str, Any]:
    """Walk every saved search and poll it.

    Operator-facing trigger for the cockpit "alerts" tab; the same
    helper can later become the body of a background lifespan loop.
    Per-search failures are isolated.
    """

    chat = chat or get_chat_store()
    if not chat.enabled:
        return {"ok": False, "reason": "chat_store_disabled"}
    saved = await chat.list_saved_searches(limit=limit)
    if not saved:
        return {
            "ok": True,
            "polled": 0,
            "alerted": 0,
            "results": [],
        }

    results: list[dict[str, Any]] = []
    alerted = 0
    for s in saved:
        try:
            res = await poll_saved_search(s.id, chat=chat, top_k=top_k)
        except Exception as exc:
            log.warning("poll_saved_search %s failed: %s", s.id, exc)
            res = {"ok": False, "search_id": s.id, "error": str(exc)}
        if res.get("alerted"):
            alerted += 1
        results.append(res)
    return {
        "ok": True,
        "polled": len(results),
        "alerted": alerted,
        "results": results,
    }
