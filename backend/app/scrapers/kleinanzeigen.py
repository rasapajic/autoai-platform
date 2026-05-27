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
}

KNOWN_MAKES = [
    "Volkswagen", "VW", "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Toyota",
    "Ford", "Opel", "Skoda", "Renault", "Peugeot", "Hyundai", "Kia", "Volvo",
    "Seat", "Mazda", "Honda", "Nissan", "Fiat", "Citroën", "Citroen", "Porsche",
    "Land Rover", "Jeep", "Dacia", "Suzuki", "Mitsubishi", "Subaru", "Tesla",
    "Alfa Romeo", "Lexus", "Mini", "Smart", "Jaguar", "Bentley", "Lancia",
]


def _clean_text(text: str, max_len: int = 100) -> str:
    """Čisti HTML entitete, whitespace i ograničava dužinu"""
    if not text:
        return ""
    # Ukloni HTML entitete
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&#x[0-9a-fA-F]+;', '', text)
    text = re.sub(r'&\w+;', ' ', text)
    # Uzmi samo prvi red
    text = text.split("\n")[0].strip()
    # Ukloni višestruke razmake
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


def _parse_price(val) -> float | None:
    if val is None:
        return None
    try:
        s = str(val).strip()
        s = re.sub(r"[€EUR\s]", "", s)
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


def _normalize_fuel(val) -> str | None:
    if not val:
        return None
    val = val.lower()
    if "diesel" in val: return "diesel"
    if "benzin" in val or "petrol" in val: return "petrol"
    if "elektro" in val or "electric" in val: return "electric"
    if "hybrid" in val: return "hybrid"
    if "lpg" in val or "autogas" in val: return "lpg"
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


def _parse_listings_from_html(html: str) -> list:
    listings = []

    # article[data-adid] HTML parsing
    article_pattern = re.compile(
        r'<article[^>]+data-adid="(\d+)"[^>]*data-href="([^"]*)"[^>]*>(.*?)</article>',
        re.DOTALL
    )

    for match in article_pattern.finditer(html):
        ad_id   = match.group(1)
        ad_href = match.group(2)
        content = match.group(3)

        # Samo auto kategorija
        if "-216-" not in ad_href:
            continue

        # Naslov
        title = ""
        for pat in [
            r'class="[^"]*text-module-begin[^"]*"[^>]*>(.*?)</a>',
            r'class="[^"]*ellipsis[^"]*"[^>]*>(.*?)</a>',
        ]:
            m = re.search(pat, content, re.DOTALL)
            if m:
                title = _clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 200)
                break
        if not title:
            m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', content, re.DOTALL)
            if m:
                title = _clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 200)

        # Cena
        price_text = ""
        for pat in [
            r'class="[^"]*aditem-main--middle--price[^"]*"[^>]*>(.*?)</p>',
            r'class="[^"]*price[^"]*"[^>]*>(.*?)</',
        ]:
            m = re.search(pat, content, re.DOTALL)
            if m:
                price_text = _clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 50)
                break

        # Lokacija — samo postal code + naziv grada, max 1 red
        city = ""
        for pat in [
            r'class="[^"]*aditem-main--top--left[^"]*"[^>]*>(.*?)</p>',
            r'class="[^"]*locality[^"]*"[^>]*>(.*?)</',
        ]:
            m = re.search(pat, content, re.DOTALL)
            if m:
                raw = re.sub(r'<[^>]+>', ' ', m.group(1))
                city = _clean_text(raw, 100)
                # Ukloni datum
                city = re.sub(r'\b(Heute|Gestern|\d{2}\.\d{2}\.\d{4}|\d+\.\d+\.)\b.*', '', city).strip()
                city = city[:100]
                break

        # Slika
        img_url = ""
        m = re.search(r'<img[^>]+(?:src|data-src)="(https://img\.kleinanzeigen\.de[^"]+)"', content)
        if m:
            img_url = m.group(1)

        # Godište iz naslova
        year_m = re.search(r'\b(20[0-2]\d|199\d)\b', title)

        # Km iz naslova
        km_m = re.search(r'([\d.]+)\s*km', title, re.IGNORECASE)
        km_val = None
        if km_m:
            km_val = _parse_int(km_m.group(1).replace(".", ""))

        price = _parse_price(price_text)
        if not price:
            continue

        ad_url = f"https://www.kleinanzeigen.de{ad_href}" if ad_href.startswith("/") else ad_href

        listings.append({
            "id":      ad_id,
            "title":   title,
            "price":   price,
            "city":    city,
            "image":   img_url,
            "url":     ad_url,
            "year":    _parse_int(year_m.group(1)) if year_m else None,
            "mileage": km_val,
        })

    print(f"[Kleinanzeigen] HTML parsing: {len(listings)} auto oglasa")
    return listings


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("id") or "")
        if not item_id:
            return None

        title = item.get("title") or ""
        price = item.get("price")
        if not price:
            return None

        make, model = _extract_make_model(title)
        year = item.get("year")
        if year and year < 2000:
            return None

        city = item.get("city") or ""
        # Finalni cleanup grada
        city = _clean_text(city, 100)

        images = []
        img = item.get("image", "")
        if img and img.startswith("http"):
            images.append(img)

        return {
            "external_id":  f"ka_{item_id}",
            "source":       "kleinanzeigen",
            "make":         make,
            "model":        model,
            "year":         year,
            "price":        price,
            "currency":     "EUR",
            "mileage":      item.get("mileage"),
            "fuel_type":    None,
            "transmission": None,
            "country":      "DE",
            "city":         city or None,
            "description":  title[:500] if title else None,
            "images":       images,
            "url":          item.get("url") or f"https://www.kleinanzeigen.de/s-anzeige/{item_id}",
        }
    except Exception as e:
        print(f"[Kleinanzeigen] Parse greška: {e}")
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
                        print(f"[Kleinanzeigen] Status: {resp.status}")
                        if resp.status != 200:
                            break

                        html = await resp.text()
                        items = _parse_listings_from_html(html)

                        if not items:
                            break

                        before = len(all_listings)
                        for item in items:
                            parsed = _parse_listing(item)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        added = len(all_listings) - before
                        print(f"[Kleinanzeigen] Str.{page_num}: +{added} | Ukupno: {len(all_listings)}")

                        if len(items) < 10:
                            break

                        await asyncio.sleep(2.0)

                except Exception as e:
                    print(f"[Kleinanzeigen] Greška: {e}")
                    break

        print(f"[Kleinanzeigen] Završeno — {len(all_listings)} oglasa")
        return all_listings
