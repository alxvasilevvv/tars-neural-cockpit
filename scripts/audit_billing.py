"""End-to-end billing / cap enforcement audit (P6.1-P6.6).

Verifies:

1. ``Tier`` table loads with expected caps.
2. ``can_run`` returns False after cap is exceeded.
3. ``/api/entitlements/upgrade`` accepts a mock token.
4. ``/api/entitlements/can_run`` reflects ledger state.
5. **Critical gap test**: chat / planner / voice DO NOT call
   ``can_run`` before issuing cloud LLM calls.
6. Rate limiter is configured for at most pairing/recovery
   routes, NOT for /api/chat or /api/planner.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from fastapi.testclient import TestClient


def _isolate_state(tmpdir: str) -> None:
    os.environ["MEEET_STORE_PATH"] = os.path.join(tmpdir, "audit-meeet.sqlite")
    os.environ["TARS_ENTITLEMENTS_DB"] = os.path.join(tmpdir, "audit-ent.sqlite")
    os.environ.pop("MEEET_INGEST_URL", None)


def _reset_singletons() -> None:
    from backend.core.meeet import client as client_mod, store as store_mod

    client_mod._SINGLETON = None
    store_mod._SINGLETON = None


async def _check_tier_table_loads() -> tuple[bool, str]:
    from backend.core.entitlements import LIMITS, Tier

    if Tier.FREE not in LIMITS:
        return False, "FREE tier missing"
    if Tier.PRO not in LIMITS:
        return False, "PRO tier missing"
    if Tier.BUSINESS not in LIMITS:
        return False, "BUSINESS tier missing"
    free = LIMITS[Tier.FREE]
    if free.daily_cloud_budget_usd != 0.0:
        return False, f"FREE budget should be $0, got {free.daily_cloud_budget_usd}"
    return True, (
        f"FREE=${LIMITS[Tier.FREE].daily_cloud_budget_usd:.4f}/d "
        f"PRO=${LIMITS[Tier.PRO].daily_cloud_budget_usd:.4f}/d "
        f"BUSINESS=${LIMITS[Tier.BUSINESS].daily_cloud_budget_usd:.4f}/d"
    )


async def _check_can_run_blocks_at_cap() -> tuple[bool, str]:
    """Push fake usage.tokens events past the FREE cap and verify
    can_run flips to False."""

    from backend.core.entitlements import can_run, get_store as get_ent_store
    from backend.core.entitlements.tiers import Tier
    from backend.core.meeet import get_client, trace_scope

    # Reset to FREE (cap = $0)
    get_ent_store().set_tier(Tier.FREE)
    get_ent_store().set_byo(False)

    gate = await can_run(kind="cloud")
    # FREE tier with cap=$0 should immediately block (remaining=0)
    if gate.allowed:
        return False, f"FREE tier should not allow any cloud calls (cap=$0), got allowed=True"
    if gate.reason != "cap_hit":
        return False, f"reason should be cap_hit, got {gate.reason!r}"

    # Now upgrade to PRO and verify ALLOW
    get_ent_store().set_tier(Tier.PRO)
    gate = await can_run(kind="cloud")
    if not gate.allowed:
        return False, f"PRO tier should allow when no spend yet, got allowed=False reason={gate.reason}"

    # Push a single usage.tokens event with cost > PRO daily cap
    pro_cap = await _get_pro_cap()
    client = get_client()
    with trace_scope():
        await client.emit("usage.tokens", {
            "model": "gpt-4o",
            "input_tokens": 10000,
            "output_tokens": 5000,
            "cost_usd": pro_cap + 1.0,  # blast past the cap
            "route": "cloud",
        })

    gate = await can_run(kind="cloud")
    if gate.allowed:
        return False, f"PRO tier should block after spend > cap; spent={gate.spent_usd} cap={gate.cap_usd}"

    return True, (
        f"FREE blocked, PRO allowed → after $> {pro_cap:.4f} blocked "
        f"(reason={gate.reason}, remaining=${gate.remaining_usd:.4f})"
    )


async def _get_pro_cap() -> float:
    from backend.core.entitlements import LIMITS, Tier
    return LIMITS[Tier.PRO].daily_cloud_budget_usd


def _check_upgrade_accepts_mock(client: TestClient) -> tuple[bool, str]:
    r = client.post("/api/entitlements/upgrade", json={
        "tier": "pro", "payment_token": "mock_audit_token",
    })
    if r.status_code != 200:
        return False, f"upgrade returned {r.status_code}"
    body = r.json()
    if body.get("tier") != "pro":
        return False, f"tier should be 'pro', got {body.get('tier')!r}"
    return True, f"ok — moved to {body.get('tier')}, caps={body.get('caps', {}).get('daily_cloud_budget_usd')}"


def _check_can_run_endpoint(client: TestClient) -> tuple[bool, str]:
    r = client.post("/api/entitlements/can_run", json={"kind": "cloud"})
    if r.status_code != 200:
        return False, f"returned {r.status_code}"
    body = r.json()
    return True, (
        f"allowed={body.get('allowed')} tier={body.get('tier')} "
        f"spent=${body.get('spent_usd')} cap=${body.get('cap_usd')}"
    )


def _check_can_run_NOT_called_in_cloud_paths() -> tuple[bool, str]:
    """**Audit gap test**: which cloud-LLM-touching modules call
    can_run before issuing the call?"""

    import pathlib, re

    cloud_modules = [
        "backend/core/chat/orchestrator.py",
        "backend/core/voice/synthesis.py",
        "backend/core/council/orchestrator.py",
        "backend/core/planner/runner.py",
    ]
    callers = {}
    for mod_path in cloud_modules:
        p = pathlib.Path(mod_path)
        if not p.exists():
            callers[mod_path] = "FILE NOT FOUND"
            continue
        text = p.read_text()
        # Look for either `can_run(` call or `entitlements.can_run`
        # import — the *use*, not the import line by itself.
        has_call = bool(re.search(r"\bcan_run\s*\(", text))
        has_import = "from backend.core.entitlements" in text
        callers[mod_path] = (
            "✔ enforced" if has_call else
            ("⚠ imports but doesn't call" if has_import else "✗ NOT enforced")
        )

    enforced = sum(1 for v in callers.values() if "enforced" in v and "NOT" not in v)
    summary = "; ".join(f"{p.split('/')[-1]}={v}" for p, v in callers.items())
    return enforced > 0, f"{enforced}/{len(callers)} cloud paths call can_run → {summary}"


def _check_rate_limiter_coverage() -> tuple[bool, str]:
    """How many routers actually call get_rate_limiter?"""

    import pathlib, re

    web_routers = pathlib.Path("web_extras/routers")
    routers_using_rl = []
    for p in web_routers.glob("*.py"):
        text = p.read_text()
        if "get_rate_limiter" in text or "RateLimiter" in text:
            routers_using_rl.append(p.name)

    total = len(list(web_routers.glob("*.py"))) - 1  # minus __init__
    return (
        len(routers_using_rl) >= 2,
        f"{len(routers_using_rl)}/{total} routers wire the rate limiter "
        f"({', '.join(routers_using_rl) or 'NONE'})"
    )


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tars-bill-") as tmp:
        _isolate_state(tmp)
        _reset_singletons()

        from web_extras.app import app

        results: list[tuple[str, bool, str]] = []

        ok, note = await _check_tier_table_loads()
        results.append(("Tier table loads", ok, note))

        ok, note = await _check_can_run_blocks_at_cap()
        results.append(("can_run blocks at cap", ok, note))

        client = TestClient(app)
        ok, note = _check_upgrade_accepts_mock(client)
        results.append(("upgrade accepts mock token", ok, note))

        ok, note = _check_can_run_endpoint(client)
        results.append(("/api/entitlements/can_run", ok, note))

        # The two structural / gap checks
        ok, note = _check_can_run_NOT_called_in_cloud_paths()
        results.append(("can_run enforced in cloud paths?", ok, note))

        ok, note = _check_rate_limiter_coverage()
        results.append(("rate limiter coverage", ok, note))

        print("=" * 90)
        print(f"{'check':40} {'status':10}  notes")
        print("=" * 90)
        for name, ok, note in results:
            label = "✔ pass" if ok else "✗ FAIL"
            print(f"{name:40} {label:10}  {note}")
        print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
