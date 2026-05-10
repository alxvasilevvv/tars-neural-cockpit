"""Outgoing webhook dispatch.

Two entry points:

- :func:`dispatch` — given an event, look up matching active outgoing
  webhooks, persist a Delivery row per webhook, and fire the HTTP
  POST. Used by :func:`backend.core.webhooks.emit` (the hot-path
  helper).
- :func:`fire_delivery` — re-attempt an existing Delivery row. Used
  by the dispatcher loop's retry sweep + the manual replay endpoint.

Transport: stdlib ``urllib`` (HTTP/1.1) with a short connect / read
timeout. We do NOT pull httpx into the dependency tree just for this.

Headers on every POST::

    X-TARS-Signature: t=<ts>,v1=<hex>
    X-TARS-Event: <event_type>
    X-TARS-Delivery-Id: <delivery_id>
    Content-Type: application/json
    User-Agent: TARS-Webhooks/<contract_version>

Retry policy: exponential backoff at 30s / 2min / 10min / 1hr (4
attempts max). Honours the upstream ``Retry-After`` header (seconds
or HTTP-date) when present. Rows that exhaust the budget are marked
``failed`` — operators can manually replay via the HTTP surface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Any

from .models import (
    CONTRACT_VERSION,
    Delivery,
    DeliveryStatus,
    OutgoingWebhook,
    build_envelope,
    next_attempt_delay,
)
from .signing import sign_payload
from .store import WebhookStore

log = logging.getLogger("tars.webhooks.dispatcher")

DEFAULT_TIMEOUT_S = 10.0
USER_AGENT = f"TARS-Webhooks/{CONTRACT_VERSION}"


def _parse_retry_after(value: str | None) -> float | None:
    """Return seconds to wait, or None if header missing / malformed."""

    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    # numeric seconds
    try:
        secs = float(raw)
        if secs < 0:
            return None
        return secs
    except ValueError:
        pass
    # HTTP-date
    try:
        dt = parsedate_to_datetime(raw)
        if dt is None:
            return None
        wait = dt.timestamp() - time.time()
        return max(0.0, wait)
    except (TypeError, ValueError, IndexError):
        return None


def _post_sync(
    *,
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float,
) -> tuple[int, str | None, str | None]:
    """Blocking POST. Returns ``(status_code, retry_after_header, error)``.

    ``error`` is non-None only when the connection itself blew up (DNS,
    refused, timeout). HTTP non-2xx is returned as ``(code, header, None)``
    so the caller can decide retry vs fail.
    """

    req = urllib.request.Request(url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.headers.get("Retry-After"), None
    except urllib.error.HTTPError as exc:
        retry_after = None
        try:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
        except Exception:
            retry_after = None
        return int(exc.code), retry_after, None
    except urllib.error.URLError as exc:
        return 0, None, f"URLError: {exc.reason}"
    except (TimeoutError, OSError) as exc:
        return 0, None, f"{type(exc).__name__}: {exc}"


def deliver_telegram(webhook: OutgoingWebhook, payload: bytes) -> tuple[int, str | None, str | None]:
    """Wave 108 — internal "delivery channel" for ``telegram://`` URLs.

    Recognised forms (parsed from ``webhook.url``):

    * ``telegram://self``           -> route to the operator's saved chat id
    * ``telegram://chat/{chat_id}`` -> route to an explicit chat id

    Returns ``(status_code, retry_after_header, error)`` mirroring the
    HTTP path shape so :func:`fire_delivery` can branch uniformly. We
    surface the JSON envelope as a Markdown code block in the message
    body -- Telegram has no rich payload, so this is the most useful
    rendering for human eyes.
    """

    from backend.core.connectors import (
        ConnectorAuthError,
        ConnectorNotConfigured,
        ConnectorTransportError,
    )
    from backend.core.connectors import telegram as _tg

    url = (webhook.url or "").strip()
    target: str | int
    if url == "telegram://self":
        chat_id = _tg.get_self_chat_id()
        if chat_id is None:
            return 0, None, "telegram self chat_id not configured"
        target = chat_id
    elif url.startswith("telegram://chat/"):
        suffix = url[len("telegram://chat/"):].strip()
        if not suffix:
            return 0, None, "telegram chat path missing chat_id"
        try:
            target = int(suffix)
        except ValueError:
            target = suffix  # username form, e.g. "@channel_name"
    else:
        return 0, None, f"unrecognised telegram URL: {url!r}"

    try:
        body_str = payload.decode("utf-8")
    except UnicodeDecodeError:
        body_str = "<binary payload>"
    # Telegram message limit is 4096 chars; trim conservatively.
    snippet = body_str if len(body_str) <= 3500 else body_str[:3500] + "\n…(truncated)"
    text = f"*TARS · {webhook.name or 'webhook'}*\n```\n{snippet}\n```"

    try:
        client = _tg.TelegramClient.from_stored_token()
        client.send_message(target, text, parse_mode="Markdown")
        return 200, None, None
    except (ConnectorNotConfigured, ConnectorAuthError) as exc:
        return 0, None, f"telegram auth: {exc}"
    except ConnectorTransportError as exc:
        return 0, None, f"telegram transport: {exc}"
    except Exception as exc:  # pragma: no cover -- belt-and-suspenders
        return 0, None, f"{type(exc).__name__}: {exc}"


async def fire_delivery(
    delivery: Delivery,
    *,
    webhook: OutgoingWebhook,
    store: WebhookStore,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    now: float | None = None,
) -> Delivery:
    """Send (or re-send) one Delivery and update the row.

    Walks the row through the state machine:

    - 2xx response → ``success``.
    - non-2xx or transport error with retries left → ``retry`` +
      schedule next_attempt_at via :func:`next_attempt_delay` (or
      ``Retry-After``, whichever is later).
    - no retries left → ``failed``.
    """

    payload_bytes = delivery.payload_json.encode("utf-8")
    timestamp = int(now if now is not None else time.time())
    sig_header = sign_payload(webhook.secret, payload_bytes, timestamp)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-TARS-Signature": sig_header,
        "X-TARS-Event": delivery.event_type,
        "X-TARS-Delivery-Id": delivery.id,
    }

    # Wave 108 — `telegram://...` URLs are dispatched through the
    # Telegram Bot API instead of an HTTP POST. The signature header
    # is still computed (for receipt-chain provenance) but not sent
    # over the wire; Telegram has its own delivery semantics.
    if (webhook.url or "").startswith("telegram://"):
        code, retry_after_hdr, transport_err = await asyncio.to_thread(
            deliver_telegram, webhook, payload_bytes
        )
    else:
        code, retry_after_hdr, transport_err = await asyncio.to_thread(
            _post_sync,
            url=webhook.url,
            body=payload_bytes,
            headers=headers,
            timeout=timeout_s,
        )

    attempts = delivery.attempts + 1
    last_attempt_at = float(timestamp)

    if transport_err is None and 200 <= code < 300:
        updated = await store.patch_delivery(
            delivery.id,
            {
                "status": DeliveryStatus.SUCCESS,
                "attempts": attempts,
                "last_attempt_at": last_attempt_at,
                "next_attempt_at": None,
                "last_error": None,
                "last_status_code": code,
                "signature_used": sig_header,
            },
        )
        log.info(
            "webhook delivered: id=%s webhook=%s event=%s status=%s attempts=%s",
            delivery.id,
            webhook.id,
            delivery.event_type,
            code,
            attempts,
        )
        return updated or delivery

    # failure path
    error_summary = transport_err or f"HTTP {code}"
    delay = next_attempt_delay(attempts)
    if delay is None:
        # retry budget exhausted
        updated = await store.patch_delivery(
            delivery.id,
            {
                "status": DeliveryStatus.FAILED,
                "attempts": attempts,
                "last_attempt_at": last_attempt_at,
                "next_attempt_at": None,
                "last_error": error_summary,
                "last_status_code": code if transport_err is None else None,
                "signature_used": sig_header,
            },
        )
        log.warning(
            "webhook gave up: id=%s webhook=%s event=%s attempts=%s error=%s",
            delivery.id,
            webhook.id,
            delivery.event_type,
            attempts,
            error_summary,
        )
        return updated or delivery

    retry_after_secs = _parse_retry_after(retry_after_hdr)
    if retry_after_secs is not None and retry_after_secs > delay:
        delay = retry_after_secs
    next_at = last_attempt_at + delay

    updated = await store.patch_delivery(
        delivery.id,
        {
            "status": DeliveryStatus.RETRY,
            "attempts": attempts,
            "last_attempt_at": last_attempt_at,
            "next_attempt_at": next_at,
            "last_error": error_summary,
            "last_status_code": code if transport_err is None else None,
            "signature_used": sig_header,
        },
    )
    log.info(
        "webhook retry scheduled: id=%s webhook=%s event=%s attempts=%s next_in_s=%.0f error=%s",
        delivery.id,
        webhook.id,
        delivery.event_type,
        attempts,
        delay,
        error_summary,
    )
    return updated or delivery


async def dispatch(
    event_type: str,
    payload: dict[str, Any],
    *,
    store: WebhookStore,
    fire_immediately: bool = True,
) -> dict[str, Any]:
    """Look up matching outgoing webhooks, create Delivery rows, fire them.

    Returns a summary dict ``{ok, count, fired, deferred, deliveries: [...]}``.

    Pass ``fire_immediately=False`` (used by the test suite + the
    `/test` endpoint when an operator wants to inspect the row before
    the network attempt) to skip the synchronous POST — the row stays
    ``pending`` and the dispatcher loop will pick it up on the next
    sweep.
    """

    if not store.enabled:
        return {"ok": True, "count": 0, "fired": 0, "deferred": 0, "deliveries": []}

    matched = await store.list_active_outgoing_for(event_type)
    envelope = build_envelope(event_type, payload)
    payload_json = json.dumps(envelope, default=str, sort_keys=True)

    deliveries: list[Delivery] = []
    for hook in matched:
        deliveries.append(
            await store.create_delivery(
                webhook_id=hook.id,
                event_id=envelope["id"],
                event_type=event_type,
                payload_json=payload_json,
            )
        )

    fired = 0
    deferred = 0
    if fire_immediately:
        for hook, row in zip(matched, deliveries):
            try:
                await fire_delivery(row, webhook=hook, store=store)
                fired += 1
            except Exception as exc:  # never propagate
                log.warning(
                    "webhook dispatch tick failed: id=%s err=%s: %s",
                    row.id,
                    type(exc).__name__,
                    exc,
                )
                deferred += 1
    else:
        deferred = len(deliveries)

    return {
        "ok": True,
        "count": len(deliveries),
        "fired": fired,
        "deferred": deferred,
        "event_id": envelope["id"],
        "deliveries": [d.id for d in deliveries],
    }
