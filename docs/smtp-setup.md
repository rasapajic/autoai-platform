# SMTP setup for closed beta

AutoAI uses SMTP for saved-search email notifications. For Gmail, use an App Password instead of your normal Google password.

## Gmail App Password

1. Open your Google Account.
2. Go to Security.
3. Enable 2-Step Verification if it is not already enabled.
4. Open App passwords.
5. Create an app password for Mail, or choose Other and name it AutoAI.
6. Copy the generated 16-character password.
7. Put it in `.env` as `SMTP_PASSWORD` without spaces.

## Required values

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail-address@gmail.com
SMTP_PASSWORD=your_16_character_app_password
SMTP_FROM=AutoAI <your-gmail-address@gmail.com>
FRONTEND_URL=http://localhost:3000
```

## Send one test email

Run this from the backend container:

```bash
docker compose exec backend python -m app.scripts.send_test_email user@example.com
```

Or, if your local Python environment has backend dependencies installed:

```bash
cd backend
python -m app.scripts.send_test_email user@example.com
```

The command sends one simple AutoAI test email. If SMTP is missing, it exits safely and prints what needs to be configured.
