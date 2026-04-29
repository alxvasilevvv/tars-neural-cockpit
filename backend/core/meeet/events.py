"""Event types for the meeet.world bridge."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping


# Contract version policy:
#
# - 1.0.0 (baseline) — trace_id / kind / source / contract_version / ts / payload,
#   plus optional session_id / route added in batch K1.
# - 1.1.0 (Phase L5) — adds two **optional** fields, ``ciphertext`` and
#   ``envelope``, that carry an XChaCha20-Poly1305 sealed payload + the
#   metadata needed to open it (X25519 ephemeral pubkey + per-device wrapped
#   keys). Events without those fields stay 1.0.0 and the wire format is
#   indistinguishable from before, so every 1.0.0 consumer ignores 1.1.0
#   events safely.
#
# The constants below are the source of truth — bumping them forces every
# emitter to think about the migration.
BASELINE_CONTRACT_VERSION = "1.0.0"
ENCRYPTED_CONTRACT_VERSION = "1.1.0"


@dataclass(frozen=True)
class TARSEvent:
    """A single event sent to meeet.world ingest.

    The shape is intentionally tiny and stable. Anything domain-specific
    lives inside ``payload`` so we never have to migrate schema.

    ``session_id`` and ``route`` are the routing/correlation tags
    introduced by the K1 batch. They are optional on the wire (older
    consumers ignore unknown fields) but always present in our local
    durable buffer so the cockpit can render session timelines and
    edge↔cloud routing maps.

    ``ciphertext`` and ``envelope`` are the Phase L5 sync-encryption
    fields. When both are set, ``contract_version`` auto-bumps to
    ``1.1.0`` and ``payload`` is allowed to be empty (the actual
    payload lives sealed inside ``ciphertext``).
    """

    trace_id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    source: str = "tars"
    contract_version: str = BASELINE_CONTRACT_VERSION
    ts: float = field(default_factory=time.time)
    session_id: str | None = None
    route: str | None = None
    ciphertext: str | None = None
    envelope: Mapping[str, Any] | None = None

    @property
    def is_encrypted(self) -> bool:
        return bool(self.ciphertext) and self.envelope is not None

    def effective_contract_version(self) -> str:
        if self.is_encrypted:
            return ENCRYPTED_CONTRACT_VERSION
        return self.contract_version

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "trace_id": self.trace_id,
            "kind": self.kind,
            "source": self.source,
            "contract_version": self.effective_contract_version(),
            "ts": self.ts,
            "payload": dict(self.payload),
        }
        if self.session_id:
            out["session_id"] = self.session_id
        if self.route:
            out["route"] = self.route
        if self.is_encrypted:
            out["ciphertext"] = self.ciphertext
            out["envelope"] = dict(self.envelope or {})
        return out
