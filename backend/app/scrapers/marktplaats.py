import asyncio
import json
import re
import aiohttp

# Marktplaats API — kategorija 91 = Auto's
API_URL = "https://www.marktplaats.nl/lrp/api/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Referer": "https://www.marktplaats.nl/c/auto-s/c91.html",
}


def _parse_price(val) -> float | None:
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
        "diesel": "diesel", "benzine": "petrol", "petrol": "petrol",
        "electric": "electric", "elektrisch": "electric", "elektr": "electric",
        "hybrid": "hybrid", "lpg": "lpg", "cng": "cng",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automaat", "automatic", "automat", "dsg", "cvt"]):
        return "automatic"
    if any(w in val for w in ["handgeschakeld", "manual", "manueel", "schakel"]):
        return "manual"
    return val


def _get_attribute(attributes: list, name: str) -> str | None:
    """Traži vrednost atributa po imenu u Marktplaats format"""
    for attr in attributes:
        key = attr.get("key", "").lower()
        if name.lower() in key:
            val = attr.get("value") or attr.get("values", [None])[0] if attr.get("values") else None
            if val:
                return str(val)
    return None


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("itemId", "") or item.get("id", ""))
        if not item_id:
            return None

        title = item.get("title", "") or ""

        # Cena
        price_obj = item.get("price", {}) or {}
        price_raw = (price_obj.get("priceInfo", {}) or {}).get("priceCents")
        if price_raw:
            price = price_raw / 100  # cents → EUR
        else:
            price_str = price_obj.get("priceInfo", {}).get("priceText") or str(price_obj)
            price = _parse_price(price_str)

        if not price or price < 500:
            return None

        # Lokacija
        location = item.get("location", {}) or {}
        city = location.get("cityName") or location.get("city") or ""
        country = "NL"

        # Atributi (make, model, year, km, fuel, transmission)
        attributes = item.get("attributes", []) or []
        extended   = item.get("extendedAttributes", []) or []
        all_attrs  = attributes + extended

        make         = _get_attribute(all_attrs, "merk") or _get_attribute(all_attrs, "make") or _get_attribute(all_attrs, "brand")
        model        = _get_attribute(all_attrs, "model")
        year_str     = _get_attribute(all_attrs, "bouwjaar") or _get_attribute(all_attrs, "year") or _get_attribute(all_attrs, "constructiejaar")
        km_str       = _get_attribute(all_attrs, "kilometerstand") or _get_attribute(all_attrs, "mileage") or _get_attribute(all_attrs, "km")
        fuel_str     = _get_attribute(all_attrs, "brandstof") or _get_attribute(all_attrs, "fuel")
        trans_str    = _get_attribute(all_attrs, "transmissie") or _get_attribute(all_attrs, "versnellingsbak") or _get_attribute(all_attrs, "transmission")
        body_str     = _get_attribute(all_attrs, "carrosserie") or _get_attribute(all_attrs, "body")
        power_str    = _get_attribute(all_attrs, "vermogen") or _get_attribute(all_attrs, "power")
        color_str    = _get_attribute(all_attrs, "kleur") or _get_attribute(all_attrs, "color")

        # Ako nema make iz atributa, pokušaj iz naslova
        if not make and title:
            # Naslovi su obično "Merk Model Godiste ..."
            parts = title.split()
            if parts:
                make = parts[0]
                model = parts[1] if len(parts) > 1 else None

        year = _parse_int(year_str)
        if year and year < 2000:
            return None

        # Slike
        images = []
        for img in (item.get("pictures", []) or item.get("images", []) or []):
            if isinstance(img, dict):
                url = (img.get("mediumUrl") or img.get("largeUrl") or
                       img.get("url") or img.get("src") or "")
                # Marktplaats image format
                if not url and img.get("id"):
                    url = f"https://images.marktplaats.com/api/v1/listing-mp-p/{img['id']}/image.jpg?rule=ecg_mp_eps$_79.jpg"
            else:
                url = str(img)
            if url:
                images.append(url)

        # URL oglasa
        vip_url = item.get("vipUrl") or item.get("url") or ""
        if vip_url and not vip_url.startswith("http"):
            vip_url = f"https://www.marktplaats.nl{vip_url}"
        if not vip_url:
            vip_url = f"https://www.marktplaats.nl/a/{item_id}.html"

        return {
            "external_id":     f"mp_{item_id}",
            "source":          "marktplaats",
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
            "country":         country,
            "city":            city.strip() if city else None,
            "description":     title,
            "images":          images[:6],
            "url":             vip_url,
        }
    except Exception as e:
        print(f"[Marktplaats] Parse greška: {e}")
        return None


class MarktplaatsScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        limit = 30

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(max_pages):
                offset = page_num * limit
                params = {
                    "l1CategoryId": 91,
                    "l2CategoryId": 91,
                    "searchInTitleAndDescription": "true",
                    "viewOptions": "list-view",
                    "sortBy": "SORT_INDEX",
                    "sortOrder": "DECREASING",
                    "limit": limit,
                    "offset": offset,
                }

                if filters.get("min_price"):
                    params["priceFrom"] = filters["min_price"]
                if filters.get("max_price"):
                    params["priceTo"] = filters["max_price"]

                print(f"[Marktplaats] Stranica {page_num + 1}, offset={offset}")

                try:
                    async with session.get(API_URL, params=params,
                                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[Marktplaats] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status != 200:
                            print(f"[Marktplaats] Nije 200 — prekidam")
                            break

                        text = await resp.text()
                        print(f"[Marktplaats] Preview: {text[:400]}")

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            print(f"[Marktplaats] JSON greška: {je}")
                            break

                        # Pokušaj razne ključeve za listu oglasa
                        listings = (data.get("listings") or
                                   data.get("searchListings") or
                                   data.get("items") or
                                   data.get("results") or [])

                        if not listings:
                            print(f"[Marktplaats] Ključevi odgovora: {list(data.keys())[:10]}")
                            break

                        print(f"[Marktplaats] Pronađeno {len(listings)} oglasa")

                        before = len(all_listings)
                        for item in listings:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Marktplaats] Str.{page_num+1}: +{added} | Ukupno: {len(all_listings)}")

                        if len(listings) < limit:
                            print(f"[Marktplaats] Poslednja stranica")
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[Marktplaats] Greška str.{page_num+1}: {e}")
                    break

        print(f"[Marktplaats] Završeno — {len(all_listings)} oglasa")
        return all_listings
