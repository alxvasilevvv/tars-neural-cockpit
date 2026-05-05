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

from typing import Iterable, TYPE_CHECKING

from .config import MeeetConfig, load_config
from .events import TARSEvent
from .store import MeeetStore, get_store
from .tracing import (
    current_route,
    current_session,
    current_thread_id,
    current_trace,
    new_trace_id,
    trace_scope,
)

if TYPE_CHECKING:
    from backend.core.crypto import DeviceKey


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

        if kind == "usage.tokens":
            try:
                from backend.core.meeet_billing import mirror_usage

                await mirror_usage.after_usage_tokens_emitted(
                    route=event.route,
                    payload=merged_payload,
                    trace_id=event.trace_id,
                )
            except Exception:
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

    async def emit_encrypted(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        recipients: "Iterable[DeviceKey] | None" = None,
        session_id: str | None = None,
        route: str | None = None,
        require_recipients: bool = False,
    ) -> dict[str, Any]:
        """Encrypt + emit in one call. Sealed for all paired devices.

        Looks up paired-device keys from the singleton
        :class:`backend.core.pairing.PairingStore` when ``recipients`` is
        omitted, then seals ``payload`` per device using
        :func:`backend.core.crypto.encrypt_event` and forwards the
        resulting envelope through the regular :meth:`emit` pipeline.

        AAD binding: the AEAD associated-data string is
        ``trace_id|kind`` (see :mod:`backend.core.crypto.envelope`),
        so we resolve / mint the trace id BEFORE sealing and pin the
        same id on the :meth:`emit` call. If the caller is already
        inside an outer ``trace_scope`` we reuse the existing id;
        otherwise we wrap the emit in a one-shot scope so the
        ``ciphertext / envelope`` binding survives the durable-store
        round-trip and any later ``replay_unpushed`` flush.

        Degradation policy:

        - ``require_recipients=False`` (default): when no paired devices
          are reachable, fall through to a plain :meth:`emit` so
          cockpit-only operators don't have to fork their call sites
          for the "no paired phone yet" case.
        - ``require_recipients=True``: raise ``ValueError`` when the
          recipient set is empty. Useful for end-to-end privacy
          guarantees ("only emit when at least one paired device can
          decrypt") — operator-grade callers in chat / wallet flows
          should opt in.

        Returns the same dict :meth:`emit` returns, so the caller can
        treat ``emit_encrypted`` and ``emit`` as interchangeable in
        the happy path.
        """

        if recipients is None:
            from backend.core.pairing import get_pairing_store

            materialised = list(get_pairing_store().device_keys())
        else:
            materialised = list(recipients)

        if not materialised:
            if require_recipients:
                raise ValueError(
                    "emit_encrypted: no paired devices and require_recipients=True"
                )
            return await self.emit(
                kind,
                payload=payload,
                session_id=session_id,
                route=route,
            )

        # Pin the trace id BEFORE sealing so the AAD matches what emit()
        # stamps on the wire and in the durable buffer.
        trace_id = current_trace() or new_trace_id()

        from backend.core.crypto import encrypt_event

        sealed = encrypt_event(
            payload=payload or {},
            recipients=materialised,
            trace_id=trace_id,
            kind=kind,
        )

        if current_trace() == trace_id:
            return await self.emit(
                kind,
                payload={},
                session_id=session_id,
                route=route,
                **sealed.to_kwargs(),
            )

        # No outer scope — open a fresh one so emit() reads the same id
        # current_trace() returned above and the ciphertext/envelope
        # AAD binding stays consistent.
        with trace_scope(parent=trace_id):
            return await self.emit(
                kind,
                payload={},
                session_id=session_id,
                route=route,
                **sealed.to_kwargs(),
            )

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

        result = await self.store.replay_unpushed(self._push, limit=limit)
        result["enabled"] = True
        result["ran_at"] = ts
        self.last_replay = dict(result)
        return result

    async def repush_trace(
        self, trace_id: str, *, limit: int = 1000
    ) -> dict[str, Any]:
        """Force-push every event for one trace, regardless of ``pushed``.

        The fleet-ops follow-up to ``planner-replay-run``: after a
        meeet ingest outage / contract bump, the operator needs to
        re-emit one specific run's events upstream for billing
        backfill or audit. ``replay_unpushed`` only handles
        ``pushed=0`` rows; this method scopes by ``trace_id`` and
        bypasses the flag (the rows still get ``pushed_at`` bumped
        on success so the audit trail reflects the latest push).

        No-op when the ingest is unset (returns ``enabled=False``
        envelope, identical to ``replay_unpushed``). Stamps
        ``last_replay`` so ``/api/meeet/health`` reflects the
        repush as the most recent push activity.
        """

        ts = time.time()
        if not self.config.enabled or not self.config.ingest_url:
            out: dict[str, Any] = {
                "enabled": False,
                "trace_id": trace_id,
                "pushed": 0,
                "failed": 0,
                "remaining": 0,
                "ran_at": ts,
            }
            self.last_replay = dict(out)
            return out

        result = await self.store.repush_trace(
            self._push, trace_id=trace_id, limit=limit
        )
        result["enabled"] = True
        result["ran_at"] = ts
        self.last_replay = dict(result)
        return result

    async def _push(self, body: dict[str, Any]) -> None:
        """Internal push primitive shared by ``replay_unpushed`` and
        ``repush_trace``. Raises on transport failure so the caller
        records ``last_error`` and leaves ``pushed`` unchanged.
        """

        await asyncio.to_thread(
            _post_json,
            self.config.ingest_url,
            body,
            self.config.api_key,
            self.config.contract_version,
            self.timeout_s,
        )

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
