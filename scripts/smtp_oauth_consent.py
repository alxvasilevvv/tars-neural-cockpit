#!/usr/bin/env python3
"""Operator helper for the SMTP OAuth initial-consent flow.

Walks the operator through a one-shot authorization-code dance and
prints the resulting refresh token + the env line they need to add to
their TARS install. Wraps
:mod:`backend.core.domains.packs.business.oauth_consent` and ships a
tiny built-in HTTP receiver on ``127.0.0.1:<port>/cb`` so the operator
never has to copy-paste the auth code by hand.

Usage
-----

Gmail (SMTP send scope):

    .venv/bin/python scripts/smtp_oauth_consent.py \\
        --provider gmail \\
        --client-id YOUR_CLIENT_ID \\
        --client-secret YOUR_CLIENT_SECRET

Microsoft 365 (Outlook SMTP):

    .venv/bin/python scripts/smtp_oauth_consent.py \\
        --provider office365 \\
        --client-id YOUR_PUBLIC_CLIENT_ID \\
        --tenant common

The script:

1. Picks an open localhost port (or the one you pass via ``--port``).
2. Builds the consent URL via ``build_consent_url`` and opens it in
   your default browser (override with ``--no-browser`` to copy
   manually).
3. Spins up a one-shot HTTP server bound to ``127.0.0.1:<port>`` and
   waits for the provider to redirect back with ``?code=...&state=...``.
4. Verifies the state token (HMAC-SHA256 + freshness + provider match).
5. Calls ``exchange_authorization_code`` to swap the code for refresh
   + access tokens.
6. Prints the refresh token + the env line.

Stdlib-only on purpose so the helper runs in any Python 3.12+ that
already imports the TARS package — no `requests`, no `flask`, no
`uvicorn` standalone.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# Make the script self-bootstrapping so the operator can run it from
# anywhere without remembering to set PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.core.domains.packs.business.oauth_consent import (  # noqa: E402
    build_consent_url,
    exchange_authorization_code,
    verify_state,
)


log = logging.getLogger("tars.scripts.smtp_oauth_consent")


# Mutable container the request handler writes the callback into.
_callback: dict[str, Any] = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    """Writes the parsed ``?code=...&state=...`` into ``_callback``
    and ACKs the operator's browser. The runner thread reads
    ``_callback`` after :meth:`HTTPServer.serve_forever` exits."""

    server_version = "tars-smtp-oauth-consent/1.0"

    def do_GET(self) -> None:  # noqa: N802  (BaseHTTPRequestHandler API)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/cb":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not found")
            return

        params = dict(urllib.parse.parse_qsl(parsed.query))
        _callback.update(params)

        if "error" in params:
            body = (
                "<html><body><h1>OAuth consent failed</h1>"
                f"<p>{params.get('error', '')}: "
                f"{params.get('error_description', '')}</p>"
                "<p>You can close this tab.</p></body></html>"
            ).encode("utf-8")
            self.send_response(400)
        else:
            body = (
                "<html><body><h1>TARS — consent received</h1>"
                "<p>You can close this tab now. Return to the terminal "
                "for the refresh token.</p></body></html>"
            ).encode("utf-8")
            self.send_response(200)

        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
        # Silence the default ``stderr`` access log so the operator
        # only sees TARS-relevant output. Errors still surface via
        # the logger above.
        return


def _pick_port() -> int:
    """Bind to an OS-assigned free port and return it. Closes the
    socket immediately — there's a tiny race window before the
    HTTPServer reuses the port, but localhost listeners on a quiet
    host don't collide in practice."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_callback(server: HTTPServer, timeout_s: float) -> None:
    """Run ``serve_forever`` in the current thread until either the
    callback fires or ``timeout_s`` elapses. Implementation: poll
    ``handle_request`` with the socket timeout set so we can break
    on stale waits without a separate watchdog thread."""

    server.timeout = 1.0
    deadline = time.time() + timeout_s
    while not _callback and time.time() < deadline:
        server.handle_request()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="TARS — SMTP OAuth initial-consent dance"
    )
    p.add_argument("--provider", required=True, choices=[
        "gmail", "google", "googlemail", "office365", "o365", "outlook",
    ])
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret", default=None,
                   help="Required for Gmail; optional for Microsoft public clients.")
    p.add_argument("--tenant", default="common",
                   help="Microsoft tenant id (default: common).")
    p.add_argument("--scope", default=None,
                   help="Override the default SMTP-only scope for the provider.")
    p.add_argument("--port", type=int, default=None,
                   help="Localhost port to bind the receiver. Default: OS-assigned.")
    p.add_argument("--timeout", type=float, default=300.0,
                   help="Wait this many seconds for the operator to finish (default: 300).")
    p.add_argument("--no-browser", action="store_true",
                   help="Don't open the URL in the browser; print it for manual copy.")
    p.add_argument("--login-hint", default=None,
                   help="Pre-fill the user account (e.g. alice@example.com).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    port = args.port or _pick_port()
    redirect_uri = f"http://127.0.0.1:{port}/cb"

    extra: dict[str, str] = {}
    if args.login_hint:
        extra["login_hint"] = args.login_hint

    consent = build_consent_url(
        client_id=args.client_id,
        redirect_uri=redirect_uri,
        provider=args.provider,
        scope=args.scope,
        tenant=args.tenant,
        extra_params=extra or None,
    )

    print()
    print(f"Listening for callback on {redirect_uri}")
    print(f"Provider: {args.provider}")
    print()
    print("Open this URL in your browser:")
    print()
    print(f"  {consent.url}")
    print()

    if not args.no_browser:
        webbrowser.open(consent.url)
        print("(Tried to open it in your default browser.)")
        print()

    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    try:
        _wait_for_callback(server, args.timeout)
    finally:
        server.server_close()

    if not _callback:
        print(f"ERROR: no callback received within {args.timeout}s.")
        return 2
    if "error" in _callback:
        print(f"ERROR: provider returned {_callback.get('error')}: "
              f"{_callback.get('error_description', '')}")
        return 3

    code = _callback.get("code")
    state = _callback.get("state")
    if not code or not state:
        print("ERROR: callback missing code or state.")
        return 4

    try:
        verify_state(state, expected_provider=args.provider)
    except ValueError as exc:
        print(f"ERROR: state verification failed: {exc}")
        return 5

    print("State verified. Exchanging code for tokens...")
    result = exchange_authorization_code(
        code=code,
        code_verifier=consent.code_verifier,
        redirect_uri=redirect_uri,
        client_id=args.client_id,
        client_secret=args.client_secret,
        provider=args.provider,
        tenant=args.tenant,
    )

    if not result.ok:
        print(f"ERROR: token exchange failed ({result.reason}): {result.error}")
        return 6

    if not result.refresh_token:
        print("WARNING: provider returned no refresh_token. The consent "
              "completed but TARS won't be able to auto-refresh.")
        print("  → For Gmail: confirm `access_type=offline + prompt=consent`.")
        print("  → For Microsoft: confirm scope includes `offline_access`.")
        print()
        print("Access token (one-shot, ~1h):")
        print(f"  {result.access_token}")
        return 0

    print()
    print("SUCCESS — consent complete. Add this to your TARS env:")
    print()
    print(f"    export TARS_SMTP_OAUTH_REFRESH_TOKEN='{result.refresh_token}'")
    print(f"    export TARS_SMTP_OAUTH_CLIENT_ID='{args.client_id}'")
    if args.client_secret:
        print(f"    export TARS_SMTP_OAUTH_CLIENT_SECRET='{args.client_secret}'")
    print(f"    export TARS_SMTP_PROVIDER='{args.provider}'")
    if args.tenant and args.tenant != "common":
        print(f"    export TARS_SMTP_OAUTH_TENANT='{args.tenant}'")
    print()
    if result.expires_in:
        print(f"(Initial access token expires in ~{int(result.expires_in)}s; "
              "TARS will refresh automatically.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
