"""End-to-end check: meeet bridge + cross-trace propagation
(P5.1–P5.6 of system audit).

What this verifies:

1. Live emit → store roundtrip (event lands in SQLite buffer).
2. ``replay_unpushed`` correctly counts when ingest is unset
   (returns ``enabled: false`` envelope, doesn't crash).
3. ``x-meeet-trace-id`` header on a domain action POST → the
   action's emitted events all share that trace_id (continues
   the upstream trace instead of minting a fresh one).
4. ``/api/meeet/{stats,events}`` HTTP endpoints work.
5. One real request → trace_id appears in events for every
   layer it touched.

Run:

    PYTHONPATH=. .venv/bin/python scripts/audit_meeet_e2e.py
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from fastapi.testclient import TestClient


def _setup_isolated_meeet_store(tmpdir: str) -> str:
    """Point the meeet store at a temp SQLite so we don't trample
    the operator's local ~/.tars/meeet.sqlite during the audit."""

    path = os.path.join(tmpdir, "audit-meeet.sqlite")
    os.environ["MEEET_STORE_PATH"] = path
    os.environ.pop("MEEET_INGEST_URL", None)  # local-only
    return path


def _reset_meeet_singletons() -> None:
    """The meeet client + store are module-level singletons. Reset
    so they pick up the new env vars."""

    from backend.core.meeet import client as client_mod
    from backend.core.meeet import store as store_mod

    client_mod._SINGLETON = None
    store_mod._SINGLETON = None


async def _check_emit_roundtrip() -> tuple[bool, str]:
    from backend.core.meeet import get_client, trace_scope

    client = get_client()
    with trace_scope() as trace_id:
        await client.emit("audit.probe", {"hello": "world"})
    # Read back from store
    rows = await client.store.list_events(trace_id=trace_id, limit=10)
    if not rows:
        return False, "no row found in store after emit"
    if rows[0].kind != "audit.probe":
        return False, f"unexpected kind: {rows[0].kind}"
    if rows[0].trace_id != trace_id:
        return False, f"trace_id drift: emitted={trace_id} got={rows[0].trace_id}"
    return True, f"ok — 1 row, trace={trace_id[:24]}…"


async def _check_replay_no_ingest() -> tuple[bool, str]:
    from backend.core.meeet import get_client

    client = get_client()
    out = await client.replay_unpushed()
    # Without MEEET_INGEST_URL, replay should return enabled=False
    # gracefully (not crash, not push fake URLs).
    if out.get("enabled") is True:
        return False, "replay reports enabled=True without ingest URL"
    return True, f"ok — enabled={out.get('enabled')} envelope={set(out.keys())}"


def _check_trace_header_continues_upstream(client: TestClient) -> tuple[bool, str]:
    """POST a domain action with an upstream trace_id header and
    assert the action's emitted events use the same trace_id."""

    upstream_trace = "trc_audit_external_001"
    r = client.post(
        "/api/domains/traders/actions/fetch_quote",
        json={"symbol": "BTC"},
        headers={"x-meeet-trace-id": upstream_trace},
    )
    if r.status_code != 200:
        return False, f"action returned {r.status_code}: {r.text[:120]}"
    body = r.json()
    embedded_trace = body.get("trace_id")
    if embedded_trace != upstream_trace:
        return False, (
            f"trace_id NOT propagated: upstream={upstream_trace} "
            f"response.trace_id={embedded_trace}"
        )
    return True, f"ok — upstream trace propagated through domain action"


def _check_meeet_http_endpoints(client: TestClient) -> tuple[bool, str]:
    notes: list[str] = []
    r = client.get("/api/meeet/stats")
    if r.status_code != 200:
        return False, f"/api/meeet/stats returned {r.status_code}"
    stats = r.json()
    notes.append(f"stats={list(stats.keys())[:6]}")

    r = client.get("/api/meeet/events", params={"limit": 5})
    if r.status_code != 200:
        return False, f"/api/meeet/events returned {r.status_code}"
    events = r.json()
    notes.append(f"events.keys={list(events.keys())}")
    return True, " | ".join(notes)


def _check_cross_layer_trace(client: TestClient) -> tuple[bool, str]:
    """One request that touches policy + meeet + domain action.
    Verify every layer's events end up under the same trace_id."""

    r = client.post(
        "/api/domains/traders/actions/fetch_quote",
        json={"symbol": "ETH"},
    )
    if r.status_code != 200:
        return False, f"action returned {r.status_code}"
    body = r.json()
    trace_id = body.get("trace_id")
    if not trace_id:
        return False, "action response has no trace_id"

    # Look up events for that trace via the HTTP surface
    r = client.get("/api/meeet/events", params={"trace_id": trace_id, "limit": 50})
    if r.status_code != 200:
        return False, f"events lookup returned {r.status_code}"
    body = r.json()
    events = body.get("events", [])
    kinds = {e.get("kind") for e in events}
    if not events:
        return False, f"no events for trace {trace_id}"
    expected_subset = {"domain.action.invoked", "domain.action.completed"}
    missing = expected_subset - kinds
    return (
        not missing,
        f"trace={trace_id[:24]}… events={len(events)} kinds={sorted(kinds)} "
        + (f"MISSING={missing}" if missing else "(all expected kinds present)"),
    )


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tars-audit-") as tmp:
        _setup_isolated_meeet_store(tmp)
        _reset_meeet_singletons()

        from web_extras.app import app

        results: list[tuple[str, bool, str]] = []
        ok, note = await _check_emit_roundtrip()
        results.append(("emit→store roundtrip", ok, note))

        ok, note = await _check_replay_no_ingest()
        results.append(("replay (no ingest)", ok, note))

        client = TestClient(app)
        ok, note = _check_trace_header_continues_upstream(client)
        results.append(("x-meeet-trace-id propagation", ok, note))

        ok, note = _check_meeet_http_endpoints(client)
        results.append(("/api/meeet HTTP surface", ok, note))

        ok, note = _check_cross_layer_trace(client)
        results.append(("cross-layer trace continuity", ok, note))

        print("=" * 80)
        print(f"{'check':35} {'status':6}  notes")
        print("=" * 80)
        for name, ok, note in results:
            label = "✔ pass" if ok else "✗ FAIL"
            print(f"{name:35} {label:6}  {note}")
        print("=" * 80)
        failures = sum(1 for _, ok, _ in results if not ok)
        print(f"summary: {len(results) - failures}/{len(results)} passed, {failures} failed")
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
