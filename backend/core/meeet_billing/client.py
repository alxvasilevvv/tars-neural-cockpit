"""HTTP client for meeet.world operator billing snapshot (stdlib only)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

_log = logging.getLogger(__name__)

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


def _post_usage_sync(delta_usd: float, trace_id: str | None) -> dict[str, Any]:
    url = _usage_url()
    key = (os.getenv(_KEY_ENV) or "").strip()
    if not url or not key:
        return {"ok": False, "error": "missing_billing_url_or_key"}
    payload_obj: dict[str, Any] = {"delta_usd": round(float(delta_usd), 6)}
    if trace_id:
        tid = trace_id.strip()[:256]
        if tid:
            payload_obj["trace_id"] = tid
    body = json.dumps(payload_obj).encode("utf-8")
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


def _http_code_transient(code: int) -> bool:
    return code in {408, 425, 429, 500, 502, 503, 504}


def _usage_result_transient(out: dict[str, Any]) -> bool:
    if out.get("ok") is True:
        return False
    err = str(out.get("error", ""))
    if err.startswith("http_"):
        try:
            c = int(err.split("_", 1)[1])
        except (ValueError, IndexError):
            return False
        return _http_code_transient(c)
    if err.startswith("url_"):
        return True
    low = err.lower()
    return "timed out" in low or "temporarily" in low


async def post_operator_usage_delta(
    delta_usd: float,
    *,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """POST ``delta_usd`` cloud spend to meeet ``/operator/usage`` (remote mode only).

    Retries transient HTTP / transport failures a few times (see
    ``MEEET_BILLING_USAGE_RETRIES``). Optional ``trace_id`` enables server-side
    idempotency on the billing edge.
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
    retries = int(os.getenv("MEEET_BILLING_USAGE_RETRIES") or "3")
    retries = max(1, min(8, retries))
    tid = trace_id.strip()[:256] if isinstance(trace_id, str) and trace_id.strip() else None

    last: dict[str, Any] = {"ok": False, "error": "exhausted_retries"}
    for attempt in range(retries):
        try:
            out = await asyncio.to_thread(_post_usage_sync, d, tid)
        except urllib.error.HTTPError as exc:
            out = {"ok": False, "error": f"http_{exc.code}"}
            if not _http_code_transient(exc.code):
                return out
        except urllib.error.URLError as exc:
            out = {"ok": False, "error": f"url_{exc.reason}"}
        except (TimeoutError, json.JSONDecodeError, OSError) as exc:
            out = {"ok": False, "error": str(exc)}
        else:
            if not _usage_result_transient(out):
                return out
        last = out
        if attempt + 1 < retries:
            await asyncio.sleep(min(2.0, 0.12 * (2**attempt)))
    # Retry budget exhausted. Emit a structured event so the operator
    # cockpit + ops dashboards can flag a stuck mirror without diffing
    # individual warnings. Trace id, attempts taken, and last error
    # shape are the minimal triage payload.
    _log.warning(
        "meeet.mirror.usage.exhausted",
        extra={
            "trace_id": tid,
            "attempts": retries,
            "last_error": (last or {}).get("error"),
            "delta_usd": d,
        },
    )
    return last


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
