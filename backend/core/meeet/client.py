"""HTTP client for the meeet.world ingest endpoint.

Stdlib only. Sync HTTP wrapped in ``asyncio.to_thread`` so the rest of the
app stays non-blocking.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping

from .config import MeeetConfig, load_config
from .events import TARSEvent
from .tracing import current_trace, new_trace_id


class MeeetClient:
    """Minimal client. ``emit`` is fire-and-forget by default.

    When ``config.enabled`` is False the client only runs the local-log
    side-effect (if configured) and returns the event payload — no network.
    """

    def __init__(self, config: MeeetConfig | None = None, *, timeout_s: float = 2.5) -> None:
        self.config = config or load_config()
        self.timeout_s = timeout_s

    async def emit(self, kind: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        trace_id = current_trace() or new_trace_id()
        event = TARSEvent(
            trace_id=trace_id,
            kind=kind,
            payload=dict(payload or {}),
            source=self.config.source,
            contract_version=self.config.contract_version,
        )
        body = event.to_dict()

        if self.config.local_log_path:
            try:
                await asyncio.to_thread(_append_jsonl, self.config.local_log_path, body)
            except OSError:
                # Local logging must never crash the request path.
                pass

        if not self.config.enabled or not self.config.ingest_url:
            return body

        try:
            await asyncio.to_thread(
                _post_json,
                self.config.ingest_url,
                body,
                self.config.api_key,
                self.config.contract_version,
                self.timeout_s,
            )
        except (urllib.error.URLError, TimeoutError, OSError):
            # Ingest must never crash the host. Real deployments add retry
            # via the observability layer; this client stays simple.
            pass

        return body


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
