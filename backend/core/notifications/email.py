"""SMTP / Email bridge — third notification sibling (Wave 163).

Same shape as ``imessage.py`` + ``telegram.py``: one ``send_*``
primitive + a ``fanout_doctor_change`` helper, result-dict
contract, never raises. Pure stdlib (``smtplib`` + ``email``).

Why stdlib instead of a richer library (aiosmtplib, requests-based
SaaS)?
  - Operators on locked-down corporate networks can already SMTP
    through their existing relay; no extra dep to install.
  - The notifications module is supposed to stay light — heavier
    delivery (Resend, SES, SendGrid) belongs in the W98 outreach
    module, not here.

Config — all via env (override per-call via kwargs):

  TARS_SMTP_HOST     (required)
  TARS_SMTP_PORT     (default 587 for STARTTLS, 465 for SSL,
                      25 for plaintext)
  TARS_SMTP_USER     (optional — anonymous SMTP if unset)
  TARS_SMTP_PASSWORD (optional — paired with user)
  TARS_SMTP_FROM     (required — From header)
  TARS_SMTP_TLS      ('starttls' | 'ssl' | 'plain'; default starttls)

Honest framing:
  - **No HTML.** v0.1 sends text/plain only. HTML lands in v9.1.3.
  - **No attachments.** v0.1 is body-only. Attachments in v9.2.
  - **No DKIM signing.** That's the SMTP relay's job — most
    operators use a hosted relay (Gmail, Postmark, SES) that
    signs on the way out.
  - **Synchronous send.** Each call blocks on the SMTP handshake.
    For high-volume use the W98 outreach module is the right path.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any


log = logging.getLogger("tars.notifications.email")


CONTRACT_VERSION = "0.1.0"
_DEFAULT_PORTS = {"starttls": 587, "ssl": 465, "plain": 25}


def _resolve_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge env defaults with caller overrides. Returns dict."""

    overrides = overrides or {}

    host = overrides.get("host") or os.getenv("TARS_SMTP_HOST")
    user = overrides.get("user") or os.getenv("TARS_SMTP_USER")
    password = overrides.get("password") or os.getenv("TARS_SMTP_PASSWORD")
    sender = overrides.get("from_addr") or os.getenv("TARS_SMTP_FROM")
    tls = (overrides.get("tls") or os.getenv("TARS_SMTP_TLS") or "starttls").strip().lower()
    if tls not in _DEFAULT_PORTS:
        tls = "starttls"

    port_raw = overrides.get("port") or os.getenv("TARS_SMTP_PORT")
    if port_raw:
        try:
            port = int(port_raw)
        except (TypeError, ValueError):
            port = _DEFAULT_PORTS[tls]
    else:
        port = _DEFAULT_PORTS[tls]

    return {
        "host": host, "port": port,
        "user": user, "password": password,
        "from_addr": sender, "tls": tls,
    }


def is_configured() -> bool:
    """True iff the minimum env vars are present (HOST + FROM)."""

    cfg = _resolve_config()
    return bool(cfg["host"]) and bool(cfg["from_addr"])


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    *,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    from_addr: str | None = None,
    tls: str | None = None,
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Send a plain-text email.

    ``to`` accepts a single address or a list. Returns
    ``{ok, to, subject, message_id?, error?, detail?}``. Never raises.
    """

    if isinstance(to, str):
        to_list = [t.strip() for t in to.split(",") if t.strip()]
    else:
        to_list = [t.strip() for t in to if t and t.strip()]
    if not to_list:
        return {"ok": False, "error": "to_required"}

    subject = (subject or "").strip()
    if not subject:
        return {"ok": False, "error": "subject_required"}
    if not body:
        return {"ok": False, "error": "body_required"}

    cfg = _resolve_config({
        "host": host, "port": port,
        "user": user, "password": password,
        "from_addr": from_addr, "tls": tls,
    })
    if not cfg["host"]:
        return {
            "ok": False, "error": "host_missing",
            "hint": "set TARS_SMTP_HOST env or pass host= kwarg",
        }
    if not cfg["from_addr"]:
        return {
            "ok": False, "error": "from_missing",
            "hint": "set TARS_SMTP_FROM env or pass from_addr= kwarg",
        }

    msg = EmailMessage()
    msg["From"] = cfg["from_addr"]
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg_id = make_msgid(domain="tars.local")
    msg["Message-ID"] = msg_id
    msg.set_content(body)

    try:
        if cfg["tls"] == "ssl":
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                host=cfg["host"], port=cfg["port"],
                context=ctx, timeout=timeout_s,
            ) as smtp:
                if cfg["user"] and cfg["password"]:
                    smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(
                host=cfg["host"], port=cfg["port"], timeout=timeout_s,
            ) as smtp:
                smtp.ehlo()
                if cfg["tls"] == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if cfg["user"] and cfg["password"]:
                    smtp.login(cfg["user"], cfg["password"])
                smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        return {
            "ok": False, "error": "auth_failed",
            "detail": str(exc)[:300],
        }
    except smtplib.SMTPException as exc:
        return {
            "ok": False, "error": "smtp_error",
            "detail": str(exc)[:300],
        }
    except (TimeoutError, OSError) as exc:
        return {
            "ok": False, "error": "transport_error",
            "detail": str(exc)[:300],
        }

    return {
        "ok": True,
        "to": to_list,
        "subject": subject,
        "message_id": msg_id,
        "body_len": len(body),
    }


def fanout_doctor_change(
    change: dict[str, Any],
    *,
    to: str | None = None,
) -> dict[str, Any]:
    """One-line fan-out of a doctor.status_changed entry to email.

    ``to`` falls back to ``TARS_DOCTOR_ALERT_EMAIL`` env. Returns
    the same shape as :func:`send_email`.
    """

    to_addr = to or os.getenv("TARS_DOCTOR_ALERT_EMAIL")
    if not to_addr:
        return {
            "ok": False,
            "error": "to_required",
            "hint": "set TARS_DOCTOR_ALERT_EMAIL env",
        }

    slug = change.get("slug", "?")
    frm = change.get("from", "?")
    to_status = change.get("to", "?")
    summary = (change.get("summary") or "").strip()
    glyph = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}.get(
        to_status, to_status.upper()
    )
    subject = f"[TARS:{glyph}] {slug}: {frm} → {to_status}"
    body_lines = [
        f"TARS health check transition detected.",
        "",
        f"Check:    {slug}",
        f"From:     {frm}",
        f"To:       {to_status}",
    ]
    if summary:
        body_lines.append(f"Summary:  {summary}")
    body_lines.append("")
    body_lines.append("— TARS background daemon (Wave 157)")
    return send_email(to_addr, subject, "\n".join(body_lines))
