import requests
from bs4 import BeautifulSoup
import psycopg2
import os
import time
import random
import json

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
    make = parts[0] if parts else None
    model = parts[1] if len(parts) > 1 else None
    return make, model

def scrape_page(url, session):
    resp = session.get(url, timeout=15)
    print(f"  Status: {resp.status_code} | Bytes: {len(resp.content)}")

    preview = resp.text[:100]
    if '<' not in preview:
        print(f"  GRESKA: Nije HTML! {repr(preview)}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("article.classified")
    print(f"  article.classified: {len(items)}")

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

            href = link_el.get("href", "")
            full_url = "https://www.polovniautomobili.com" + href
            external_id = "pola_" + href.strip("/").split("/")[-1]

            title = title_el.text.strip() if title_el else ""
            make, model = parse_make_model(title)

            price_raw = price_el.text.strip() if price_el else ""
            price = int(''.join(filter(str.isdigit, price_raw)) or 0) or None

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
            images = json.dumps([img_src]) if img_src else json.dumps([])

            listings.append({
                "external_id": external_id,
                "source": "polovniautomobili",
                "make": make,
                "model": model,
                "year": year,
                "price": price,
                "mileage": mileage,
                "fuel_type": fuel_type,
                "url": full_url,
                "images": images,
            })
        except Exception as e:
            print(f"  Error: {e}")

    print(f"  Pronadjeno: {len(listings)}")
    return listings

def save_listings(listings):
    conn = get_conn()
    cur = conn.cursor()
    saved = 0
    for l in listings:
        try:
            cur.execute("""
                INSERT INTO listings
                    (external_id, source, make, model, year, price, mileage, fuel_type, url, images)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_id) DO NOTHING
            """, (
                l["external_id"], l["source"], l["make"], l["model"],
                l["year"], l["price"], l["mileage"], l["fuel_type"],
                l["url"], l["images"]
            ))
            conn.commit()
            saved += 1
        except Exception as e:
            conn.rollback()
            print(f"  DB error: {e}")
    cur.close()
    conn.close()
    return saved

def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    session.get("https://www.polovniautomobili.com/", timeout=15)
    time.sleep(2)

    base_url = "https://www.polovniautomobili.com/auto-oglasi/pretraga?page={}&sort=basic&without_price=1"
    total = 0

    for page in range(1, 11):
        url = base_url.format(page)
        print(f"Scraping page {page}...")
        listings = scrape_page(url, session)
        saved = save_listings(listings)
        total += saved
        print(f"Saved {saved} (total: {total})")
        time.sleep(random.uniform(3, 6))

    print(f"Done! Total: {total}")

if __name__ == "__main__":
    main()
