"""Pin the iframe + CORS contracts for the tars.meeet.world subdomain.

Two regressions guarded:

1. **Frame embedding (TARS#8 task 3b).** `experiments/neural-showcase-v3/
   public/_headers` must let `https://meeet.world` embed the cockpit in
   an iframe. We do that via CSP `frame-ancestors 'self'
   https://meeet.world` rather than `X-Frame-Options` because XFO
   cannot list multiple origins.

2. **CORS allowlist for `/api/product/*`** (TARS#8 task 5 +
   `docs/contracts/TARS_SUBDOMAIN.md` §4). The same-origin Pages
   Functions must echo `Access-Control-Allow-Origin: https://meeet.world`
   when an `Origin: https://meeet.world` request arrives, so the
   meeet.world marketing page can render the canonical TARS download
   widget directly from JS. Same-origin SPA traffic is unaffected.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SHOWCASE = REPO / "experiments" / "neural-showcase-v3"
HEADERS = SHOWCASE / "public" / "_headers"
CORS_MODULE = SHOWCASE / "functions" / "_cors.ts"
DOWNLOADS_FN = SHOWCASE / "functions" / "api" / "product" / "downloads.ts"
VERSION_FN = SHOWCASE / "functions" / "api" / "product" / "version.ts"


@pytest.fixture(scope="module")
def headers() -> str:
    return HEADERS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cors_module() -> str:
    return CORS_MODULE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def downloads_fn() -> str:
    return DOWNLOADS_FN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def version_fn() -> str:
    return VERSION_FN.read_text(encoding="utf-8")


# ---------- frame-ancestors ----------


def test_headers_csp_frame_ancestors_allows_meeet_world(headers: str) -> None:
    pattern = re.compile(
        r"^\s*Content-Security-Policy:\s*frame-ancestors\s+'self'\s+https://meeet\.world\b",
        re.IGNORECASE | re.MULTILINE,
    )
    assert pattern.search(headers), (
        "missing CSP `frame-ancestors 'self' https://meeet.world` directive — "
        "without it meeet.world cannot iframe the cockpit (TARS#8 task 3b)."
    )


def test_headers_no_x_frame_options_deny(headers: str) -> None:
    # XFO can only express DENY / SAMEORIGIN — keeping it would block
    # meeet.world embedding even if CSP allows it (the most restrictive
    # of the two wins on browsers that honour XFO).
    pattern = re.compile(r"^\s*X-Frame-Options:\s*DENY\b", re.IGNORECASE | re.MULTILINE)
    assert not pattern.search(headers), (
        "X-Frame-Options: DENY conflicts with CSP frame-ancestors and would "
        "block legitimate meeet.world iframe embedding."
    )


# ---------- CORS allowlist ----------


def test_cors_module_allowlist_includes_meeet_world_and_subdomain(cors_module: str) -> None:
    for required in ('"https://meeet.world"', '"https://tars.meeet.world"'):
        assert required in cors_module, f"CORS allowlist missing {required}"


def test_cors_module_includes_vary_origin(cors_module: str) -> None:
    assert 'vary: "Origin"' in cors_module, (
        "CORS responses must set `Vary: Origin` to prevent cache pollution "
        "between allowed and disallowed callers."
    )


def test_cors_module_handles_preflight(cors_module: str) -> None:
    assert "preflightResponse" in cors_module, "missing preflight helper"
    assert "204" in cors_module, "preflight should answer 204 No Content"


@pytest.mark.parametrize(
    "fn_name,fn_text",
    [
        ("downloads.ts", None),
        ("version.ts", None),
    ],
)
def test_pages_function_imports_cors(
    fn_name: str,
    fn_text: str | None,
    downloads_fn: str,
    version_fn: str,
) -> None:
    text = downloads_fn if fn_name == "downloads.ts" else version_fn
    assert 'import { corsHeaders, preflightResponse } from "../../_cors.ts"' in text, (
        f"{fn_name} must import the shared CORS helpers"
    )
    assert "corsHeaders(origin)" in text, f"{fn_name} must echo CORS headers in responses"
    assert 'request.method === "OPTIONS"' in text, f"{fn_name} must handle preflight"
