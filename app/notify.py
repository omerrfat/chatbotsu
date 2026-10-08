"""Owner notifications. Free channels first: email (SMTP), Telegram bot, or log."""
import json
import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

log = logging.getLogger("notify")


def _lead_text(tenant: dict, kind: str, fields: dict | None, reason: str, transcript: list[dict]) -> tuple[str, str]:
    name = tenant["business_name"]
    if kind == "lead":
        subject = f"[{name}] New booking/enquiry"
        body = "New request received:\n\n" + "\n".join(f"- {k}: {v}" for k, v in (fields or {}).items())
    else:
        subject = f"[{name}] Customer needs a human"
        body = f"Reason: {reason or 'n/a'}"
    last = transcript[-6:]
    body += "\n\nRecent conversation:\n" + "\n".join(f"{m['role']}: {m['content']}" for m in last)
    return subject, body


def send(tenant: dict, kind: str, fields: dict | None, reason: str, transcript: list[dict]) -> bool:
    """kind: 'lead' | 'handoff'. Returns True if delivered (log counts as delivered). Never raises."""
    subject, body = _lead_text(tenant, kind, fields, reason, transcript)
    target = tenant["contact_for_handoff"]
    try:
        if target["type"] == "email":
            return _email(target["value"], subject, body)
        if target["type"] == "telegram":
            return _telegram(target["value"], f"{subject}\n\n{body}")
    except Exception as e:  # notification failure must never break the chat
        log.error("notify failed for %s: %s", tenant["tenant_id"], e)
        return False
    log.info("NOTIFY %s\n%s\n%s", tenant["tenant_id"], subject, body)
    return True


def _email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        log.warning("SMTP_HOST not set; email to %s not sent", to)
        return False
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "bot@localhost"))
    msg["To"], msg["Subject"] = to, subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return True


def _telegram(chat_id: str, text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN not set; telegram message not sent")
        return False
    r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat_id, "text": text[:4000]}, timeout=15)
    return r.status_code == 200
