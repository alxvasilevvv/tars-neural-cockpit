"""SASL XOAUTH2 + provider shorthand for ``business.draft_email`` SMTP path.

The base ``LOGIN`` flow is already pinned in ``test_business_smtp.py``;
this module covers the OAuth2 bearer-token path (Gmail / Office365) and
the ``SMTP_PROVIDER`` shorthand that pre-fills host / port / TLS.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import pytest

from backend.core.domains.packs.business import smtp as business_smtp


def _clear_smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "SMTP_HOST",
        "TARS_SMTP_HOST",
        "SMTP_PORT",
        "TARS_SMTP_PORT",
        "SMTP_USER",
        "TARS_SMTP_USER",
        "SMTP_PASSWORD",
        "TARS_SMTP_PASSWORD",
        "SMTP_OAUTH_TOKEN",
        "TARS_SMTP_OAUTH_TOKEN",
        "SMTP_FROM",
        "TARS_SMTP_FROM",
        "SMTP_PROVIDER",
        "TARS_SMTP_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)


def test_xoauth2_payload_uses_sasl_format() -> None:
    authobj = business_smtp._xoauth2_authobj("alice@example.com", "ya29.fake")
    payload = authobj()
    assert payload == "user=alice@example.com\x01auth=Bearer ya29.fake\x01\x01"
    assert payload == authobj(b"server-challenge-ignored")


def test_smtp_config_load_picks_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "ya29.fake")
    monkeypatch.setenv("SMTP_FROM", "alice@example.com")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.oauth_token == "ya29.fake"
    assert cfg.password is None
    assert cfg.auth_method == "xoauth2"


def test_auth_method_prefers_xoauth2_when_both_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "fallback-pass")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "ya29.fake")
    monkeypatch.setenv("SMTP_FROM", "alice@example.com")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.auth_method == "xoauth2"


def test_auth_method_falls_back_to_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "hunter2")
    monkeypatch.setenv("SMTP_FROM", "alice@example.com")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.auth_method == "password"


def test_provider_gmail_fills_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_PROVIDER", "gmail")
    monkeypatch.setenv("SMTP_USER", "alice@gmail.com")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "ya29.fake")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.host == "smtp.gmail.com"
    assert cfg.port == 465
    assert cfg.implicit_tls is True
    assert cfg.starttls is False
    assert cfg.provider == "gmail"
    assert cfg.from_addr == "alice@gmail.com"
    assert cfg.auth_method == "xoauth2"


def test_provider_office365_uses_starttls_587(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_PROVIDER", "office365")
    monkeypatch.setenv("SMTP_USER", "ops@contoso.com")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "EwAAA...")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.host == "smtp.office365.com"
    assert cfg.port == 587
    assert cfg.starttls is True
    assert cfg.implicit_tls is False
    assert cfg.provider == "office365"


def test_provider_outlook_aliases_office365(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_PROVIDER", "outlook")
    monkeypatch.setenv("SMTP_USER", "ops@contoso.com")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "EwAAA...")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.provider == "office365"
    assert cfg.host == "smtp.office365.com"


def test_explicit_host_wins_over_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_PROVIDER", "gmail")
    monkeypatch.setenv("SMTP_HOST", "relay.internal.example.com")
    monkeypatch.setenv("SMTP_PORT", "25")
    monkeypatch.setenv("SMTP_USER", "alice@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "alice@example.com")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.host == "relay.internal.example.com"
    assert cfg.port == 25
    assert cfg.implicit_tls is False
    assert cfg.starttls is False


def test_unknown_provider_is_ignored_when_no_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_PROVIDER", "carrierpigeon")
    monkeypatch.setenv("SMTP_USER", "alice@example.com")
    monkeypatch.setenv("SMTP_OAUTH_TOKEN", "x")
    assert business_smtp.SmtpConfig.load() is None


class _FakeSmtpServer:
    """Minimal smtplib.SMTP stand-in to capture auth + send_message calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def __enter__(self) -> "_FakeSmtpServer":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def ehlo(self) -> None:
        self.calls.append(("ehlo", None))

    def starttls(self, context: ssl.SSLContext | None = None) -> None:
        self.calls.append(("starttls", context is not None))

    def auth(
        self,
        mechanism: str,
        authobject,
        *,
        initial_response_ok: bool = True,
    ) -> None:
        self.calls.append(("auth", (mechanism, authobject(None))))

    def login(self, user: str, password: str) -> None:
        self.calls.append(("login", (user, password)))

    def send_message(self, msg: EmailMessage) -> None:
        self.calls.append(("send_message", msg.get("To")))


def _patch_smtp(
    monkeypatch: pytest.MonkeyPatch, captured: list[_FakeSmtpServer]
) -> None:
    """Patch both smtplib.SMTP and smtplib.SMTP_SSL with the same stand-in."""

    def factory(*_a, **_kw):  # noqa: ANN001
        srv = _FakeSmtpServer()
        captured.append(srv)
        return srv

    monkeypatch.setattr(smtplib, "SMTP", factory)
    monkeypatch.setattr(smtplib, "SMTP_SSL", factory)


def test_send_sync_uses_xoauth2_when_token_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[_FakeSmtpServer] = []
    _patch_smtp(monkeypatch, captured)

    cfg = business_smtp.SmtpConfig(
        host="smtp.gmail.com",
        port=465,
        user="alice@gmail.com",
        password=None,
        from_addr="alice@gmail.com",
        starttls=False,
        implicit_tls=True,
        oauth_token="ya29.fake",
        provider="gmail",
    )
    msg = EmailMessage()
    msg["From"] = "alice@gmail.com"
    msg["To"] = "bob@example.org"
    msg["Subject"] = "hi"
    msg.set_content("hello")

    result = business_smtp._send_sync(cfg, msg, timeout_s=2.0)
    assert result.sent is True
    assert result.via == "smtp_ssl"
    assert result.auth_method == "xoauth2"

    assert captured, "factory must have been hit"
    server = captured[0]
    auth_calls = [c for c in server.calls if c[0] == "auth"]
    assert auth_calls, server.calls
    mechanism, payload = auth_calls[0][1]
    assert mechanism == "XOAUTH2"
    assert payload == "user=alice@gmail.com\x01auth=Bearer ya29.fake\x01\x01"

    assert ("send_message", "bob@example.org") in server.calls
    assert all(c[0] != "login" for c in server.calls)


def test_send_sync_uses_login_when_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[_FakeSmtpServer] = []
    _patch_smtp(monkeypatch, captured)

    cfg = business_smtp.SmtpConfig(
        host="mail.example.com",
        port=587,
        user="ops@example.com",
        password="hunter2",
        from_addr="ops@example.com",
        starttls=True,
        implicit_tls=False,
    )
    msg = EmailMessage()
    msg["From"] = "ops@example.com"
    msg["To"] = "x@y.z"
    msg["Subject"] = "hi"
    msg.set_content("hello")

    result = business_smtp._send_sync(cfg, msg, timeout_s=2.0)
    assert result.sent is True
    assert result.auth_method == "password"

    server = captured[0]
    assert ("login", ("ops@example.com", "hunter2")) in server.calls
    assert all(c[0] != "auth" for c in server.calls)


def test_send_sync_xoauth2_failure_surfaces_as_send_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _AuthBoom(_FakeSmtpServer):
        def auth(self, mechanism, authobject, *, initial_response_ok=True):
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 invalid token")

    def factory(*_a, **_kw):
        return _AuthBoom()

    monkeypatch.setattr(smtplib, "SMTP_SSL", factory)
    monkeypatch.setattr(smtplib, "SMTP", factory)

    cfg = business_smtp.SmtpConfig(
        host="smtp.gmail.com",
        port=465,
        user="alice@gmail.com",
        password=None,
        from_addr="alice@gmail.com",
        starttls=False,
        implicit_tls=True,
        oauth_token="ya29.expired",
    )
    msg = EmailMessage()
    msg["From"] = "alice@gmail.com"
    msg["To"] = "bob@example.org"
    msg["Subject"] = "hi"
    msg.set_content("hello")

    result = business_smtp._send_sync(cfg, msg, timeout_s=2.0)
    assert result.sent is False
    assert result.error and "5.7.8" in result.error
    assert result.auth_method == "none"


def test_send_email_returns_unavailable_hint_mentions_oauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_smtp_env(monkeypatch)
    out = asyncio.run(
        business_smtp.send_email(
            to_addr="x@y.z", subject="hi", body="hello"
        )
    )
    assert out["unavailable"] is True
    assert "SMTP_OAUTH_TOKEN" in out["hint"]
    assert "SMTP_PROVIDER" in out["hint"]


def test_send_email_result_carries_auth_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[_FakeSmtpServer] = []
    _patch_smtp(monkeypatch, captured)

    cfg = business_smtp.SmtpConfig(
        host="smtp.gmail.com",
        port=465,
        user="alice@gmail.com",
        password=None,
        from_addr="alice@gmail.com",
        starttls=False,
        implicit_tls=True,
        oauth_token="ya29.fake",
        provider="gmail",
    )
    out = asyncio.run(
        business_smtp.send_email(
            to_addr="bob@example.org",
            subject="hi",
            body="hello",
            config=cfg,
        )
    )
    assert out["sent"] is True
    assert out["auth_method"] == "xoauth2"


def test_business_pack_declares_oauth_vault_keys() -> None:
    from backend.core.domains.registry import get_pack

    pack = get_pack("business")
    assert pack is not None
    keys = pack.auth_vault_keys()
    assert "SMTP_OAUTH_TOKEN" in keys
    assert "SMTP_PROVIDER" in keys
