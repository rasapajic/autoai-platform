import asyncio
import re
import aiohttp

# La Centrale — pravi API endpoint
SEARCH_URL = "https://recherche.lacentrale.fr/v3/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Origin": "https://www.lacentrale.fr",
    "Referer": "https://www.lacentrale.fr/listing?families=AUTO",
    "X-Client-Source": "classified:lcpab:recherche-react",
    "x-api-key": "2vHD2GjDJ07RpNvbGYpJG7s6bQNwRNkI9SEkgQnR",
}


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = re.sub(r"[^\d.]", "", str(val))
        price = float(s) if s else None
        return price if price and price >= 500 else None
    except Exception:
        return None


def _normalize_fuel(val) -> str | None:
    if not val:
        return None
    val = val.lower()
    if "elect" in val:      return "electric"
    if "hybr" in val:       return "hybrid"
    if "diesel" in val:     return "diesel"
    if "essence" in val or "petrol" in val: return "petrol"
    if "gpl" in val or "lpg" in val:        return "lpg"
    return val


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower()
    if any(w in val for w in ["auto", "dsg", "cvt", "bva", "bvd"]): return "automatic"
    if any(w in val for w in ["man", "bvm", "bvs"]): return "manual"
    return val


def _parse_hit(hit: dict) -> dict | None:
    try:
        item    = hit.get("item") or hit
        vehicle = item.get("vehicle") or {}
        ad      = item.get("classified") or item.get("ad") or item

        # ID
        item_id = str(
            item.get("id") or ad.get("id") or
            item.get("adId") or hit.get("id") or ""
        )
        if not item_id:
            return None

        # Marka i model
        make  = vehicle.get("make") or vehicle.get("brand") or item.get("make") or ""
        model = vehicle.get("model") or item.get("model") or ""

        # Cena
        price_raw = (
            ad.get("price") or item.get("price") or
            ad.get("sellingPrice") or vehicle.get("price")
        )
        if isinstance(price_raw, dict):
            price_raw = price_raw.get("value") or price_raw.get("amount") or 0
        price = _parse_price(price_raw)
        if not price:
            return None

        # Specifikacije
        year     = vehicle.get("year") or vehicle.get("yearOfManufacture") or item.get("year")
        mileage  = vehicle.get("mileage") or vehicle.get("km") or item.get("mileage")
        fuel     = vehicle.get("fuelType") or vehicle.get("energy") or vehicle.get("energie") or ""
        trans    = vehicle.get("gearbox") or vehicle.get("transmission") or vehicle.get("boite") or ""
        body     = vehicle.get("bodyType") or vehicle.get("carrosserie") or ""
        power_cv = vehicle.get("powerCV") or vehicle.get("power") or vehicle.get("puissance")

        # Lokacija
        seller   = item.get("seller") or ad.get("seller") or {}
        location = seller.get("location") or item.get("location") or {}
        if isinstance(location, dict):
            city = location.get("city") or location.get("cityName") or location.get("ville") or ""
        else:
            city = str(location)

        # Slike
        images = []
        for key in ["photos", "images", "pictures", "imageUrls", "medias"]:
            imgs = item.get(key) or vehicle.get(key) or ad.get(key) or []
            if isinstance(imgs, list):
                for img in imgs[:8]:
                    url = (img.get("url") or img.get("src") or img.get("large") or
                           img.get("medium") or "") if isinstance(img, dict) else str(img)
                    if url and url.startswith("http"):
                        images.append(url)
                if images:
                    break

        # URL oglasa
        vip_url = (ad.get("url") or item.get("url") or ad.get("link") or
                   item.get("link") or "")
        if not vip_url:
            vip_url = f"https://www.lacentrale.fr/auto-occasion-annonce-{item_id}.html"

        year_int = int(str(year)[:4]) if year else None
        if year_int and (year_int < 2000 or year_int > 2026):
            return None

        power_kw = None
        if power_cv:
            p = int(re.sub(r"[^\d]", "", str(power_cv)) or 0)
            if p > 0:
                power_kw = round(p * 0.7355) if p > 250 else p

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
            "mileage":         int(re.sub(r"[^\d]", "", str(mileage)) or 0) or None,
            "fuel_type":       _normalize_fuel(str(fuel)),
            "transmission":    _normalize_transmission(str(trans)),
            "body_type":       str(body).strip() or None,
            "engine_power_kw": power_kw,
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

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                params = {
                    "families":  "AUTO",
                    "pageSize":  30,
                    "page":      page_num,
                    "boostVo":   "true",
                    "regions":   "FR-IDF,FR-ARA,FR-OCC,FR-NAQ,FR-PAC",
                }

                if filters.get("make"):
                    params["makesModelsCommercialNames"] = filters["make"].upper()
                if filters.get("min_year"):
                    params["yearMin"] = filters["min_year"]
                if filters.get("max_year"):
                    params["yearMax"] = filters["max_year"]
                if filters.get("max_km"):
                    params["mileageMax"] = filters["max_km"]

                print(f"[LaCentrale] Stranica {page_num}...")

                try:
                    async with session.get(
                        SEARCH_URL, params=params,
                        timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        print(f"[LaCentrale] Status: {resp.status}")

                        if resp.status == 403:
                            print("[LaCentrale] 403 — blokiran")
                            break
                        if resp.status != 200:
                            text = await resp.text()
                            print(f"[LaCentrale] Preview: {text[:300]}")
                            break

                        data = await resp.json(content_type=None)

                        # Struktura: {"hits": [...], "total": N}
                        hits = (data.get("hits") or data.get("results") or
                                data.get("ads") or data.get("items") or [])

                        if isinstance(hits, list) and hits and isinstance(hits[0], dict):
                            # hits mogu imati "item" unutra ili biti direktni oglasi
                            pass
                        elif isinstance(data, list):
                            hits = data

                        if not hits:
                            print(f"[LaCentrale] Nema oglasa — ključevi: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                            print(f"[LaCentrale] Preview: {str(data)[:400]}")
                            break

                        before = len(all_listings)
                        for hit in hits:
                            parsed = _parse_hit(hit)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        total = data.get("total") or data.get("totalCount") or 0
                        print(f"[LaCentrale] Str.{page_num}: +{added} | Ukupno: {len(all_listings)} | Total: {total}")

                        if len(hits) < 20 or (total and page_num * 30 >= int(total)):
                            break

                        await asyncio.sleep(1.2)

                except Exception as e:
                    print(f"[LaCentrale] Greška: {e}")
                    break

        print(f"[LaCentrale] Završeno — {len(all_listings)} oglasa")
        return all_listings
