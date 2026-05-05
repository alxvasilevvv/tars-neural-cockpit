"""HTTP client for meeet.world operator billing snapshot (stdlib only)."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

_BILLING_SOURCE_ENV = "TARS_BILLING_SOURCE"
_BASE_ENV = "MEEET_BILLING_BASE_URL"
_KEY_ENV = "MEEET_BILLING_API_KEY"
_OPERATOR_ENV = "TARS_OPERATOR_ID"

_DEFAULT_TIMEOUT_S = 3.0
_CACHE_TTL_S = 5.0

_lock = threading.Lock()
_cache_payload: dict[str, Any] | None = None
_cache_mono: float = 0.0


def is_remote_billing_configured() -> bool:
    return (os.getenv(_BILLING_SOURCE_ENV) or "local").strip().lower() == "remote"


def clear_operator_cache() -> None:
    global _cache_payload, _cache_mono
    with _lock:
        _cache_payload = None
        _cache_mono = 0.0


def _operator_url() -> str | None:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/operator"


def _usage_url() -> str | None:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/operator/usage"


def _fetch_sync() -> dict[str, Any]:
    url = _operator_url()
    key = (os.getenv(_KEY_ENV) or "").strip()
    if not url or not key:
        return {"ok": False, "error": "missing_billing_url_or_key"}
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "TARS-billing-client/1.0",
        },
        method="GET",
    )
    op_id = (os.getenv(_OPERATOR_ENV) or "").strip()
    if op_id:
        req.add_header("X-Tars-Operator-Id", op_id)
    timeout_s = float(os.getenv("MEEET_BILLING_TIMEOUT_S") or _DEFAULT_TIMEOUT_S)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — controlled URL from env
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {"ok": False, "error": "invalid_json_shape"}
    return data


def _post_usage_sync(delta_usd: float) -> dict[str, Any]:
    url = _usage_url()
    key = (os.getenv(_KEY_ENV) or "").strip()
    if not url or not key:
        return {"ok": False, "error": "missing_billing_url_or_key"}
    body = json.dumps({"delta_usd": round(float(delta_usd), 6)}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "TARS-billing-client/1.0",
        },
        method="POST",
    )
    op_id = (os.getenv(_OPERATOR_ENV) or "").strip()
    if op_id:
        req.add_header("X-Tars-Operator-Id", op_id)
    timeout_s = float(os.getenv("MEEET_BILLING_TIMEOUT_S") or _DEFAULT_TIMEOUT_S)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {"ok": False, "error": "invalid_json_shape"}
    return data


async def post_operator_usage_delta(delta_usd: float) -> dict[str, Any]:
    """POST ``delta_usd`` cloud spend to meeet ``/operator/usage`` (remote mode only).

    Returns a dict with ``ok``; on transport errors ``ok: False`` and ``error``.
    Does not touch the operator snapshot cache (callers may clear it on success).
    """

    if not is_remote_billing_configured():
        return {"ok": False, "error": "not_remote"}
    if _usage_url() is None or not (os.getenv(_KEY_ENV) or "").strip():
        return {"ok": False, "error": "missing_billing_url_or_key"}
    max_delta = float(os.getenv("MEEET_BILLING_MAX_DELTA_USD") or "50.0")
    if max_delta <= 0:
        max_delta = 50.0
    d = float(delta_usd)
    if d <= 0:
        return {"ok": False, "error": "non_positive_delta"}
    if d > max_delta:
        d = max_delta
    try:
        return await asyncio.to_thread(_post_usage_sync, d)
    except urllib.error.HTTPError as exc:  # pragma: no cover
        return {"ok": False, "error": f"http_{exc.code}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"url_{exc.reason}"}
    except (TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


async def fetch_operator_snapshot(*, bypass_cache: bool = False) -> dict[str, Any] | None:
    """Return remote operator JSON, or ``None`` if not in remote billing mode.

    Negative cache: on transport errors returns ``{"ok": False, "error": "..."}``
    (still a dict) so callers can fail closed. ``None`` means *not configured*
    for remote mode.
    """

    if not is_remote_billing_configured():
        return None
    if _operator_url() is None or not (os.getenv(_KEY_ENV) or "").strip():
        return None

    global _cache_payload, _cache_mono
    now = time.monotonic()
    if not bypass_cache:
        with _lock:
            if (
                _cache_payload is not None
                and now - _cache_mono < _CACHE_TTL_S
            ):
                return dict(_cache_payload)

    try:
        payload = await asyncio.to_thread(_fetch_sync)
    except urllib.error.HTTPError as exc:  # pragma: no cover — exercised in tests via patch
        payload = {"ok": False, "error": f"http_{exc.code}"}
    except urllib.error.URLError as exc:
        payload = {"ok": False, "error": f"url_{exc.reason}"}
    except (TimeoutError, json.JSONDecodeError, OSError) as exc:
        payload = {"ok": False, "error": str(exc)}

    with _lock:
        _cache_payload = dict(payload)
        _cache_mono = time.monotonic()
    return dict(payload)
