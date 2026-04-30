"""
qa_agent.probes — individual probe implementations.

Each probe is a callable that takes a `Context` and returns a `Probe`
record. Probes never raise; they always return a Probe (even on
exception). The orchestrator in qa_agent.runner sequences them and
aggregates the report.
"""

from __future__ import annotations

import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_TIMEOUT_S = 8.0
USER_AGENT = "TARS-QA-Agent/1.0 (+https://tars.meeet.world)"
CONTRACT_VERSION = "1.0.0"


@dataclass
class Context:
    """Runtime configuration shared by every probe."""

    tars_base: str = "https://tars.meeet.world"
    core_bridge_url: str = (
        "https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/core-bridge"
    )
    tars_supabase_url: str = "https://hhpaukjobskcwkxbgecl.supabase.co"
    bridge_shared_secret: str | None = None
    skip_subdomain: bool = False
    skip_authenticated: bool = False
    timeout_s: float = DEFAULT_TIMEOUT_S


@dataclass
class Probe:
    """Single test outcome."""

    name: str
    category: str
    status: str  # "pass" | "fail" | "skip" | "warn"
    detail: str = ""
    duration_ms: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)

    def is_red(self) -> bool:
        return self.status == "fail"


# ---------- HTTP helpers (stdlib only) ----------


def _open(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> tuple[int, dict[str, str], bytes]:
    """One-shot HTTP. Returns (status, headers_lowered, body). Never raises."""
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, method=method, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, hdrs, raw
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:
            raw = b""
        hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
        return e.code, hdrs, raw
    except (urllib.error.URLError, ssl.SSLError, socket.timeout, OSError) as e:
        return 0, {}, str(e).encode("utf-8")


def _timed(fn: Callable[[], Probe]) -> Probe:
    t0 = time.perf_counter()
    p = fn()
    p.duration_ms = int((time.perf_counter() - t0) * 1000)
    return p


def _pass(name: str, category: str, detail: str = "", **evidence: Any) -> Probe:
    return Probe(name=name, category=category, status="pass", detail=detail, evidence=evidence)


def _fail(name: str, category: str, detail: str, **evidence: Any) -> Probe:
    return Probe(name=name, category=category, status="fail", detail=detail, evidence=evidence)


def _skip(name: str, category: str, detail: str) -> Probe:
    return Probe(name=name, category=category, status="skip", detail=detail)


def _warn(name: str, category: str, detail: str, **evidence: Any) -> Probe:
    return Probe(name=name, category=category, status="warn", detail=detail, evidence=evidence)


# ---------- DNS / reachability ----------


def probe_dns(ctx: Context) -> Probe:
    def run() -> Probe:
        host = urllib.parse.urlparse(ctx.tars_base).hostname or ""
        try:
            ip = socket.gethostbyname(host)
            return _pass("dns.tars_subdomain", "infra", f"{host} → {ip}", host=host, ip=ip)
        except socket.gaierror as e:
            return _fail(
                "dns.tars_subdomain",
                "infra",
                f"{host} not resolving — DNS not provisioned yet",
                host=host,
                error=str(e),
            )

    return _timed(run)


# ---------- Subdomain HTTP surface ----------


SPA_ROUTES = [
    "/",
    "/install",
    "/cockpit",
    "/onboarding",
    "/build-with",
    "/changelog",
    "/docs",
    "/pitch",
    "/press",
    "/privacy",
    "/roadmap",
    "/security",
    "/status",
    "/terms",
]


def probe_spa_root(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("http.spa_root", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if status != 200:
            return _fail("http.spa_root", "subdomain", f"expected 200, got {status}", url=url)
        contract = hdrs.get("x-tars-contract", "")
        if contract != CONTRACT_VERSION:
            return _fail(
                "http.spa_root",
                "subdomain",
                f"missing/wrong X-Tars-Contract header: '{contract}'",
                url=url,
            )
        # SPA hydration sanity
        if b"<div id=\"root\"></div>" not in body:
            return _warn(
                "http.spa_root",
                "subdomain",
                "root div not detected — SPA may be misbuilt",
                url=url,
            )
        return _pass(
            "http.spa_root",
            "subdomain",
            f"200 OK, contract {contract}, body {len(body)}B",
            url=url,
        )

    return _timed(run)


def probe_spa_routes(ctx: Context) -> list[Probe]:
    if ctx.skip_subdomain:
        return [_skip(f"http.route{r}", "subdomain", "DNS not live yet") for r in SPA_ROUTES]
    out: list[Probe] = []
    for route in SPA_ROUTES:
        url = ctx.tars_base + route

        def run(_url: str = url, _route: str = route) -> Probe:
            status, hdrs, _body = _open("GET", _url, timeout=ctx.timeout_s)
            if status != 200:
                return _fail(
                    f"http.route{_route}", "subdomain", f"expected 200, got {status}", url=_url
                )
            return _pass(f"http.route{_route}", "subdomain", "200 OK", url=_url)

        out.append(_timed(run))
    return out


def probe_security_headers(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("http.security_headers", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        _status, hdrs, _body = _open("GET", url, timeout=ctx.timeout_s)
        required = {
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
            "strict-transport-security": "max-age=",
        }
        missing = []
        for k, expected_substr in required.items():
            v = hdrs.get(k, "")
            if expected_substr not in v:
                missing.append(f"{k}: '{v}' (expected to contain '{expected_substr}')")
        if missing:
            return _fail("http.security_headers", "subdomain", "; ".join(missing))
        return _pass("http.security_headers", "subdomain", "all required security headers present")

    return _timed(run)


def probe_session_cookie(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("http.session_cookie", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        # Send Accept: text/html so middleware emits the cookie.
        _status, hdrs, _body = _open(
            "GET", url, headers={"Accept": "text/html"}, timeout=ctx.timeout_s
        )
        set_cookie = hdrs.get("set-cookie", "")
        if "tars_session_id=" not in set_cookie:
            return _fail(
                "http.session_cookie",
                "subdomain",
                "tars_session_id cookie not issued",
                set_cookie=set_cookie,
            )
        if "Domain=.meeet.world" not in set_cookie and "domain=.meeet.world" not in set_cookie:
            return _fail(
                "http.session_cookie",
                "subdomain",
                "cookie missing Domain=.meeet.world",
                set_cookie=set_cookie,
            )
        for required in ("HttpOnly", "Secure", "SameSite=Lax"):
            if required not in set_cookie:
                return _fail(
                    "http.session_cookie",
                    "subdomain",
                    f"cookie missing attribute '{required}'",
                    set_cookie=set_cookie,
                )
        return _pass("http.session_cookie", "subdomain", "cookie OK with all required attributes")

    return _timed(run)


# ---------- Manifest / API endpoints ----------


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.][\w.]+)?$")


def _validate_manifest(body: bytes) -> tuple[bool, str, dict[str, Any]]:
    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, f"invalid JSON: {e}", {}
    if not isinstance(data, dict):
        return False, "manifest must be a JSON object", {}
    if data.get("contract_version") != CONTRACT_VERSION:
        return False, f"contract_version must be '{CONTRACT_VERSION}', got '{data.get('contract_version')}'", data
    releases = data.get("releases")
    if not isinstance(releases, list) or not releases:
        return False, "releases must be a non-empty array", data
    for i, rel in enumerate(releases):
        if not isinstance(rel, dict):
            return False, f"releases[{i}] must be an object", data
        ver = rel.get("version", "")
        if not isinstance(ver, str) or not _SEMVER_RE.match(ver.lstrip("v")):
            return False, f"releases[{i}].version '{ver}' not semver", data
        plats = rel.get("platforms")
        if not isinstance(plats, dict) or not plats:
            return False, f"releases[{i}].platforms must be a non-empty object", data
    return True, "valid manifest", data


def probe_manifest_subdomain(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("api.manifest_subdomain", "api", "DNS not live yet")
        url = ctx.tars_base + "/api/product/downloads"
        status, _hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if status != 200:
            return _fail("api.manifest_subdomain", "api", f"expected 200, got {status}", url=url)
        ok, reason, _data = _validate_manifest(body)
        if not ok:
            return _fail("api.manifest_subdomain", "api", reason, url=url)
        return _pass("api.manifest_subdomain", "api", "200 + valid manifest", url=url)

    return _timed(run)


def probe_manifest_origin(ctx: Context) -> Probe:
    def run() -> Probe:
        url = ctx.tars_supabase_url + "/functions/v1/tars-downloads"
        status, _hdrs, body = _open(
            "GET",
            url,
            headers={"Origin": "https://tars.meeet.world"},
            timeout=ctx.timeout_s,
        )
        if status != 200:
            return _fail("api.manifest_origin", "api", f"expected 200, got {status}", url=url)
        ok, reason, _data = _validate_manifest(body)
        if not ok:
            return _fail("api.manifest_origin", "api", reason, url=url)
        return _pass("api.manifest_origin", "api", "200 + valid manifest", url=url)

    return _timed(run)


def probe_manifest_origin_blocked(ctx: Context) -> Probe:
    """Disallowed Origin must be 403'd by tars-downloads."""

    def run() -> Probe:
        url = ctx.tars_supabase_url + "/functions/v1/tars-downloads"
        status, _hdrs, _body = _open(
            "GET",
            url,
            headers={"Origin": "https://evil.example.com"},
            timeout=ctx.timeout_s,
        )
        if status == 403:
            return _pass("api.manifest_origin_blocked", "api", "evil origin 403 as expected")
        # Allow 200 only as a known degradation; warn loudly.
        if status == 200:
            return _warn(
                "api.manifest_origin_blocked",
                "api",
                "evil origin returned 200 — TARS_ALLOWED_ORIGINS may be permissive",
                url=url,
            )
        return _fail(
            "api.manifest_origin_blocked",
            "api",
            f"unexpected status {status}",
            url=url,
        )

    return _timed(run)


# ---------- core-bridge probes ----------


def probe_core_bridge_health(ctx: Context) -> Probe:
    def run() -> Probe:
        if not ctx.bridge_shared_secret:
            return _skip(
                "api.core_bridge_health",
                "bridge",
                "BRIDGE_SHARED_SECRET not provided",
            )
        url = ctx.core_bridge_url + "/health"
        status, _hdrs, body = _open(
            "GET",
            url,
            headers={
                "x-bridge-secret": ctx.bridge_shared_secret,
                "Origin": "https://tars.meeet.world",
            },
            timeout=ctx.timeout_s,
        )
        if status != 200:
            return _fail(
                "api.core_bridge_health",
                "bridge",
                f"expected 200, got {status}",
                url=url,
                body=body[:200].decode("utf-8", errors="replace"),
            )
        return _pass("api.core_bridge_health", "bridge", "200 OK", url=url)

    return _timed(run)


def probe_core_bridge_unauth(ctx: Context) -> Probe:
    def run() -> Probe:
        url = ctx.core_bridge_url + "/health"
        status, _hdrs, _body = _open(
            "GET",
            url,
            headers={"Origin": "https://tars.meeet.world"},
            timeout=ctx.timeout_s,
        )
        if status in (401, 403):
            return _pass("api.core_bridge_unauth", "bridge", f"unauth blocked with {status}")
        return _fail(
            "api.core_bridge_unauth",
            "bridge",
            f"expected 401/403 without secret, got {status}",
            url=url,
        )

    return _timed(run)


def probe_core_bridge_relay_roundtrip(ctx: Context) -> Probe:
    def run() -> Probe:
        if not ctx.bridge_shared_secret:
            return _skip(
                "api.relay_roundtrip",
                "bridge",
                "BRIDGE_SHARED_SECRET not provided",
            )
        url = ctx.core_bridge_url + "/relay-event"
        trace_id = f"qa_agent_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        payload = {
            "kind": "tars.qa.probe",
            "trace_id": trace_id,
            "session_id": f"qa_agent_session_{uuid.uuid4().hex[:8]}",
            "contract_version": CONTRACT_VERSION,
            "payload": {"source": "qa_agent", "host": ctx.tars_base},
        }
        status, _hdrs, body = _open(
            "POST",
            url,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://tars.meeet.world",
                "x-bridge-secret": ctx.bridge_shared_secret,
            },
            body=json.dumps(payload).encode("utf-8"),
            timeout=ctx.timeout_s,
        )
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}
        if status != 200 or data.get("ok") is not True:
            return _fail(
                "api.relay_roundtrip",
                "bridge",
                f"relay rejected (status {status})",
                url=url,
                body=body[:300].decode("utf-8", errors="replace"),
            )
        return _pass(
            "api.relay_roundtrip",
            "bridge",
            f"relay accepted (trace_id={trace_id})",
            url=url,
            trace_id=trace_id,
        )

    return _timed(run)


# ---------- Schema probes ----------


def probe_sitemap(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("schema.sitemap", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/sitemap.xml"
        status, _hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if status != 200:
            return _fail("schema.sitemap", "subdomain", f"expected 200, got {status}", url=url)
        text = body.decode("utf-8", errors="replace")
        if "<urlset" not in text or "<loc>" not in text:
            return _fail("schema.sitemap", "subdomain", "sitemap.xml malformed", url=url)
        if "tars.meeet.world" not in text:
            return _warn(
                "schema.sitemap",
                "subdomain",
                "sitemap.xml does not mention tars.meeet.world (canonical-flip pending)",
                url=url,
            )
        return _pass(
            "schema.sitemap",
            "subdomain",
            f"valid sitemap with {text.count('<loc>')} urls",
            url=url,
        )

    return _timed(run)


def probe_robots(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("schema.robots", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/robots.txt"
        status, _hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if status != 200:
            return _fail("schema.robots", "subdomain", f"expected 200, got {status}", url=url)
        text = body.decode("utf-8", errors="replace")
        if "Sitemap:" not in text:
            return _fail("schema.robots", "subdomain", "robots.txt missing Sitemap line", url=url)
        return _pass("schema.robots", "subdomain", "robots.txt valid", url=url)

    return _timed(run)


# ---------- Economy invariant probes ----------


def probe_tokenomics_invariants() -> Probe:
    """Read the cockpit Tokenomics page source and assert distribution sums to 100%."""

    def run() -> Probe:
        try:
            from pathlib import Path

            tok_path = Path(
                "experiments/neural-showcase-v3/src/pages/Tokenomics.tsx"
            )
            if not tok_path.exists():
                return _skip(
                    "economy.tokenomics_invariants",
                    "economy",
                    f"{tok_path} not present",
                )
            text = tok_path.read_text(encoding="utf-8")
            pcts = [int(m) for m in re.findall(r"pct:\s*(\d+)", text)]
            if not pcts:
                return _skip(
                    "economy.tokenomics_invariants",
                    "economy",
                    "no pct fields detected — schema may have changed",
                )
            total = sum(pcts)
            if total != 100:
                return _fail(
                    "economy.tokenomics_invariants",
                    "economy",
                    f"distribution percentages sum to {total}, not 100",
                    parts=pcts,
                )
            return _pass(
                "economy.tokenomics_invariants",
                "economy",
                f"distribution sums to 100 across {len(pcts)} buckets",
                parts=pcts,
            )
        except Exception as e:
            return _fail(
                "economy.tokenomics_invariants",
                "economy",
                f"unexpected: {e}",
            )

    return _timed(run)


# ---------- Performance probes ----------


def probe_root_ttfb(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("perf.ttfb_root", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        t0 = time.perf_counter()
        status, _hdrs, _body = _open("GET", url, timeout=ctx.timeout_s)
        dt_ms = int((time.perf_counter() - t0) * 1000)
        if status != 200:
            return _fail("perf.ttfb_root", "subdomain", f"got {status}", url=url, ttfb_ms=dt_ms)
        # Edge-served HTML should be < 800ms even from a hot cache miss.
        if dt_ms > 1500:
            return _fail(
                "perf.ttfb_root",
                "subdomain",
                f"root request {dt_ms}ms > 1500ms threshold",
                url=url,
                ttfb_ms=dt_ms,
            )
        if dt_ms > 800:
            return _warn(
                "perf.ttfb_root",
                "subdomain",
                f"root request {dt_ms}ms > 800ms target (still under 1.5s ceiling)",
                url=url,
                ttfb_ms=dt_ms,
            )
        return _pass("perf.ttfb_root", "subdomain", f"{dt_ms}ms", url=url, ttfb_ms=dt_ms)

    return _timed(run)
