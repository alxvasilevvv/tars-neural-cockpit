"""Shared helpers for Wave 105 cross-module E2E tests.

Stdlib-only context managers used across ``tests/test_b2b_e2e.py``.
Each helper returns a context manager that sets up isolated state
(temp dirs, env vars, mock servers) and tears it down on exit.

Design notes:

* No ``pytest`` deps -- the helpers are vanilla ``contextlib`` so the
  E2E suite runs under ``python3 -m unittest`` without extra packages.
* Each helper resets the relevant per-module store (``reset_store``)
  on entry and exit so tests don't leak singletons.
* HTTP mock server is a stdlib ``http.server.HTTPServer`` running in
  a daemon thread -- requests are recorded and exposed via
  ``server.received`` for assertion.
"""

from __future__ import annotations

import contextlib
import http.server
import os
import shutil
import tempfile
import threading
import time
from typing import Any, Iterator
from unittest import mock


# --------------------------------------------------------------------------
# temp_tars_home -- isolated ~/.tars directory + env wiring
# --------------------------------------------------------------------------


@contextlib.contextmanager
def temp_tars_home() -> Iterator[str]:
    """Create a temp dir, point all known TARS_* path env vars at it.

    Resets the relevant module stores (org / scheduler / webhooks /
    receipts / cohort / outreach / reports) on entry AND exit so a
    test never sees a singleton from a previous case.

    Yields the temp dir path. Cleans up on exit.
    """

    tmp = tempfile.mkdtemp(prefix="tars-e2e-")
    saved: dict[str, str | None] = {}
    overrides = {
        "TARS_ORG_DB_PATH": os.path.join(tmp, "org.sqlite"),
        "TARS_SCHEDULER_DB_PATH": os.path.join(tmp, "scheduler.sqlite"),
        "TARS_WEBHOOKS_DB_PATH": os.path.join(tmp, "webhooks.sqlite"),
        "TARS_COHORT_DB_PATH": os.path.join(tmp, "cohort.sqlite"),
        "TARS_OUTREACH_DB_PATH": os.path.join(tmp, "outreach.sqlite"),
        "TARS_REPORTS_DB_PATH": os.path.join(tmp, "reports.sqlite"),
        "TARS_REPORTS_OUTPUT_DIR": os.path.join(tmp, "reports_out"),
        "TARS_RECEIPT_DIR": os.path.join(tmp, "receipts_nd"),
        "TARS_RECEIPT_DB_PATH": os.path.join(tmp, "receipts.sqlite"),
        "TARS_RECEIPT_HOST_KEY_PATH": os.path.join(tmp, "host-key.json"),
        "TARS_EXPORT_DIR": os.path.join(tmp, "exports"),
        "TARS_CONNECTORS_DIR": os.path.join(tmp, "connectors"),
    }
    for key, val in overrides.items():
        saved[key] = os.environ.get(key)
        os.environ[key] = val
    for kill in (
        "TARS_ORG_STORE", "TARS_SCHEDULER_STORE", "TARS_WEBHOOKS_STORE",
        "TARS_COHORT_STORE", "TARS_OUTREACH_STORE", "TARS_REPORTS_STORE",
        "TARS_RECEIPT_STORE",
    ):
        saved[kill] = os.environ.get(kill)
        os.environ.pop(kill, None)

    _reset_all_stores()
    try:
        yield tmp
    finally:
        _reset_all_stores()
        for key, prev in saved.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


def _reset_all_stores() -> None:
    """Best-effort store reset across every module that publishes one."""

    for modpath in (
        "backend.core.org",
        "backend.core.scheduler",
        "backend.core.webhooks",
        "backend.core.cohort",
        "backend.core.outreach",
        "backend.core.reports",
        "backend.core.receipts",
    ):
        try:
            mod = __import__(modpath, fromlist=["reset_store"])
            reset = getattr(mod, "reset_store", None)
            if callable(reset):
                reset()
        except Exception:
            pass


# --------------------------------------------------------------------------
# mock_llm -- monkeypatch council.llm to return a fixed response
# --------------------------------------------------------------------------


@contextlib.contextmanager
def mock_llm(response_text: str) -> Iterator[mock.MagicMock]:
    """Patch outreach drafter LLM hooks to return ``response_text``."""

    fake = mock.MagicMock(return_value=response_text)
    targets = [
        "backend.core.outreach.drafter._llm_call_anthropic",
        "backend.core.outreach.drafter._llm_call_openai",
    ]
    patches = [mock.patch(t, fake) for t in targets]
    for p in patches:
        p.start()
    try:
        yield fake
    finally:
        for p in patches:
            try:
                p.stop()
            except Exception:
                pass


# --------------------------------------------------------------------------
# mock_gmail_send -- record sent message instead of HTTP call
# --------------------------------------------------------------------------


class _SentRecord:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self.calls)


@contextlib.contextmanager
def mock_gmail_send() -> Iterator[_SentRecord]:
    """Stub Gmail HTTP send so outreach.send_draft completes offline."""

    record = _SentRecord()

    class _FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body
        def read(self) -> bytes:
            return self._body
        def __enter__(self) -> "_FakeResp":
            return self
        def __exit__(self, *_a: Any) -> None:
            return None

    def _fake_urlopen(req, timeout=None):
        record.calls.append({
            "url": getattr(req, "full_url", "?"),
            "data": getattr(req, "data", b""),
            "headers": dict(getattr(req, "headers", {})),
        })
        body = b'{"id":"stub_' + str(len(record.calls)).encode() + b'"}'
        return _FakeResp(body)

    class _FakeClient:
        _blob = {"profile_email": "ops@example.com"}

        @classmethod
        def from_stored_token(cls) -> "_FakeClient":
            return cls()

        def _ensure_fresh(self) -> str:
            return "fake-access-token"

    patches = [
        mock.patch(
            "backend.core.connectors.gmail.GmailClient",
            _FakeClient,
        ),
        mock.patch(
            "backend.core.outreach.sender.urllib.request.urlopen",
            _fake_urlopen,
        ),
    ]
    for p in patches:
        try:
            p.start()
        except Exception:
            pass
    try:
        yield record
    finally:
        for p in patches:
            try:
                p.stop()
            except Exception:
                pass


# --------------------------------------------------------------------------
# mock_http_server -- localhost HTTP recorder for webhook delivery
# --------------------------------------------------------------------------


class _RecorderHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.server.received.append({
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers.items()),
            "body": body,
        })
        fail_remaining = getattr(self.server, "fail_count", 0)
        if fail_remaining > 0:
            self.server.fail_count = fail_remaining - 1
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"forced fail")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *_: Any) -> None:
        return


class _RecorderServer(http.server.HTTPServer):
    received: list[dict[str, Any]]
    fail_count: int


@contextlib.contextmanager
def mock_http_server(*, fail_count: int = 0) -> Iterator[_RecorderServer]:
    """Spin a daemon-thread HTTPServer on a random localhost port."""

    server = _RecorderServer(("127.0.0.1", 0), _RecorderHandler)
    server.received = []
    server.fail_count = fail_count
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


# --------------------------------------------------------------------------
# freeze_time -- monkeypatch time.time to return a fixed value
# --------------------------------------------------------------------------


@contextlib.contextmanager
def freeze_time(epoch_seconds: float) -> Iterator[mock.MagicMock]:
    """Freeze ``time.time()`` at ``epoch_seconds``."""

    fake = mock.MagicMock(return_value=float(epoch_seconds))
    p = mock.patch("time.time", fake)
    p.start()
    try:
        yield fake
    finally:
        try:
            p.stop()
        except Exception:
            pass


# --------------------------------------------------------------------------
# clear_connector_env -- ensure no leaked OAuth credentials
# --------------------------------------------------------------------------


@contextlib.contextmanager
def clear_connector_env() -> Iterator[None]:
    """Pop SLACK_* / GOOGLE_* env vars; restore on exit."""

    keys = (
        "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REDIRECT_URI",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
    )
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    try:
        yield None
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --------------------------------------------------------------------------
# wait_for -- bounded polling helper
# --------------------------------------------------------------------------


def wait_for(predicate, *, timeout_s: float = 3.0, interval_s: float = 0.05) -> bool:
    """Poll ``predicate()`` until truthy or timeout."""

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval_s)
    try:
        return bool(predicate())
    except Exception:
        return False


__all__ = [
    "clear_connector_env",
    "freeze_time",
    "mock_gmail_send",
    "mock_http_server",
    "mock_llm",
    "temp_tars_home",
    "wait_for",
]
