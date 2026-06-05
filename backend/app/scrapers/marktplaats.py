import asyncio
import json
import re
import aiohttp

API_URL = "https://www.marktplaats.nl/lrp/api/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Referer": "https://www.marktplaats.nl/c/auto-s/c91.html",
}

DETAIL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Referer": "https://www.marktplaats.nl/",
}


def _hq_image(url: str) -> str:
    if not url:
        return url
    url = re.sub(r'ecg_mp_eps\$_\d+\.jpg', 'ecg_mp_eps$_57.jpg', url)
    url = re.sub(r'\$_\d+\.AUTO', '$_57.AUTO', url)
    url = re.sub(r'rule=ecg_mp_eps\$_\d+', 'rule=ecg_mp_eps$_57', url)
    url = re.sub(r'rule=\d+', 'rule=ecg_mp_eps$_57.jpg', url)
    url = re.sub(r'[?&]s=\d+x\d+', '', url)
    return url


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
        "electric": "electric", "elektrisch": "electric",
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


def _get_attr(attributes: list, *keys) -> str | None:
    for attr in attributes:
        key = attr.get("key", "").lower()
        for k in keys:
            if k.lower() in key:
                val = attr.get("value")
                if not val and attr.get("values"):
                    val = attr["values"][0] if attr["values"] else None
                if val:
                    return str(val)
    return None


def _extract_price(item: dict) -> float | None:
    price_obj = item.get("price")
    if isinstance(price_obj, dict):
        info = price_obj.get("priceInfo", {}) or {}
        cents = info.get("priceCents")
        if cents:
            return float(cents) / 100
        text = info.get("priceText") or ""
        p = _parse_price(text)
        if p:
            return p
    info2 = item.get("priceInfo", {}) or {}
    cents2 = info2.get("priceCents")
    if cents2:
        return float(cents2) / 100
    if isinstance(price_obj, (int, float)):
        p = float(price_obj)
        return p if p >= 500 else None
    if isinstance(price_obj, str):
        return _parse_price(price_obj)
    asking = item.get("askingPrice") or item.get("asking_price")
    if asking:
        return _parse_price(str(asking))
    return None


async def _fetch_detail_images(session: aiohttp.ClientSession, url: str) -> list:
    """Dohvati sve slike sa stranice oglasa."""
    images = []
    try:
        async with session.get(url, headers=DETAIL_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return images
            html = await resp.text()

            # Trazi sve UUID-ove koji su u blizini "marktplaats" i "images"
            seen_ids = set()
            # Najpre nadji sve UUID-ove u HTML-u
            all_uuids = re.findall(
                r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
                html
            )
            # Filtriraj samo one koji su u kontekstu marktplaats slika
            for uuid in all_uuids:
                if uuid in seen_ids:
                    continue
                idx = html.find(uuid)
                context = html[max(0, idx-100):idx+50]
                if 'marktplaats' in context and ('image' in context or 'listing' in context):
                    seen_ids.add(uuid)
                    images.append(
                        f"https://images.marktplaats.com/api/v1/hz-mp-pro-listing/images/{uuid}?rule=ecg_mp_eps$_57"
                    )

    except Exception as e:
        print(f"[Marktplaats] Detail greška {url}: {e}")

    return images
            html = await resp.text()

            # Decode unicode escape karaktere
            # Izvuci sve jedinstvene image UUID-ove (direktno, bez decode)
            seen_ids = set()
            for m in re.finditer(
                r'images\.marktplaats\.com(?:\\\\u002F|/|%2F)api(?:\\\\u002F|/|%2F)v1(?:\\\\u002F|/|%2F)(?:hz-mp-pro-listing|listing-mp-p)(?:\\\\u002F|/|%2F)images(?:\\\\u002F|/|%2F)([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
            ):
                img_id = m.group(1)
                if img_id not in seen_ids:
                    seen_ids.add(img_id)
                    images.append(
                        f"https://images.marktplaats.com/api/v1/hz-mp-pro-listing/images/{img_id}?rule=ecg_mp_eps$_57"
                    )

    except Exception as e:
        print(f"[Marktplaats] Detail greška {url}: {e}")

    return images


def _parse_listing(item: dict, detail_images: list = None) -> dict | None:
    try:
        item_id = str(item.get("itemId", "") or item.get("id", ""))
        if not item_id:
            return None

        title = item.get("title", "") or ""
        price = _extract_price(item)

        if not price or price < 500:
            return None

        location = item.get("location", {}) or {}
        city = location.get("cityName") or location.get("city") or ""

        attributes = item.get("attributes", []) or []
        extended   = item.get("extendedAttributes", []) or []
        all_attrs  = attributes + extended

        make      = _get_attr(all_attrs, "merk", "make", "brand", "car_make")
        model     = _get_attr(all_attrs, "model", "car_model")
        year_str  = _get_attr(all_attrs, "constructionyear", "bouwjaar", "year", "constructiejaar")
        km_str    = _get_attr(all_attrs, "mileage", "kilometerstand", "km")
        fuel_str  = _get_attr(all_attrs, "fuel", "brandstof", "fueltype")
        trans_str = _get_attr(all_attrs, "transmission", "transmissie", "versnellingsbak")
        body_str  = _get_attr(all_attrs, "body", "carrosserie", "bodytype")
        power_str = _get_attr(all_attrs, "power", "vermogen", "enginepower")
        color_str = _get_attr(all_attrs, "color", "kleur", "colour")

        if not make and title:
            parts = title.split()
            make  = parts[0] if parts else None
            model = model or (parts[1] if len(parts) > 1 else None)

        year = _parse_int(year_str)
        if year and year < 1970:
            return None

        # Slike: detalji > API thumbnail
        if detail_images:
            images = detail_images
        else:
            images = []
            for img in (item.get("pictures", []) or item.get("images", []) or []):
                if isinstance(img, dict):
                    url = (img.get("largeUrl") or img.get("mediumUrl") or
                           img.get("url") or img.get("src") or "")
                    if not url and img.get("id"):
                        url = f"https://images.marktplaats.com/api/v1/listing-mp-p/{img['id']}/image.jpg?rule=ecg_mp_eps$_57.jpg&imageVariantName=MASTER"
                else:
                    url = str(img)
                if url and url.startswith("http"):
                    images.append(_hq_image(url))

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
            "country":         "NL",
            "city":            city.strip() if city else None,
            "description":     title,
            "images":          images,
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
                        print(f"[Marktplaats] Status: {resp.status}")
                        if resp.status != 200:
                            break

                        text = await resp.text()
                        data = json.loads(text)

                        regular   = data.get("listings") or []
                        top       = data.get("topBlock") or []
                        all_items = regular + top

                        print(f"[Marktplaats] listings={len(regular)}, topBlock={len(top)}, total={data.get('totalResultCount',0)}")

                        if not all_items:
                            break

                        # Dohvati slike paralelno (max 5 odjednom)
                        semaphore = asyncio.Semaphore(5)

                        async def fetch_images(item):
                            vip = item.get("vipUrl") or ""
                            if vip and not vip.startswith("http"):
                                vip = f"https://www.marktplaats.nl{vip}"
                            if not vip:
                                return []
                            async with semaphore:
                                await asyncio.sleep(0.3)
                                return await _fetch_detail_images(session, vip)

                        detail_images_list = await asyncio.gather(
                            *[fetch_images(it) for it in all_items],
                            return_exceptions=True
                        )

                        before = len(all_listings)
                        for item, det_imgs in zip(all_items, detail_images_list):
                            if isinstance(det_imgs, Exception):
                                det_imgs = []
                            parsed = _parse_listing(item, det_imgs if det_imgs else None)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Marktplaats] Str.{page_num+1}: +{added} | Ukupno: {len(all_listings)}")

                        total = data.get("totalResultCount", 0)
                        if offset + limit >= total or len(all_items) < limit:
                            break

                        await asyncio.sleep(2.0)

                except Exception as e:
                    print(f"[Marktplaats] Greška str.{page_num+1}: {e}")
                    break

        print(f"[Marktplaats] Završeno — {len(all_listings)} oglasa")
        return all_listings
