"""HTTP client for the meeet.world ingest endpoint.

Stdlib only. Sync HTTP wrapped in ``asyncio.to_thread`` so the rest of the
app stays non-blocking.

Every event flows through the durable :class:`MeeetStore` first
(``backend/core/meeet/store.py``); ingest push happens on top. When the
ingest is offline or unset, events sit in the SQLite WAL with
``pushed=0`` and a later :meth:`replay_unpushed` flushes them.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

import time

from .config import MeeetConfig, load_config
from .events import TARSEvent
from .store import MeeetStore, get_store
from .tracing import current_route, current_session, current_thread_id, current_trace, new_trace_id


class MeeetClient:
    """Minimal client. ``emit`` is fire-and-forget by default.

    When ``config.enabled`` is False the client only runs the local-log
    + durable-store side-effects and returns the event payload — no network.
    """

    def __init__(
        self,
        config: MeeetConfig | None = None,
        *,
        timeout_s: float = 2.5,
        store: MeeetStore | None = None,
    ) -> None:
        self.config = config or load_config()
        self.timeout_s = timeout_s
        self.store = store if store is not None else get_store()
        # Last replay attempt metadata — used by /api/meeet/health.
        self.last_replay: dict[str, Any] | None = None

    async def emit(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        session_id: str | None = None,
        route: str | None = None,
        ciphertext: str | None = None,
        envelope: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace_id = current_trace() or new_trace_id()
        # Auto-inject the active chat thread id when the contextvar is set
        # (typically inside an HTTP entry that opened
        # ``thread_id_scope(x_tars_thread_id)``). Call-sites that already
        # placed ``thread_id`` in the payload always win — the contextvar
        # is only a fallback so existing per-event explicit values
        # (e.g. policy router re-attaching from the persisted row) keep
        # the same behaviour.
        merged_payload = dict(payload or {})
        ctx_thread = current_thread_id()
        if ctx_thread and "thread_id" not in merged_payload:
            merged_payload["thread_id"] = ctx_thread
        event = TARSEvent(
            trace_id=trace_id,
            kind=kind,
            payload=merged_payload,
            source=self.config.source,
            contract_version=self.config.contract_version,
            session_id=session_id or current_session(),
            route=route or current_route(),
            ciphertext=ciphertext,
            envelope=dict(envelope) if envelope is not None else None,
        )
        body = event.to_dict()

        # Durable buffer first — this is the local-first guarantee.
        try:
            event_id = await self.store.insert(body)
        except Exception:
            event_id = None

        if self.config.local_log_path:
            try:
                await asyncio.to_thread(_append_jsonl, self.config.local_log_path, body)
            except OSError:
                # Local logging must never crash the request path.
                pass

        if not self.config.enabled or not self.config.ingest_url:
            return body

        push_error: str | None = None
        try:
            await asyncio.to_thread(
                _post_json,
                self.config.ingest_url,
                body,
                self.config.api_key,
                self.config.contract_version,
                self.timeout_s,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            push_error = str(exc)
            # Ingest must never crash the host. Real deployments add retry
            # via the observability layer; this client stays simple.

        if event_id:
            try:
                await self.store.mark_pushed(event_id, error=push_error)
            except Exception:
                pass

        return body

    async def replay_unpushed(self, *, limit: int = 100) -> dict[str, Any]:
        """Flush any locally-buffered events to ingest.

        No-op when the ingest is unset. Always stamps ``self.last_replay``
        so :func:`/api/meeet/health` can render the bridge state.
        """

        ts = time.time()
        if not self.config.enabled or not self.config.ingest_url:
            out: dict[str, Any] = {
                "enabled": False,
                "pushed": 0,
                "failed": 0,
                "remaining": 0,
                "ran_at": ts,
            }
            self.last_replay = dict(out)
            return out

        async def _push(body: dict[str, Any]) -> None:
            await asyncio.to_thread(
                _post_json,
                self.config.ingest_url,
                body,
                self.config.api_key,
                self.config.contract_version,
                self.timeout_s,
            )

        result = await self.store.replay_unpushed(_push, limit=limit)
        result["enabled"] = True
        result["ran_at"] = ts
        self.last_replay = dict(result)
        return result

    async def health(self) -> dict[str, Any]:
        """Snapshot of the durable-buffer + ingest bridge.

        Cheap to call: hits the SQLite stats and returns the cached
        ``last_replay`` blob without performing any network I/O.
        """

        try:
            stats = await self.store.stats()
        except Exception as exc:
            stats = {"error": str(exc), "total": 0, "pending": 0, "pushed": 0, "failed": 0}
        return {
            "ok": True,
            "client": {
                "enabled": bool(self.config.enabled and self.config.ingest_url),
                "ingest_url": self.config.ingest_url,
                "api_key_set": bool(self.config.api_key),
                "contract_version": self.config.contract_version,
                "source": self.config.source,
            },
            "store": stats,
            "last_replay": self.last_replay,
        }


def _post_json(
    url: str,
    body: dict[str, Any],
    api_key: str | None,
    contract_version: str,
    timeout_s: float,
) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-meeet-contract-version": contract_version,
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s):
        return None


def _append_jsonl(path: str, body: dict[str, Any]) -> None:
    expanded = os.path.expanduser(path)
    parent = os.path.dirname(expanded)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(expanded, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(body) + "\n")


_SINGLETON: MeeetClient | None = None


def get_client() -> MeeetClient:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = MeeetClient()
    return _SINGLETON


def reset_client() -> None:
    """Test helper: drop the cached singleton so config is re-read."""

    global _SINGLETON
    _SINGLETON = None
