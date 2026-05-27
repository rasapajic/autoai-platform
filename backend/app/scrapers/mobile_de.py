import asyncio
import json
import re
import aiohttp

BASE_URL = "https://www.mobile.de/fahrzeuge/search.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}


def _extract_next_data(html: str) -> dict | None:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        # Pokušaj window.__INITIAL_STATE__ ili slično
        match2 = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>', html, re.DOTALL)
        if match2:
            try:
                return {"type": "initial_state", "data": json.loads(match2.group(1))}
            except Exception:
                pass
        return None
    try:
        return json.loads(match.group(1))
    except Exception as e:
        print(f"[MobileDe] JSON parse greška: {e}")
        return None


def _normalize_fuel(val):
    if not val:
        return None
    val = val.lower().strip()
    mapping = {
        "diesel": "diesel", "petrol": "petrol", "benzin": "petrol",
        "electric": "electric", "elektro": "electric",
        "hybrid": "hybrid", "lpg": "lpg",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val):
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automatic", "automat", "automatik", "dsg"]):
        return "automatic"
    if any(w in val for w in ["manual", "manuell", "schaltgetriebe"]):
        return "manual"
    return val


def _parse_price(val):
    if val is None:
        return None
    try:
        s = re.sub(r"[€EUR\s\.]", "", str(val)).replace(",", ".")
        s = re.sub(r"[^\d.]", "", s)
        price = float(s) if s else None
        if price and price < 500:
            return None
        return price
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


def _parse_listing_from_json(item: dict) -> dict | None:
    """Parser za različite JSON strukture mobile.de"""
    try:
        ad_id = str(item.get("id", "") or item.get("adId", ""))
        if not ad_id:
            return None

        # Pokušaj razne strukture
        make  = item.get("make") or item.get("brand") or ""
        model = item.get("model") or ""

        # Nested attributes
        attrs = item.get("attributes", {}) or {}
        if isinstance(attrs, dict):
            make  = make or attrs.get("make", "") or attrs.get("brand", "")
            model = model or attrs.get("model", "")

        vehicle = item.get("vehicle", {}) or {}
        if isinstance(vehicle, dict):
            make  = make or vehicle.get("make", "") or vehicle.get("brand", "")
            model = model or vehicle.get("model", "")

        if not make:
            return None

        price_raw = (item.get("price") or item.get("grossPrice") or
                     attrs.get("price") or vehicle.get("price"))
        year_raw  = (item.get("year") or item.get("firstRegistrationYear") or
                     attrs.get("year") or vehicle.get("year"))
        km_raw    = (item.get("mileage") or attrs.get("mileage") or vehicle.get("mileage"))
        fuel_raw  = (item.get("fuel") or item.get("fuelType") or
                     attrs.get("fuel") or vehicle.get("fuelType", ""))
        trans_raw = (item.get("transmission") or attrs.get("transmission") or
                     vehicle.get("transmission", ""))

        images = []
        for key in ["images", "imageUrls", "photos"]:
            imgs = item.get(key, [])
            if isinstance(imgs, list):
                for img in imgs[:6]:
                    url = img if isinstance(img, str) else img.get("url") or img.get("src", "")
                    if url:
                        images.append(url)
                break

        url = (item.get("url") or item.get("detailUrl") or
               f"https://www.mobile.de/fahrzeuge/details.html/{ad_id}")
        if not url.startswith("http"):
            url = f"https://www.mobile.de{url}"

        price = _parse_price(price_raw)
        if not price:
            return None

        return {
            "external_id":  f"mde_{ad_id}",
            "source":       "mobile.de",
            "make":         str(make).strip(),
            "model":        str(model).strip() or None,
            "year":         _parse_int(year_raw),
            "price":        price,
            "currency":     "EUR",
            "mileage":      _parse_int(km_raw),
            "fuel_type":    _normalize_fuel(str(fuel_raw)),
            "transmission": _normalize_transmission(str(trans_raw)),
            "country":      "DE",
            "images":       images,
            "url":          url,
        }
    except Exception as e:
        print(f"[MobileDe] Parse greška: {e}")
        return None


def _find_listings_in_data(data: dict) -> list:
    """Rekurzivno traži listu oglasa u JSON strukturi"""
    if not isinstance(data, dict):
        return []

    # Direktni ključevi
    for key in ["items", "listings", "results", "vehicles", "ads", "data", "searchResults"]:
        val = data.get(key)
        if isinstance(val, list) and len(val) > 0:
            print(f"[MobileDe] Pronađeno {len(val)} oglasa pod ključem '{key}'")
            return val
        if isinstance(val, dict):
            sub = _find_listings_in_data(val)
            if sub:
                return sub

    # Next.js pageProps
    props = data.get("props", {})
    if props:
        page_props = props.get("pageProps", {})
        if page_props:
            result = _find_listings_in_data(page_props)
            if result:
                return result

    return []


class MobileDeScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page in range(1, max_pages + 1):
                params = {
                    "isSearchRequest": "true",
                    "scopeId": "C",
                    "sortOption.sortBy": "creationTime",
                    "sortOption.sortOrder": "DESCENDING",
                    "damageUnrepaired": "false",
                }
                if page > 1:
                    params["pageNumber"] = page

                if filters.get("make"):
                    params["makeModelVariant1.makeId"] = filters["make"]
                if filters.get("max_price"):
                    params["price.maxValue"] = str(filters["max_price"])
                if filters.get("min_year"):
                    params["firstRegistrationYear.minValue"] = str(filters["min_year"])
                if filters.get("max_km"):
                    params["mileage.maxValue"] = str(filters["max_km"])

                print(f"[MobileDe] Stranica {page}...")

                try:
                    async with session.get(BASE_URL, params=params,
                                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[MobileDe] Status: {resp.status} | CT: {resp.content_type}")
                        if resp.status != 200:
                            print(f"[MobileDe] Nije 200 — prekidam")
                            break

                        html = await resp.text()
                        print(f"[MobileDe] HTML dužina: {len(html)} | Preview: {html[:200]}")

                        next_data = _extract_next_data(html)
                        if not next_data:
                            print(f"[MobileDe] Nema JSON strukture")
                            break

                        items = _find_listings_in_data(next_data)
                        if not items:
                            print(f"[MobileDe] Nema oglasa u JSON-u")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing_from_json(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[MobileDe] Str.{page}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < 10:
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[MobileDe] Greška str.{page}: {e}")
                    break

        print(f"[MobileDe] Završeno — {len(all_listings)} oglasa")
        return all_listings
