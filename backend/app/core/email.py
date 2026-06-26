import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

import httpx

from app.core.config import settings


RESEND_URL = "https://api.resend.com/emails"

PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "test.local",
    "localhost",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def is_deliverable_email(email: str | None) -> bool:
    if not email:
        return False

    _, parsed = parseaddr(email)
    normalized = parsed.strip().lower()
    if not EMAIL_RE.match(normalized):
        return False

    domain = normalized.rsplit("@", 1)[1]
    if domain in PLACEHOLDER_EMAIL_DOMAINS:
        return False
    if domain.endswith(".localhost") or domain.endswith(".local"):
        return False
    if "demo" in normalized:
        return False

    return True


def public_link(url_or_path: str) -> str:
    if url_or_path.startswith(("http://", "https://")):
        return url_or_path
    return settings.app_url(url_or_path)


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not is_deliverable_email(to_email):
        return False

    if not email_is_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)

    return True


def send_alert_email(
    to_email: str,
    car_title: str,
    car_price: float,
    car_url: str,
    search_name: str,
) -> bool:
    if not is_deliverable_email(to_email):
        return False

    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        return False

    href = public_link(car_url)
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;
                background:#0f0f0f;color:#fff;border-radius:12px;overflow:hidden;">
      <div style="background:#FF6B00;padding:24px 32px;">
        <h1 style="margin:0;font-size:22px;">AutoAI Alert</h1>
        <p style="margin:8px 0 0;opacity:.8;font-size:14px;">
          Novi oglas za tvoju pretragu: <strong>{search_name}</strong>
        </p>
      </div>
      <div style="padding:32px;">
        <h2 style="margin:0 0 8px;font-size:20px;">{car_title}</h2>
        <div style="font-size:28px;font-weight:800;color:#FF6B00;margin:12px 0;">
          {int(car_price):,} EUR
        </div>
        <a href="{href}"
           style="display:inline-block;background:#FF6B00;color:#fff;
                  padding:14px 28px;border-radius:8px;text-decoration:none;
                  font-weight:700;margin-top:16px;">
          Pogledaj oglas
        </a>
      </div>
      <div style="padding:16px 32px;border-top:1px solid #222;
                  font-size:12px;color:#666;">
        AutoAI - AI platforma za polovne automobile
      </div>
    </div>
    """

    try:
        resp = httpx.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.SMTP_FROM or "AutoAI <onboarding@resend.dev>",
                "to": [to_email],
                "subject": f"AutoAI - novi oglas: {car_title} - {int(car_price):,} EUR",
                "html": html,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False
