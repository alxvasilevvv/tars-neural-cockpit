#!/usr/bin/env python3
"""One-shot: with repo `.env` already sourced, call remote billing snapshot (stdlib).

Used by `make smoke-billing-tars` — no uvicorn; validates keys + URL for local dev.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Repo root on PYTHONPATH when invoked via Makefile
from backend.core.meeet_billing.client import (
    clear_operator_cache,
    fetch_operator_snapshot,
    is_remote_billing_configured,
)


async def _main() -> int:
    if not is_remote_billing_configured():
        print("TARS_BILLING_SOURCE is not `remote` — set it in .env or export.", file=sys.stderr)
        return 2
    base = (os.getenv("MEEET_BILLING_BASE_URL") or "").strip()
    if not base:
        print("MEEET_BILLING_BASE_URL unset.", file=sys.stderr)
        return 2
    if not (os.getenv("MEEET_BILLING_API_KEY") or "").strip():
        print("MEEET_BILLING_API_KEY unset.", file=sys.stderr)
        return 2

    clear_operator_cache()
    snap = await fetch_operator_snapshot(bypass_cache=True)
    if snap is None:
        print("fetch_operator_snapshot returned None (misconfigured).", file=sys.stderr)
        return 1
    if not snap.get("ok"):
        print("Remote billing error:", snap.get("error"), snap, file=sys.stderr)
        return 1

    tier = snap.get("tier")
    live = snap.get("live") or {}
    print("ok remote billing snapshot")
    print("  tier:", tier)
    print("  spent_usd_24h:", live.get("spent_usd_24h"))
    print("  allowed_cloud:", live.get("allowed_cloud"))
    print("  remaining_usd:", live.get("remaining_usd"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
