import asyncio
import json
import re
import aiohttp

# Subito.it — isti API format kao Marktplaats i 2dehands
API_URL = "https://www.subito.it/hades/v1/search/items"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Referer": "https://www.subito.it/annunci-italia/vendita/auto/",
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
        "diesel": "diesel", "benzina": "petrol", "petrol": "petrol",
        "elettric": "electric", "electric": "electric",
        "hybrid": "hybrid", "ibrido": "hybrid",
        "gpl": "lpg", "lpg": "lpg", "metano": "cng",
    }
    for key, norm in mapping.items():
        if key in val:
            return norm
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower().strip()
    if any(w in val for w in ["automatico", "automatic", "automat", "dsg", "cvt"]):
        return "automatic"
    if any(w in val for w in ["manuale", "manual"]):
        return "manual"
    return val


def _get_feature(features: list, name: str) -> str | None:
    for f in features:
        if isinstance(f, dict):
            key = (f.get("label") or f.get("name") or f.get("key") or "").lower()
            if name.lower() in key:
                val = f.get("value") or f.get("values", [None])[0] if f.get("values") else None
                if val:
                    return str(val)
    return None


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("urn") or item.get("id") or item.get("pk") or "")
        # Ukloni prefix iz URN-a
        item_id = item_id.replace("item:", "").replace("urn:subito:classified:", "")
        if not item_id:
            return None

        subject = item.get("subject") or item.get("title") or ""
        body    = item.get("body") or item.get("description") or ""

        # Cena
        prices = item.get("prices", []) or []
        price = None
        for p in prices:
            if isinstance(p, dict):
                val = p.get("value")
                if val:
                    price = _parse_price(str(val))
                    if price:
                        break
        if not price:
            price = _parse_price(item.get("price"))
        if not price:
            return None

        # Lokacija
        geo = item.get("geo", {}) or {}
        city    = geo.get("city", {}).get("value") or geo.get("town", {}).get("value") or ""
        region  = geo.get("region", {}).get("value") or ""

        # Features (make, model, year, km, fuel, transmission)
        features = item.get("features", []) or []
        # Subito koristi nested features
        all_features = []
        for f in features:
            if isinstance(f, dict):
                vals = f.get("values", [])
                if isinstance(vals, list):
                    all_features.extend(vals)
                else:
                    all_features.append(f)

        make      = _get_feature(all_features, "marca") or _get_feature(all_features, "make") or _get_feature(all_features, "brand")
        model     = _get_feature(all_features, "modello") or _get_feature(all_features, "model")
        year_str  = _get_feature(all_features, "anno") or _get_feature(all_features, "year")
        km_str    = _get_feature(all_features, "chilometri") or _get_feature(all_features, "km") or _get_feature(all_features, "mileage")
        fuel_str  = _get_feature(all_features, "alimentazione") or _get_feature(all_features, "carburante") or _get_feature(all_features, "fuel")
        trans_str = _get_feature(all_features, "cambio") or _get_feature(all_features, "transmission")
        body_str  = _get_feature(all_features, "carrozzeria") or _get_feature(all_features, "body")
        power_str = _get_feature(all_features, "potenza") or _get_feature(all_features, "power")
        color_str = _get_feature(all_features, "colore") or _get_feature(all_features, "color")

        # Izvuci make iz naslova ako nema
        if not make and subject:
            parts = subject.split()
            make  = parts[0] if parts else None
            model = model or (parts[1] if len(parts) > 1 else None)

        year = _parse_int(year_str)
        if year and year < 2000:
            return None

        # Slike
        images = []
        for img in (item.get("images", []) or item.get("photos", []) or []):
            if isinstance(img, dict):
                url = (img.get("scale", [{}])[0].get("uri") or
                       img.get("uri") or img.get("url") or img.get("src") or "")
                # Subito image format
                if not url:
                    scales = img.get("scale", [])
                    for s in scales:
                        u = s.get("uri") or s.get("url")
                        if u:
                            url = u
                            break
            else:
                url = str(img)
            if url and (url.startswith("http") or url.startswith("//")):
                if url.startswith("//"):
                    url = "https:" + url
                images.append(url)

        # URL
        urls = item.get("urls", {}) or {}
        vip_url = (urls.get("default") or urls.get("vip") or
                   item.get("url") or item.get("vipUrl") or "")
        if vip_url and not vip_url.startswith("http"):
            vip_url = f"https://www.subito.it{vip_url}"
        if not vip_url:
            vip_url = f"https://www.subito.it/annunci-italia/vendita/auto/{item_id}.htm"

        return {
            "external_id":     f"sub_{item_id}",
            "source":          "subito",
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
            "country":         "IT",
            "city":            (city or region).strip() or None,
            "description":     subject or None,
            "images":          images[:6],
            "url":             vip_url,
        }
    except Exception as e:
        print(f"[Subito] Parse greška: {e}")
        return None


class SubitoScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        size = 30
        first_run = True

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(max_pages):
                params = {
                    "cat": 31,        # Auto kategorija na Subito
                    "start": page_num * size,
                    "size": size,
                    "sort": "datedesc",
                    "t": "s",
                }

                if filters.get("min_price"):
                    params["ps"] = filters["min_price"]
                if filters.get("max_price"):
                    params["pe"] = filters["max_price"]
                if filters.get("min_year"):
                    params["ys"] = filters["min_year"]
                if filters.get("max_year"):
                    params["ye"] = filters["max_year"]
                if filters.get("max_km"):
                    params["kme"] = filters["max_km"]

                print(f"[Subito] Stranica {page_num + 1}, start={page_num * size}")

                try:
                    async with session.get(API_URL, params=params,
                                           timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        print(f"[Subito] Status: {resp.status} | CT: {resp.content_type}")

                        if resp.status != 200:
                            print(f"[Subito] Nije 200 — prekidam")
                            break

                        text = await resp.text()

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            print(f"[Subito] JSON greška: {je}")
                            print(f"[Subito] Preview: {text[:300]}")
                            break

                        if first_run:
                            first_run = False
                            print(f"[Subito] Ključevi: {list(data.keys())[:10] if isinstance(data, dict) else type(data)}")

                        # Subito vraća items na različitim nivoima
                        items = []
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            for key in ["items", "ads", "results", "data", "listings", "classified"]:
                                val = data.get(key)
                                if isinstance(val, list) and val:
                                    items = val
                                    print(f"[Subito] Pronađeno {len(items)} pod '{key}'")
                                    break

                        if not items:
                            print(f"[Subito] Nema oglasa")
                            if isinstance(data, dict):
                                print(f"[Subito] Preview: {text[:500]}")
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Subito] Str.{page_num+1}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < size:
                            break

                        await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"[Subito] Greška str.{page_num+1}: {e}")
                    break

        print(f"[Subito] Završeno — {len(all_listings)} oglasa")
        return all_listings
