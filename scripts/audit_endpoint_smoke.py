"""End-to-end endpoint smoke (P1.5 / P1.6 of system audit).

Walks every router on `web_extras.app:app`, tries a representative
GET endpoint per router, and reports which ones return 2xx with a
JSON envelope. Operator-readable summary at the end.

Run:

    PYTHONPATH=. .venv/bin/python scripts/audit_endpoint_smoke.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi.testclient import TestClient

from web_extras.app import app


# Per-router probes: (path, expect_keys_subset). Picks the cheapest
# safe GET on each router (no destructive ops, no auth required).
PROBES: list[tuple[str, str, list[str]]] = [
    ("health",       "/health",                  ["ok", "service"]),
    ("root",         "/",                        ["service"]),
    ("openapi",      "/openapi.json",            ["openapi", "info"]),
    ("domains",      "/api/domains",             []),
    ("domains.manifest", "/api/domains/manifest", []),
    ("usage",        "/api/usage",               ["ok"]),
    ("planner.list", "/api/planner",             []),
    ("planner.stats","/api/planner/_stats",      []),
    ("playbooks",    "/api/playbooks",           ["playbooks"]),
    ("policy.pending","/api/policy/pending",     ["ok"]),
    ("policy.recent","/api/policy/recent",       ["ok"]),
    ("meeet.stats",  "/api/meeet/stats",         []),
    ("entitlements", "/api/entitlements",        ["ok", "tier"]),
    ("entitlements.tiers", "/api/entitlements/tiers", ["ok", "tiers"]),
    ("vault",        "/api/vault/status",        ["ok"]),
    ("wallet.policy", "/api/wallet/policy/status", []),
    ("wallet.list",  "/api/wallet",              []),
    ("agents",       "/api/agents",              ["ok"]),
    ("memory.stats", "/api/memory/stats",        []),
    ("search",       "/api/search/saved",        ["ok"]),
    ("product.version","/api/product/version",   []),
    ("product.downloads","/api/product/downloads",[]),
    ("product.updater","/api/product/updater/targets",[]),
    ("roles",        "/api/roles",               ["ok"]),
    ("voice.health", "/api/voice/health",        []),
    ("voice.personas","/api/voice/personas",     []),
]


def main() -> int:
    client = TestClient(app)

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for name, path, expect_keys in PROBES:
        try:
            r = client.get(path)
        except Exception as exc:
            rows.append({
                "name": name, "path": path, "ok": False,
                "status": None, "error": f"exception: {exc!r}",
            })
            counts["error"] += 1
            continue
        try:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        except Exception as exc:
            body = {}
        ok_status = 200 <= r.status_code < 300
        missing = [k for k in expect_keys if k not in body] if isinstance(body, dict) else expect_keys
        ok_envelope = ok_status and not missing
        rows.append({
            "name": name,
            "path": path,
            "status": r.status_code,
            "ok": ok_envelope,
            "missing_keys": missing,
            "has_body": bool(body),
        })
        if ok_envelope:
            counts["ok"] += 1
        elif ok_status:
            counts["partial"] += 1
        else:
            counts["fail"] += 1

    # Print
    print("=" * 76)
    print(f"{'router':22}  {'status':6}  {'ok':4}  path  →  notes")
    print("=" * 76)
    for r in rows:
        ok_label = "✔" if r["ok"] else ("·" if r.get("status") and 200 <= r["status"] < 300 else "✗")
        notes = ""
        if r.get("missing_keys"):
            notes = f"missing keys: {r['missing_keys']}"
        if r.get("error"):
            notes = r["error"]
        print(f"{r['name']:22}  {str(r['status'] or 'ERR'):6}  {ok_label:4}  {r['path']}  {notes}")
    print("=" * 76)
    print(f"summary: ok={counts.get('ok',0)}  partial={counts.get('partial',0)}  fail={counts.get('fail',0)}  error={counts.get('error',0)}")
    print(f"total routers checked: {len(PROBES)}")

    return 0 if counts.get("fail", 0) == 0 and counts.get("error", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
