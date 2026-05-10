"""DuckDuckGo HTML adapter — keyless fallback.

DuckDuckGo's API is officially the Instant Answer endpoint, but it
only returns "0-click" results (definitions, dictionary, etc.) and
nothing useful for general web queries. Their HTML mirror
``html.duckduckgo.com`` returns the same SERP a browser would render
without an API key, which is what most "no-key" search libraries
actually scrape.

We parse it with stdlib only (no BeautifulSoup) to keep the runtime
footprint flat. Three regex passes are enough because the markup is
stable: result links live in ``<a class="result__a" href="…">title</a>``
followed by ``<a class="result__snippet">snippet</a>``.

DDG sometimes wraps its outbound URLs through ``//duckduckgo.com/l/?
uddg=<encoded>``; we unwrap those so the operator sees the real URL.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Iterable

from ...._http import NetworkError, get_text
from ._base import AdapterResult, SearchHit, trim


DDG_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"


_RESULT_BLOCK = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(?P<href>[^"]+)"[^>]*>'
    r"(?P<title>.*?)</a>"
    r"(?:.*?<a[^>]*class=\"[^\"]*result__snippet[^\"]*\"[^>]*>"
    r"(?P<snippet>.*?)</a>)?",
    re.DOTALL,
)
_TAGS = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return html.unescape(_TAGS.sub("", s or "")).strip()


def _unwrap(url: str) -> str:
    """Resolve `//duckduckgo.com/l/?uddg=…` redirects to the real URL."""
    u = url.strip()
    if not u:
        return u
    if u.startswith("//"):
        u = "https:" + u
    parsed = urllib.parse.urlparse(u)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.endswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        target = (qs.get("uddg") or [None])[0]
        if target:
            return urllib.parse.unquote(target)
    return u


def _parse(body: str, *, limit: int) -> list[SearchHit]:
    out: list[SearchHit] = []
    for match in _RESULT_BLOCK.finditer(body):
        if len(out) >= limit:
            break
        href = _unwrap(match.group("href") or "")
        title = _strip_html(match.group("title") or "")
        snippet = trim(_strip_html(match.group("snippet") or ""))
        if not href or not title:
            continue
        out.append(
            SearchHit(title=title, url=href, snippet=snippet, source="ddg")
        )
    return out


async def search(
    query: str,
    *,
    limit: int,
    timeout: float = 8.0,
) -> AdapterResult:
    """Run a DuckDuckGo HTML search and normalise the rows."""

    try:
        status, body = await get_text(
            DDG_HTML_ENDPOINT,
            params={"q": query, "kl": "wt-wt"},
            headers={
                "Accept": "text/html,application/xhtml+xml",
                # DDG returns a CAPTCHA / rate-limit page if UA looks
                # too automated. Use a realistic browser UA — we are a
                # legitimate keyless fallback and they document this.
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Safari/605.1.15 TARS/1.0"
                ),
            },
            timeout=timeout,
        )
    except NetworkError as e:
        return AdapterResult(
            ok=False, adapter="ddg", error="network_error", detail=str(e)
        )

    if status >= 400 or not body:
        return AdapterResult(
            ok=False,
            adapter="ddg",
            error="upstream_status",
            upstream_status=status,
        )

    if "Anomaly" in body[:500] and "DuckDuckGo" in body[:500]:
        # DDG occasionally returns a "captcha-ish" page when called too
        # fast. Surface this as an explicit fallback signal so the
        # dispatcher can move on.
        return AdapterResult(
            ok=False,
            adapter="ddg",
            error="rate_limited",
            detail="DuckDuckGo HTML returned an anomaly / captcha page.",
        )

    hits = _parse(body, limit=limit)
    return AdapterResult(ok=True, adapter="ddg", hits=tuple(hits))


__all__ = ["search", "_parse", "_unwrap"]
