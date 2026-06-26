import asyncio
import json
import re
import aiohttp

BASE_URL = "https://www.kleinanzeigen.de/s-autos/c216"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.kleinanzeigen.de/",
}

KNOWN_MAKES = [
    "Volkswagen", "VW", "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Toyota",
    "Ford", "Opel", "Skoda", "Renault", "Peugeot", "Hyundai", "Kia", "Volvo",
    "Seat", "Mazda", "Honda", "Nissan", "Fiat", "CitroÃ«n", "Citroen", "Porsche",
    "Land Rover", "Jeep", "Dacia", "Suzuki", "Mitsubishi", "Subaru", "Tesla",
    "Alfa Romeo", "Lexus", "Mini", "Smart", "Jaguar", "Bentley", "Lancia",
    "Cupra", "Polestar", "MG", "BYD", "Xpeng",
]


def _clean_text(text: str, max_len: int = 100) -> str:
    if not text:
        return ""
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&#x[0-9a-fA-F]+;', '', text)
    text = re.sub(r'&\w+;', ' ', text)
    text = text.split("\n")[0].strip()
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


def _hq_image(url: str) -> str:
    """Zamijeni bilo koji rule sa $_57.AUTO (visoka rezolucija ~900px)"""
    if not url:
        return url
    return re.sub(r'\$_\w+\.AUTO', '$_57.AUTO', url)


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = str(val).strip()
        s = re.sub(r'\b(VB|VHB|EUR|â‚¬)\b', '', s, flags=re.IGNORECASE)
        s = re.sub(r"[â‚¬\s]", "", s)
        if "," in s:
            parts = s.split(",")
            s = parts[0].replace(".", "") + "." + parts[1]
        else:
            s = s.replace(".", "")
        s = re.sub(r"[^\d.]", "", s)
        if not s:
            return None
        price = float(s)
        if price < 500 or price > 500000:
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


def _extract_make_model(title: str) -> tuple:
    if not title:
        return None, None
    for make in sorted(KNOWN_MAKES, key=len, reverse=True):
        if make.lower() in title.lower():
            rest  = re.sub(re.escape(make), "", title, flags=re.IGNORECASE).strip()
            words = rest.split()
            model = " ".join(words[:2]) if words else None
            return make, model[:100] if model else None
    words = title.split()
    return (words[0][:100] if words else None), (" ".join(words[1:3])[:100] if len(words) > 1 else None)


async def _fetch_detail(session: aiohttp.ClientSession, url: str) -> dict:
    """Dohvati detalje oglasa: sve slike + grad + gorivo + km"""
    result = {"images": [], "city": "", "fuel_type": None, "mileage": None, "year": None}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return result
            html = await resp.text()

            # â”€â”€ Slike iz LD+JSON (sve, ne samo prva) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            for ld_match in re.finditer(
                r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            ):
                try:
                    ld = json.loads(ld_match.group(1))
                    # Samo slike iz glavnog oglasa (ItemPage ili Vehicle)
                    ld_type = ld.get("@type", "")
                    if ld_type in ("ItemPage", "Vehicle", "Product", "Offer") or not ld_type:
                        if ld.get("image"):
                            imgs = ld["image"] if isinstance(ld["image"], list) else [ld["image"]]
                            result["images"] += [_hq_image(i) for i in imgs if i]
                        elif ld.get("contentUrl"):
                            result["images"].append(_hq_image(ld["contentUrl"]))
                except Exception:
                    pass

            # â”€â”€ Fallback slike iz gallery JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if not result["images"]:
                gallery_m = re.search(r'"imageUrls"\s*:\s*(\[[^\]]+\])', html)
                if gallery_m:
                    try:
                        urls = json.loads(gallery_m.group(1))
                        result["images"] = [_hq_image(u) for u in urls if u]
                    except Exception:
                        pass

            # â”€â”€ Fallback slike iz img tagova â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if not result["images"]:
                for m in re.finditer(r'<img[^>]+(?:src|data-src)="(https://img\.kleinanzeigen\.de[^"]+)"', html):
                    result["images"].append(_hq_image(m.group(1)))

            # â”€â”€ Deduplikacija slika â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            seen = set()
            unique = []
            for img in result["images"]:
                key = re.sub(r'\$_\w+\.AUTO', '', img)
                if key not in seen:
                    seen.add(key)
                    unique.append(img)
            result["images"] = unique

            # â”€â”€ Grad â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Kleinanzeigen prikazuje grad u vise mjesta
            for city_pat in [
                r'\d{5}\s+\w[\w\s]+-\s*([\w\s]+)',
                r'<span[^>]+itemprop="addressLocality"[^>]*>([^<]+)</span>',
                r'class="[^"]*breadcrump-link[^"]*"[^>]*>([^<]{4,50})</a>',
                r'"addressLocality"\s*:\s*"([^"]+)"',
                r'class="addetail-user--city"[^>]*>([^<]+)<',
                r'<span[^>]+class="[^"]*location[^"]*"[^>]*>([^<]+)</span>',
            ]:
                m = re.search(city_pat, html)
                if m:
                    city = _clean_text(m.group(1), 100).strip()
                    if city and len(city) > 2:
                        result["city"] = city
                        break

            # â”€â”€ Gorivo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            fuel_map = {
                'benzin': 'petrol', 'super': 'petrol', 'gasoline': 'petrol', 'petrol': 'petrol',
                'diesel': 'diesel', 'dizel': 'diesel',
                'elektro': 'electric', 'electric': 'electric', 'elektr': 'electric', 'bev': 'electric',
                'hybrid': 'hybrid', 'plug-in': 'hybrid', 'phev': 'hybrid',
                'autogas': 'lpg', 'lpg': 'lpg', 'gas': 'lpg',
                'erdgas': 'cng', 'cng': 'cng',
            }
            # TraÅ¾i u structured data ili attribute sekciji
            attr_section = re.search(
                r'Kraftstoffart.*?<[^>]+>([^<]{3,30})<',
                html, re.IGNORECASE | re.DOTALL
            )
            fuel_text = attr_section.group(1).lower().strip() if attr_section else ''
            if not fuel_text:
                # Fallback: traÅ¾i keyword u tekstu stranice
                page_lower = html.lower()
                for kw, ftype in sorted(fuel_map.items(), key=lambda x: -len(x[0])):
                    if f'>{kw}<' in page_lower or f'"kraftstoff">{kw}' in page_lower:
                        fuel_text = kw
                        break
            for kw, ftype in sorted(fuel_map.items(), key=lambda x: -len(x[0])):
                if kw in fuel_text:
                    result["fuel_type"] = ftype
                    break

            # â”€â”€ KilometraÅ¾a â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            km_m = re.search(r'Kilometerstand.*?(\d[\d.]+)\s*km', html, re.IGNORECASE | re.DOTALL)
            if km_m:
                result["mileage"] = _parse_int(km_m.group(1).replace(".", ""))

            # â”€â”€ GodiÅ¡te â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            year_m = re.search(
                r'(?:Erstzulassung|Baujahr|EZ)[^\d]*(?:\w+\s+)?(\d{4})',
                html,
                re.IGNORECASE,
            )
            if not year_m:
                alt_year_m = re.search(r'Erstzulassung.*?(\w+)\s+(\d{4})', html, re.IGNORECASE)
                if alt_year_m:
                    year_m = alt_year_m

            if year_m:
                group_index = 2 if len(year_m.groups()) >= 2 else 1
                y = int(year_m.group(group_index))
                if 1970 <= y <= 2026:
                    result["year"] = y
    except Exception as e:
        print(f"[Kleinanzeigen] Detail greÅ¡ka {url}: {e}")

    return result


def _parse_listings_from_html(html: str) -> list:
    listings = []
    article_pattern = re.compile(
        r'<article[^>]+data-adid="(\d+)"[^>]+data-href="([^"]*)"[^>]*>(.*?)</article>',
        re.DOTALL
    )

    for match in article_pattern.finditer(html):
        ad_id   = match.group(1)
        ad_href = match.group(2)
        content = match.group(3)

        if "-216-" not in ad_href:
            continue

        ad_url = f"https://www.kleinanzeigen.de{ad_href}"

        title = description = ""
        thumb_images = []

        # LD+JSON listing thumbnail
        ld_match = re.search(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            content, re.DOTALL
        )
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
                title       = ld.get("title") or ld.get("name") or ""
                description = ld.get("description") or ""
                if ld.get("image"):
                    imgs = ld["image"] if isinstance(ld["image"], list) else [ld["image"]]
                    thumb_images = [_hq_image(i) for i in imgs if i]
                elif ld.get("contentUrl"):
                    thumb_images = [_hq_image(ld["contentUrl"])]
            except Exception:
                pass

        if not title:
            for pat in [
                r'class="[^"]*text-module-begin[^"]*"[^>]*>(.*?)</a>',
                r'<h[23][^>]*>(.*?)</h[23]>',
            ]:
                m = re.search(pat, content, re.DOTALL)
                if m:
                    title = _clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 200)
                    break

        # Cena
        price = None
        m = re.search(
            r'class="aditem-main--middle--price-shipping--price"[^>]*>(.*?)</',
            content, re.DOTALL
        )
        if m:
            price = _parse_price(_clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 50))
        if not price:
            for p_str in re.findall(r'([\d.,]+)\s*â‚¬', content):
                p = _parse_price(p_str)
                if p:
                    price = p
                    break
        if not price:
            continue

        # Grad sa listinga (grubi)
        city = ""
        for city_pat in [
            r'class="aditem-main--top--left"[^>]*>(.*?)</(?:p|div)>',
            r'class="[^"]*location[^"]*"[^>]*>(.*?)</',
            r'<span[^>]*itemprop="addressLocality"[^>]*>(.*?)</span>',
        ]:
            m = re.search(city_pat, content, re.DOTALL)
            if m:
                raw = _clean_text(re.sub(r'<[^>]+>', ' ', m.group(1)), 100)
                raw = re.sub(r'\b(Heute|Gestern|\d{2}\.\d{2}\.\d{4}|\d+\.\d+\.)\b.*', '', raw).strip()
                city_extract = re.search(r'\d{5}\s+[\w\s]+-\s*([\w\s]+)', raw)
                if city_extract:
                    raw = city_extract.group(1).strip()
                if raw:
                    city = raw
                    break

        year_m = re.search(r'\b(19[789]\d|200\d|201[0-9]|202[0-4])\b', title + ' ' + description)
        km_m   = re.search(r'([\d.]+)\s*km', title + ' ' + description, re.IGNORECASE)

        listings.append({
            "id":      ad_id,
            "title":   _clean_text(title, 200),
            "price":   price,
            "city":    city,
            "images":  thumb_images,
            "url":     ad_url,
            "year":    _parse_int(year_m.group(1)) if year_m else None,
            "mileage": _parse_int(km_m.group(1).replace(".", "")) if km_m else None,
            "desc":    _clean_text(description, 500),
        })

    print(f"[Kleinanzeigen] Parsiranih: {len(listings)}")
    return listings


def _parse_listing(item: dict, detail: dict | None = None) -> dict | None:
    try:
        item_id = str(item.get("id") or "")
        if not item_id:
            return None

        title = item.get("title") or ""
        price = item.get("price")
        if not price:
            return None

        make, model = _extract_make_model(title)
        year = (detail or {}).get("year") or item.get("year")
        if year and year < 1970:
            return None

        # Grad: detalj ima bolji
        city = ""
        if detail and detail.get("city"):
            city = detail["city"]
        elif item.get("city"):
            city = item["city"]

        # Slike: detalj ima sve, listing samo thumbnail
        images = []
        if detail and detail.get("images"):
            images = detail["images"]
        elif item.get("images"):
            images = [_hq_image(i) for i in item["images"] if i and i.startswith("http")]

        fuel_type = (detail or {}).get("fuel_type")
        mileage   = (detail or {}).get("mileage") or item.get("mileage")

        return {
            "external_id":  f"ka_{item_id}",
            "source":       "kleinanzeigen",
            "make":         make,
            "model":        model,
            "year":         year,
            "price":        price,
            "currency":     "EUR",
            "mileage":      mileage,
            "fuel_type":    fuel_type,
            "transmission": None,
            "country":      "DE",
            "city":         city or None,
            "description":  (item.get("desc") or title)[:500] or None,
            "images":       images,
            "url":          item.get("url") or f"https://www.kleinanzeigen.de/s-anzeige/{item_id}",
        }
    except Exception as e:
        print(f"[Kleinanzeigen] Parse greÅ¡ka: {e}")
        return None


class KleinanzeigenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                url = f"{BASE_URL}/seite:{page_num}" if page_num > 1 else BASE_URL
                print(f"[Kleinanzeigen] Stranica {page_num}...")

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                        if resp.status != 200:
                            break
                        html = await resp.text()
                        items = _parse_listings_from_html(html)
                        if not items:
                            break

                        # â”€â”€ Detalji paralelno, max 5 odjednom â”€â”€â”€â”€â”€â”€
                        semaphore = asyncio.Semaphore(5)

                        async def fetch_with_sem(item):
                            async with semaphore:
                                await asyncio.sleep(0.3)
                                return await _fetch_detail(session, item["url"])

                        details = await asyncio.gather(
                            *[fetch_with_sem(it) for it in items],
                            return_exceptions=True
                        )

                        before = len(all_listings)
                        for item, detail in zip(items, details):
                            if isinstance(detail, Exception):
                                detail = None
                            parsed = _parse_listing(item, detail)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Kleinanzeigen] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < 10:
                            break

                        await asyncio.sleep(2.5)

                except Exception as e:
                    print(f"[Kleinanzeigen] GreÅ¡ka: {e}")
                    break

        print(f"[Kleinanzeigen] ZavrÅ¡eno â€” {len(all_listings)} oglasa")
        return all_listings
