"""Privacy mode + data sovereignty indicators (W244).

Three privacy modes:

- ``normal``  -- default. Cloud LLMs allowed, meeet telemetry allowed,
  outbound connectors allowed.
- ``privacy`` -- block cloud LLMs. Only ``local:*`` models go through.
  Meeet telemetry + connectors stay on (operator's data still flows
  to/from chosen integrations, but no model-data leaks).
- ``strict``  -- block ALL outbound network. Cloud LLMs, meeet ingest,
  Slack/Gmail/Calendar connectors -- every external destination is
  refused. Only local stack (LM Studio / Ollama / local SQLite) runs.

The single source of truth for the active config is
``~/.tars/privacy.json``. Every cloud-touching call site flows through
:func:`check_can_call` with a destination string like ``"anthropic"``,
``"openai"``, ``"meeet.world"``, ``"slack"``, ``"local:llama-3"``. The
helper returns ``(allowed, reason_if_blocked)`` and records the attempt
in an in-memory ring buffer so the cockpit's data-plane indicator can
show "where is my data going right now".

The ring buffer is intentionally **non-persistent** (RAM only, capped
at 1000 events) -- it's a live debug feed, not an audit log. Anchored
receipts continue to live in ``backend/core/receipts``.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Deque, Literal

__all__ = [
    "PrivacyConfig",
    "PrivacyMode",
    "DataFlowEvent",
    "load_privacy",
    "save_privacy",
    "check_can_call",
    "recent_flows",
    "snapshot",
    "reset_for_tests",
    "classify_destination",
]

PrivacyMode = Literal["normal", "privacy", "strict"]


# -- config dataclass ---------------------------------------------------


@dataclass
class PrivacyConfig:
    """Operator-configurable privacy contract.

    ``mode`` is the primary lever -- it preselects the three other
    toggles to the canonical preset. Operators can still tweak any
    bool independently after picking a mode (e.g. ``privacy`` + allow
    meeet telemetry off because they don't trust the relayer).
    """

    mode: PrivacyMode = "normal"
    block_cloud_llm: bool = False
    block_meeet_telemetry: bool = False
    block_outbound_connectors: bool = False
    local_only_models: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PrivacyConfig":
        mode = str(raw.get("mode") or "normal").lower()
        if mode not in ("normal", "privacy", "strict"):
            mode = "normal"
        return cls(
            mode=mode,  # type: ignore[arg-type]
            block_cloud_llm=bool(raw.get("block_cloud_llm", False)),
            block_meeet_telemetry=bool(raw.get("block_meeet_telemetry", False)),
            block_outbound_connectors=bool(raw.get("block_outbound_connectors", False)),
            local_only_models=bool(raw.get("local_only_models", False)),
        )

    @classmethod
    def preset_for(cls, mode: PrivacyMode) -> "PrivacyConfig":
        """Canonical preset for each mode. Used to initialise toggles
        when the operator picks a mode from the UI."""
        if mode == "privacy":
            return cls(
                mode="privacy",
                block_cloud_llm=True,
                block_meeet_telemetry=False,
                block_outbound_connectors=False,
                local_only_models=True,
            )
        if mode == "strict":
            return cls(
                mode="strict",
                block_cloud_llm=True,
                block_meeet_telemetry=True,
                block_outbound_connectors=True,
                local_only_models=True,
            )
        return cls(mode="normal")


@dataclass
class DataFlowEvent:
    """One row in the live data-plane feed."""

    ts: float
    source: str
    dest: str
    kind: str          # llm | telemetry | connector | local | other
    allowed: bool
    reason: str = ""
    bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": round(self.ts, 3),
            "source": self.source,
            "dest": self.dest,
            "kind": self.kind,
            "allowed": self.allowed,
            "blocked": not self.allowed,
            "reason": self.reason,
            "bytes": self.bytes,
        }


# -- persistence --------------------------------------------------------


def _config_path() -> Path:
    raw = os.environ.get("TARS_PRIVACY_CONFIG_PATH") or "~/.tars/privacy.json"
    return Path(os.path.expanduser(raw))


_CFG_LOCK = threading.Lock()
_CACHED: PrivacyConfig | None = None


def load_privacy() -> PrivacyConfig:
    """Read the persisted config; default to ``normal`` mode if missing
    or unreadable. Cached for the lifetime of the process; mutations
    via :func:`save_privacy` refresh the cache."""
    global _CACHED
    with _CFG_LOCK:
        if _CACHED is not None:
            return _CACHED
        p = _config_path()
        try:
            if p.is_file():
                raw = json.loads(p.read_text(encoding="utf-8") or "{}")
                if isinstance(raw, dict):
                    _CACHED = PrivacyConfig.from_dict(raw)
                    return _CACHED
        except (OSError, json.JSONDecodeError):
            pass
        _CACHED = PrivacyConfig()
        return _CACHED


def save_privacy(cfg: PrivacyConfig) -> None:
    """Persist + refresh the in-process cache."""
    global _CACHED
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(cfg.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    with _CFG_LOCK:
        _CACHED = cfg


# -- destination classification ----------------------------------------


_CLOUD_LLM_TOKENS = (
    "anthropic", "openai", "openrouter", "gemini", "google",
    "mistral", "cohere", "deepseek", "groq", "perplexity",
    "fireworks", "together",
)
_MEEET_TOKENS = ("meeet.world", "meeet", "meeet_ingest")
_CONNECTOR_TOKENS = (
    "slack", "gmail", "calendar", "github", "telegram",
    "smtp", "imap", "hubspot",
)


def classify_destination(target: str) -> str:
    """Bucket a destination string into a coarse kind.

    Returns one of ``llm | telemetry | connector | local | other``.
    """
    t = (target or "").strip().lower()
    if not t:
        return "other"
    if t.startswith("local:") or t in ("ollama", "lmstudio", "lm_studio", "local"):
        return "local"
    if any(tok in t for tok in _CLOUD_LLM_TOKENS):
        return "llm"
    if any(tok in t for tok in _MEEET_TOKENS):
        return "telemetry"
    if any(tok in t for tok in _CONNECTOR_TOKENS):
        return "connector"
    return "other"


# -- ring buffer + check -----------------------------------------------


_RING_MAX = 1000
_RING: Deque[DataFlowEvent] = deque(maxlen=_RING_MAX)
_RING_LOCK = threading.Lock()


def _record(evt: DataFlowEvent) -> None:
    with _RING_LOCK:
        _RING.append(evt)


def check_can_call(
    target: str,
    *,
    source: str = "tars",
    bytes_: int = 0,
) -> tuple[bool, str]:
    """Gate every outbound call.

    Returns ``(allowed, reason_if_blocked)``. Always records the
    attempt in the ring buffer so the data-plane indicator can
    surface "where is my data going right now".

    Reason strings are short and machine-checkable:

    - ``"privacy_block_cloud_llm"`` -- privacy mode blocks cloud LLMs
    - ``"strict_block_outbound"``   -- strict mode blocks every outbound
    - ``"privacy_block_telemetry"`` -- meeet telemetry off
    - ``"privacy_block_connector"`` -- connector outbound off
    - ``"local_only_models"``       -- config demands ``local:*`` only
    - ``""``                        -- allowed
    """
    cfg = load_privacy()
    kind = classify_destination(target)
    allowed = True
    reason = ""

    if (
        cfg.mode == "strict"
        or cfg.block_cloud_llm
        or cfg.block_meeet_telemetry
        or cfg.block_outbound_connectors
        or cfg.local_only_models
    ):
        if kind == "local":
            # Local destinations are always allowed; that's the whole
            # point of privacy/strict mode existing.
            allowed = True
        elif cfg.mode == "strict":
            allowed = False
            reason = "strict_block_outbound"
        elif kind == "llm":
            if cfg.local_only_models:
                allowed = False
                reason = "local_only_models"
            elif cfg.block_cloud_llm:
                allowed = False
                reason = "privacy_block_cloud_llm"
        elif kind == "telemetry":
            if cfg.block_meeet_telemetry:
                allowed = False
                reason = "privacy_block_telemetry"
        elif kind == "connector":
            if cfg.block_outbound_connectors:
                allowed = False
                reason = "privacy_block_connector"

    evt = DataFlowEvent(
        ts=time.time(),
        source=source,
        dest=target,
        kind=kind,
        allowed=allowed,
        reason=reason,
        bytes=int(bytes_ or 0),
    )
    _record(evt)
    # W248 — push every data-plane decision onto the unified WS bus.
    try:
        from backend.core.realtime import publish_event as _rt_publish
        _rt_publish("privacy.data_plane", evt.to_dict())
    except Exception:
        pass
    return allowed, reason


# -- inspection helpers (consumed by router + tests) -------------------


def recent_flows(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent flow events, newest-first."""
    n = max(1, min(int(limit or 50), _RING_MAX))
    with _RING_LOCK:
        items = list(_RING)
    items.reverse()
    return [evt.to_dict() for evt in items[:n]]


def snapshot(limit: int = 50) -> dict[str, Any]:
    """Aggregated view used by ``GET /api/privacy/data_plane``."""
    rows = recent_flows(limit=limit)
    allowed = sorted({r["dest"] for r in rows if r["allowed"]})
    blocked = sorted({r["dest"] for r in rows if not r["allowed"]})
    last_outbound = next(
        (r for r in rows if r["kind"] != "local" and r["allowed"]), None
    )
    return {
        "ok": True,
        "config": load_privacy().to_dict(),
        "recent_flows": rows,
        "allowed_destinations": allowed,
        "blocked_destinations": blocked,
        "last_outbound": last_outbound,  # most recent non-local allowed flow
        "ring_capacity": _RING_MAX,
    }


def reset_for_tests() -> None:
    """Wipe cache + ring. Test-only helper; not exported via router."""
    global _CACHED
    with _CFG_LOCK:
        _CACHED = None
    with _RING_LOCK:
        _RING.clear()


def _ring_size() -> int:
    """Number of events currently in the ring (test introspection)."""
    with _RING_LOCK:
        return len(_RING)
