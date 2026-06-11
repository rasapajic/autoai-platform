import psycopg2
import os
import json
import uuid
import asyncio
import logging
import sys
sys.path.insert(0, '/app')
from app.core.email import send_alert_email
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def save_listings(listings):
    conn  = get_conn()
    cur   = conn.cursor()
    saved = 0
    for l in listings:
        try:
            images = l.get("images")
            if isinstance(images, list):
                images = json.dumps(images)
            cur.execute("""
                INSERT INTO listings
                    (id, external_id, source, make, model, year, price,
                     mileage, fuel_type, body_type, url, images, is_active, country,
                     contact_type, contact_url)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s,%s)
                ON CONFLICT (external_id) DO UPDATE SET
                    year         = CASE WHEN listings.year IS NULL THEN EXCLUDED.year ELSE listings.year END,
                    mileage      = COALESCE(EXCLUDED.mileage, listings.mileage),
                    fuel_type    = CASE WHEN listings.fuel_type IS NULL THEN EXCLUDED.fuel_type ELSE listings.fuel_type END,
                    body_type    = CASE WHEN listings.body_type IS NULL THEN EXCLUDED.body_type ELSE listings.body_type END,
                    price        = CASE WHEN EXCLUDED.price IS NOT NULL THEN EXCLUDED.price ELSE listings.price END,
                    contact_type = CASE WHEN EXCLUDED.contact_type != 'unknown' THEN EXCLUDED.contact_type ELSE listings.contact_type END,
                    contact_url  = COALESCE(EXCLUDED.contact_url, listings.contact_url)
            """, (
                str(uuid.uuid4()),
                l.get("external_id"), l.get("source"),
                l.get("make"), l.get("model"), l.get("year"),
                l.get("price"), l.get("mileage"), l.get("fuel_type"),
                l.get("body_type"),
                l.get("url"), images, l.get("country"),
                l.get("contact_type", "unknown"), l.get("contact_url"),
            ))
            conn.commit()
            saved += 1
        except Exception as e:
            conn.rollback()
            print(f"  DB error: {e}")
    cur.close()
    conn.close()
    return saved

def run_price_estimation():
    from app.core.valuation import run_price_estimation as _run
    _run(DATABASE_URL)

async def run_autoscout24():
    print("\n=== AUTOSCOUT24 DE ===")
    total = 0
    try:
        from app.scrapers.autoscout24 import AutoScout24Scraper
        for fuel_name, pages in [("diesel",4),("petrol",4),("electric",2),("hybrid",2)]:
            print(f"  AS24 DE {fuel_name}...")
            scraper  = AutoScout24Scraper()
            listings = await scraper.scrape_listings({"fuel_type": fuel_name}, max_pages=pages)
            saved    = save_listings(listings)
            total   += saved
            print(f"  {fuel_name}: {saved}")
            await asyncio.sleep(2)
        print(f"  AS24 DE ukupno: {total}")
        return total
    except Exception as e:
        print(f"  AS24 DE greska: {e}")
        return 0

async def run_autoscout24_at():
    print("\n=== AUTOSCOUT24 AT ===")
    total = 0
    try:
        from app.scrapers.autoscout24 import AutoScout24Scraper
        for fuel_name, pages in [("diesel",2),("petrol",2),("electric",1),("hybrid",1)]:
            print(f"  AS24 AT {fuel_name}...")
            scraper  = AutoScout24Scraper()
            listings = await scraper.scrape_listings({"fuel_type": fuel_name, "country": "A"}, max_pages=pages)
            saved    = save_listings(listings)
            total   += saved
            print(f"  {fuel_name}: {saved}")
            await asyncio.sleep(2)
        print(f"  AS24 AT ukupno: {total}")
        return total
    except Exception as e:
        print(f"  AS24 AT greska: {e}")
        return 0

async def run_mobile_de():
    print("\n=== MOBILE.DE ===")
    try:
        from app.scrapers.mobile_de import MobileDeScraper
        scraper  = MobileDeScraper()
        listings = await scraper.scrape_listings({}, max_pages=2)
        saved    = save_listings(listings)
        print(f"  Mobile.de: {saved}")
        return saved
    except Exception as e:
        print(f"  Mobile.de greska: {e}")
        return 0

async def run_willhaben():
    print("\n=== WILLHABEN ===")
    try:
        from app.scrapers.willhaben import WillhabenScraper
        scraper = WillhabenScraper()
        listings = await scraper.scrape_listings({}, max_pages=3)
        saved = save_listings(listings)
        print(f"  Willhaben: {saved}")
        return saved
    except Exception as e:
        print(f"  Willhaben greska: {e}")
        return 0

def check_alerts():
    print("\n=== ALERT CHECK ===")
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT a.id, a.name, a.filters, a.last_checked, u.email
            FROM saved_searches a
            JOIN users u ON u.id = a.user_id
            WHERE a.is_active = TRUE
        """)
        alerts = cur.fetchall()
        print(f"  Aktivnih alerta: {len(alerts)}")

        for alert_id, alert_name, filters, last_checked, user_email in alerts:
            try:
                conditions = ["created_at > %s"]
                params = [last_checked]

                if filters.get("make"):
                    conditions.append("LOWER(make) = LOWER(%s)")
                    params.append(filters["make"])
                if filters.get("model"):
                    conditions.append("LOWER(model) LIKE LOWER(%s)")
                    params.append(f"%{filters['model']}%")
                if filters.get("price_max"):
                    conditions.append("price <= %s")
                    params.append(filters["price_max"])
                if filters.get("price_min"):
                    conditions.append("price >= %s")
                    params.append(filters["price_min"])
                if filters.get("year_min"):
                    conditions.append("year >= %s")
                    params.append(filters["year_min"])
                if filters.get("mileage_max"):
                    conditions.append("mileage <= %s")
                    params.append(filters["mileage_max"])
                if filters.get("fuel_type"):
                    conditions.append("LOWER(fuel_type) = LOWER(%s)")
                    params.append(filters["fuel_type"])

                where = " AND ".join(conditions)
                cur.execute(f"""
                    SELECT id, make, model, year, price, url
                    FROM listings
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT 5
                """, params)
                matches = cur.fetchall()
                print(f"  Alert '{alert_name}' ({user_email}): {len(matches)} novih")

                for listing_id, make, model, year, price, url in matches:
                    cur.execute("""
                        SELECT 1 FROM alert_log
                        WHERE alert_id = %s AND listing_id = %s
                    """, (alert_id, str(listing_id)))
                    if cur.fetchone():
                        continue

                    title = f"{year} {make} {model}"
                    sent = send_alert_email(
                        to_email=user_email,
                        car_title=title,
                        car_price=float(price),
                        car_url=url,
                        search_name=alert_name,
                    )

                    if sent:
                        cur.execute("""
                            INSERT INTO alert_log (alert_id, listing_id)
                            VALUES (%s, %s)
                        """, (alert_id, str(listing_id)))
                        conn.commit()

                cur.execute("""
                    UPDATE saved_searches SET last_checked = NOW()
                    WHERE id = %s
                """, (alert_id,))
                conn.commit()

            except Exception as e:
                print(f"  Alert greška ({alert_name}): {e}")
                conn.rollback()

        cur.close()
        conn.close()

    except Exception as e:
        print(f"  Alert check greška: {e}")


def main():
    total  = 0
    total += asyncio.run(run_autoscout24())
    total += asyncio.run(run_autoscout24_at())
    total += asyncio.run(run_mobile_de())
    total += asyncio.run(run_willhaben())
    run_price_estimation()
    check_alerts()
    print(f"\n=== UKUPNO: {total} ===")


if __name__ == "__main__":
    main()
