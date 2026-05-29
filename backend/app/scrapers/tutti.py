import asyncio
import re
import aiohttp

# Tutti.ch — švajcarski oglasnik
# API baziran na Tutti/Scout24 platformi
SEARCH_URL = "https://www.tutti.ch/api/v10/ads"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
    "Origin": "https://www.tutti.ch",
    "Referer": "https://www.tutti.ch/de/q/fahrzeuge/occasionen/autos",
    "X-Tutti-Client": "web",
}


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = re.sub(r"[^\d.]", "", str(val))
        p = float(s) if s else None
        return p if p and p >= 500 else None
    except Exception:
        return None


def _normalize_fuel(val) -> str | None:
    if not val:
        return None
    val = val.lower()
    if "elektr" in val or "electric" in val: return "electric"
    if "hybrid" in val:                       return "hybrid"
    if "diesel" in val:                       return "diesel"
    if "benzin" in val or "petrol" in val or "essence" in val: return "petrol"
    if "gas" in val or "lpg" in val:          return "lpg"
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower()
    if any(w in val for w in ["automat", "dsg", "cvt"]): return "automatic"
    if any(w in val for w in ["manual", "schalt"]):       return "manual"
    return val


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("id") or item.get("adId") or "")
        if not item_id:
            return None

        # Osnovi podaci
        subject  = item.get("subject") or item.get("title") or ""
        body     = item.get("body") or item.get("description") or ""

        # Attributes mapa
        attrs = {}
        for a in (item.get("attributes") or []):
            if isinstance(a, dict):
                key = (a.get("key") or a.get("name") or "").lower()
                val = a.get("value") or a.get("label") or ""
                if key:
                    attrs[key] = val

        # Marka i model iz atributa ili naslova
        make  = attrs.get("make") or attrs.get("brand") or attrs.get("marke") or ""
        model = attrs.get("model") or attrs.get("modell") or ""

        # Ako nema u atributima — izvuci iz naslova
        if not make and subject:
            parts = subject.split()
            if len(parts) >= 2:
                make  = parts[0]
                model = " ".join(parts[1:3])

        # Cena
        price_obj = item.get("price") or {}
        if isinstance(price_obj, dict):
            price_raw = price_obj.get("amount") or price_obj.get("value") or price_obj.get("raw") or 0
        else:
            price_raw = price_obj
        price = _parse_price(price_raw)
        if not price:
            return None

        # Godište
        year_raw = attrs.get("year") or attrs.get("firstregistration") or attrs.get("jahrgang") or ""
        year_int = None
        if year_raw:
            m = re.search(r"(20\d{2}|19\d{2})", str(year_raw))
            if m:
                year_int = int(m.group(1))

        # Kilometraža
        km_raw = attrs.get("mileage") or attrs.get("km") or attrs.get("kilometerstand") or ""
        mileage = None
        if km_raw:
            km_clean = re.sub(r"[^\d]", "", str(km_raw))
            mileage = int(km_clean) if km_clean else None

        # Gorivo i menjač
        fuel  = attrs.get("fuel") or attrs.get("fueltype") or attrs.get("treibstoff") or ""
        trans = attrs.get("transmission") or attrs.get("gearbox") or attrs.get("getriebe") or ""

        # Snaga
        power_raw = attrs.get("power") or attrs.get("ps") or attrs.get("leistung") or ""
        power_kw  = None
        if power_raw:
            p = re.sub(r"[^\d]", "", str(power_raw))
            if p:
                ps = int(p)
                power_kw = round(ps * 0.7355) if ps > 200 else ps

        # Lokacija
        location = item.get("location") or {}
        if isinstance(location, dict):
            city   = location.get("locality") or location.get("city") or location.get("zipCode") or ""
            canton = location.get("region") or location.get("canton") or ""
            city   = f"{city}, {canton}".strip(", ") if canton else city
        else:
            city = str(location)

        # Slike
        images = []
        for key in ["images", "photos", "media", "pictures"]:
            imgs = item.get(key) or []
            if isinstance(imgs, list):
                for img in imgs[:8]:
                    if isinstance(img, dict):
                        url = (img.get("originalUrl") or img.get("url") or
                               img.get("src") or img.get("normalUrl") or "")
                    else:
                        url = str(img)
                    if url and url.startswith("http"):
                        images.append(url)
                if images:
                    break

        # URL
        vip_url = item.get("url") or item.get("link") or ""
        if not vip_url:
            slug = item.get("slug") or item.get("permalink") or ""
            if slug:
                vip_url = f"https://www.tutti.ch/{slug}" if not slug.startswith("http") else slug
        if not vip_url:
            vip_url = f"https://www.tutti.ch/de/vi/{item_id}"

        if year_int and (year_int < 2000 or year_int > 2026):
            return None
        if not make:
            return None

        return {
            "external_id":     f"tutti_{item_id}",
            "source":          "tutti",
            "make":            str(make).strip(),
            "model":           str(model).strip() or None,
            "year":            year_int,
            "price":           price,
            "currency":        "CHF",
            "mileage":         mileage,
            "fuel_type":       _normalize_fuel(str(fuel)),
            "transmission":    _normalize_transmission(str(trans)),
            "engine_power_kw": power_kw,
            "country":         "CH",
            "city":            str(city).strip() or None,
            "images":          images,
            "url":             vip_url,
            "description":     str(body)[:500] if body else None,
        }
    except Exception as e:
        print(f"[Tutti] Parse greška: {e}")
        return None


class TuttiScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                params = {
                    "category_id": 10,   # Vozila
                    "sub_category_id": 11,  # Automobili
                    "page":     page_num,
                    "page_size": 40,
                    "sort":     "date_desc",
                }

                if filters.get("make"):
                    params["query"] = filters["make"]

                print(f"[Tutti] Stranica {page_num}...")

                try:
                    async with session.get(
                        SEARCH_URL, params=params,
                        timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        print(f"[Tutti] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status == 403:
                            print("[Tutti] 403 — blokiran")
                            raise Exception(f"403 BODY={(await resp.text())[:400]}")

                        if resp.status != 200:
                            text = await resp.text()
                            raise Exception(f"STATUS={resp.status} BODY={text[:400]}")

                        data = await resp.json(content_type=None)

                        # Debug prve stranice
                        if page_num == 1:
                            print(f"[Tutti] Ključevi: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                            print(f"[Tutti] Preview: {str(data)[:500]}")

                        # Pokušaj razne ključeve
                        items = []
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            for key in ["ads", "items", "results", "data", "listings", "hits", "content"]:
                                val = data.get(key)
                                if isinstance(val, list) and val:
                                    items = val
                                    print(f"[Tutti] Pronađeno {len(items)} pod '{key}'")
                                    break

                        if not items:
                            print(f"[Tutti] Nema oglasa na stranici {page_num}")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Tutti] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        total = data.get("total") or data.get("totalCount") or 0 if isinstance(data, dict) else 0
                        if len(items) < 20 or (total and page_num * 40 >= int(total)):
                            break

                        await asyncio.sleep(1.2)

                except Exception as e:
                    print(f"[Tutti] Greška: {e}")
                    break

        print(f"[Tutti] Završeno — {len(all_listings)} oglasa")
        return all_listings
