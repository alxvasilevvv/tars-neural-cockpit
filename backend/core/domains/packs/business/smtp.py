"""SMTP outbound for the business pack.

Stdlib-only ``smtplib`` + ``email.message``. Reads config from the
vault via :mod:`backend.core.vault.keychain` plus a few non-secret
``SMTP_*`` env vars.

Vault keys (any of):

- ``TARS_SMTP_HOST`` / ``SMTP_HOST`` (env: ``SMTP_HOST``)
- ``TARS_SMTP_PORT`` / ``SMTP_PORT`` (env: ``SMTP_PORT``, default 587)
- ``TARS_SMTP_USER`` / ``SMTP_USER`` (env: ``SMTP_USER``)
- ``TARS_SMTP_PASSWORD`` / ``SMTP_PASSWORD`` (env: ``SMTP_PASSWORD``)
- ``TARS_SMTP_FROM`` / ``SMTP_FROM`` (env: ``SMTP_FROM``, default user)

Behaviour:

- ``starttls`` is enabled by default on port 587, off on port 465 (which
  uses implicit TLS), and off on port 25 (no encryption — only for
  local/test relays).
- Config-missing → returns ``unavailable`` so the action degrades to
  draft-only mode without crashing.
- SMTP errors → returned as structured ``send_failed`` so the cockpit
  surfaces them; the policy gate already blocked unconfirmed sends.

We deliberately DON'T support OAuth / JMAP here — operators wanting
those plug in higher-level providers via the same vault interface.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from backend.core.vault import get_secret


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str | None
    password: str | None
    from_addr: str
    starttls: bool
    implicit_tls: bool

    @classmethod
    def load(cls) -> "SmtpConfig | None":
        host = (
            get_secret("TARS_SMTP_HOST")
            or get_secret("SMTP_HOST")
            or os.getenv("SMTP_HOST")
        )
        if not host:
            return None
        port_raw = (
            get_secret("TARS_SMTP_PORT")
            or get_secret("SMTP_PORT")
            or os.getenv("SMTP_PORT")
            or "587"
        )
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            port = 587
        user = (
            get_secret("TARS_SMTP_USER")
            or get_secret("SMTP_USER")
            or os.getenv("SMTP_USER")
        )
        password = (
            get_secret("TARS_SMTP_PASSWORD")
            or get_secret("SMTP_PASSWORD")
            or os.getenv("SMTP_PASSWORD")
        )
        from_addr = (
            get_secret("TARS_SMTP_FROM")
            or get_secret("SMTP_FROM")
            or os.getenv("SMTP_FROM")
            or user
            or ""
        )
        if not from_addr:
            return None
        implicit_tls = port == 465
        starttls = port == 587
        return cls(
            host=str(host).strip(),
            port=port,
            user=user.strip() if isinstance(user, str) else None,
            password=password if isinstance(password, str) else None,
            from_addr=str(from_addr).strip(),
            starttls=starttls,
            implicit_tls=implicit_tls,
        )


@dataclass(frozen=True)
class SmtpResult:
    sent: bool
    via: str  # "smtp" | "smtp_ssl"
    server: str
    from_addr: str
    to_addr: str
    response_code: int | None
    elapsed_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "via": self.via,
            "server": self.server,
            "from": self.from_addr,
            "to": self.to_addr,
            "response_code": self.response_code,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "error": self.error,
        }


def _build_message(
    *,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    cc: str | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _send_sync(
    config: SmtpConfig,
    msg: EmailMessage,
    *,
    timeout_s: float,
) -> SmtpResult:
    started = time.perf_counter()
    via = "smtp"
    response_code: int | None = None
    try:
        if config.implicit_tls:
            via = "smtp_ssl"
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                config.host, config.port, timeout=timeout_s, context=ctx
            ) as server:
                if config.user and config.password:
                    server.login(config.user, config.password)
                server.send_message(msg)
                response_code = 250
        else:
            with smtplib.SMTP(
                config.host, config.port, timeout=timeout_s
            ) as server:
                server.ehlo()
                if config.starttls:
                    ctx = ssl.create_default_context()
                    server.starttls(context=ctx)
                    server.ehlo()
                if config.user and config.password:
                    server.login(config.user, config.password)
                server.send_message(msg)
                response_code = 250
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        return SmtpResult(
            sent=False,
            via=via,
            server=f"{config.host}:{config.port}",
            from_addr=config.from_addr,
            to_addr=str(msg.get("To") or ""),
            response_code=None,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            error=str(exc),
        )
    return SmtpResult(
        sent=True,
        via=via,
        server=f"{config.host}:{config.port}",
        from_addr=config.from_addr,
        to_addr=str(msg.get("To") or ""),
        response_code=response_code,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        error=None,
    )


async def send_email(
    *,
    to_addr: str,
    subject: str,
    body: str,
    cc: str | None = None,
    timeout_s: float = 15.0,
    config: SmtpConfig | None = None,
) -> dict[str, Any]:
    """Send an email through SMTP.

    Returns ``{"unavailable": True, ...}`` when no SMTP_* config is
    present so the caller can fall back to draft-only mode. Errors
    surface as ``{"sent": False, "error": "..."}`` rather than
    exceptions — destructive actions stay deterministic.
    """

    cfg = config or SmtpConfig.load()
    if cfg is None:
        return {
            "unavailable": True,
            "reason": "smtp_not_configured",
            "hint": (
                "set SMTP_HOST + SMTP_USER/SMTP_PASSWORD (or vault keys "
                "TARS_SMTP_HOST etc.) to enable real outbound mail."
            ),
        }
    msg = _build_message(
        from_addr=cfg.from_addr,
        to_addr=to_addr,
        subject=subject,
        body=body,
        cc=cc,
    )
    result = await asyncio.to_thread(_send_sync, cfg, msg, timeout_s=timeout_s)
    return result.to_dict()
