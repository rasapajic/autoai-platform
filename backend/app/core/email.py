import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
import re

from app.core.config import settings


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
