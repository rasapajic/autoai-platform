import asyncio
import json
import re
import aiohttp

CATEGORIES = ["limousine", "suv-gelaendewagen", "cabrio-roadster"]
CAR_TYPES = ["4", "5", "6", "9", "10"]  # kombi, kleinwagen, coupe, van, pickup

BASE_URL = "https://www.willhaben.at/iad/gebrauchtwagen/auto"
BASE_URL_TYPES = "https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenboerse"
IMG_BASE = "https://cache.willhaben.at/mmo/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}


def _extract_next_data(html: str) -> dict | None:
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception as e:
        print(f"[Willhaben] JSON parse greška: {e}")
        return None


def _extract_listings_from_next_data(data: dict) -> list:
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        candidates = [
            page_props.get("searchResult", {}).get("advertSummaryList", {}).get("advertSummary", []),
            page_props.get("advertSummaryList", {}).get("advertSummary", []),
            page_props.get("listings", []),
            page_props.get("results", []),
        ]
        for c in candidates:
            if c:
                return c
        print(f"[Willhaben] pageProps ključevi: {list(page_props.keys())[:15]}")
        return []
    except Exception as e:
        print(f"[Willhaben] Greška ekstrakcije: {e}")
        return []


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = str(val).strip()
        s = re.sub(r"[€EUR\s/Monat]", "", s).strip()
        if not s:
            return None
        if "," not in s and "." in s:
            parts = s.split(".")
            if len(parts[-1]) == 3:
                s = s.replace(".", "")
        else:
            s = s.replace(".", "").replace(",", ".")
        s = re.sub(r"[^\d.]", "", s)
        if not s:
            return None
        price = float(s)
        if price < 500:
            return None
        return price
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


def _get_attr(attributes, name):
    for attr in attributes:
        if attr.get("name") == name:
            vals = attr.get("values", [])
            return vals[0] if vals else None
    return None


async def _fetch_detail_images(session: aiohttp.ClientSession, url: str) -> tuple[list, str, str | None]:
    """Dohvati sve slike i kontakt tip sa stranice oglasa."""
    images = []
    contact_type = "unknown"
    contact_url = None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return images
            html = await resp.text()
            next_data = _extract_next_data(html)
            if not next_data:
                return images

            # Pokušaj naći sve slike u __NEXT_DATA__
            props = next_data.get("props", {}).get("pageProps", {})
            advert = props.get("advert", props.get("advertDetails", props.get("advertSummary", {})))

            attrs = advert.get("attributes", {}).get("attribute", [])
            all_imgs = _get_attr(attrs, "ALL_IMAGE_URLS")
            if all_imgs:
                paths = all_imgs.split(";")
                images = [f"{IMG_BASE}{p.strip()}" for p in paths if p.strip()]

            # Fallback: traži u advertImageList
            if not images:
                img_list = advert.get("advertImageList", {}).get("advertImage", [])
                for img in img_list:
                    ref = img.get("reference")
                    if ref:
                        images.append(f"{IMG_BASE}{ref}")

            # Fallback: traži MMO putanje u HTML-u
            if not images:
                mmo_paths = re.findall(r'"reference"\s*:\s*"([^"]+\.jpg)"', html)
                seen = set()
                for p in mmo_paths:
                    if p not in seen:
                        seen.add(p)
                        images.append(f"{IMG_BASE}{p}")

            # Detekcija kontakt tipa
            if re.search(r'mailto:', html):
                contact_type = "email"
                m = re.search(r'mailto:([^\s"\'<>]+)', html)
                if m:
                    contact_url = m.group(0)
            elif re.search(r'(H[aä]ndler\s+kontaktieren|Kontakt aufnehmen|open-contact|/contact)', html, re.IGNORECASE):
                contact_type = "form"
                m = re.search(r'href=["\']([^"\']*(?:open-contact|/contact|send-message)[^"\']*)["\']', html, re.IGNORECASE)
                if m:
                    raw = m.group(1)
                    contact_url = f"https://www.willhaben.at{raw}" if raw.startswith("/") else raw
            elif re.search(r'tel:', html):
                contact_type = "phone"
                m = re.search(r'tel:([^\s"\'<>]+)', html)
                if m:
                    contact_url = m.group(0)

    except Exception as e:
        print(f"[Willhaben] Detail greška {url}: {e}")
    return images, contact_type, contact_url


def _parse_ad(ad: dict, detail_images: list = None, contact_type: str = "unknown", contact_url: str = None) -> dict | None:
    try:
        attrs = ad.get("attributes", {}).get("attribute", [])
        def g(name):
            return _get_attr(attrs, name)

        ad_id        = str(ad.get("id", ""))
        make         = g("CAR_MODEL/MAKE")
        model        = g("CAR_MODEL/MODEL")
        variant      = g("CAR_MODEL/MODEL_SPECIFICATION")
        year_str     = g("YEAR_MODEL") or g("YEAR")
        price_str    = g("PRICE") or g("PRICE_FOR_DISPLAY")
        mileage_str  = g("MILEAGE")
        fuel         = g("ENGINE/FUEL_RESOLVED") or g("ENGINE/FUEL") or ""
        transmission = g("TRANSMISSION_RESOLVED") or g("TRANSMISSION") or ""
        body         = g("CAR_TYPE") or ""
        power        = g("ENGINE/EFFECT") or ""
        color        = g("EXTERIORCOLOURMAIN") or ""
        city         = g("LOCATION") or g("DISTRICT") or ""
        country      = g("COUNTRY") or "AT"
        seo_url      = g("SEO_URL") or ""
        description  = ad.get("description", "") or ""

        year = None
        if year_str:
            try:
                m = re.search(r'(\d{4})', str(year_str))
                if m:
                    year = int(m.group(1))
            except Exception:
                pass
        if not year:
            ez = g("EZ") or g("REGISTRATION_DATE") or ""
            if ez:
                m = re.search(r'(\d{4})', str(ez))
                if m:
                    year = int(m.group(1))

        price = _parse_price(price_str)
        if price is None:
            return None

        # Slike: detail > search thumbnail
        if detail_images:
            images = detail_images
        else:
            images = []
            all_imgs = g("ALL_IMAGE_URLS")
            if all_imgs:
                paths = all_imgs.split(";")
                images = [f"{IMG_BASE}{p.strip()}" for p in paths if p.strip()]
            if not images:
                for img in (ad.get("advertImageList", {}).get("advertImage", []) or []):
                    ref = img.get("reference")
                    if ref:
                        images.append(f"{IMG_BASE}{ref}")

        # URL
        if seo_url:
            if seo_url.startswith("/iad"):
                url = f"https://www.willhaben.at{seo_url}"
            elif seo_url.startswith("/"):
                url = f"https://www.willhaben.at/iad{seo_url}"
            else:
                url = f"https://www.willhaben.at/iad/{seo_url}"
        else:
            url = f"https://www.willhaben.at/iad/gebrauchtwagen/d/auto/{ad_id}"

        if not ad_id or not make:
            return None

        return {
            "external_id":     f"wh_{ad_id}",
            "source":          "willhaben",
            "make":            make,
            "model":           model,
            "variant":         variant,
            "year":            year,
            "price":           price,
            "currency":        "EUR",
            "mileage":         _parse_int(mileage_str),
            "fuel_type":       _normalize_fuel(fuel),
            "transmission":    _normalize_transmission(transmission),
            "body_type":       body or None,
            "engine_power_kw": _parse_int(power),
            "color":           color.strip() or None,
            "country":         "AT",
            "city":            city.strip() or None,
            "description":     description.strip() or None,
            "images":          images,
            "url":             url,
        }
    except Exception as e:
        print(f"[Willhaben] Parse greška: {e}")
        return None


async def _scrape_page(session, url, params, category_name, all_listings, seen_ids):
    """Scrape jedne stranice i dohvati detalje paralelno."""
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return False
            html = await resp.text()
            next_data = _extract_next_data(html)
            if not next_data:
                return False
            adverts = _extract_listings_from_next_data(next_data)
            if not adverts:
                return False

            # Dohvati URL-ove oglasa
            items_with_urls = []
            for ad in adverts:
                attrs = ad.get("attributes", {}).get("attribute", [])
                seo_url = _get_attr(attrs, "SEO_URL") or ""
                if seo_url.startswith("/iad"):
                    detail_url = f"https://www.willhaben.at{seo_url}"
                elif seo_url.startswith("/"):
                    detail_url = f"https://www.willhaben.at/iad{seo_url}"
                elif seo_url:
                    detail_url = f"https://www.willhaben.at/iad/{seo_url}"
                else:
                    ad_id = str(ad.get("id", ""))
                    detail_url = f"https://www.willhaben.at/iad/gebrauchtwagen/d/auto/{ad_id}"
                items_with_urls.append((ad, detail_url))

            # Dohvati slike paralelno (max 5)
            semaphore = asyncio.Semaphore(5)
            async def fetch_imgs(ad, detail_url):
                async with semaphore:
                    await asyncio.sleep(0.3)
                    return await _fetch_detail_images(session, detail_url)

            detail_images_list = await asyncio.gather(
                *[fetch_imgs(ad, du) for ad, du in items_with_urls],
                return_exceptions=True
            )

            before = len(all_listings)
            for (ad, _), det_imgs in zip(items_with_urls, detail_images_list):
                if isinstance(det_imgs, Exception):
                    det_imgs = []
                parsed = _parse_ad(ad, det_imgs if det_imgs else None)
                if parsed and parsed["external_id"] not in seen_ids:
                    seen_ids.add(parsed["external_id"])
                    all_listings.append(parsed)

            added = len(all_listings) - before
            print(f"[Willhaben] {category_name}: +{added} | Ukupno: {len(all_listings)}")
            return len(adverts) >= 10

    except Exception as e:
        print(f"[Willhaben] Greška {category_name}: {e}")
        return False


class WillhabenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:

            # ── Kategorije ──────────────────────────────────────────
            for category in CATEGORIES:
                url = f"{BASE_URL}/{category}"
                print(f"[Willhaben] Kategorija: {category}")
                for page in range(1, max_pages + 1):
                    params = {}
                    if page > 1:
                        params["page"] = page
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
                    has_more = await _scrape_page(session, url, params, f"{category} str.{page}", all_listings, seen_ids)
                    if not has_more:
                        break
                    await asyncio.sleep(1.5)

            # ── CAR_TYPE stranice ───────────────────────────────────
            for car_type in CAR_TYPES:
                print(f"[Willhaben] CAR_TYPE: {car_type}")
                for page in range(1, max_pages + 1):
                    params = {"CAR_TYPE": car_type}
                    if page > 1:
                        params["page"] = page
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
                    has_more = await _scrape_page(session, BASE_URL_TYPES, params, f"CAR_TYPE={car_type} str.{page}", all_listings, seen_ids)
                    if not has_more:
                        break
                    await asyncio.sleep(1.5)

        print(f"[Willhaben] Završeno — {len(all_listings)} oglasa")
        return all_listings
