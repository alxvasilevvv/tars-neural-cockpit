#!/usr/bin/env python3
"""Idempotent Cloudflare dynamic redirect rules for meeet.world B-001 /dl/* paths."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
ZONE_NAME = "meeet.world"
RULESET_NAME = "meeet-b001-dl-redirects"
PHASE = "http_request_dynamic_redirect"

REDIRECTS: list[tuple[str, str, str]] = [
    ("/dl/TARS-8.4.0-arm64.dmg", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_aarch64.dmg", "B-001 legacy arm64 dmg"),
    ("/dl/TARS-8.4.0-setup.exe", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_x64-setup.exe", "B-001 legacy setup exe"),
    ("/dl/TARS-8.4.0.AppImage", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_amd64.AppImage", "B-001 legacy AppImage"),
    ("/dl/TARS_10.0.0-rc.1_aarch64.dmg", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_aarch64.dmg", "B-001 RC.1 aarch64 dmg"),
    ("/dl/TARS_10.0.0-rc.1_x64.dmg", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_x64-setup.exe", "B-001 RC.1 x64 dmg"),
    ("/dl/TARS_10.0.0-rc.1_x64-setup.exe", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_x64-setup.exe", "B-001 RC.1 setup exe"),
    ("/dl/TARS_10.0.0-rc.1_amd64.AppImage", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_amd64.AppImage", "B-001 RC.1 AppImage"),
    ("/dl/TARS_10.0.0-rc.1_amd64.deb", "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_amd64.AppImage", "B-001 RC.1 deb"),
]


def cf(method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.cloudflare.com/client/v4{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        payload = e.read().decode()
        print(f"HTTP {e.code} {path}: {payload[:500]}", file=sys.stderr)
        raise


def zone_id() -> str:
    q = urllib.parse.quote(ZONE_NAME)
    data = cf("GET", f"/zones?name={q}&status=active")
    zones = data.get("result") or []
    if not zones:
        raise SystemExit(f"zone not found or token lacks access: {ZONE_NAME}")
    return zones[0]["id"]


def build_rules() -> list[dict]:
    rules = []
    for path, target, desc in REDIRECTS:
        rules.append(
            {
                "description": desc,
                "expression": f'(http.request.uri.path eq "{path}")',
                "action": "redirect",
                "action_parameters": {
                    "from_value": {
                        "status_code": 302,
                        "target_url": {"value": target},
                        "preserve_query_string": False,
                    }
                },
            }
        )
    return rules


def main() -> None:
    zid = zone_id()
    print(f"zone {ZONE_NAME} id={zid}")

    desired = build_rules()
    desired_desc = {r["description"] for r in desired}

    entry = cf("GET", f"/zones/{zid}/rulesets/phases/{PHASE}/entrypoint")
    rs = entry.get("result") or {}
    rs_id = rs.get("id")
    existing = list(rs.get("rules") or [])

    kept = [r for r in existing if (r.get("description") or "") not in desired_desc]
    merged = kept + desired

    if DRY_RUN:
        print(f"dry-run: would set {len(desired)} B-001 rules ({len(kept)} other rules kept)")
        return

    if rs_id:
        out = cf(
            "PUT",
            f"/zones/{zid}/rulesets/{rs_id}",
            {"name": rs.get("name") or RULESET_NAME, "rules": merged},
        )
    else:
        out = cf(
            "POST",
            f"/zones/{zid}/rulesets",
            {
                "name": RULESET_NAME,
                "kind": "zone",
                "phase": PHASE,
                "rules": merged,
            },
        )

    if not out.get("success"):
        raise SystemExit(f"ruleset update failed: {out.get('errors')}")
    print(f"ok: applied {len(desired)} redirect rules on {ZONE_NAME}")


if __name__ == "__main__":
    main()
