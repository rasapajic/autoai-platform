import psycopg2
import os
import json
import uuid
import asyncio
import logging

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
                     mileage, fuel_type, body_type, url, images, is_active, country)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)
                ON CONFLICT (external_id) DO UPDATE SET
                    year      = CASE WHEN listings.year IS NULL THEN EXCLUDED.year ELSE listings.year END,
                    mileage   = COALESCE(EXCLUDED.mileage, listings.mileage),
                    fuel_type = CASE WHEN listings.fuel_type IS NULL THEN EXCLUDED.fuel_type ELSE listings.fuel_type END,
                    body_type = CASE WHEN listings.body_type IS NULL THEN EXCLUDED.body_type ELSE listings.body_type END,
                    price     = CASE WHEN EXCLUDED.price IS NOT NULL THEN EXCLUDED.price ELSE listings.price END
            """, (
                str(uuid.uuid4()),
                l.get("external_id"), l.get("source"),
                l.get("make"), l.get("model"), l.get("year"),
                l.get("price"), l.get("mileage"), l.get("fuel_type"),
                l.get("body_type"),
                l.get("url"), images, l.get("country"),
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
    print("\n=== PRICE ESTIMATION ===")
    conn = get_conn()
    cur  = conn.cursor()
    try:
        # Korak 1: Izračunaj median cenu po make/model/godiste/km segmentu
        cur.execute("""
            UPDATE listings l
            SET
                price_estimated = sub.median_price,
                price_delta_pct = ROUND(
                    ((l.price - sub.median_price) / sub.median_price * 100)::numeric, 1
                )
            FROM (
                SELECT
                    l1.id,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l2.price::numeric) AS median_price
                FROM listings l1
                JOIN listings l2 ON
                    l1.make = l2.make AND
                    l1.model = l2.model AND
                    l2.price IS NOT NULL AND
                    l2.price::numeric BETWEEN 500 AND 500000 AND
                    (l1.year IS NULL OR l2.year IS NULL OR ABS(l2.year - l1.year) <= 2) AND
                    (
                        l1.mileage IS NULL OR l2.mileage IS NULL OR
                        (
                            CASE
                                WHEN l1.mileage < 50000  THEN l2.mileage < 50000
                                WHEN l1.mileage < 150000 THEN l2.mileage BETWEEN 50000 AND 150000
                                ELSE l2.mileage >= 150000
                            END
                        )
                    )
                WHERE l1.price IS NOT NULL
                GROUP BY l1.id
                HAVING COUNT(l2.id) >= 2
            ) sub
            WHERE l.id = sub.id
              AND sub.median_price > 0
        """)
        updated = cur.rowcount
        conn.commit()
        print(f"  Price estimation: {updated} oglasa azurirano")

        # Korak 2: Postavi price_rating na osnovu price_delta_pct
        cur.execute("""
            UPDATE listings
            SET price_rating = CASE
                WHEN price_delta_pct < -10 THEN 'great'
                WHEN price_delta_pct < -3  THEN 'good'
                WHEN price_delta_pct <= 5  THEN 'fair'
                WHEN price_delta_pct <= 15 THEN 'high'
                WHEN price_delta_pct > 15  THEN 'overpriced'
                ELSE NULL
            END
            WHERE price_estimated IS NOT NULL
        """)
        rated = cur.rowcount
        conn.commit()
        print(f"  Price rating: {rated} oglasa azurirano")

        return updated
    except Exception as e:
        conn.rollback()
        print(f"  Price estimation greska: {e}")
        import traceback
        print(traceback.format_exc())
        return 0
    finally:
        cur.close()
        conn.close()

async def run_autoscout24():
    print("\n=== AUTOSCOUT24 DE ===")
    total = 0
    try:
        import sys
        sys.path.insert(0, '/app')
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
        import sys
        sys.path.insert(0, '/app')
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
        import sys
        sys.path.insert(0, '/app')
        from app.scrapers.mobile_de import MobileDeScraper
        scraper  = MobileDeScraper()
        listings = await scraper.scrape_listings({}, max_pages=2)
        saved    = save_listings(listings)
        print(f"  Mobile.de: {saved}")
        return saved
    except Exception as e:
        print(f"  Mobile.de greska: {e}")
        return 0

def main():
    def check_alerts():
    print("\n=== ALERT CHECK ===")
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Uzmi sve aktivne alerte sa email korisnika
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
                # Izgradi WHERE uslove iz filtera
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
                    # Proveri da li je email već poslat
                    cur.execute("""
                        SELECT 1 FROM alert_log
                        WHERE alert_id = %s AND listing_id = %s
                    """, (alert_id, str(listing_id)))
                    if cur.fetchone():
                        continue

                    # Pošalji email
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

                # Ažuriraj last_checked
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
    run_price_estimation()
    check_alerts()
    print(f"\n=== UKUPNO: {total} ===")


if __name__ == "__main__":
    main()
