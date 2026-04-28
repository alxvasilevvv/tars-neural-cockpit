"""Event types for the meeet.world bridge."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class TARSEvent:
    """A single event sent to meeet.world ingest.

    The shape is intentionally tiny and stable. Anything domain-specific
    lives inside ``payload`` so we never have to migrate schema.
    """

    trace_id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    source: str = "tars"
    contract_version: str = "1.0.0"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "kind": self.kind,
            "source": self.source,
            "contract_version": self.contract_version,
            "ts": self.ts,
            "payload": dict(self.payload),
        }
