import requests
from bs4 import BeautifulSoup
import psycopg2
import os
import time
import random

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def scrape_page(url, headers):
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    listings = []
    for item in soup.select("article.classified"):
        try:
            title = item.select_one("h3.classified__title")
            price = item.select_one(".price-box__price")
            year = item.select_one(".details li:nth-child(1)")
            km = item.select_one(".details li:nth-child(2)")
            fuel = item.select_one(".details li:nth-child(3)")
            link = item.select_one("a.classified__titleLink")
            img = item.select_one("img")
            if not title or not price:
                continue
            listings.append({
                "title": title.text.strip(),
                "price": int(''.join(filter(str.isdigit, price.text.strip())) or 0),
                "year": int(year.text.strip()) if year else None,
                "mileage": int(''.join(filter(str.isdigit, km.text.strip())) or 0) if km else None,
                "fuel_type": fuel.text.strip() if fuel else None,
                "url": "https://www.polovniautomobili.com" + link["href"] if link else None,
                "image_url": img.get("data-src") or img.get("src") if img else None,
                "source": "polovniautomobili",
            })
        except Exception as e:
            print(f"Error parsing item: {e}")
    return listings

def save_listings(listings):
    conn = get_conn()
    cur = conn.cursor()
    for l in listings:
        try:
            cur.execute("""
                INSERT INTO listings (title, price, year, mileage, fuel_type, url, image_url, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (url) DO NOTHING
            """, (l["title"], l["price"], l["year"], l["mileage"], l["fuel_type"], l["url"], l["image_url"], l["source"]))
        except Exception as e:
            print(f"DB error: {e}")
    conn.commit()
    cur.close()
    conn.close()

def main():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    base_url = "https://www.polovniautomobili.com/auto-oglasi/pretraga?page={}"
    total = 0
    for page in range(1, 11):
        url = base_url.format(page)
        print(f"Scraping page {page}...")
        listings = scrape_page(url, headers)
        save_listings(listings)
        total += len(listings)
        print(f"Saved {len(listings)} listings (total: {total})")
        time.sleep(random.uniform(2, 4))
    print(f"Done! Total: {total}")

if __name__ == "__main__":
    main()
