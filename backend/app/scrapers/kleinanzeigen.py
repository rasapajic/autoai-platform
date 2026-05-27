import asyncio
import json
import re
import aiohttp
from html.parser import HTMLParser

BASE_URL = "https://www.kleinanzeigen.de/s-autos/c216"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
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
    val = val.lower()
    if "diesel" in val: return "diesel"
    if "benzin" in val or "petrol" in val: return "petrol"
    if "elektro" in val or "electric" in val: return "electric"
    if "hybrid" in val: return "hybrid"
    if "lpg" in val or "gas" in val: return "lpg"
    return None


def _normalize_transmission(val) -> str | None:
    if not val:
        return None
    val = val.lower()
    if any(w in val for w in ["automatik", "automatic", "dsg"]): return "automatic"
    if any(w in val for w in ["schaltgetriebe", "manual", "manuell"]): return "manual"
    return None


def _parse_listings_from_html(html: str) -> list:
    listings = []

    # Metoda 1: Tražimo JSON embedded u script tagovima
    script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for script in script_matches:
        # Traži window.__data__ ili slično
        for pattern in [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?})(?:;|\s*</)',
            r'window\.__data__\s*=\s*({.*?})(?:;|\s*</)',
            r'"ads"\s*:\s*(\[.*?\])',
            r'"listings"\s*:\s*(\[.*?\])',
            r'"items"\s*:\s*(\[.*?\])',
        ]:
            m = re.search(pattern, script, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    if isinstance(data, list) and len(data) > 0:
                        print(f"[Kleinanzeigen] Pronađeno {len(data)} oglasa u script tagu")
                        return data
                    elif isinstance(data, dict):
                        for key in ["ads", "listings", "items", "results"]:
                            if isinstance(data.get(key), list) and data[key]:
                                print(f"[Kleinanzeigen] Pronađeno {len(data[key])} pod '{key}'")
                                return data[key]
                except Exception:
                    pass

    # Metoda 2: HTML parsing — article tagovi
    # Kleinanzeigen koristi <article class="aditem" data-adid="...">
    article_pattern = re.compile(
        r'<article[^>]+data-adid="(\d+)"[^>]*>(.*?)</article>',
        re.DOTALL
    )

    for match in article_pattern.finditer(html):
        ad_id = match.group(1)
        content = match.group(2)

        # Naslov
        title_m = re.search(r'<a[^>]+class="[^"]*ellipsis[^"]*"[^>]*>(.*?)</a>', content, re.DOTALL)
        if not title_m:
            title_m = re.search(r'data-testid="ad-title"[^>]*>(.*?)</', content, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""

        # Cena
        price_m = re.search(r'class="[^"]*price[^"]*"[^>]*>(.*?)</', content, re.DOTALL)
        price_text = re.sub(r'<[^>]+>', '', price_m.group(1)).strip() if price_m else ""

        # Opis/detalji
        desc_m = re.search(r'class="[^"]*description[^"]*"[^>]*>(.*?)</', content, re.DOTALL)
        desc_text = re.sub(r'<[^>]+>', ' ', desc_m.group(1)).strip() if desc_m else ""

        # Lokacija
        loc_m = re.search(r'class="[^"]*locality[^"]*"[^>]*>(.*?)</', content, re.DOTALL)
        if not loc_m:
            loc_m = re.search(r'data-testid="ad-address"[^>]*>(.*?)</', content, re.DOTALL)
        city = re.sub(r'<[^>]+>', '', loc_m.group(1)).strip() if loc_m else ""

        # Slika
        img_m = re.search(r'<img[^>]+(?:src|data-src)="([^"]+)"[^>]*>', content)
        img_url = img_m.group(1) if img_m else ""

        # URL
        link_m = re.search(r'<a[^>]+href="(/s-anzeige/[^"]+)"', content)
        ad_url = f"https://www.kleinanzeigen.de{link_m.group(1)}" if link_m else f"https://www.kleinanzeigen.de/s-anzeige/{ad_id}"

        # Parsiramo godinu i km iz opisa
        year_m = re.search(r'\b(20[0-2]\d|199\d)\b', desc_text + " " + title)
        km_m   = re.search(r'([\d.,]+)\s*km', desc_text + " " + title, re.IGNORECASE)

        price = _parse_price(price_text)
        if not price:
            continue

        listings.append({
            "id": ad_id,
            "title": title,
            "price_text": price_text,
            "description": desc_text,
            "city": city,
            "image": img_url,
            "url": ad_url,
            "year_text": year_m.group(1) if year_m else None,
            "km_text": km_m.group(1) if km_m else None,
        })

    print(f"[Kleinanzeigen] HTML parsing: {len(listings)} oglasa")
    return listings


def _parse_listing(item: dict) -> dict | None:
    try:
        item_id = str(item.get("id") or item.get("adId") or "")
        if not item_id:
            return None

        title = item.get("title") or item.get("subject") or ""
        price = _parse_price(item.get("price_text") or item.get("price") or 0)
        if not price:
            return None

        year = _parse_int(item.get("year_text") or item.get("year"))
        if year and year < 2000:
            return None

        # Izvuci make/model iz naslova
        make, model = _extract_make_model(title)

        images = []
        img = item.get("image") or item.get("imageUrl") or ""
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
            "mileage":      _parse_int(item.get("km_text") or item.get("mileage")),
            "fuel_type":    _normalize_fuel(item.get("fuel") or ""),
            "transmission": _normalize_transmission(item.get("transmission") or ""),
            "country":      "DE",
            "city":         (item.get("city") or "").strip() or None,
            "description":  title or None,
            "images":       images,
            "url":          item.get("url") or f"https://www.kleinanzeigen.de/s-anzeige/{item_id}",
        }
    except Exception as e:
        print(f"[Kleinanzeigen] Parse greška: {e}")
        return None


KNOWN_MAKES = [
    "Volkswagen", "VW", "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Toyota",
    "Ford", "Opel", "Skoda", "Renault", "Peugeot", "Hyundai", "Kia", "Volvo",
    "Seat", "Mazda", "Honda", "Nissan", "Fiat", "Citroën", "Citroen", "Porsche",
    "Land Rover", "Jeep", "Dacia", "Suzuki", "Mitsubishi", "Subaru", "Tesla",
    "Alfa Romeo", "Lexus", "Mini", "Smart", "Jaguar", "Bentley",
]


def _extract_make_model(title: str) -> tuple:
    if not title:
        return None, None
    for make in sorted(KNOWN_MAKES, key=len, reverse=True):
        if make.lower() in title.lower():
            rest  = re.sub(re.escape(make), "", title, flags=re.IGNORECASE).strip()
            words = rest.split()
            return make, (" ".join(words[:2]) if words else None)
    words = title.split()
    return (words[0] if words else None), (" ".join(words[1:3]) if len(words) > 1 else None)


class KleinanzeigenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            for page_num in range(1, max_pages + 1):
                url = f"{BASE_URL}/seite:{page_num}" if page_num > 1 else BASE_URL
                print(f"[Kleinanzeigen] Stranica {page_num}: {url}")

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                        print(f"[Kleinanzeigen] Status: {resp.status} | HTML dužina: ", end="")

                        if resp.status != 200:
                            print(f"[Kleinanzeigen] Nije 200 — prekidam")
                            break

                        html = await resp.text()
                        print(len(html))

                        items = _parse_listings_from_html(html)

                        if not items:
                            print(f"[Kleinanzeigen] Nema oglasa — kraj")
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
                    print(f"[Kleinanzeigen] Greška str.{page_num}: {e}")
                    break

        print(f"[Kleinanzeigen] Završeno — {len(all_listings)} oglasa")
        return all_listings
