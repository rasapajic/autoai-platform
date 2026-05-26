import asyncio
import json
import re
import aiohttp

CATEGORIES = ["limousine"]

BASE_URL = "https://www.willhaben.at/iad/gebrauchtwagen/auto"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}


def _extract_next_data(html: str) -> dict | None:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception as e:
        print(f"[Willhaben] JSON parse greška: {e}")
        return None


def _extract_listings_from_next_data(data: dict) -> list:
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        candidates = [
            page_props.get("searchResult", {}).get("advertSummaryList", {}).get("advertSummary", []),
            page_props.get("advertSummaryList", {}).get("advertSummary", []),
            page_props.get("listings", []),
            page_props.get("results", []),
        ]
        for c in candidates:
            if c:
                print(f"[Willhaben] Pronađena lista sa {len(c)} oglasa")
                attrs = c[0].get("attributes", {}).get("attribute", [])
                attr_names = [a.get("name") for a in attrs]
                print(f"[Willhaben] Svi atributi: {attr_names}")
                print(f"[Willhaben] Opis: {c[0].get('description')}")
                return c
        print(f"[Willhaben] pageProps ključevi: {list(page_props.keys())[:15]}")
        return []
    except Exception as e:
        print(f"[Willhaben] Greška ekstrakcije: {e}")
        return []


def _parse_price(val):
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(val).replace(",", ".").replace(" ", ""))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def _parse_int(val):
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d]", "", str(val))
        return int(cleaned) if cleaned else None
    except Exception:
        return None


def _normalize_fuel(val):
    if not val:
        return None
    val = val.lower().strip()
    mapping = {
        "diesel": "diesel", "petrol": "petrol", "benzin": "petrol",
        "benzine": "petrol", "electric": "electric", "elektro": "electric",
        "hybrid": "hybrid", "phev": "hybrid", "lpg": "lpg",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val):
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automatic", "automat", "automatik", "dsg", "cvt"]):
        return "automatic"
    if any(w in val for w in ["manual", "manuell", "schaltgetriebe"]):
        return "manual"
    return val


def _get_attr(attributes, name):
    for attr in attributes:
        if attr.get("name") == name:
            vals = attr.get("values", [])
            return vals[0] if vals else None
    return None


def _parse_ad(ad: dict) -> dict | None:
    try:
        attrs = ad.get("attributes", {}).get("attribute", [])
        def g(name):
            return _get_attr(attrs, name)

        ad_id       = str(ad.get("id", ""))
        make        = g("MAKE")
        model       = g("MODEL")
        year_str    = g("YEAR")
        price_str   = g("PRICE_FOR_DISPLAY") or g("PRICE")
        mileage_str = g("MILEAGE")
        fuel        = g("FUEL_TYPE") or ""
        transmission = g("TRANSMISSION_TYPE") or ""
        body        = g("CAR_TYPE") or ""
        power       = g("POWER_KW") or g("ENGINE_POWER")
        color       = g("COLOR") or ""
        city        = g("LOCATION") or g("DISTRICT") or ""
        description = ad.get("description", "") or ""

        year = None
        if year_str:
            try:
                year = int(str(year_str)[:4])
            except Exception:
                pass

        images = []
        for img in (ad.get("advertImageList", {}).get("advertImage", []) or []):
            ref = img.get("reference")
            if ref:
                images.append(f"https://cache.willhaben.at/mmo/{ref}?rule=online-_x800")
        if not images:
            for img in (ad.get("images", []) or []):
                url = img.get("url") or img.get("src")
                if url:
                    images.append(url)

        if not ad_id or not make:
            return None

        return {
            "external_id":     f"wh_{ad_id}",
            "source":          "willhaben",
            "make":            make,
            "model":           model,
            "year":            year,
            "price":           _parse_price(price_str),
            "currency":        "EUR",
            "mileage":         _parse_int(mileage_str),
            "fuel_type":       _normalize_fuel(fuel),
            "transmission":    _normalize_transmission(transmission),
            "body_type":       body or None,
            "engine_power_kw": _parse_int(power),
            "color":           color.strip() or None,
            "country":         "AT",
            "city":            city.strip() or None,
            "description":     description.strip() or None,
            "images":          images[:6],
            "url":             f"https://www.willhaben.at/iad/gebrauchtwagen/d/auto/{ad_id}",
        }
    except Exception as e:
        print(f"[Willhaben] Parse greška: {e}")
        return None


class WillhabenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for category in CATEGORIES:
                url = f"{BASE_URL}/{category}"
                print(f"[Willhaben] Kategorija: {category}")

                for page in range(1, max_pages + 1):
                    params = {}
                    if page > 1:
                        params["page"] = page
                    if filters.get("min_price"):
                        params["PRICE_FROM"] = filters["min_price"]
                    if filters.get("max_price"):
                        params["PRICE_TO"] = filters["max_price"]
                    if filters.get("min_year"):
                        params["YEAR_FROM"] = filters["min_year"]
                    if filters.get("max_year"):
                        params["YEAR_TO"] = filters["max_year"]
                    if filters.get("max_km"):
                        params["MILEAGE_TO"] = filters["max_km"]

                    try:
                        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                            print(f"[Willhaben] {category} str.{page} → status {resp.status}")
                            if resp.status != 200:
                                break

                            html = await resp.text()
                            next_data = _extract_next_data(html)
                            if not next_data:
                                print(f"[Willhaben] Nema __NEXT_DATA__")
                                break

                            adverts = _extract_listings_from_next_data(next_data)
                            if not adverts:
                                break

                            before = len(all_listings)
                            for ad in adverts:
                                parsed = _parse_ad(ad)
                                if parsed and parsed["external_id"] not in seen_ids:
                                    seen_ids.add(parsed["external_id"])
                                    all_listings.append(parsed)

                            added = len(all_listings) - before
                            print(f"[Willhaben] {category} str.{page}: +{added} | Ukupno: {len(all_listings)}")

                            if len(adverts) < 10:
                                break

                            await asyncio.sleep(1.5)

                    except Exception as e:
                        print(f"[Willhaben] Greška {category} str.{page}: {e}")
                        break

        print(f"[Willhaben] Završeno — {len(all_listings)} oglasa")
        return all_listings
