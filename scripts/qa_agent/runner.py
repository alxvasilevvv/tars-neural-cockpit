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

from .probes import (
    Context,
    Probe,
    probe_core_bridge_health,
    probe_core_bridge_relay_roundtrip,
    probe_core_bridge_unauth,
    probe_dns,
    probe_manifest_origin,
    probe_manifest_origin_blocked,
    probe_manifest_subdomain,
    probe_robots,
    probe_root_ttfb,
    probe_security_headers,
    probe_session_cookie,
    probe_sitemap,
    probe_spa_root,
    probe_spa_routes,
    probe_tokenomics_invariants,
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

    # 3. schema (sitemap / robots)
    probes.append(probe_sitemap(ctx))
    probes.append(probe_robots(ctx))

    # 4. API / manifest (origin reachable independent of subdomain DNS)
    probes.append(probe_manifest_origin(ctx))
    probes.append(probe_manifest_origin_blocked(ctx))
    probes.append(probe_manifest_subdomain(ctx))

    # 5. core-bridge
    probes.append(probe_core_bridge_unauth(ctx))
    probes.append(probe_core_bridge_health(ctx))
    probes.append(probe_core_bridge_relay_roundtrip(ctx))

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
        "--json", action="store_true", help="Emit JSON instead of text"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable ANSI colors in text mode"
    )
    parser.add_argument(
        "--allow-warnings", action="store_true",
        help="Exit 0 if all FAILs are clean even if WARNs are present (default: WARN→0, FAIL→1)",
    )
    args = parser.parse_args(argv)

    ctx = Context(
        tars_base=args.target.rstrip("/"),
        core_bridge_url=args.core_bridge.rstrip("/"),
        tars_supabase_url=args.tars_supabase.rstrip("/"),
        bridge_shared_secret=args.bridge_secret,
    )

    probes = run_all(ctx)

    if args.json:
        print(render_json(probes, ctx))
    else:
        color = not args.no_color and sys.stdout.isatty()
        print(render_text(probes, ctx, color))

    fails = sum(1 for p in probes if p.status == "fail")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
