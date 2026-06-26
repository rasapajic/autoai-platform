import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.scripts.send_test_email user@example.com")
        return 2

    from app.core.email import send_email

    to_email = sys.argv[1]
    subject = "AutoAI test email"
    body = (
        "Zdravo,\n\n"
        "Ovo je test email iz AutoAI 5 SMTP konfiguracije.\n"
        "Ako vidis ovu poruku, email notifikacije za sacuvane potrage mogu da salju email.\n\n"
        "AutoAI"
    )

    sent = send_email(to_email, subject, body)
    if not sent:
        print("SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and optional SMTP_FROM.")
        return 1

    print(f"Test email sent to {to_email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
