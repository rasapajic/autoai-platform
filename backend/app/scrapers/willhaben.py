import asyncio
import json
import re
import aiohttp

BASE_URL = "https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenmarkt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Referer": "https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenmarkt",
    "x-wh-client": "api=v1.24.0",
}


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


def _normalize_body(val):
    if not val:
        return None
    val = val.lower().strip()
    mapping = {
        "limousine": "sedan", "sedan": "sedan",
        "suv": "suv", "geländewagen": "suv",
        "hatchback": "hatchback", "schrägheck": "hatchback",
        "kombi": "kombi", "estate": "kombi",
        "coupe": "coupe", "coupé": "coupe",
        "cabrio": "cabrio", "van": "van",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _get_attr(attributes, name):
    for attr in attributes:
        if attr.get("name") == name:
            vals = attr.get("values", [])
            return vals[0] if vals else None
    return None


def _parse_ad(ad):
    try:
        attrs = ad.get("attributes", {}).get("attribute", [])
        def g(name):
            return _get_attr(attrs, name)

        ad_id     = str(ad.get("id", ""))
        make      = g("MAKE")
        model     = g("MODEL")
        year_str  = g("YEAR")
        price_str = g("PRICE_FOR_DISPLAY") or g("PRICE")
        mileage_str = g("MILEAGE")
        fuel      = g("FUEL_TYPE") or ""
        transmission = g("TRANSMISSION_TYPE") or ""
        body      = g("CAR_TYPE") or ""
        power     = g("POWER_KW") or g("ENGINE_POWER")
        color     = g("COLOR") or ""
        city      = g("LOCATION") or g("DISTRICT") or ""
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
            "body_type":       _normalize_body(body),
            "engine_power_kw": _parse_int(power),
            "color":           color.strip() or None,
            "country":         "AT",
            "city":            city.strip() or None,
            "description":     description.strip() or None,
            "images":          images[:6],
            "url":             f"https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagen/{ad_id}",
        }
    except Exception as e:
        print(f"[Willhaben] Parse greška: {e}")
        return None


class WillhabenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        rows = 25

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(max_pages):
                offset = page_num * rows
                params = {
                    "sfId": "",
                    "rows": rows,
                    "isNavigation": "false",
                    "pagingOffset": offset,
                    "sort": 1,
                }

                if filters.get("make"):
                    params["MAKE"] = filters["make"].upper()
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

                print(f"[Willhaben] Stranica {page_num + 1}, offset={offset}")

                try:
                    async with session.get(BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[Willhaben] Status: {resp.status} | Content-Type: {resp.content_type}")

                        if resp.status != 200:
                            print(f"[Willhaben] Nije 200 — prekidam")
                            break

                        text = await resp.text()
                        print(f"[Willhaben] Preview: {text[:500]}")

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            print(f"[Willhaben] JSON greška: {je}")
                            break

                        adverts = data.get("advertSummaryList", {}).get("advertSummary", [])
                        print(f"[Willhaben] Oglasi u odgovoru: {len(adverts)}")

                        if not adverts:
                            print(f"[Willhaben] Nema oglasa — kraj")
                            break

                        for ad in adverts:
                            parsed = _parse_ad(ad)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        print(f"[Willhaben] +{len(adverts)} | Ukupno: {len(all_listings)}")
                        await asyncio.sleep(1.2)

                except Exception as e:
                    print(f"[Willhaben] Greška str {page_num + 1}: {e}")
                    break

        print(f"[Willhaben] Završeno — {len(all_listings)} oglasa")
        return all_listings
