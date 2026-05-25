import os
import requests

RESEND_URL = "https://api.resend.com/emails"


def send_alert_email(to_email: str, car_title: str, car_price: float,
                     car_url: str, search_name: str) -> bool:
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        print("  ⚠️ RESEND_API_KEY nije postavljen")
        return False

    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;
                background:#0f0f0f;color:#fff;border-radius:12px;overflow:hidden;">
      <div style="background:#FF6B00;padding:24px 32px;">
        <h1 style="margin:0;font-size:22px;">🚗 AutoAI Alert</h1>
        <p style="margin:8px 0 0;opacity:.8;font-size:14px;">
          Novi oglas za tvoju pretragu: <strong>{search_name}</strong>
        </p>
      </div>
      <div style="padding:32px;">
        <h2 style="margin:0 0 8px;font-size:20px;">{car_title}</h2>
        <div style="font-size:28px;font-weight:800;color:#FF6B00;margin:12px 0;">
          {int(car_price):,} €
        </div>
        <a href="{car_url}"
           style="display:inline-block;background:#FF6B00;color:#fff;
                  padding:14px 28px;border-radius:8px;text-decoration:none;
                  font-weight:700;margin-top:16px;">
          Pogledaj oglas →
        </a>
      </div>
      <div style="padding:16px 32px;border-top:1px solid #222;
                  font-size:12px;color:#666;">
        AutoAI — AI platforma za polovne automobile
      </div>
    </div>
    """

    try:
        resp = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "AutoAI <onboarding@resend.dev>",
                "to": [to_email],
                "subject": f"🚗 Novi oglas: {car_title} — {int(car_price):,} €",
                "html": html,
            },
            timeout=10,
        )
        print(f"  📧 Email poslat na {to_email}: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"  ❌ Email greška: {e}")
        return False
