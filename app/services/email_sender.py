"""
app/services/email_sender.py — Sprint 2.2

Basit SMTP gönderici. .env şu değişkenleri okur:
  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS,
  SMTP_FROM (varsayılan SMTP_USER), SMTP_TLS (default 1)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailNotConfigured(RuntimeError):
    pass


def _cfg() -> dict:
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    if not host or not user:
        raise EmailNotConfigured(
            "SMTP_HOST veya SMTP_USER tanımlı değil — .env dosyasına ekleyin."
        )
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "pass": os.getenv("SMTP_PASS", ""),
        "from": os.getenv("SMTP_FROM", user),
        "tls" : os.getenv("SMTP_TLS", "1") != "0",
    }


def send_report_email(
    *,
    to: list[str],
    subject: str,
    body_text: str,
    attachment_bytes: bytes,
    attachment_name: str,
    attachment_mime: str,
) -> dict:
    """
    Raporu attachment olarak e-posta ile gönderir.
    Döner: {"sent": True, "recipients": [...]} veya hata fırlatır.
    """
    if not to:
        raise ValueError("Alıcı listesi boş.")

    cfg = _cfg()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = cfg["from"]
    msg["To"]      = ", ".join(to)
    msg.set_content(body_text or "SAP-AI tarafından üretilen rapor ektedir.")

    maintype, _, subtype = attachment_mime.partition("/")
    subtype = (subtype or "octet-stream").split(";")[0].strip()
    msg.add_attachment(
        attachment_bytes,
        maintype=maintype or "application",
        subtype=subtype or "octet-stream",
        filename=attachment_name,
    )

    ctx = ssl.create_default_context()
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
        s.ehlo()
        if cfg["tls"]:
            s.starttls(context=ctx)
            s.ehlo()
        if cfg["pass"]:
            s.login(cfg["user"], cfg["pass"])
        s.send_message(msg)

    return {"sent": True, "recipients": to}
