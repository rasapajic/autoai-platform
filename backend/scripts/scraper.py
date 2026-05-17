import requests
from bs4 import BeautifulSoup
import psycopg2
import os
import time
import random
import json
import uuid
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.polovniautomobili.com/",
    "Connection": "keep-alive",
}

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def parse_make_model(title):
    parts = title.strip().split(" ", 1)
    make  = parts[0] if parts else None
    model = parts[1] if len(parts) > 1 else None
    return make, model

def scrape_polovni_page(url, session):
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            break
        except Exception as e:
            print(f"  Timeout pokusaj {attempt+1}/3: {e}")
            if attempt == 2:
                return []
            time.sleep(5 * (attempt + 1))
    if '<' not in resp.text[:100]:
        return []
    soup     = BeautifulSoup(resp.text, "html.parser")
    items    = soup.select("article.classified")
    listings = []
    for item in items:
        try:
            title_el = item.select_one("h3.classified-title")
            price_el = item.select_one(".price-box .price")
            link_el  = item.select_one("a.ga-title")
            details  = item.select(".classified-details li")
            img_el   = item.select_one("img")
            if not link_el:
                continue
            href        = link_el.get("href", "")
            full_url    = "https://www.polovniautomobili.com" + href
            external_id = "pola_" + href.strip("/").split("/")[-1]
            title       = title_el.text.strip() if title_el else ""
            make, model = parse_make_model(title)
            price_raw   = price_el.text.strip() if price_el else ""
            price       = int(''.join(filter(str.isdigit, price_raw)) or 0) or None
            year = mileage = fuel_type = None
            for d in details:
                t = d.text.strip()
                if t.isdigit() and len(t) == 4:
                    year = int(t)
                elif "km" in t.lower():
                    mileage = int(''.join(filter(str.isdigit, t)) or 0) or None
                elif any(f in t.lower() for f in ["dizel","benzin","elektr","hibrid","gas"]):
                    fuel_type = t
            img_src = img_el.get("data-src") or img_el.get("src") if img_el else None
            images  = json.dumps([img_src]) if img_src else json.dumps([])
            listings.append({
                "external_id": external_id, "source": "polovniautomobili",
                "make": make, "model": model, "year": year, "price": price,
                "mileage": mileage, "fuel_type": fuel_type, "body_type": None,
                "url": full_url, "images": images, "country": "RS",
            })
        except Exception as e:
            print(f"  Error: {e}")
    return listings

def run_polovni():
    print("\n=== POLOVNI AUTOMOBILI ===")
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.polovniautomobili.com/", timeout=30)
        time.sleep(2)
    except: pass
    base_url = "https://www.polovniautomobili.com/auto-oglasi/pretraga?page={}&sort=basic&without_price=1"
    total = 0
    for page in range(1, 3):
        listings = scrape_polovni_page(base_url.format(page), session)
        saved    = save_listings(listings)
        total   += saved
        print(f"  Polovni str {page}: {saved}")
        time.sleep(random.uniform(2, 4))
    print(f"  Polovni ukupno: {total}")
    return total

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

async def run_autoscout24():
    print("\n=== AUTOSCOUT24 DE ===")
    total = 0
    try:
        import sys
        sys.path.insert(0, '/app')
        from app.scrapers.autoscout24 import AutoScout24Scraper
        for fuel_name, pages in [("diesel",2),("petrol",2),("electric",1),("hybrid",1)]:
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
        for fuel_name, pages in [("diesel",1),("petrol",1),("electric",1),("hybrid",1)]:
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
    total  = 0
    total += run_polovni()
    total += asyncio.run(run_autoscout24())
    total += asyncio.run(run_autoscout24_at())
    total += asyncio.run(run_mobile_de())
    print(f"\n=== UKUPNO: {total} ===")

if __name__ == "__main__":
    main()
