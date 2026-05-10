"""
qa_agent.alerts — alert escalation + history persistence (Wave 117).

The QA agent now runs every 5 minutes (Wave 117 — was every 30 in
Wave 75 baseline). Alerting on every probe blip would drown an
on-call in noise, so we de-duplicate via a small sliding-window of
the last N runs persisted to ``~/.tars/qa-agent/history.json``.

Public surface:

* :func:`should_alert(history, threshold=3)` — sliding-window check.
  Returns True iff the last ``threshold`` recorded outcomes are all
  failures. Resets on the first non-fail.
* :func:`record_run(name, status)` — append an outcome to the named
  probe's history (in-place mutation, caller saves).
* :func:`load_history(path)` / :func:`save_history(path, history)` —
  JSON round-trip. Tolerant of missing / corrupt files.
* :func:`send_alert(probe_name, summary, channel="telegram", ...)` —
  Telegram via ``backend.core.connectors.telegram.TelegramClient`` if
  ``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_OPERATOR_CHAT_ID`` are set, plus
  Wave 90 webhook ``qa.alert``. Both are best-effort: a missing token
  logs and returns ``{ok: False, reason: ...}`` rather than raising.
* :data:`KNOWN_FLAKY` — names operators can append to silence false
  positives. Probes in this set never trigger ``send_alert``.

History shape on disk::

    {
      "version": 1,
      "probes": {
        "http.route_v117_": ["pass","pass","fail","fail","pass"],
        "bundle.imports":   ["pass"]
      },
      "updated_at": 1715000000.0
    }

Per-probe list capped at ``HISTORY_MAX_PER_PROBE`` (default 10).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger("tars.qa_agent.alerts")

DEFAULT_HISTORY_PATH = Path.home() / ".tars" / "qa-agent" / "history.json"
HISTORY_MAX_PER_PROBE = 10
DEFAULT_THRESHOLD = 3

# Operators can append probe names here to silence noisy false
# positives without removing the probe entirely. Documented in
# docs/QA_AGENT_RUNBOOK.md.
KNOWN_FLAKY: set[str] = set()


# -- history I/O -----------------------------------------------------


def load_history(path: Path | str = DEFAULT_HISTORY_PATH) -> dict[str, Any]:
    """Load the persisted history dict. Returns a fresh skeleton on any
    error (missing file, bad JSON, wrong shape). Never raises."""

    p = Path(path)
    skeleton = {"version": 1, "probes": {}, "updated_at": 0.0}
    try:
        raw = p.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return skeleton
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.warning("qa_agent: history.json corrupt, starting fresh (%s)", p)
        return skeleton
    if not isinstance(data, dict) or "probes" not in data:
        return skeleton
    probes = data.get("probes") or {}
    if not isinstance(probes, dict):
        return skeleton
    # Coerce to list[str].
    cleaned: dict[str, list[str]] = {}
    for k, v in probes.items():
        if isinstance(k, str) and isinstance(v, list):
            cleaned[k] = [s for s in v if isinstance(s, str)]
    return {
        "version": int(data.get("version") or 1),
        "probes": cleaned,
        "updated_at": float(data.get("updated_at") or 0.0),
    }


def save_history(
    history: dict[str, Any],
    path: Path | str = DEFAULT_HISTORY_PATH,
) -> bool:
    """Persist history dict. Creates parent dirs. Returns True on success."""

    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        history = dict(history)
        history["updated_at"] = time.time()
        p.write_text(json.dumps(history, indent=2), encoding="utf-8")
        return True
    except OSError as exc:
        log.warning("qa_agent: failed to persist history.json (%s): %s", p, exc)
        return False


def record_run(
    history: dict[str, Any],
    probe_name: str,
    status: str,
) -> None:
    """Append a status to the probe's history list (in-place).

    Caps at ``HISTORY_MAX_PER_PROBE`` entries. ``status`` is one of
    ``pass`` / ``fail`` / ``warn`` / ``skip`` (no validation here —
    we just store what the probe reported).
    """

    probes = history.setdefault("probes", {})
    series = probes.setdefault(probe_name, [])
    series.append(status)
    if len(series) > HISTORY_MAX_PER_PROBE:
        del series[: len(series) - HISTORY_MAX_PER_PROBE]


# -- alert decision --------------------------------------------------


def should_alert(
    failures_history: list[str],
    threshold: int = DEFAULT_THRESHOLD,
) -> bool:
    """Return True iff the last ``threshold`` entries are all fails.

    A single non-``fail`` entry within the window resets the streak.
    Empty / short histories return False.
    """

    if threshold <= 0:
        return False
    if len(failures_history) < threshold:
        return False
    tail = failures_history[-threshold:]
    return all(s == "fail" for s in tail)


# -- send_alert ------------------------------------------------------


def _telegram_token_chat() -> tuple[str | None, str | None]:
    tok = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip() or None
    chat = (os.getenv("TELEGRAM_OPERATOR_CHAT_ID") or "").strip() or None
    return tok, chat


def _send_telegram(text: str) -> dict[str, Any]:
    """Send via Telegram Bot API. Best-effort; never raises.

    Prefers Wave 108's TelegramClient when importable, falls back to a
    local urllib POST if the backend module isn't on sys.path (the QA
    agent often runs in a slim CI image without the full backend).
    """

    tok, chat = _telegram_token_chat()
    if not tok:
        log.info("qa_agent.alerts: TELEGRAM_BOT_TOKEN not set, skipping Telegram alert")
        return {"ok": False, "reason": "no_token"}
    if not chat:
        log.info(
            "qa_agent.alerts: TELEGRAM_OPERATOR_CHAT_ID not set, skipping Telegram alert"
        )
        return {"ok": False, "reason": "no_chat_id"}
    # Try the rich client first.
    try:
        from backend.core.connectors.telegram import TelegramClient  # type: ignore

        client = TelegramClient(tok)
        client.send_message(chat, text, parse_mode="Markdown")
        return {"ok": True, "via": "TelegramClient"}
    except Exception as exc:  # pragma: no cover — fallback path
        log.debug("qa_agent.alerts: TelegramClient unavailable (%s), fallback", exc)
    # Stdlib fallback.
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    body = urllib.parse.urlencode(
        {
            "chat_id": chat,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            if resp.status == 200:
                return {"ok": True, "via": "urllib"}
            return {"ok": False, "reason": f"telegram_status_{resp.status}"}
    except (urllib.error.URLError, OSError) as exc:
        log.warning("qa_agent.alerts: telegram POST failed: %s", exc)
        return {"ok": False, "reason": f"transport:{exc}"}


def _emit_webhook(probe_name: str, summary: str) -> dict[str, Any]:
    """Best-effort fire of Wave 90 ``qa.alert`` webhook event.

    Imported lazily and async-run inline; if the webhook subsystem
    isn't importable (slim CI image), we no-op silently.
    """

    try:
        import asyncio

        from backend.core.webhooks import emit  # type: ignore

        payload = {
            "probe": probe_name,
            "summary": summary,
            "ts": time.time(),
            "source": "qa_agent",
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Fire-and-forget when called from inside a loop.
                asyncio.ensure_future(emit("qa.alert", payload))
                return {"ok": True, "via": "ensure_future"}
        except RuntimeError:
            pass
        result = asyncio.run(emit("qa.alert", payload))
        return {"ok": True, "via": "asyncio.run", "result": result}
    except Exception as exc:
        log.debug("qa_agent.alerts: webhook emit skipped: %s", exc)
        return {"ok": False, "reason": f"unavailable:{exc}"}


def send_alert(
    probe_name: str,
    failure_summary: str,
    channel: str = "telegram",
) -> dict[str, Any]:
    """Fire an alert for a failing probe.

    Currently the only ``channel`` value with rich behaviour is
    ``telegram``; any other value just emits the webhook event. The
    webhook is fired regardless so downstream systems can subscribe.

    Returns a dict aggregating per-channel outcomes — useful in tests
    and in the run summary table.
    """

    if probe_name in KNOWN_FLAKY:
        log.info("qa_agent.alerts: %s is in KNOWN_FLAKY, no alert sent", probe_name)
        return {"ok": True, "skipped": "flaky"}

    text = (
        f"*TARS QA Agent — alert*\n"
        f"Probe: `{probe_name}`\n"
        f"Status: 3+ consecutive failures\n"
        f"Detail: {failure_summary}\n"
        f"Action: open the latest qa-agent run on GitHub Actions."
    )

    result: dict[str, Any] = {"probe": probe_name}
    if channel == "telegram":
        result["telegram"] = _send_telegram(text)
    else:
        result["telegram"] = {"ok": False, "reason": f"unknown_channel:{channel}"}
    result["webhook"] = _emit_webhook(probe_name, failure_summary)
    return result
