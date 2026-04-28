"""Configuration for the meeet.world bridge.

Driven by environment variables so the bridge stays usable in any host:

- ``MEEET_INGEST_URL`` — POST endpoint for events. If unset, the client runs
  in no-op mode (still useful: trace_id is generated, code paths exercised).
- ``MEEET_CONTRACT_VERSION`` — pinned contract version. Default ``1.0.0``.
- ``MEEET_API_KEY`` — optional bearer for the ingest endpoint.
- ``MEEET_SOURCE`` — logical source identifier. Default ``tars``.
- ``MEEET_LOCAL_LOG`` — optional path. When set, every event is appended as
  one JSON line. Useful for offline replay.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MeeetConfig:
    ingest_url: str | None
    contract_version: str
    api_key: str | None
    source: str
    local_log_path: str | None

    @property
    def enabled(self) -> bool:
        return bool(self.ingest_url)


def load_config() -> MeeetConfig:
    return MeeetConfig(
        ingest_url=_clean(os.environ.get("MEEET_INGEST_URL")),
        contract_version=_clean(os.environ.get("MEEET_CONTRACT_VERSION")) or "1.0.0",
        api_key=_clean(os.environ.get("MEEET_API_KEY")),
        source=_clean(os.environ.get("MEEET_SOURCE")) or "tars",
        local_log_path=_clean(os.environ.get("MEEET_LOCAL_LOG")),
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
