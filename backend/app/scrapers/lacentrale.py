import asyncio
import json
import re
import aiohttp

# La Centrale — drugi najveći auto portal u Francuskoj
API_URL = "https://www.lacentrale.fr/api/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.lacentrale.fr/listing?",
    "Origin": "https://www.lacentrale.fr",
}


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
        "diesel": "diesel", "essence": "petrol", "petrol": "petrol",
        "electrique": "electric", "electric": "electric", "électrique": "electric",
        "hybride": "hybrid", "hybrid": "hybrid",
        "gpl": "lpg", "lpg": "lpg",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automatique", "automatic", "automat", "dsg"]):
        return "automatic"
    if any(w in val for w in ["manuelle", "manual"]):
        return "manual"
    return val


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(
            item.get("id") or item.get("adId") or item.get("listingId") or
            item.get("vehicleId") or item.get("uid") or ""
        )
        if not item_id:
            return None

        # Marka i model
        make  = item.get("make") or item.get("brand") or item.get("marque") or ""
        model = item.get("model") or item.get("modele") or ""

        # Ako je ugnjezdeno
        vehicle = item.get("vehicle") or item.get("vehicleDetails") or {}
        if isinstance(vehicle, dict) and not make:
            make  = vehicle.get("make") or vehicle.get("brand") or vehicle.get("marque") or ""
            model = vehicle.get("model") or vehicle.get("modele") or model

        # Cena
        price_raw = (item.get("price") or item.get("prix") or
                     item.get("sellingPrice") or item.get("priceCents"))
        if isinstance(price_raw, dict):
            price_raw = price_raw.get("value") or price_raw.get("amount") or 0
        if str(price_raw).endswith("00") and len(str(price_raw)) > 5:
            # cents format
            price = float(price_raw) / 100
        else:
            price = _parse_price(price_raw)

        if not price or price < 500:
            return None

        # Spec podaci
        year     = item.get("year") or item.get("yearOfManufacture") or item.get("annee")
        mileage  = item.get("mileage") or item.get("km") or item.get("kilometersDriven") or item.get("kilometrage")
        fuel     = item.get("fuelType") or item.get("fuel") or item.get("energie") or item.get("carburant") or ""
        trans    = item.get("transmission") or item.get("gearbox") or item.get("boite") or ""
        body     = item.get("bodyType") or item.get("carrosserie") or ""
        power    = item.get("powerCV") or item.get("powerKW") or item.get("puissance") or item.get("enginePower")
        color    = item.get("color") or item.get("couleur") or ""

        # Lokacija
        location = item.get("location") or item.get("seller", {}) or {}
        if isinstance(location, dict):
            city       = location.get("city") or location.get("ville") or location.get("cityName") or ""
            department = location.get("department") or location.get("departement") or ""
            city       = city or department
        else:
            city = str(location)

        # Slike
        images = []
        for key in ["photos", "images", "pictures", "imageUrls"]:
            imgs = item.get(key, [])
            if isinstance(imgs, list):
                for img in imgs[:6]:
                    if isinstance(img, dict):
                        url = img.get("url") or img.get("src") or img.get("large") or img.get("medium") or ""
                    else:
                        url = str(img)
                    if url and url.startswith("http"):
                        images.append(url)
                if images:
                    break

        # URL
        vip_url = item.get("url") or item.get("link") or item.get("adUrl") or ""
        if not vip_url:
            slug = item.get("slug") or item.get("permalink") or ""
            if slug:
                vip_url = f"https://www.lacentrale.fr/{slug}" if not slug.startswith("http") else slug
        if not vip_url:
            vip_url = f"https://www.lacentrale.fr/auto-occasion-annonce-{item_id}.html"

        year_int = _parse_int(year)
        if year_int and year_int < 2000:
            return None

        # Snaga — konvertuj CV u kW ako treba
        power_kw = None
        if power:
            p = _parse_int(power)
            if p:
                # Heuristika: ako > 300, verovatno CV
                power_kw = round(p * 0.7355) if p > 300 else p

        if not make:
            return None

        return {
            "external_id":     f"lc_{item_id}",
            "source":          "lacentrale",
            "make":            str(make).strip(),
            "model":           str(model).strip() or None,
            "year":            year_int,
            "price":           price,
            "currency":        "EUR",
            "mileage":         _parse_int(mileage),
            "fuel_type":       _normalize_fuel(str(fuel)),
            "transmission":    _normalize_transmission(str(trans)),
            "body_type":       str(body).strip() or None,
            "engine_power_kw": power_kw,
            "color":           str(color).strip() or None,
            "country":         "FR",
            "city":            str(city).strip() or None,
            "images":          images,
            "url":             vip_url,
        }
    except Exception as e:
        print(f"[LaCentrale] Parse greška: {e}")
        return None


class LaCentraleScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        first_run = True

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                # Pokušaj razne API formate
                params = {
                    "page":     page_num,
                    "pageSize": 30,
                    "sort":     "createdAt:desc",
                }

                if filters.get("make"):
                    params["make"] = filters["make"]
                if filters.get("min_price"):
                    params["priceFrom"] = filters["min_price"]
                if filters.get("max_price"):
                    params["priceTo"] = filters["max_price"]
                if filters.get("min_year"):
                    params["yearFrom"] = filters["min_year"]
                if filters.get("max_year"):
                    params["yearTo"] = filters["max_year"]
                if filters.get("max_km"):
                    params["mileageTo"] = filters["max_km"]

                print(f"[LaCentrale] Stranica {page_num}...")

                try:
                    async with session.get(API_URL, params=params,
                                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[LaCentrale] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status == 403:
                            print(f"[LaCentrale] 403 — Cloudflare blokira")
                            break

                        if resp.status != 200:
                            text = await resp.text()
                            print(f"[LaCentrale] Preview: {text[:300]}")
                            break

                        text = await resp.text()

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            print(f"[LaCentrale] JSON greška: {je}")
                            print(f"[LaCentrale] Preview: {text[:400]}")
                            break

                        if first_run:
                            first_run = False
                            print(f"[LaCentrale] Ključevi: {list(data.keys())[:10] if isinstance(data, dict) else type(data)}")
                            if isinstance(data, dict):
                                print(f"[LaCentrale] FULL preview: {text[:600]}")

                        # Pokušaj razne ključeve
                        items = []
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            for key in ["ads", "listings", "results", "items", "data",
                                        "vehicles", "annonces", "searchResults", "content"]:
                                val = data.get(key)
                                if isinstance(val, list) and val:
                                    items = val
                                    print(f"[LaCentrale] Pronađeno {len(items)} pod '{key}'")
                                    break

                        if not items:
                            print(f"[LaCentrale] Nema oglasa")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[LaCentrale] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        # Paginacija
                        total = (data.get("total") or data.get("totalCount") or
                                 data.get("totalResults") or 0 if isinstance(data, dict) else 0)
                        if len(items) < 20 or (total and page_num * 30 >= total):
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[LaCentrale] Greška str.{page_num}: {e}")
                    break

        print(f"[LaCentrale] Završeno — {len(all_listings)} oglasa")
        return all_listings
