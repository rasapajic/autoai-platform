import asyncio
import json
import re
import aiohttp

# Kleinanzeigen.de (bivši eBay Kleinanzeigen) — Next.js sajt
BASE_URL = "https://www.kleinanzeigen.de/s-autos/c216"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

KNOWN_MAKES = [
    "Volkswagen", "VW", "BMW", "Mercedes", "Audi", "Toyota", "Ford", "Opel",
    "Skoda", "Renault", "Peugeot", "Hyundai", "Kia", "Volvo", "Seat", "Mazda",
    "Honda", "Nissan", "Fiat", "Citroën", "Porsche", "Land Rover", "Jeep",
    "Dacia", "Suzuki", "Mitsubishi", "Subaru", "Alfa Romeo", "Lexus",
]


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = re.sub(r"[€EUR\s\.]", "", str(val)).replace(",", ".")
        s = re.sub(r"[^\d.]", "", s)
        price = float(s) if s else None
        return price if price and price >= 500 else None
    except Exception:
        return None


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d]", "", str(val))
        return int(cleaned) if cleaned else None
    except Exception:
        return None


def _normalize_fuel(val) -> str | None:
    if not val:
        return None
    val = val.lower().strip()
    mapping = {
        "diesel": "diesel", "benzin": "petrol", "petrol": "petrol",
        "elektro": "electric", "electric": "electric",
        "hybrid": "hybrid", "lpg": "lpg", "cng": "cng", "erdgas": "cng",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automatik", "automatic", "automat", "dsg"]):
        return "automatic"
    if any(w in val for w in ["schaltgetriebe", "manuel", "manual"]):
        return "manual"
    return val


def _extract_next_data(html: str) -> dict | None:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception as e:
        print(f"[Kleinanzeigen] JSON parse greška: {e}")
        return None


def _find_listings(data: dict) -> list:
    if not isinstance(data, dict):
        return []

    for key in ["listings", "ads", "items", "results", "classifieds", "articles"]:
        val = data.get(key)
        if isinstance(val, list) and len(val) > 0:
            print(f"[Kleinanzeigen] Pronađeno {len(val)} pod ključem '{key}'")
            return val
        if isinstance(val, dict):
            sub = _find_listings(val)
            if sub:
                return sub

    props = data.get("props", {})
    if props:
        page_props = props.get("pageProps", {})
        if page_props:
            print(f"[Kleinanzeigen] pageProps ključevi: {list(page_props.keys())[:10]}")
            result = _find_listings(page_props)
            if result:
                return result

    return []


def _parse_make_from_title(title: str) -> tuple:
    if not title:
        return None, None
    for make in sorted(KNOWN_MAKES, key=len, reverse=True):
        if make.lower() in title.lower():
            rest  = re.sub(re.escape(make), "", title, flags=re.IGNORECASE).strip()
            words = rest.split()
            return make, (" ".join(words[:2]) if words else None)
    words = title.split()
    return (words[0] if words else None), (" ".join(words[1:3]) if len(words) > 1 else None)


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(
            item.get("id") or item.get("adId") or item.get("articleId") or
            item.get("listingId") or ""
        )
        if not item_id:
            return None

        title = item.get("title") or item.get("subject") or item.get("name") or ""
        desc  = item.get("description") or item.get("body") or ""

        # Cena
        price_obj = item.get("price") or item.get("priceInfo") or {}
        if isinstance(price_obj, dict):
            price_raw = (price_obj.get("amount") or price_obj.get("value") or
                         price_obj.get("priceValue") or 0)
        else:
            price_raw = price_obj
        price = _parse_price(price_raw)
        if not price:
            return None

        # Lokacija
        location = item.get("location") or item.get("geoData") or {}
        if isinstance(location, dict):
            city = (location.get("cityName") or location.get("city") or
                    location.get("locality") or "")
        else:
            city = str(location)

        # Atributi — Kleinanzeigen koristi različite formate
        attrs    = item.get("attributes") or item.get("details") or item.get("features") or []
        attr_map = {}
        if isinstance(attrs, list):
            for a in attrs:
                if isinstance(a, dict):
                    k = (a.get("key") or a.get("name") or "").lower()
                    v = a.get("value") or (a.get("values", [None])[0] if a.get("values") else None)
                    if k and v:
                        attr_map[k] = str(v)
        elif isinstance(attrs, dict):
            attr_map = {k.lower(): str(v) for k, v in attrs.items()}

        make  = attr_map.get("marke") or attr_map.get("make") or attr_map.get("brand") or attr_map.get("hersteller")
        model = attr_map.get("modell") or attr_map.get("model")
        year_str  = attr_map.get("baujahr") or attr_map.get("year") or attr_map.get("erstzulassung")
        km_str    = attr_map.get("kilometerstand") or attr_map.get("mileage") or attr_map.get("km")
        fuel_str  = attr_map.get("kraftstoffart") or attr_map.get("fuel") or attr_map.get("treibstoff")
        trans_str = attr_map.get("getriebe") or attr_map.get("transmission")
        body_str  = attr_map.get("fahrzeugart") or attr_map.get("body") or attr_map.get("karosserie")
        power_str = attr_map.get("leistung") or attr_map.get("power") or attr_map.get("ps")
        color_str = attr_map.get("farbe") or attr_map.get("color") or attr_map.get("colour")

        # Fallback na naslov
        if not make:
            make, model_from_title = _parse_make_from_title(title)
            if not model:
                model = model_from_title

        year = _parse_int(year_str)
        if year and year < 2000:
            return None

        # Slike
        images = []
        for key in ["images", "pictures", "photos", "imageUrls"]:
            imgs = item.get(key, [])
            if isinstance(imgs, list):
                for img in imgs[:6]:
                    if isinstance(img, dict):
                        url = (img.get("src") or img.get("url") or
                               img.get("large") or img.get("medium") or "")
                    else:
                        url = str(img)
                    if url and url.startswith("http"):
                        images.append(url)
                if images:
                    break

        # URL
        vip_url = item.get("url") or item.get("link") or item.get("adUrl") or ""
        if vip_url and not vip_url.startswith("http"):
            vip_url = f"https://www.kleinanzeigen.de{vip_url}"
        if not vip_url:
            vip_url = f"https://www.kleinanzeigen.de/s-anzeige/{item_id}"

        return {
            "external_id":     f"ka_{item_id}",
            "source":          "kleinanzeigen",
            "make":            make.strip() if make else None,
            "model":           model.strip() if model else None,
            "year":            year,
            "price":           price,
            "currency":        "EUR",
            "mileage":         _parse_int(km_str),
            "fuel_type":       _normalize_fuel(fuel_str),
            "transmission":    _normalize_transmission(trans_str),
            "body_type":       body_str or None,
            "engine_power_kw": _parse_int(power_str),
            "color":           color_str or None,
            "country":         "DE",
            "city":            city.strip() if city else None,
            "description":     (title or desc or None),
            "images":          images,
            "url":             vip_url,
        }
    except Exception as e:
        print(f"[Kleinanzeigen] Parse greška: {e}")
        return None


class KleinanzeigenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        first_run = True

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                url = f"{BASE_URL}/seite:{page_num}" if page_num > 1 else BASE_URL

                print(f"[Kleinanzeigen] Stranica {page_num}: {url}")

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[Kleinanzeigen] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status != 200:
                            print(f"[Kleinanzeigen] Nije 200 — prekidam")
                            break

                        html = await resp.text()
                        print(f"[Kleinanzeigen] HTML dužina: {len(html)}")

                        next_data = _extract_next_data(html)
                        if not next_data:
                            print(f"[Kleinanzeigen] Nema __NEXT_DATA__ — pokušavam HTML parsing")
                            # Pokušaj direktno iz HTML-a
                            items_json = re.findall(r'"adId"\s*:\s*"(\d+)"', html)
                            print(f"[Kleinanzeigen] adId u HTML-u: {len(items_json)}")
                            break

                        if first_run:
                            first_run = False
                            print(f"[Kleinanzeigen] Top ključevi: {list(next_data.keys())[:10]}")

                        items = _find_listings(next_data)
                        if not items:
                            print(f"[Kleinanzeigen] Nema oglasa u JSON-u")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Kleinanzeigen] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < 10:
                            break

                        await asyncio.sleep(2.0)

                except Exception as e:
                    print(f"[Kleinanzeigen] Greška str.{page_num}: {e}")
                    break

        print(f"[Kleinanzeigen] Završeno — {len(all_listings)} oglasa")
        return all_listings
