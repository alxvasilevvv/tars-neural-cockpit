"""Resolve QA-agent credentials from CLI + env (single source for runner + loop)."""

from __future__ import annotations

import os


def resolved_ingest_api_key(cli_value: str | None) -> str | None:
    """Prefer explicit CLI, then TARS_INGEST_API_KEY, then MEEET_API_KEY (backend parity)."""
    if cli_value and str(cli_value).strip():
        return str(cli_value).strip()
    for k in ("TARS_INGEST_API_KEY", "MEEET_API_KEY"):
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return None
