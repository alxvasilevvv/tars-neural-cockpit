"""Tiny stdlib-only async HTTP helpers shared by domain action adapters.

Why not requests/httpx: keeping the runtime dep footprint to the
stdlib so the cockpit can run on a bare Python 3.10+. Anything that
needs more (auth, streaming, websockets) can graduate to an SDK later.
"""

from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping


DEFAULT_TIMEOUT = 6.0
DEFAULT_UA = "TARS/1.0 (+meeet.world)"


def _do_request(
    url: str,
    *,
    timeout: float,
    headers: Mapping[str, str] | None,
) -> tuple[int, str]:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", DEFAULT_UA)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.getcode() or 0, body
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover
            pass
        return e.code, body
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        raise NetworkError(str(e)) from e


class NetworkError(RuntimeError):
    """Raised when the underlying transport fails (offline, timeout, DNS)."""


async def get_text(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, str]:
    """GET ``url`` and return ``(status, body)``.

    Raises :class:`NetworkError` on transport failure. HTTP error
    statuses (4xx/5xx) are returned as the tuple so callers can decide
    how to surface them.
    """

    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params, doseq=True)}"
    return await asyncio.to_thread(
        _do_request, url, timeout=timeout, headers=headers
    )


async def get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, Any]:
    status, body = await get_text(
        url, params=params, headers=headers, timeout=timeout
    )
    if not body:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, None


def _do_post_json(
    url: str,
    body: Mapping[str, Any] | None,
    *,
    timeout: float,
    headers: Mapping[str, str] | None,
) -> tuple[int, str]:
    data = json.dumps(dict(body or {})).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("User-Agent", DEFAULT_UA)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.getcode() or 0, raw
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover
            pass
        return e.code, raw
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        raise NetworkError(str(e)) from e


async def post_json(
    url: str,
    body: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, Any]:
    """POST JSON and parse the response body as JSON (or return raw)."""

    status, raw = await asyncio.to_thread(
        _do_post_json, url, body, timeout=timeout, headers=headers
    )
    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw
