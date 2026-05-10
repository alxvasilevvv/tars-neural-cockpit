"""
qa_agent.runner — orchestrates probes, prints reports, returns exit code.

Stdlib-only. No deps. Designed to run from:
  - macOS local: `python -m scripts.qa_agent`
  - GH Actions: same command, no setup
  - Cron: `*/30 * * * * cd /repo && python -m scripts.qa_agent --json`

Exit codes:
  0   all critical probes passed (warns are OK)
  1   one or more critical probes failed
  2   user error (bad args, missing module, etc.)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .alerts import (
    DEFAULT_HISTORY_PATH,
    DEFAULT_THRESHOLD,
    KNOWN_FLAKY,
    load_history,
    record_run,
    save_history,
    send_alert,
    should_alert,
)
from .env_resolve import resolved_ingest_api_key
from .probes import (
    Context,
    Probe,
    probe_all_routes,
    probe_bundle_imports,
    probe_client_error_endpoint,
    probe_core_bridge_health,
    probe_core_bridge_relay_roundtrip,
    probe_core_bridge_unauth,
    probe_dns,
    probe_manifest_cors_meeet_world,
    probe_manifest_origin,
    probe_manifest_origin_blocked,
    probe_manifest_subdomain,
    probe_meeet_ingest_heartbeat,
    probe_robots,
    probe_root_ttfb,
    probe_security_headers,
    probe_session_cookie,
    probe_sitemap,
    probe_spa_root,
    probe_spa_routes,
    probe_sw_version,
    probe_tokenomics_invariants,
    probe_version_subdomain,
)


# ANSI shortcuts. Disable when piping to JSON or in CI without a TTY.
def _color(c: str, s: str, enabled: bool) -> str:
    return f"\033[{c}m{s}\033[0m" if enabled else s


def run_all(ctx: Context) -> list[Probe]:
    """Run every probe in priority order."""
    probes: list[Probe] = []

    # 0. infra
    probes.append(probe_dns(ctx))
    if probes[-1].status in ("fail", "warn"):
        ctx.skip_subdomain = True

    # 1. economy invariants (works without network)
    probes.append(probe_tokenomics_invariants())

    # 2. subdomain HTTP
    probes.append(probe_spa_root(ctx))
    probes.extend(probe_spa_routes(ctx))
    probes.append(probe_security_headers(ctx))
    probes.append(probe_session_cookie(ctx))
    probes.append(probe_root_ttfb(ctx))

    # 2b. Wave 117 — comprehensive route + bundle + SW probes
    probes.extend(probe_all_routes(ctx))
    probes.append(probe_sw_version(ctx))
    probes.append(probe_bundle_imports(ctx))

    # 3. schema (sitemap / robots)
    probes.append(probe_sitemap(ctx))
    probes.append(probe_robots(ctx))

    # 4. API / manifest (origin reachable independent of subdomain DNS)
    probes.append(probe_manifest_origin(ctx))
    probes.append(probe_manifest_origin_blocked(ctx))
    probes.append(probe_manifest_subdomain(ctx))
    probes.append(probe_manifest_cors_meeet_world(ctx))
    probes.append(probe_version_subdomain(ctx))
    probes.append(probe_client_error_endpoint(ctx))

    # 5. core-bridge
    probes.append(probe_core_bridge_unauth(ctx))
    probes.append(probe_core_bridge_health(ctx))
    probes.append(probe_core_bridge_relay_roundtrip(ctx))

    # 6. meeet bridge heartbeat
    probes.append(probe_meeet_ingest_heartbeat(ctx))

    return probes


def render_text(probes: list[Probe], ctx: Context, color: bool) -> str:
    lines = []
    counts: Counter[str] = Counter()
    for p in probes:
        counts[p.status] += 1

    lines.append("=" * 70)
    lines.append("  TARS QA Agent — report")
    lines.append("=" * 70)
    lines.append(f"  target:        {ctx.tars_base}")
    lines.append(f"  bridge_url:    {ctx.core_bridge_url}")
    lines.append(f"  authenticated: {'yes' if ctx.bridge_shared_secret else 'no'}")
    lines.append(f"  generated:     {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(f"  passed: {counts['pass']:>3}  "
                 f"failed: {counts['fail']:>3}  "
                 f"warned: {counts['warn']:>3}  "
                 f"skipped: {counts['skip']:>3}  "
                 f"total: {len(probes):>3}")
    lines.append("")
    lines.append("-" * 70)
    for p in probes:
        if p.status == "pass":
            tag = _color("32", " PASS", color)
        elif p.status == "fail":
            tag = _color("31", " FAIL", color)
        elif p.status == "warn":
            tag = _color("33", " WARN", color)
        else:
            tag = _color("90", " SKIP", color)
        lines.append(f"{tag}  {p.category:<10} {p.name:<32} {p.duration_ms:>5}ms  {p.detail}")
        if p.status == "fail" and p.evidence:
            for k, v in p.evidence.items():
                lines.append(f"        ↳ {k}: {str(v)[:200]}")
    lines.append("-" * 70)
    if counts["fail"]:
        lines.append(_color("31", f"  RESULT: RED ({counts['fail']} failure{'s' if counts['fail'] != 1 else ''})", color))
    elif counts["warn"]:
        lines.append(_color("33", f"  RESULT: YELLOW ({counts['warn']} warning{'s' if counts['warn'] != 1 else ''})", color))
    else:
        lines.append(_color("32", "  RESULT: GREEN", color))
    lines.append("=" * 70)
    return "\n".join(lines)


def render_json(probes: list[Probe], ctx: Context) -> str:
    data = {
        "agent_version": "1.0.0",
        "target": ctx.tars_base,
        "bridge_url": ctx.core_bridge_url,
        "authenticated": bool(ctx.bridge_shared_secret),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "total": len(probes),
            "pass": sum(1 for p in probes if p.status == "pass"),
            "fail": sum(1 for p in probes if p.status == "fail"),
            "warn": sum(1 for p in probes if p.status == "warn"),
            "skip": sum(1 for p in probes if p.status == "skip"),
        },
        "probes": [asdict(p) for p in probes],
    }
    return json.dumps(data, indent=2, default=str)




def maybe_escalate_alerts(
    probes: list[Probe],
    *,
    history_path: Path | str = DEFAULT_HISTORY_PATH,
    threshold: int = DEFAULT_THRESHOLD,
    enabled: bool = True,
) -> dict[str, Any]:
    """Wave 117 — update history.json and fire alerts on streaks.

    For every probe in this run we append the status to its rolling
    history. After updating, any probe with ``threshold`` consecutive
    fails (and not in ``KNOWN_FLAKY``) gets a ``send_alert`` call.
    """

    history = load_history(history_path)
    fired: dict[str, Any] = {}
    for p in probes:
        record_run(history, p.name, p.status)
        series = history.get("probes", {}).get(p.name, [])
        if (
            enabled
            and p.is_red()
            and p.name not in KNOWN_FLAKY
            and should_alert(series, threshold=threshold)
        ):
            fired[p.name] = send_alert(p.name, p.detail or "(no detail)")
    save_history(history, history_path)
    return {"history_path": str(history_path), "fired": fired}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qa_agent",
        description="TARS QA Agent — autonomous probe of tars.meeet.world + bridge.",
    )
    parser.add_argument(
        "--target", default=os.environ.get("TARS_BASE", "https://tars.meeet.world"),
        help="Base URL for TARS subdomain (default: env TARS_BASE or prod)",
    )
    parser.add_argument(
        "--core-bridge",
        default=os.environ.get(
            "CORE_BRIDGE_URL",
            "https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge",
        ),
        help="core-bridge endpoint URL",
    )
    parser.add_argument(
        "--tars-supabase",
        default=os.environ.get(
            "TARS_SUPABASE_URL", "https://hhpaukjobskcwkxbgecl.supabase.co"
        ),
        help="TARS Supabase project URL (where tars-downloads / tars-ingest live)",
    )
    parser.add_argument(
        "--bridge-secret",
        default=os.environ.get("BRIDGE_SHARED_SECRET", "") or None,
        help="Shared secret for authenticated core-bridge probes",
    )
    parser.add_argument(
        "--core-supabase",
        default=os.environ.get(
            "CORE_SUPABASE_URL", "https://zujrmifaabkletgnpoyw.supabase.co"
        ),
        help="Core (meeet.world) Supabase project URL — used for tars-ingest heartbeat",
    )
    parser.add_argument(
        "--ingest-api-key",
        default=None,
        help="Bearer / x-api-key for tars-ingest (default: env TARS_INGEST_API_KEY or MEEET_API_KEY)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of text"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable ANSI colors in text mode"
    )
    parser.add_argument(
        "--allow-warnings", action="store_true",
        help="Exit 0 if all FAILs are clean even if WARNs are present (default: WARN→0, FAIL→1)",
    )
    parser.add_argument(
        "--soft-fail", action="store_true",
        help=(
            "Always exit 0, even when probes FAIL. The report is still printed "
            "(and uploaded as an artefact in CI), so failures are visible to "
            "operators without turning the workflow red on upstream brokenness "
            "outside this repo (e.g. CF custom-domain bound to wrong project). "
            "Promote back to hard-fail once tars.meeet.world prod cutover is "
            "complete and B-019 is resolved. Set via env QA_AGENT_SOFT_FAIL=1."
        ),
    )
    parser.add_argument(
        "--escalate-alerts", action="store_true",
        help=(
            "Wave 117: persist run history to ~/.tars/qa-agent/history.json "
            "and call send_alert() for any probe with N consecutive fails. "
            "Set via env QA_AGENT_ESCALATE_ALERTS=1."
        ),
    )
    parser.add_argument(
        "--alert-threshold", type=int, default=DEFAULT_THRESHOLD,
        help=f"Consecutive-failure threshold for alerting (default {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--history-path", default=str(DEFAULT_HISTORY_PATH),
        help="Path to history.json for alert dedup (default: ~/.tars/qa-agent/history.json).",
    )
    args = parser.parse_args(argv)
    soft_fail = args.soft_fail or os.environ.get("QA_AGENT_SOFT_FAIL") in ("1", "true", "yes")
    escalate = args.escalate_alerts or os.environ.get("QA_AGENT_ESCALATE_ALERTS") in ("1", "true", "yes")
    ingest_key = resolved_ingest_api_key(args.ingest_api_key)

    ctx = Context(
        tars_base=args.target.rstrip("/"),
        core_bridge_url=args.core_bridge.rstrip("/"),
        tars_supabase_url=args.tars_supabase.rstrip("/"),
        core_supabase_url=args.core_supabase.rstrip("/"),
        tars_ingest_api_key=ingest_key,
        bridge_shared_secret=args.bridge_secret,
    )

    probes = run_all(ctx)

    if args.json:
        print(render_json(probes, ctx))
    else:
        color = not args.no_color and sys.stdout.isatty()
        print(render_text(probes, ctx, color))

    if escalate:
        alert_outcome = maybe_escalate_alerts(
            probes,
            history_path=args.history_path,
            threshold=args.alert_threshold,
            enabled=True,
        )
        if alert_outcome.get("fired"):
            print(
                f"::warning::qa_agent: alerts fired for {len(alert_outcome['fired'])} probe(s): "
                f"{','.join(alert_outcome['fired'].keys())}",
                file=sys.stderr,
            )

    fails = sum(1 for p in probes if p.status == "fail")
    if fails == 0:
        return 0
    if soft_fail:
        # Print the verdict but do not fail the process. Operators see the
        # FAIL annotations in the report; CI workflows pick the report up
        # as an artefact for triage. Used during the B-019 cutover where
        # prod tars.meeet.world is bound to the wrong CF Pages project.
        print(
            f"::warning::qa_agent: {fails} FAIL(s) suppressed by --soft-fail "
            "(see report for details — workflow stays green on upstream "
            "brokenness, must be removed once B-019 is resolved).",
            file=sys.stderr,
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
