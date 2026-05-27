import asyncio
import json
import re
import aiohttp

BASE_URL = "https://www.bilbasen.dk/brugt/bil"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

# DKK → EUR konverzija
DKK_TO_EUR = 7.46


def _dkk_to_eur(val) -> float | None:
    if val is None:
        return None
    try:
        s = re.sub(r"[^\d]", "", str(val))
        dkk = float(s) if s else None
        if not dkk:
            return None
        eur = round(dkk / DKK_TO_EUR, 0)
        return eur if eur >= 500 else None
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
        "el": "electric", "electric": "electric", "elbil": "electric",
        "hybrid": "hybrid", "plug-in": "hybrid",
        "lpg": "lpg", "cng": "cng",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automatisk", "automatic", "automat", "dsg"]):
        return "automatic"
    if any(w in val for w in ["manuel", "manual"]):
        return "manual"
    return val


def _extract_next_data(html: str) -> dict | None:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception as e:
        print(f"[Bilbasen] JSON parse greška: {e}")
        return None


def _find_listings(data: dict) -> list:
    """Rekurzivno traži listu oglasa"""
    if not isinstance(data, dict):
        return []

    for key in ["listings", "cars", "vehicles", "results", "items", "data", "searchResults", "carListings"]:
        val = data.get(key)
        if isinstance(val, list) and len(val) > 0:
            print(f"[Bilbasen] Pronađeno {len(val)} pod ključem '{key}'")
            return val
        if isinstance(val, dict):
            sub = _find_listings(val)
            if sub:
                return sub

    # Next.js pageProps
    props = data.get("props", {})
    if props:
        page_props = props.get("pageProps", {})
        if page_props:
            print(f"[Bilbasen] pageProps ključevi: {list(page_props.keys())[:10]}")
            result = _find_listings(page_props)
            if result:
                return result

    return []


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(
            item.get("id") or item.get("Id") or item.get("vehicleId") or
            item.get("listingId") or item.get("carId") or ""
        )
        if not item_id:
            return None

        make  = (item.get("make") or item.get("Make") or item.get("brand") or
                 item.get("Brand") or item.get("manufacturer") or "")
        model = item.get("model") or item.get("Model") or item.get("variant") or ""

        if not make:
            return None

        # Cena — može biti u DKK ili EUR
        price_raw = (item.get("price") or item.get("Price") or
                     item.get("retailPrice") or item.get("listPrice") or
                     item.get("priceDkk") or 0)

        # Ako je objekat
        if isinstance(price_raw, dict):
            price_raw = (price_raw.get("value") or price_raw.get("amount") or
                         price_raw.get("price") or 0)

        price_num = float(re.sub(r"[^\d.]", "", str(price_raw))) if price_raw else 0

        # Heuristika: ako je > 50000, verovatno DKK
        if price_num > 50000:
            price = round(price_num / DKK_TO_EUR, 0)
        else:
            price = price_num

        if not price or price < 500:
            return None

        year     = item.get("year") or item.get("Year") or item.get("modelYear")
        mileage  = item.get("mileage") or item.get("Mileage") or item.get("kilometersDriven")
        fuel     = item.get("fuelType") or item.get("fuel") or item.get("FuelType") or ""
        trans    = item.get("transmission") or item.get("Transmission") or item.get("gearType") or ""
        body     = item.get("bodyType") or item.get("BodyType") or item.get("carType") or ""
        power_kw = item.get("engineKw") or item.get("powerKw") or item.get("EngineSizeKw")
        color    = item.get("color") or item.get("Color") or item.get("colour") or ""
        city     = item.get("city") or item.get("City") or item.get("location") or ""

        # Slike
        images = []
        for key in ["images", "Images", "photos", "imageUrls"]:
            imgs = item.get(key, [])
            if isinstance(imgs, list):
                for img in imgs[:6]:
                    url = img if isinstance(img, str) else (img.get("url") or img.get("Url") or "")
                    if url and url.startswith("http"):
                        images.append(url)
                if images:
                    break
        if not images:
            for key in ["imageUrl", "ImageUrl", "mainImage", "thumbnailUrl"]:
                url = item.get(key, "")
                if url and url.startswith("http"):
                    images.append(url)
                    break

        # URL
        slug = item.get("url") or item.get("Url") or item.get("detailUrl") or item.get("permalink") or ""
        if slug and not slug.startswith("http"):
            vip_url = f"https://www.bilbasen.dk{slug}"
        elif slug:
            vip_url = slug
        else:
            vip_url = f"https://www.bilbasen.dk/brugt/bil/{item_id}"

        year_int = _parse_int(year)
        if year_int and year_int < 2000:
            return None

        return {
            "external_id":     f"bb_{item_id}",
            "source":          "bilbasen",
            "make":            str(make).strip(),
            "model":           str(model).strip() or None,
            "year":            year_int,
            "price":           price,
            "currency":        "EUR",
            "mileage":         _parse_int(mileage),
            "fuel_type":       _normalize_fuel(str(fuel)),
            "transmission":    _normalize_transmission(str(trans)),
            "body_type":       str(body).strip() or None,
            "engine_power_kw": _parse_int(power_kw),
            "color":           str(color).strip() or None,
            "country":         "DK",
            "city":            str(city).strip() or None,
            "images":          images,
            "url":             vip_url,
        }
    except Exception as e:
        print(f"[Bilbasen] Parse greška: {e}")
        return None


class BilbasenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                params = {"page": page_num}

                if filters.get("make"):
                    params["make"] = filters["make"]
                if filters.get("min_year"):
                    params["yearFrom"] = filters["min_year"]
                if filters.get("max_year"):
                    params["yearTo"] = filters["max_year"]
                if filters.get("max_km"):
                    params["mileageTo"] = filters["max_km"]

                print(f"[Bilbasen] Stranica {page_num}...")

                try:
                    async with session.get(BASE_URL, params=params,
                                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[Bilbasen] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status != 200:
                            print(f"[Bilbasen] Nije 200 — prekidam")
                            break

                        html = await resp.text()
                        print(f"[Bilbasen] HTML dužina: {len(html)}")

                        next_data = _extract_next_data(html)
                        if not next_data:
                            print(f"[Bilbasen] Nema __NEXT_DATA__ — pokušavam regex")
                            # Pokušaj direktno iz HTML-a
                            break

                        items = _find_listings(next_data)
                        if not items:
                            print(f"[Bilbasen] Nema oglasa u JSON-u")
                            if page_num == 1:
                                # Log top-level ključeva za debug
                                print(f"[Bilbasen] Top ključevi: {list(next_data.keys())[:10]}")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Bilbasen] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < 10:
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[Bilbasen] Greška str.{page_num}: {e}")
                    break

        print(f"[Bilbasen] Završeno — {len(all_listings)} oglasa")
        return all_listings
