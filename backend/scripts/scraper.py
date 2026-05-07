import requests
from bs4 import BeautifulSoup
import psycopg2
import os
import time
import random

DATABASE_URL = os.environ.get("DATABASE_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8",
    # Accept-Encoding UKLONJEN - requests sam hendluje gzip
    "Referer": "https://www.polovniautomobili.com/",
    "Connection": "keep-alive",
}

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def scrape_page(url, session):
    resp = session.get(url, timeout=15)
    print(f"  Status: {resp.status_code} | Bytes: {len(resp.content)}")
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # DEBUG: pokazi sta se zapravo vraca
    articles = soup.select("article.classified")
    print(f"  article.classified: {len(articles)}")
    
    # Probaj alternativne selektore
    alt1 = soup.select("article[data-classifiedid]")
    alt2 = soup.select(".classified-list article")
    alt3 = soup.select(".oglas")
    alt4 = soup.select("[class*='classified']")
    print(f"  article[data-classifiedid]: {len(alt1)}")
    print(f"  .classified-list article: {len(alt2)}")
    print(f"  .oglas: {len(alt3)}")
    print(f"  [class*='classified']: {len(alt4)}")
    
    # Ako nista ne pronadje, ispisi pocetak HTML-a
    if not articles and not alt1 and not alt2 and not alt3:
        print(f"  HTML preview: {resp.text[2000:3000]}")
    
    listings = []
    
    # Probaj sve moguce selektore
    items = articles or alt1 or alt2 or alt3
    
    for item in items:
        try:
            title = (item.select_one("h3.classified__title") or 
                     item.select_one("h3") or 
                     item.select_one("[class*='title']"))
            price = (item.select_one(".price-box__price") or 
                     item.select_one("[class*='price']"))
            year = item.select_one(".details li:nth-child(1)")
            km = item.select_one(".details li:nth-child(2)")
            fuel = item.select_one(".details li:nth-child(3)")
            link = (item.select_one("a.classified__titleLink") or 
                    item.select_one("a[href*='/auto-oglasi/']"))
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
            print(f"  Error parsing item: {e}")

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
            print(f"  DB error: {e}")
    conn.commit()
    cur.close()
    conn.close()

def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Prvo poseti homepage da dobije kolacice
    session.get("https://www.polovniautomobili.com/", timeout=15)
    time.sleep(2)
    
    base_url = "https://www.polovniautomobili.com/auto-oglasi/pretraga?page={}&sort=basic&without_price=1"
    total = 0

    for page in range(1, 11):
        url = base_url.format(page)
        print(f"Scraping page {page}...")
        listings = scrape_page(url, session)
        save_listings(listings)
        total += len(listings)
        print(f"Saved {len(listings)} listings (total: {total})")
        time.sleep(random.uniform(3, 6))

    print(f"Done! Total: {total}")

if __name__ == "__main__":
    main()
