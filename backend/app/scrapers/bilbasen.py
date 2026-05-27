import asyncio
import json
import re
import aiohttp

# Bilbasen API — danski najveći auto sajt
API_URL = "https://www.bilbasen.dk/api/car/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    "Referer": "https://www.bilbasen.dk/brugt/bil",
}


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = re.sub(r"[^0-9]", "", str(val))
        price = float(s) if s else None
        # DKK → EUR (1 EUR ≈ 7.46 DKK)
        if price and price > 10000:
            price = round(price / 7.46, 0)
        if price and price < 500:
            return None
        return price
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
    if any(w in val for w in ["automatisk", "automatic", "automat", "dsg", "cvt"]):
        return "automatic"
    if any(w in val for w in ["manuel", "manual", "manuell"]):
        return "manual"
    return val


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("Id") or item.get("id") or item.get("VehicleId") or "")
        if not item_id:
            return None

        make  = item.get("Make") or item.get("make") or item.get("Brand") or ""
        model = item.get("Model") or item.get("model") or ""

        if not make:
            return None

        # Cena u DKK → EUR
        price_raw = (item.get("Price") or item.get("price") or
                     item.get("RetailPriceDkk") or item.get("PriceDkk") or 0)
        price = _parse_price(price_raw)
        if not price:
            return None

        year     = item.get("Year") or item.get("year") or item.get("ModelYear")
        mileage  = item.get("Mileage") or item.get("mileage") or item.get("KilometersDriven")
        fuel     = item.get("FuelType") or item.get("fuelType") or item.get("Fuel") or ""
        trans    = item.get("Transmission") or item.get("transmission") or item.get("GearType") or ""
        body     = item.get("BodyType") or item.get("bodyType") or item.get("CarType") or ""
        power_kw = item.get("EngineSizeKw") or item.get("PowerKw") or item.get("engineKw")
        color    = item.get("Color") or item.get("color") or item.get("Colour") or ""
        city     = item.get("City") or item.get("city") or item.get("Zipcode") or ""

        # Slike
        images = []
        for key in ["Images", "images", "Photos", "photos", "ImageUrls"]:
            imgs = item.get(key, [])
            if isinstance(imgs, list):
                for img in imgs[:6]:
                    url = img if isinstance(img, str) else (img.get("Url") or img.get("url") or "")
                    if url and url.startswith("http"):
                        images.append(url)
                if images:
                    break

        # Jedna slika
        if not images:
            for key in ["ImageUrl", "imageUrl", "MainImage", "ThumbnailUrl"]:
                url = item.get(key, "")
                if url and url.startswith("http"):
                    images.append(url)
                    break

        # URL
        slug = item.get("Url") or item.get("url") or item.get("DetailUrl") or ""
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
        page_size = 25

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                params = {
                    "page": page_num,
                    "pagesize": page_size,
                    "sort": "latestfirst",
                    "includeLeasing": "false",
                }

                if filters.get("make"):
                    params["make"] = filters["make"]
                if filters.get("min_price"):
                    params["PriceFrom"] = int(float(filters["min_price"]) * 7.46)
                if filters.get("max_price"):
                    params["PriceTo"] = int(float(filters["max_price"]) * 7.46)
                if filters.get("min_year"):
                    params["YearFrom"] = filters["min_year"]
                if filters.get("max_year"):
                    params["YearTo"] = filters["max_year"]
                if filters.get("max_km"):
                    params["MileageTo"] = filters["max_km"]

                print(f"[Bilbasen] Stranica {page_num}...")

                try:
                    async with session.get(API_URL, params=params,
                                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[Bilbasen] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status != 200:
                            print(f"[Bilbasen] Nije 200 — prekidam")
                            break

                        text = await resp.text()
                        print(f"[Bilbasen] Preview: {text[:400]}")

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            print(f"[Bilbasen] JSON greška: {je}")
                            break

                        # Debug prvog poziva
                        if page_num == 1:
                            print(f"[Bilbasen] Ključevi: {list(data.keys())[:10] if isinstance(data, dict) else type(data)}")

                        # Pokušaj razne ključeve
                        items = []
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            for key in ["Items", "items", "Results", "results", "Cars", "cars", "Listings", "Data", "data"]:
                                val = data.get(key)
                                if isinstance(val, list) and val:
                                    items = val
                                    print(f"[Bilbasen] Pronađeno pod ključem '{key}': {len(items)}")
                                    break

                        if not items:
                            print(f"[Bilbasen] Nema oglasa — kraj")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Bilbasen] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < page_size:
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[Bilbasen] Greška str.{page_num}: {e}")
                    break

        print(f"[Bilbasen] Završeno — {len(all_listings)} oglasa")
        return all_listings
