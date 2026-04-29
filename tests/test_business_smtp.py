"""Tests for the SMTP outbound integration in ``business.draft_email``."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.core.domains.packs.business import actions as business_actions
from backend.core.domains.packs.business import smtp as business_smtp


def _draft(args: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(business_actions.draft_email(args))


def test_draft_only_when_send_false(monkeypatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    out = _draft({"to": "x@y.z", "subject": "Hi"})
    assert out["sent"] is False
    assert out["delivery"]["status"] == "draft"


def test_send_true_without_smtp_returns_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("TARS_SMTP_HOST", raising=False)
    out = _draft({"to": "x@y.z", "subject": "Hi", "send": True})
    assert out["sent"] is False
    assert out["delivery"]["status"] == "unavailable"
    assert out["delivery"]["reason"] == "smtp_not_configured"


def test_smtp_config_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "ops@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "hunter2")
    monkeypatch.setenv("SMTP_FROM", "ops@example.com")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.host == "mail.example.com"
    assert cfg.port == 587
    assert cfg.starttls is True
    assert cfg.implicit_tls is False
    assert cfg.from_addr == "ops@example.com"


def test_smtp_config_load_returns_none_without_host(monkeypatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("TARS_SMTP_HOST", raising=False)
    assert business_smtp.SmtpConfig.load() is None


def test_implicit_tls_on_465(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "x@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "x@example.com")
    cfg = business_smtp.SmtpConfig.load()
    assert cfg is not None
    assert cfg.implicit_tls is True
    assert cfg.starttls is False


def test_send_email_routes_through_smtp_send(monkeypatch) -> None:
    """send_email must call _send_sync when config is present."""

    cfg = business_smtp.SmtpConfig(
        host="mail.example.com",
        port=587,
        user="ops@example.com",
        password="p",
        from_addr="ops@example.com",
        starttls=True,
        implicit_tls=False,
    )
    captured: dict[str, Any] = {}

    def fake_send(config, msg, *, timeout_s):
        captured["host"] = config.host
        captured["to"] = msg.get("To")
        captured["subject"] = msg.get("Subject")
        return business_smtp.SmtpResult(
            sent=True,
            via="smtp",
            server=f"{config.host}:{config.port}",
            from_addr=config.from_addr,
            to_addr=str(msg.get("To") or ""),
            response_code=250,
            elapsed_ms=12.0,
        )

    monkeypatch.setattr(business_smtp, "_send_sync", fake_send)

    out = asyncio.run(
        business_smtp.send_email(
            to_addr="x@y.z",
            subject="Hi",
            body="Hello world",
            config=cfg,
        )
    )
    assert out["sent"] is True
    assert captured["host"] == "mail.example.com"
    assert captured["to"] == "x@y.z"
    assert captured["subject"] == "Hi"


def test_draft_email_send_path_uses_send_email(monkeypatch) -> None:
    """draft_email handler must hand off to send_email when send=true and SMTP configured."""

    monkeypatch.setenv("SMTP_HOST", "mail.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "ops@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_FROM", "ops@example.com")

    fake_delivery = {
        "sent": True,
        "via": "smtp",
        "server": "mail.example.com:587",
        "from": "ops@example.com",
        "to": "x@y.z",
        "response_code": 250,
        "elapsed_ms": 5.0,
        "error": None,
    }

    captured: dict[str, Any] = {}

    async def fake_send_email(*, to_addr, subject, body, cc=None, **kwargs):
        captured["to_addr"] = to_addr
        captured["subject"] = subject
        captured["body"] = body
        captured["cc"] = cc
        return dict(fake_delivery)

    monkeypatch.setattr(business_actions, "send_email", fake_send_email)

    out = _draft(
        {
            "to": "x@y.z",
            "subject": "Hello",
            "body": "Custom body line.",
            "send": True,
        }
    )
    assert out["sent"] is True
    assert out["delivery"]["status"] == "sent"
    assert out["delivery"]["via"] == "smtp"
    assert captured["body"] == "Custom body line."


def test_business_pack_declares_smtp_vault_keys() -> None:
    from backend.core.domains.registry import get_pack

    pack = get_pack("business")
    assert pack is not None
    keys = pack.auth_vault_keys()
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        assert k in keys
