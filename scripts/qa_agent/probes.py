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
    # ``tars-ingest`` lives on the *core* Supabase project (`meeet.world` lane).
    # Default points at the canonical project URL. Override via CLI / env if
    # the heartbeat is being directed elsewhere (e.g. a staging mirror).
    core_supabase_url: str = "https://zujrmifaabkletgnpoyw.supabase.co"
    tars_ingest_api_key: str | None = None
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Treat redirects as terminal responses — we want to *see* the
    `Location` header instead of silently following it. Without this,
    urllib follows 302 → meeet.world and the probe reports a 200 from
    the wrong host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def _open(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> tuple[int, dict[str, str], bytes]:
    """One-shot HTTP. Returns (status, headers_lowered, body). Never raises.
    Does NOT follow redirects — see _NoRedirect."""
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, method=method, data=body, headers=h)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
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
            # WARN, not FAIL — DNS-not-yet is a blocking-but-known state during
            # bootstrap; we don't want CI cron to spam red while the Operator
            # is in the middle of setup. Once DNS is live, downstream subdomain
            # probes will run and any failures there are actionable.
            return _warn(
                "dns.tars_subdomain",
                "infra",
                f"{host} not resolving yet — pre-DNS state, downstream probes will skip",
                host=host,
                error=str(e),
            )

    return _timed(run)


# ---------- Subdomain HTTP surface ----------


SPA_ROUTES = [
    "/",
    "/install",
    "/pricing",
    "/faq",
    "/compare",
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


def _looks_like_lovable_redirect(status: int, hdrs: dict[str, str]) -> bool:
    """Detect the documented pre-cutover state where DNS is wired but the
    CNAME points at the Lovable wildcard. Symptom: 302 → meeet.world host.
    Probes downgrade to WARN in that case so CI doesn't go red on a
    known-and-tracked Operator-side blocker.
    """
    if status != 302:
        return False
    location = hdrs.get("location", "")
    # Match anything redirected off the tars subdomain, regardless of path.
    if "//meeet.world" in location or location.startswith("https://meeet.world"):
        return True
    return False


def probe_spa_root(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("http.spa_root", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "http.spa_root",
                "subdomain",
                "302 → meeet.world (CNAME points at Lovable wildcard, OPS_TODO Step 4 pending)",
                url=url,
            )
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
            if _looks_like_lovable_redirect(status, hdrs):
                return _warn(
                    f"http.route{_route}",
                    "subdomain",
                    "Lovable redirect (CNAME pre-cutover)",
                    url=_url,
                )
            if status != 200:
                return _fail(
                    f"http.route{_route}", "subdomain", f"expected 200, got {status}", url=_url
                )
            return _pass(f"http.route{_route}", "subdomain", "200 OK", url=_url)

        out.append(_timed(run))
    return out


def probe_unknown_route_returns_spa_200(ctx: Context) -> Probe:
    """Regression sentinel for the 2026-05-01 SPA `404.html` incident.

    Cloudflare Pages serves `404.html` with HTTP 404 even when the body
    is the SPA shell, which silently broke `/install`, `/cockpit`, etc.
    We assert that an unknown deep-link route returns HTTP 200 + the SPA
    shell, so the `_redirects` rule (`/* /index.html 200`) cannot
    silently regress to a `cp index.html 404.html` style fallback.
    """

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip(
                "http.unknown_route_spa_200", "subdomain", "DNS not live yet"
            )
        url = ctx.tars_base + "/__qa_agent_unknown_route_should_render_spa"
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "http.unknown_route_spa_200",
                "subdomain",
                "Lovable redirect (CNAME pre-cutover)",
                url=url,
            )
        if status != 200:
            return _fail(
                "http.unknown_route_spa_200",
                "subdomain",
                f"expected 200 (SPA fallback), got {status} — `_redirects` rule may be shadowed by 404.html",
                url=url,
                status=status,
            )
        if b"<div id=\"root\"></div>" not in body:
            return _fail(
                "http.unknown_route_spa_200",
                "subdomain",
                "200 returned but body is not SPA shell — wrong fallback",
                url=url,
            )
        return _pass(
            "http.unknown_route_spa_200",
            "subdomain",
            f"200 OK + SPA shell ({len(body)}B)",
            url=url,
        )

    return _timed(run)


def probe_security_headers(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("http.security_headers", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        status, hdrs, _body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "http.security_headers",
                "subdomain",
                "skipped — Lovable redirect (pre-cutover)",
                url=url,
            )
        # Hard requirements (never relaxed).
        required = {
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

        # Frame embedding gate: either CSP `frame-ancestors` or the
        # legacy `X-Frame-Options` must be present. The migration to
        # CSP `frame-ancestors 'self' https://meeet.world` (TARS#8 task
        # 3b) takes one deploy cycle; tolerate the old shape during
        # that window with a WARN, fail only when both are missing.
        csp = hdrs.get("content-security-policy", "")
        xfo = hdrs.get("x-frame-options", "")
        if "frame-ancestors" in csp:
            if "https://meeet.world" not in csp:
                return _warn(
                    "http.security_headers",
                    "subdomain",
                    "CSP frame-ancestors set but does not include https://meeet.world "
                    f"(got {csp!r})",
                )
            return _pass(
                "http.security_headers",
                "subdomain",
                "all required + CSP frame-ancestors allows meeet.world",
            )
        if xfo:
            return _warn(
                "http.security_headers",
                "subdomain",
                f"legacy X-Frame-Options ({xfo!r}); migrate to CSP frame-ancestors "
                "with https://meeet.world allowance (TARS#8 task 3b)",
            )
        return _fail(
            "http.security_headers",
            "subdomain",
            "no frame-ancestors / X-Frame-Options — anything can iframe the cockpit",
        )

    return _timed(run)


def probe_session_cookie(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("http.session_cookie", "subdomain", "DNS not live yet")
        url = ctx.tars_base + "/"
        # Send Accept: text/html so middleware emits the cookie.
        status, hdrs, _body = _open(
            "GET", url, headers={"Accept": "text/html"}, timeout=ctx.timeout_s
        )
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "http.session_cookie",
                "subdomain",
                "skipped — Lovable redirect (pre-cutover)",
                url=url,
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
        # Frontend and tars-downloads EF agree on `artifacts` (flat array of
        # {os, arch, kind, filename, url}). Older agent versions probed for
        # `platforms` (mapped object) — that field has never been part of
        # the contract.
        artifacts = rel.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False, f"releases[{i}].artifacts must be a non-empty array", data
        oses = {a.get("os") for a in artifacts if isinstance(a, dict)}
        # We don't require all three OSes (early releases ship one), but at
        # least one must be one of the supported set.
        supported = {"macos", "windows", "linux"}
        if not (oses & supported):
            return False, f"releases[{i}].artifacts has no supported OS (saw {sorted(oses)})", data
        for j, art in enumerate(artifacts):
            if not isinstance(art, dict):
                return False, f"releases[{i}].artifacts[{j}] not an object", data
            for required_key in ("os", "arch", "kind", "filename", "url"):
                if required_key not in art:
                    return False, f"releases[{i}].artifacts[{j}] missing '{required_key}'", data
            if not str(art["url"]).startswith("https://"):
                return False, f"releases[{i}].artifacts[{j}].url must be https", data
    return True, "valid manifest", data


def probe_manifest_subdomain(ctx: Context) -> Probe:
    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("api.manifest_subdomain", "api", "DNS not live yet")
        url = ctx.tars_base + "/api/product/downloads"
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "api.manifest_subdomain",
                "api",
                "skipped — Lovable redirect (pre-cutover)",
                url=url,
            )
        if status != 200:
            return _fail("api.manifest_subdomain", "api", f"expected 200, got {status}", url=url)
        ok, reason, _data = _validate_manifest(body)
        if not ok:
            return _fail("api.manifest_subdomain", "api", reason, url=url)
        return _pass("api.manifest_subdomain", "api", "200 + valid manifest", url=url)

    return _timed(run)


def probe_manifest_cors_meeet_world(ctx: Context) -> Probe:
    """`/api/product/downloads` must echo `Access-Control-Allow-Origin: https://meeet.world`.

    Required by `docs/contracts/TARS_SUBDOMAIN.md` §4 so meeet.world can
    render the download widget against the canonical TARS manifest from
    the browser. Pre-cutover (subdomain not live) the probe is skipped.
    """

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("api.manifest_cors", "api", "DNS not live yet")
        url = ctx.tars_base + "/api/product/downloads"
        status, hdrs, _body = _open(
            "GET",
            url,
            headers={"Origin": "https://meeet.world"},
            timeout=ctx.timeout_s,
        )
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "api.manifest_cors",
                "api",
                "skipped — Lovable redirect (pre-cutover)",
                url=url,
            )
        if status != 200:
            return _fail(
                "api.manifest_cors", "api", f"expected 200, got {status}", url=url
            )
        allow = hdrs.get("access-control-allow-origin", "")
        if allow != "https://meeet.world":
            # WARN (not FAIL) so the probe stays green during the
            # PR-before-deploy window. Promote to FAIL in a follow-up
            # once the deploy has landed and CORS is live in prod.
            return _warn(
                "api.manifest_cors",
                "api",
                f"expected Access-Control-Allow-Origin=https://meeet.world, got '{allow}'",
                url=url,
            )
        vary = hdrs.get("vary", "")
        if "Origin" not in vary:
            return _warn(
                "api.manifest_cors",
                "api",
                f"Vary header missing Origin (got '{vary}') — risk of cache pollution",
                url=url,
            )
        return _pass(
            "api.manifest_cors",
            "api",
            "Access-Control-Allow-Origin echoes meeet.world + Vary: Origin",
            url=url,
        )

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
        # The Supabase `tars-downloads` function is in the process of being
        # decommissioned now that the source of truth lives in the Pages
        # Function (`functions/api/product/downloads.ts`). Until the
        # operator removes it from the new project we still probe it,
        # but if it returns the legacy fallback shape that's still OK.
        if status == 404:
            return _skip(
                "api.manifest_origin",
                "api",
                "Supabase tars-downloads decommissioned (see TARS_MEEET_OPS_TODO §3)",
                url=url,
            )
        if status != 200:
            return _fail("api.manifest_origin", "api", f"expected 200, got {status}", url=url)
        ok, reason, _data = _validate_manifest(body)
        if not ok:
            return _fail("api.manifest_origin", "api", reason, url=url)
        return _pass("api.manifest_origin", "api", "200 + valid manifest", url=url)

    return _timed(run)


def probe_version_subdomain(ctx: Context) -> Probe:
    """Same-origin /api/product/version returns the embedded latest release."""

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("api.version_subdomain", "api", "DNS not live yet")
        url = ctx.tars_base + "/api/product/version"
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "api.version_subdomain",
                "api",
                "skipped — Lovable redirect (pre-cutover)",
                url=url,
            )
        if status != 200:
            return _fail(
                "api.version_subdomain",
                "api",
                f"expected 200, got {status}",
                url=url,
            )
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            return _fail(
                "api.version_subdomain",
                "api",
                f"invalid JSON: {exc}",
                url=url,
            )
        required = ("ok", "product", "contract_version", "channel", "version", "released_at")
        missing = [k for k in required if k not in data]
        if missing:
            return _fail(
                "api.version_subdomain",
                "api",
                f"missing keys: {','.join(missing)}",
                url=url,
            )
        if data.get("ok") is not True:
            return _fail("api.version_subdomain", "api", "ok != true", url=url)
        if data.get("contract_version") != CONTRACT_VERSION:
            return _fail(
                "api.version_subdomain",
                "api",
                f"unexpected contract_version: {data.get('contract_version')}",
                url=url,
            )
        version = str(data.get("version", ""))
        if not re.match(r"^\d+\.\d+\.\d+", version):
            return _fail(
                "api.version_subdomain",
                "api",
                f"version not semver-like: {version!r}",
                url=url,
            )
        return _pass(
            "api.version_subdomain",
            "api",
            f"200 + version={version}",
            url=url,
        )

    return _timed(run)


def probe_client_error_endpoint(ctx: Context) -> Probe:
    """`POST /api/client-error` must accept a well-formed payload.

    The Pages Function is the public surface for browser-side errors. It
    proxies into core-bridge via `BRIDGE_SHARED_SECRET`. Two healthy
    outcomes:
      • `persisted=true` → the bridge accepted the event end-to-end.
      • `persisted=false` with `bridge_unconfigured` → schema OK, but
        operator hasn't pasted the secret yet → warn, do not fail.
    Anything else is a fail.
    """

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("api.client_error", "api", "DNS not live yet")
        url = ctx.tars_base + "/api/client-error"
        trace_id = uuid.uuid4().hex
        session_id = "qa-agent-" + uuid.uuid4().hex[:12]
        payload = {
            "kind": "tars.client.error",
            "trace_id": trace_id,
            "session_id": session_id,
            "contract_version": CONTRACT_VERSION,
            "payload": {
                "sub_kind": "qa.synthetic",
                "message": "QA agent synthetic error report",
                "url": ctx.tars_base + "/__qa__",
                "user_agent": USER_AGENT,
                "released_at_client": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        status, hdrs, body = _open(
            "POST",
            url,
            headers={
                "content-type": "application/json",
                "x-tars-contract": CONTRACT_VERSION,
                "x-trace-id": trace_id,
            },
            body=body_bytes,
            timeout=ctx.timeout_s,
        )
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "api.client_error",
                "api",
                "skipped — Lovable redirect (pre-cutover)",
                url=url,
            )
        if status != 200:
            return _fail(
                "api.client_error",
                "api",
                f"expected 200, got {status}: {body[:200]!r}",
                url=url,
            )
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            return _fail("api.client_error", "api", f"invalid JSON: {exc}", url=url)
        if data.get("ok") is not True:
            return _fail("api.client_error", "api", f"ok != true: {data!r}", url=url)
        if data.get("persisted") is True:
            return _pass(
                "api.client_error",
                "api",
                "synthetic error persisted via core-bridge",
                url=url,
                trace_id=trace_id,
            )
        reason = str(data.get("reason") or data.get("upstream") or "")
        if "bridge_unconfigured" in reason:
            return _warn(
                "api.client_error",
                "api",
                "schema OK but BRIDGE_SHARED_SECRET not pasted yet — see TARS_MEEET_OPS_TODO §1",
                url=url,
                trace_id=trace_id,
            )
        return _fail(
            "api.client_error",
            "api",
            f"persisted=false and not bridge_unconfigured: {data!r}",
            url=url,
        )

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
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "schema.sitemap", "subdomain", "skipped — Lovable redirect (pre-cutover)", url=url
            )
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
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "schema.robots", "subdomain", "skipped — Lovable redirect (pre-cutover)", url=url
            )
        if status != 200:
            return _fail("schema.robots", "subdomain", f"expected 200, got {status}", url=url)
        text = body.decode("utf-8", errors="replace")
        if "Sitemap:" not in text:
            return _fail("schema.robots", "subdomain", "robots.txt missing Sitemap line", url=url)
        return _pass("schema.robots", "subdomain", "robots.txt valid", url=url)

    return _timed(run)


# ---------- Economy invariant probes ----------


def probe_tokenomics_invariants() -> Probe:
    """Read the cockpit Tokenomics page source and assert distribution sums to 100%.

    The TARS cockpit (this repo) does not own the tokenomics page — that
    lives in `meeet.world` (Lovable). We still keep the probe so that if
    we ever add a `Tokenomics.tsx` mirror locally, it gets validated. In
    the meantime the probe SKIPs cleanly rather than failing.
    """

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
                    "Tokenomics page lives in meeet.world (Lovable lane), not in this repo",
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
        status, hdrs, _body = _open("GET", url, timeout=ctx.timeout_s)
        dt_ms = int((time.perf_counter() - t0) * 1000)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(
                "perf.ttfb_root",
                "subdomain",
                f"skipped — Lovable redirect (pre-cutover, ttfb {dt_ms}ms)",
                url=url,
                ttfb_ms=dt_ms,
            )
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


# ---------- meeet.world heartbeat (tars-ingest) ----------


def probe_meeet_ingest_heartbeat(ctx: Context) -> Probe:
    """Synthetic ``awareness.snapshot.completed`` heartbeat into ``tars-ingest``.

    Goal: prove end-to-end that the meeet bridge has somewhere live to
    ingest TARS events. We don't go through the Python client here — the
    probe must work even when the operator runs the QA agent without the
    full backend installed. We simulate exactly what
    ``MeeetClient.emit("awareness.snapshot.completed", ...)`` would put on
    the wire.

    Healthy outcomes:

      • 200 with ``{ok: true, accepted: 1}`` → end-to-end green.
      • 200 with ``persisted: false`` and ``warning`` mentioning the
        ingest table → schema accepted, persistence not wired yet → warn.
      • 401 ``unauthorized`` → fail (operator forgot the API key).
      • 0 / network error → warn (offline).
    """

    def run() -> Probe:
        ingest_url = ctx.core_supabase_url.rstrip("/") + "/functions/v1/tars-ingest"
        trace_id = uuid.uuid4().hex
        session_id = "qa-agent-" + uuid.uuid4().hex[:12]
        payload = {
            "kind": "awareness.snapshot.completed",
            "trace_id": trace_id,
            "session_id": session_id,
            "source": "tars-qa-agent",
            "contract_version": CONTRACT_VERSION,
            "ts": time.time(),
            "payload": {
                "slug": "qa.synthetic",
                "source_id": "qa.heartbeat",
                "took_ms": 1,
                "ok": True,
                "agent": "tars-qa-agent",
            },
        }
        headers: dict[str, str] = {
            "content-type": "application/json",
            "x-meeet-contract-version": CONTRACT_VERSION,
            "x-tars-contract-version": CONTRACT_VERSION,
        }
        if ctx.tars_ingest_api_key:
            headers["authorization"] = f"Bearer {ctx.tars_ingest_api_key}"
            headers["x-api-key"] = ctx.tars_ingest_api_key
        body_bytes = json.dumps(payload).encode("utf-8")
        status, _hdrs, body = _open(
            "POST",
            ingest_url,
            headers=headers,
            body=body_bytes,
            timeout=ctx.timeout_s,
        )
        if status == 0:
            return _warn(
                "meeet.ingest_heartbeat",
                "meeet",
                "tars-ingest unreachable (offline?)",
                url=ingest_url,
                error=body[:200].decode("utf-8", errors="replace"),
            )
        if status == 401:
            # No key configured → operator action gap, keep CI yellow not red
            # (mirrors how api.client_error handles bridge_unconfigured).
            if not ctx.tars_ingest_api_key:
                return _warn(
                    "meeet.ingest_heartbeat",
                    "meeet",
                    "tars-ingest enforcing auth — set TARS_INGEST_API_KEY or MEEET_API_KEY "
                    "(see docs/TARS_MEEET_OPS_TODO §1 step 4)",
                    url=ingest_url,
                    trace_id=trace_id,
                )
            return _fail(
                "meeet.ingest_heartbeat",
                "meeet",
                "tars-ingest rejected request (TARS_INGEST_API_KEY mismatch)",
                url=ingest_url,
                trace_id=trace_id,
            )
        if status == 405:
            return _warn(
                "meeet.ingest_heartbeat",
                "meeet",
                "tars-ingest reported method_not_allowed — function not deployed?",
                url=ingest_url,
            )
        if status != 200:
            return _fail(
                "meeet.ingest_heartbeat",
                "meeet",
                f"expected 200, got {status}: {body[:200]!r}",
                url=ingest_url,
                trace_id=trace_id,
            )
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            return _fail(
                "meeet.ingest_heartbeat",
                "meeet",
                f"non-JSON response: {exc}",
                url=ingest_url,
            )
        if data.get("ok") is not True:
            return _fail(
                "meeet.ingest_heartbeat",
                "meeet",
                f"ok != true: {data!r}",
                url=ingest_url,
                trace_id=trace_id,
            )
        accepted = int(data.get("accepted") or 0)
        if accepted < 1:
            return _fail(
                "meeet.ingest_heartbeat",
                "meeet",
                f"no events accepted: {data!r}",
                url=ingest_url,
                trace_id=trace_id,
            )
        if data.get("persisted") is False:
            return _warn(
                "meeet.ingest_heartbeat",
                "meeet",
                f"accepted but not persisted: {data.get('warning') or 'no detail'}",
                url=ingest_url,
                trace_id=trace_id,
            )
        return _pass(
            "meeet.ingest_heartbeat",
            "meeet",
            f"awareness.snapshot.completed accepted+persisted (trace {trace_id[:8]})",
            url=ingest_url,
            trace_id=trace_id,
            accepted=accepted,
        )

    return _timed(run)


# ---------- Wave 117: comprehensive route + bundle probes ----------


# Critical SPA routes — every entry must HTTP 200, render the SPA shell,
# and not contain hard error markers. Title/heading hints in the second
# tuple slot are matched against the first 5 KB of the response body
# (case-insensitive); the probe still passes if the SPA shell is intact
# even when the title hint is absent (the SPA renders titles via JS
# after hydration). Hints exist mainly to flag wholesale page swaps.
WAVE117_ROUTES: list[tuple[str, list[str]]] = [
    ("/", ["TARS", "your machine"]),
    ("/install", ["install"]),
    ("/cockpit", ["cockpit"]),
    ("/pricing", ["pricing"]),
    ("/compare", ["TARS"]),
    ("/faq", ["faq"]),
    ("/workshop", ["workshop"]),
    ("/workshop/enterprise", ["workshop"]),
    ("/workshop/roi", ["roi"]),
    ("/workshop/materials", ["materials"]),
    ("/workshop/assess", ["assess"]),
    ("/workshop/cohort", ["cohort"]),
    ("/dashboard", ["dashboard"]),
    ("/onboard/org", ["onboard"]),
    ("/inbox", ["inbox"]),
    ("/files", ["files"]),
    ("/reports", ["reports"]),
    ("/marketplace", ["marketplace"]),
    ("/compliance", ["compliance"]),
    ("/workspaces", ["workspaces"]),
    ("/bundles", ["bundles"]),
    ("/admin/perf", ["perf"]),
    ("/schedules", ["schedules"]),
    ("/outreach", ["outreach"]),
]


# JS runtime / build-time error markers that should never appear in the
# initial HTML response. If they do, prod is serving a broken bundle.
_HTML_ERROR_MARKERS = (
    b"is not defined",
    b"RENDER ERROR",
    b"Application error",
    b"Internal Server Error",
    b"<title>500</title>",
    b"<title>Error</title>",
    b"Cannot GET",
)


def probe_route_renders(
    ctx: Context,
    route: str,
    expected_titles: list[str] | None = None,
) -> Probe:
    """Verify a single route returns 200 + SPA shell, no error markers.

    The SPA boots client-side so JS runtime errors won't show up here —
    that's what the Wave 116 vitest smoke-render covers. This probe
    catches the strictly-server-observable failure mode: 5xx, totally
    wrong body, or markers leaking through the build.
    """

    name = f"http.route_v117{route.replace('/', '_') or '_root'}"

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip(name, "routes", "DNS not live yet")
        url = ctx.tars_base + route
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn(name, "routes", "Lovable redirect (pre-cutover)", url=url)
        if status != 200:
            return _fail(
                name,
                "routes",
                f"expected 200, got {status}",
                url=url,
                status=status,
            )
        if b"<div id=\"root\"></div>" not in body:
            return _fail(
                name,
                "routes",
                "SPA shell (`<div id=\"root\"></div>`) missing — wrong build?",
                url=url,
            )
        for marker in _HTML_ERROR_MARKERS:
            if marker in body:
                return _fail(
                    name,
                    "routes",
                    f"error marker present in HTML: {marker.decode('utf-8', 'replace')!r}",
                    url=url,
                )
        if expected_titles:
            head = body[:5120].lower()
            hits = [t for t in expected_titles if t.lower().encode("utf-8") in head]
            if not hits:
                # Soft signal — the SPA fills <title> on hydration, so the
                # initial HTML may not contain the route-specific phrase.
                # WARN, don't FAIL.
                return _warn(
                    name,
                    "routes",
                    f"no expected_titles hit in first 5KB (looked for {expected_titles})",
                    url=url,
                )
        return _pass(name, "routes", f"200 OK, {len(body)}B, shell ok", url=url)

    return _timed(run)


def probe_all_routes(ctx: Context) -> list[Probe]:
    """Run probe_route_renders for every WAVE117_ROUTES entry."""
    return [probe_route_renders(ctx, route, hints) for route, hints in WAVE117_ROUTES]


_SW_VERSION_RE = re.compile(rb"VERSION\s*=\s*[\"']([^\"']+)[\"']")
_SW_EXPECTED_PREFIX_RE = re.compile(r"^(?:tars-)?v?9\.\d+\.\d+")


def probe_sw_version(ctx: Context) -> Probe:
    """Fetch /sw.js and surface the VERSION constant.

    Used to correlate user reports with SW state (a stale SW serving
    pre-Wave-114 cached HTML is the exact failure mode that drove
    Waves 114/115). We don't fail on a particular value — we fail
    only when sw.js is missing or VERSION can't be parsed; we WARN
    when VERSION doesn't match the expected v9.x.y pattern.
    """

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("pwa.sw_version", "pwa", "DNS not live yet")
        url = ctx.tars_base + "/sw.js"
        status, hdrs, body = _open("GET", url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn("pwa.sw_version", "pwa", "Lovable redirect", url=url)
        if status != 200:
            return _fail(
                "pwa.sw_version",
                "pwa",
                f"expected 200, got {status}",
                url=url,
            )
        m = _SW_VERSION_RE.search(body)
        if not m:
            return _fail(
                "pwa.sw_version",
                "pwa",
                "VERSION constant not found in /sw.js — SW shape changed?",
                url=url,
            )
        version = m.group(1).decode("utf-8", errors="replace")
        normalized = version.replace("tars-", "")
        if not _SW_EXPECTED_PREFIX_RE.match(normalized):
            return _warn(
                "pwa.sw_version",
                "pwa",
                f"SW VERSION {version!r} doesn't match v9.x.y pattern",
                url=url,
                version=version,
            )
        return _pass(
            "pwa.sw_version",
            "pwa",
            f"VERSION={version}",
            url=url,
            version=version,
        )

    return _timed(run)


_SCRIPT_SRC_RE = re.compile(
    rb"<script[^>]*\bsrc=[\"']([^\"']+\.js)[\"'][^>]*>",
    re.IGNORECASE,
)


def probe_bundle_imports(ctx: Context) -> Probe:
    """Fetch the main JS bundle from index.html and verify it's healthy.

    Checks:
      * bundle is referenced from index.html (one or more <script src=...>)
      * bundle is >100 KB (a chunked-out router.js is fine; we check the
        largest JS reference)
      * bundle contains the literal string ``Workshop`` (proves Workshop
        page is in the build — direct prevention against the Wave 114
        500 caused by a missing Workshop lazy import)
      * bundle has roughly balanced parens (sanity check against a
        truncated download / partial deploy)
    """

    def run() -> Probe:
        if ctx.skip_subdomain:
            return _skip("bundle.imports", "bundle", "DNS not live yet")
        # Fetch index.html
        idx_url = ctx.tars_base + "/"
        status, hdrs, body = _open("GET", idx_url, timeout=ctx.timeout_s)
        if _looks_like_lovable_redirect(status, hdrs):
            return _warn("bundle.imports", "bundle", "Lovable redirect", url=idx_url)
        if status != 200:
            return _fail(
                "bundle.imports",
                "bundle",
                f"index.html status {status}",
                url=idx_url,
            )
        scripts = _SCRIPT_SRC_RE.findall(body)
        if not scripts:
            return _fail(
                "bundle.imports",
                "bundle",
                "no <script src=*.js> in index.html — build broken?",
                url=idx_url,
            )
        # Pick the largest plausible bundle URL — Vite's hashed
        # `assets/index-*.js` is what we want.
        candidates = [s.decode("utf-8", "replace") for s in scripts]
        # Resolve to absolute URL.
        bundles: list[str] = []
        for src in candidates:
            if src.startswith("http"):
                bundles.append(src)
            else:
                bundles.append(ctx.tars_base.rstrip("/") + "/" + src.lstrip("/"))
        # Try each candidate; first one that's >100KB wins.
        chosen_url = ""
        chosen_body = b""
        for u in bundles:
            s2, _h2, b2 = _open("GET", u, timeout=ctx.timeout_s)
            if s2 == 200 and len(b2) > 100 * 1024:
                chosen_url = u
                chosen_body = b2
                break
        if not chosen_body:
            return _fail(
                "bundle.imports",
                "bundle",
                f"no JS bundle >100KB among {len(bundles)} <script> tag(s)",
                url=idx_url,
                candidates=bundles[:5],
            )
        if b"Workshop" not in chosen_body:
            return _fail(
                "bundle.imports",
                "bundle",
                "bundle missing 'Workshop' literal — Wave 114 regression",
                url=chosen_url,
            )
        opens = chosen_body.count(b"(")
        closes = chosen_body.count(b")")
        # Allow up to 2% drift from string literals containing parens.
        drift = abs(opens - closes)
        ceiling = max(50, opens // 50)
        if drift > ceiling:
            return _fail(
                "bundle.imports",
                "bundle",
                f"paren imbalance: {opens} open vs {closes} close (drift {drift} > {ceiling})",
                url=chosen_url,
            )
        return _pass(
            "bundle.imports",
            "bundle",
            f"{len(chosen_body) // 1024}KB, has Workshop, parens ok",
            url=chosen_url,
        )

    return _timed(run)
