"""SMTP outbound for the business pack.

Stdlib-only ``smtplib`` + ``email.message``. Reads config from the
vault via :mod:`backend.core.vault.keychain` plus a few non-secret
``SMTP_*`` env vars.

Vault keys (any of):

- ``TARS_SMTP_HOST`` / ``SMTP_HOST`` (env: ``SMTP_HOST``)
- ``TARS_SMTP_PORT`` / ``SMTP_PORT`` (env: ``SMTP_PORT``, default 587)
- ``TARS_SMTP_USER`` / ``SMTP_USER`` (env: ``SMTP_USER``)
- ``TARS_SMTP_PASSWORD`` / ``SMTP_PASSWORD`` (env: ``SMTP_PASSWORD``)
- ``TARS_SMTP_OAUTH_TOKEN`` / ``SMTP_OAUTH_TOKEN``
  (env: ``SMTP_OAUTH_TOKEN``) — bearer token for SASL XOAUTH2. When
  set, takes precedence over ``SMTP_PASSWORD`` so Gmail / Office365
  OAuth2 can be plugged in without changing call sites.
- ``TARS_SMTP_FROM`` / ``SMTP_FROM`` (env: ``SMTP_FROM``, default user)
- ``TARS_SMTP_PROVIDER`` / ``SMTP_PROVIDER``
  (env: ``SMTP_PROVIDER``) — provider shorthand (``gmail``,
  ``office365`` / ``outlook``, ``fastmail``, ``yahoo``, ``zoho``).
  When set, the provider's known host/port/TLS defaults fill in any
  field the operator hasn't set explicitly. Explicit ``SMTP_HOST``
  always wins.

Behaviour:

- ``starttls`` is enabled by default on port 587, off on port 465 (which
  uses implicit TLS), and off on port 25 (no encryption — only for
  local/test relays).
- ``oauth_token`` set + ``user`` set → SASL XOAUTH2.
- ``oauth_token`` unset + ``user`` + ``password`` set → SMTP ``LOGIN``.
- Config-missing → returns ``unavailable`` so the action degrades to
  draft-only mode without crashing.
- SMTP / auth errors → returned as structured ``send_failed`` so the
  cockpit surfaces them; the policy gate already blocked unconfirmed
  sends.

Provider shorthand maps host + default port + TLS posture only.
**OAuth refresh** lives in :mod:`backend.core.domains.packs.business.oauth`
— if ``TARS_SMTP_OAUTH_REFRESH_TOKEN`` + ``TARS_SMTP_OAUTH_CLIENT_ID``
are present, ``SmtpConfig.load`` exchanges them for a fresh access
token and caches it in-process for ~55 minutes. The manually-pasted
``TARS_SMTP_OAUTH_TOKEN`` from #40 still wins when set, and is also
the fallback when refresh fails (transport / OAuth error → log + use
the manual token if there is one).
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
from backend.core.domains.packs.business.oauth import (
    OAuthRefreshConfig,
    get_fresh_access_token,
)


@dataclass(frozen=True)
class SmtpProvider:
    slug: str
    host: str
    port: int


_PROVIDERS: dict[str, SmtpProvider] = {
    "gmail": SmtpProvider("gmail", "smtp.gmail.com", 465),
    "googlemail": SmtpProvider("gmail", "smtp.gmail.com", 465),
    "google": SmtpProvider("gmail", "smtp.gmail.com", 465),
    "office365": SmtpProvider("office365", "smtp.office365.com", 587),
    "o365": SmtpProvider("office365", "smtp.office365.com", 587),
    "outlook": SmtpProvider("office365", "smtp.office365.com", 587),
    "fastmail": SmtpProvider("fastmail", "smtp.fastmail.com", 465),
    "yahoo": SmtpProvider("yahoo", "smtp.mail.yahoo.com", 465),
    "zoho": SmtpProvider("zoho", "smtp.zoho.com", 465),
}


def _lookup_provider(name: str | None) -> SmtpProvider | None:
    if not name:
        return None
    return _PROVIDERS.get(name.strip().lower()) or None


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str | None
    password: str | None
    from_addr: str
    starttls: bool
    implicit_tls: bool
    oauth_token: str | None = None
    provider: str | None = None
    # Source label for observability:
    # ``"manual"`` (operator pasted into vault) | ``"refresh"`` (just
    # refreshed via OAuth2) | ``"cache"`` (still-valid cached refresh
    # output) | ``"none"`` (no OAuth at all). The SMTP send result
    # surfaces this as ``oauth_token_source``.
    oauth_token_source: str = "none"
    oauth_expires_in: float | None = None

    @property
    def auth_method(self) -> str:
        if self.user and self.oauth_token:
            return "xoauth2"
        if self.user and self.password:
            return "password"
        return "none"

    @classmethod
    def load(cls) -> "SmtpConfig | None":
        provider = _lookup_provider(
            get_secret("TARS_SMTP_PROVIDER")
            or get_secret("SMTP_PROVIDER")
            or os.getenv("SMTP_PROVIDER")
        )
        host = (
            get_secret("TARS_SMTP_HOST")
            or get_secret("SMTP_HOST")
            or os.getenv("SMTP_HOST")
            or (provider.host if provider else None)
        )
        if not host:
            return None
        port_raw = (
            get_secret("TARS_SMTP_PORT")
            or get_secret("SMTP_PORT")
            or os.getenv("SMTP_PORT")
        )
        if port_raw is None and provider is not None:
            port = provider.port
        else:
            try:
                port = int(port_raw or "587")
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
        oauth_token = (
            get_secret("TARS_SMTP_OAUTH_TOKEN")
            or get_secret("SMTP_OAUTH_TOKEN")
            or os.getenv("SMTP_OAUTH_TOKEN")
        )
        oauth_token_source = "manual" if oauth_token else "none"
        oauth_expires_in: float | None = None
        # Refresh-token flow takes precedence when configured and no
        # manual token is already in the vault. The manual token still
        # wins when set so PR #40's contract isn't broken; the refresh
        # flow degrades gracefully when transport / OAuth fails by
        # falling back to ``oauth_token`` as-is.
        if not oauth_token:
            refresh_cfg = OAuthRefreshConfig.load(
                provider=provider.slug if provider else None
            )
            if refresh_cfg is not None:
                fresh = get_fresh_access_token(refresh_cfg)
                if fresh.get("ok"):
                    oauth_token = fresh.get("access_token")
                    oauth_token_source = str(fresh.get("source") or "refresh")
                    expires = fresh.get("expires_in")
                    if isinstance(expires, (int, float)):
                        oauth_expires_in = float(expires)
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
            oauth_token=(
                oauth_token.strip() if isinstance(oauth_token, str) else None
            ),
            provider=provider.slug if provider else None,
            oauth_token_source=oauth_token_source,
            oauth_expires_in=oauth_expires_in,
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
    auth_method: str = "none"
    error: str | None = None
    oauth_token_source: str = "none"
    oauth_expires_in: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "via": self.via,
            "server": self.server,
            "from": self.from_addr,
            "to": self.to_addr,
            "response_code": self.response_code,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "auth_method": self.auth_method,
            "oauth_token_source": self.oauth_token_source,
            "oauth_expires_in": (
                round(self.oauth_expires_in, 1)
                if self.oauth_expires_in is not None
                else None
            ),
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


def _xoauth2_authobj(user: str, token: str):
    """Return an smtplib auth callable for SASL XOAUTH2.

    The wire string is ``user=<user>\\x01auth=Bearer <token>\\x01\\x01``;
    smtplib base64-encodes it and sends as the ``AUTH XOAUTH2`` initial
    response.
    """

    payload = f"user={user}\x01auth=Bearer {token}\x01\x01"

    def authobj(challenge: bytes | None = None) -> str:
        return payload

    return authobj


def _authenticate(server: smtplib.SMTP, config: "SmtpConfig") -> str:
    """Perform SMTP AUTH using XOAUTH2 if a token is set, else LOGIN.

    Returns the chosen ``auth_method`` (``"xoauth2"`` / ``"password"`` /
    ``"none"``). Auth failures bubble up as ``smtplib.SMTPException``.
    """

    if config.user and config.oauth_token:
        server.auth(
            "XOAUTH2",
            _xoauth2_authobj(config.user, config.oauth_token),
            initial_response_ok=True,
        )
        return "xoauth2"
    if config.user and config.password:
        server.login(config.user, config.password)
        return "password"
    return "none"


def _send_sync(
    config: SmtpConfig,
    msg: EmailMessage,
    *,
    timeout_s: float,
) -> SmtpResult:
    started = time.perf_counter()
    via = "smtp"
    response_code: int | None = None
    auth_method = "none"
    try:
        if config.implicit_tls:
            via = "smtp_ssl"
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                config.host, config.port, timeout=timeout_s, context=ctx
            ) as server:
                auth_method = _authenticate(server, config)
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
                auth_method = _authenticate(server, config)
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
            auth_method=auth_method,
            error=str(exc),
            oauth_token_source=config.oauth_token_source,
            oauth_expires_in=config.oauth_expires_in,
        )
    return SmtpResult(
        sent=True,
        via=via,
        server=f"{config.host}:{config.port}",
        from_addr=config.from_addr,
        to_addr=str(msg.get("To") or ""),
        response_code=response_code,
        elapsed_ms=(time.perf_counter() - started) * 1000.0,
        auth_method=auth_method,
        error=None,
        oauth_token_source=config.oauth_token_source,
        oauth_expires_in=config.oauth_expires_in,
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
                "set SMTP_HOST + SMTP_USER/SMTP_PASSWORD or "
                "SMTP_OAUTH_TOKEN (or vault keys TARS_SMTP_HOST etc.) to "
                "enable real outbound mail. Use SMTP_PROVIDER=gmail / "
                "office365 / fastmail / yahoo / zoho for one-line provider "
                "defaults."
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
