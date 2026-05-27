import asyncio
import json
import re
import aiohttp

# LeBonCoin API
API_URL = "https://api.leboncoin.fr/finder/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Origin": "https://www.leboncoin.fr",
    "Referer": "https://www.leboncoin.fr/voitures/offres/",
    "api_key": "ba0c2dad52b3565fd92a15d2346de3e4",
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
        "electrique": "electric", "electric": "electric",
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


def _get_param(params: list, key: str) -> str | None:
    for p in params:
        if isinstance(p, dict):
            if p.get("key", "").lower() == key.lower():
                vals = p.get("value") or p.get("values", [])
                if isinstance(vals, list):
                    return vals[0] if vals else None
                return str(vals) if vals else None
    return None


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("list_id") or item.get("id") or "")
        if not item_id:
            return None

        subject = item.get("subject") or item.get("title") or ""
        price_raw = item.get("price", [0])
        if isinstance(price_raw, list):
            price_raw = price_raw[0] if price_raw else 0
        price = _parse_price(price_raw)
        if not price:
            return None

        # Lokacija
        location = item.get("location", {}) or {}
        city       = location.get("city") or location.get("city_label") or ""
        department = location.get("department_name") or ""

        # Atributi
        params = item.get("params", []) or item.get("attributes", []) or []
        make      = _get_param(params, "brand") or _get_param(params, "marque")
        model     = _get_param(params, "model") or _get_param(params, "modele")
        year_str  = _get_param(params, "regdate") or _get_param(params, "annee")
        km_str    = _get_param(params, "mileage") or _get_param(params, "kilometrage")
        fuel_str  = _get_param(params, "fuel") or _get_param(params, "energie")
        trans_str = _get_param(params, "gearbox") or _get_param(params, "boite")
        body_str  = _get_param(params, "vehicle_damage") or _get_param(params, "carrosserie")
        power_str = _get_param(params, "horse_power_din") or _get_param(params, "puissance")
        color_str = _get_param(params, "color") or _get_param(params, "couleur")

        if not make and subject:
            parts = subject.split()
            make  = parts[0] if parts else None
            model = model or (parts[1] if len(parts) > 1 else None)

        year = _parse_int(year_str)
        if year and year < 2000:
            return None

        # Slike
        images = []
        for img in (item.get("images", {}).get("urls", []) or
                    item.get("images", {}).get("urls_large", []) or []):
            if img and img.startswith("http"):
                images.append(img)

        if not images:
            thumb = item.get("images", {}).get("thumb_url")
            if thumb:
                images.append(thumb)

        # URL
        vip_url = item.get("url") or f"https://www.leboncoin.fr/voitures/{item_id}.htm"
        if not vip_url.startswith("http"):
            vip_url = f"https://www.leboncoin.fr{vip_url}"

        return {
            "external_id":     f"lbc_{item_id}",
            "source":          "leboncoin",
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
            "country":         "FR",
            "city":            (city or department).strip() or None,
            "description":     subject or None,
            "images":          images[:6],
            "url":             vip_url,
        }
    except Exception as e:
        print(f"[LeBonCoin] Parse greška: {e}")
        return None


class LeBonCoinScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        limit = 35
        first_run = True

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                payload = {
                    "limit": limit,
                    "limit_alu": 3,
                    "filters": {
                        "category": {"id": "2"},  # Voitures
                        "enums": {},
                        "ranges": {},
                        "location": {},
                        "keywords": {},
                    },
                    "offset": (page_num - 1) * limit,
                    "sort_by": "time",
                    "sort_order": "desc",
                }

                if filters.get("min_price") or filters.get("max_price"):
                    payload["filters"]["ranges"]["price"] = {}
                    if filters.get("min_price"):
                        payload["filters"]["ranges"]["price"]["min"] = int(filters["min_price"])
                    if filters.get("max_price"):
                        payload["filters"]["ranges"]["price"]["max"] = int(filters["max_price"])

                if filters.get("min_year") or filters.get("max_year"):
                    payload["filters"]["ranges"]["regdate"] = {}
                    if filters.get("min_year"):
                        payload["filters"]["ranges"]["regdate"]["min"] = int(filters["min_year"])
                    if filters.get("max_year"):
                        payload["filters"]["ranges"]["regdate"]["max"] = int(filters["max_year"])

                if filters.get("max_km"):
                    payload["filters"]["ranges"]["mileage"] = {"max": int(filters["max_km"])}

                print(f"[LeBonCoin] Stranica {page_num}...")

                try:
                    async with session.post(API_URL, json=payload,
                                            timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[LeBonCoin] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status != 200:
                            text = await resp.text()
                            print(f"[LeBonCoin] Preview: {text[:300]}")
                            break

                        text = await resp.text()
                        try:
                            data = json.loads(text)
                        except Exception as je:
                            print(f"[LeBonCoin] JSON greška: {je}")
                            break

                        if first_run:
                            first_run = False
                            print(f"[LeBonCoin] Ključevi: {list(data.keys())[:10]}")

                        items = data.get("ads") or data.get("items") or data.get("results") or []
                        print(f"[LeBonCoin] Pronađeno {len(items)} oglasa")

                        if not items:
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[LeBonCoin] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        total = data.get("total") or data.get("total_count") or 0
                        if len(items) < limit or (page_num * limit) >= total:
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[LeBonCoin] Greška str.{page_num}: {e}")
                    break

        print(f"[LeBonCoin] Završeno — {len(all_listings)} oglasa")
        return all_listings
