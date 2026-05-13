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
    make = parts[0] if parts else None
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
                print(f"  Preskacemo stranicu")
                return []
            time.sleep(5 * (attempt + 1))
    print(f"  Status: {resp.status_code} | Bytes: {len(resp.content)}")
    if '<' not in resp.text[:100]:
        print(f"  GRESKA: Nije HTML!")
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
                "external_id": external_id, "source": "polovniautomobili",
                "make": make, "model": model, "year": year, "price": price,
                "mileage": mileage, "fuel_type": fuel_type,
                "url": full_url, "images": images, "country": "RS",
            })
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Pronadjeno: {len(listings)}")
    return listings

def run_polovni():
    print("\n=== POLOVNI AUTOMOBILI ===")
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.polovniautomobili.com/", timeout=30)
        time.sleep(2)
    except Exception as e:
        print(f"  Homepage timeout: {e}")
    base_url = "https://www.polovniautomobili.com/auto-oglasi/pretraga?page={}&sort=basic&without_price=1"
    total = 0
    for page in range(1, 11):
        url = base_url.format(page)
        print(f"Scraping page {page}...")
        listings = scrape_polovni_page(url, session)
        saved = save_listings(listings)
        total += saved
        print(f"Saved {saved} (total: {total})")
        time.sleep(random.uniform(3, 6))
    print(f"Polovni done! Total: {total}")
    return total

def scrape_willhaben_page(session, offset, rows=25):
    url = "https://www.willhaben.at/iad/gebrauchtwagen/auto"
    params = {"sfId": "", "rows": rows, "isNavigation": "false", "pagingOffset": offset, "sort": 1}
    try:
        resp = session.get(url, params=params, timeout=30)
        print(f"  [Willhaben] Status: {resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not next_data_tag:
            print(f"  [Willhaben] Nema __NEXT_DATA__")
            return []
        next_data = json.loads(next_data_tag.string)
        page_props = next_data.get("props", {}).get("pageProps", {})
        search_result = page_props.get("initialSearchResult", {})
        adverts = search_result.get("advertSummaryList", {}).get("advertSummary", [])
        print(f"  [Willhaben] Oglasi: {len(adverts)}")
        return adverts
    except Exception as e:
        print(f"  [Willhaben] Greška: {e}")
        return []

def parse_willhaben_ad(ad):
    try:
        def get_attr(attrs, name):
            for a in attrs:
                if a.get("name") == name:
                    vals = a.get("values", [])
                    return vals[0] if vals else None
            return None
        attrs = ad.get("attributes", {}).get("attribute", [])
        ad_id = str(ad.get("id", ""))
        make = get_attr(attrs, "MAKE")
        model = get_attr(attrs, "MODEL")
        year_str = get_attr(attrs, "YEAR")
        price_str = get_attr(attrs, "PRICE_FOR_DISPLAY") or get_attr(attrs, "PRICE")
        mileage_str = get_attr(attrs, "MILEAGE")
        fuel = get_attr(attrs, "FUEL_TYPE") or ""
        year = None
        if year_str:
            try:
                year = int(str(year_str)[:4])
            except Exception:
                pass
        price = None
        if price_str:
            try:
                cleaned = ''.join(c for c in str(price_str) if c.isdigit() or c == '.')
                price = float(cleaned) if cleaned else None
            except Exception:
                pass
        mileage = None
        if mileage_str:
            try:
                mileage = int(''.join(filter(str.isdigit, str(mileage_str))) or 0) or None
            except Exception:
                pass
        images = []
        for img in (ad.get("advertImageList", {}).get("advertImage", []) or []):
            ref = img.get("reference")
            if ref:
                images.append(f"https://cache.willhaben.at/mmo/{ref}")
        return {
            "external_id": f"wh_{ad_id}",
            "source": "willhaben",
            "make": make,
            "model": model,
            "year": year,
            "price": price,
            "mileage": mileage,
            "fuel_type": fuel.lower() if fuel else None,
            "url": f"https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagen/{ad_id}",
            "images": json.dumps(images[:5]),
            "country": "AT",
        }
    except Exception as e:
        print(f"  [Willhaben] Parse greška: {e}")
        return None

def run_willhaben():
    print("\n=== WILLHABEN ===")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
        "Referer": "https://www.willhaben.at/",
    })
    try:
        session.get("https://www.willhaben.at/", timeout=15)
        time.sleep(2)
    except Exception as e:
        print(f"  Homepage greška: {e}")
    total = 0
    for page in range(10):
        offset = page * 25
        print(f"  Stranica {page + 1} (offset={offset})...")
        adverts = scrape_willhaben_page(session, offset)
        if not adverts:
            break
        listings = [parse_willhaben_ad(ad) for ad in adverts]
        listings = [l for l in listings if l]
        saved = save_listings(listings)
        total += saved
        print(f"  Saved {saved} (total: {total})")
        time.sleep(random.uniform(2, 4))
    print(f"  Willhaben ukupno: {total}")
    return total

def save_listings(listings):
    conn = get_conn()
    cur = conn.cursor()
    saved = 0
    for l in listings:
        try:
            images = l.get("images")
            if isinstance(images, list):
                images = json.dumps(images)
            cur.execute("""
                INSERT INTO listings
                    (id, external_id, source, make, model, year, price,
                     mileage, fuel_type, url, images, is_active, country)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)
                ON CONFLICT (external_id) DO NOTHING
            """, (
                str(uuid.uuid4()),
                l.get("external_id"), l.get("source"),
                l.get("make"), l.get("model"), l.get("year"),
                l.get("price"), l.get("mileage"), l.get("fuel_type"),
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
    print("\n=== AUTOSCOUT24 ===")
    try:
        import sys
        sys.path.insert(0, '/app')
        from app.scrapers.autoscout24 import AutoScout24Scraper
        scraper = AutoScout24Scraper()
        listings = await scraper.scrape_listings({}, max_pages=10)
        print(f"  AutoScout24 pronadjeno: {len(listings)}")
        saved = save_listings(listings)
        print(f"  AutoScout24 saved: {saved}")
        return saved
    except Exception as e:
        print(f"  AutoScout24 greska: {e}")
        return 0

async def run_mobile_de():
    print("\n=== MOBILE.DE ===")
    try:
        import sys
        sys.path.insert(0, '/app')
        from app.scrapers.mobile_de import MobileDeScraper
        scraper = MobileDeScraper()
        listings = await scraper.scrape_listings({}, max_pages=10)
        print(f"  Mobile.de pronadjeno: {len(listings)}")
        saved = save_listings(listings)
        print(f"  Mobile.de saved: {saved}")
        return saved
    except Exception as e:
        print(f"  Mobile.de greska: {e}")
        return 0

def main():
    total = 0
    total += run_polovni()
    total += run_willhaben()
    total += asyncio.run(run_autoscout24())
    total += asyncio.run(run_mobile_de())
    print(f"\n=== UKUPNO SAČUVANO: {total} ===")

if __name__ == "__main__":
    main()
