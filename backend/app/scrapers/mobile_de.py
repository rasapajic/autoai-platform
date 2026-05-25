import asyncio
import requests
import re
from typing import List, Dict, Any

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.mobile.de/",
    "Origin": "https://www.mobile.de",
}

API_URL = "https://services.mobile.de/search-service/search"

def fetch_page(page: int, params: Dict) -> List[Dict]:
    query = {
        "damageUnrepaired": "false",
        "isSearchRequest": "true",
        "pageNumber": str(page),
        "pageSize": "25",
        "scopeId": "C",
        "sortOption.sortBy": "creationTime",
        "sortOption.sortOrder": "DESCENDING",
    }

    if params.get("make"):
        query["makeModelVariant1.makeId"] = params["make"]
    if params.get("price_max"):
        query["price.maxValue"] = str(params["price_max"])
    if params.get("year_min"):
        query["firstRegistrationYear.minValue"] = str(params["year_min"])
    if params.get("mileage_max"):
        query["mileage.maxValue"] = str(params["mileage_max"])

    try:
        resp = requests.get(API_URL, params=query, headers=HEADERS, timeout=15)
        print(f"  Mobile.de page {page} status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"  Mobile.de greska: {resp.status_code}")
            return []

        data = resp.json()
        items = data.get("items", [])
        print(f"  Mobile.de pronadjeno: {len(items)}")
        return items

    except Exception as e:
        print(f"  Mobile.de fetch greska: {e}")
        return []


def parse_item(item: Dict) -> Dict:
    attrs = item.get("attributes", {})

    def get_val(key):
        v = attrs.get(key, {})
        if isinstance(v, dict):
            return v.get("value") or v.get("displayValue")
        return v

    price_raw = get_val("price")
    try:
        price = float(re.sub(r"[^\d.]", "", str(price_raw))) if price_raw else None
    except:
        price = None

    mileage_raw = get_val("mileage")
    try:
        mileage = int(re.sub(r"[^\d]", "", str(mileage_raw))) if mileage_raw else None
    except:
        mileage = None

    return {
        "source": "mobile.de",
        "external_id": str(item.get("id", "")),
        "url": f"https://www.mobile.de/fahrzeuge/details.html/{item.get('id', '')}",
        "title": item.get("description", {}).get("title", ""),
        "price": price,
        "currency": "EUR",
        "year": get_val("firstRegistrationYear"),
        "mileage": mileage,
        "fuel_type": get_val("fuel"),
        "transmission": get_val("transmission"),
        "make": get_val("make"),
        "model": get_val("model"),
        "location": item.get("seller", {}).get("region", ""),
        "images": [
            img.get("url", "")
            for img in item.get("images", {}).get("images", [])[:3]
        ],
    }


class MobileDeScraper:
    async def scrape_listings(
        self, params: Dict, max_pages: int = 10
    ) -> List[Dict[str, Any]]:
        all_listings = []

        for page in range(1, max_pages + 1):
            print(f"  Mobile.de scraping page {page}...")
            items = fetch_page(page, params)

            if not items:
                print(f"  Mobile.de nema vise rezultata na strani {page}")
                break

            for item in items:
                try:
                    listing = parse_item(item)
                    all_listings.append(listing)
                except Exception as e:
                    print(f"  Parse greska: {e}")
                    continue

            await asyncio.sleep(1.5)

        print(f"  Mobile.de ukupno: {len(all_listings)}")
        return all_listings
