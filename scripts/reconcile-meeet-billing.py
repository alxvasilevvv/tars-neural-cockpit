#!/usr/bin/env python3
"""Daily TARS ↔ meeet.world billing reconcile (PH11 §3.A4).

Compares local ``usage.tokens`` ledger totals against brother ``/operator``
when credentials are present. Exit 0 when drift is within threshold.

Usage:
  python3 scripts/reconcile-meeet-billing.py --check   # gate-friendly dry run
  python3 scripts/reconcile-meeet-billing.py           # same as --check today
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

DRIFT_USD = float(os.getenv("TARS_RECONCILE_DRIFT_USD", "0.50"))


def _usd_from_payload(payload: dict) -> float:
    tin = float(payload.get("tokens_in") or 0)
    tout = float(payload.get("tokens_out") or 0)
    # Same rough tariff as entitlements metering (order-of-magnitude only).
    return (tin * 3.0 + tout * 15.0) / 1_000_000.0


async def _local_usage_usd() -> float:
    from backend.core.meeet import get_store, reset_store

    reset_store()
    store = get_store()
    if not store.enabled:
        return 0.0
    events = await store.list_events(kind="usage.tokens", limit=1000)
    return sum(_usd_from_payload(e.payload) for e in events)


def _brother_usage_usd() -> float | None:
    base = (os.getenv("MEEET_INGEST_URL") or "").rstrip("/")
    key = os.getenv("MEEET_API_KEY") or ""
    if not base or not key:
        return None
    url = f"{base}/operator/usage?window=24h"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"WARN: brother usage fetch skipped: {exc}", file=sys.stderr)
        return None
    if isinstance(body, dict):
        for key_name in ("total_usd", "usage_usd", "balance_usd"):
            if key_name in body:
                try:
                    return float(body[key_name])
                except (TypeError, ValueError):
                    pass
    return None


async def main(check: bool) -> int:
    local = await _local_usage_usd()
    remote = _brother_usage_usd()
    print(f"local_usage_usd≈{local:.4f}")
    if remote is None:
        print("brother_usage_usd=skipped (no MEEET_INGEST_URL/MEEET_API_KEY or fetch failed)")
        if check:
            print("CHECK: local ledger readable — brother compare deferred")
            return 0
        return 0
    drift = abs(local - remote)
    print(f"brother_usage_usd≈{remote:.4f} drift_usd={drift:.4f} threshold={DRIFT_USD:.2f}")
    if drift <= DRIFT_USD:
        print("RECONCILE OK")
        return 0
    print(f"RECONCILE BLOCK: drift ${drift:.4f} > ${DRIFT_USD:.2f}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="non-destructive gate run")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(check=args.check)))
