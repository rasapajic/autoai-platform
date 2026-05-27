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
    if not text:
        return ""
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&#x[0-9a-fA-F]+;', '', text)
    text = re.sub(r'&\w+;', ' ', text)
    text = text.split("\n")[0].strip()
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

    # DEBUG — prikaži deo HTML-a oko article tagova
    article_pos = html.find('<article')
    if article_pos >= 0:
        print(f"[Kleinanzeigen] Article tag preview: {html[article_pos:article_pos+500]}")
    else:
        print(f"[Kleinanzeigen] Nema <article> tagova!")
        # Potraži alternativne strukture
        for tag in ['data-adid', 'aditem', 'adlist', 'l-container']:
            if tag in html:
                pos = html.find(tag)
                print(f"[Kleinanzeigen] Pronađeno '{tag}' na poz {pos}: {html[max(0,pos-50):pos+200]}")
                break
        print(f"[Kleinanzeigen] HTML preview (5000-6000): {html[5000:6000]}")
        return []

    # Pokušaj 1: data-adid + data-href
    pattern1 = re.compile(
        r'<article[^>]+data-adid="(\d+)"[^>]*data-href="([^"]*)"[^>]*>(.*?)</article>',
        re.DOTALL
    )
    matches1 = list(pattern1.finditer(html))
    print(f"[Kleinanzeigen] Pattern1 (data-adid+data-href): {len(matches1)} matches")

    # Pokušaj 2: samo data-adid
    pattern2 = re.compile(
        r'<article[^>]+data-adid="(\d+)"[^>]*>(.*?)</article>',
        re.DOTALL
    )
    matches2 = list(pattern2.finditer(html))
    print(f"[Kleinanzeigen] Pattern2 (samo data-adid): {len(matches2)} matches")

    # Pokušaj 3: article sa klasom
    pattern3 = re.compile(
        r'<article[^>]+class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>',
        re.DOTALL
    )
    matches3 = list(pattern3.finditer(html))
    print(f"[Kleinanzeigen] Pattern3 (class=aditem): {len(matches3)} matches")

    # Koristi koji god radi
    if matches1:
        active_matches = [(m.group(1), m.group(2), m.group(3)) for m in matches1]
    elif matches2:
        active_matches = [(m.group(1), "", m.group(2)) for m in matches2]
    elif matches3:
        active_matches = [("", "", m.group(1)) for m in matches3]
    else:
        print(f"[Kleinanzeigen] Nijedan pattern ne odgovara")
        return []

    for ad_id, ad_href, content in active_matches:
        # Samo auto kategorija
        if ad_href and "-216-" not in ad_href:
            continue

        # Naslov
        title = ""
        for pat in [
            r'class="[^"]*text-module-begin[^"]*"[^>]*>(.*?)</a>',
            r'class="[^"]*ellipsis[^"]*"[^>]*>(.*?)</a>',
            r'<a[^>]+href="[^"]*-216-[^"]*"[^>]*>(.*?)</a>',
        ]:
            m = re.search(pat, content, re.DOTALL)
            if m:
                title = _clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 200)
                break
        if not title:
            m = re.search(r'<h[23][^>]*>(.*?)</h[23]>', content, re.DOTALL)
            if m:
                title = _clean_text(re.sub(r'<[^>]+>', '', m.group(1)), 200)

        # ID iz href ako nije u data-adid
        if not ad_id:
            m = re.search(r'/(\d+)-216-', ad_href or content)
            if m:
                ad_id = m.group(1)

        # Cena
        price_text = ""
        for pat in [
            r'class="[^"]*aditem-main--middle--price[^"]*"[^>]*>(.*?)</p>',
            r'class="[^"]*price[^"]*"[^>]*>(.*?)</',
            r'€\s*([\d.,]+)',
        ]:
            m = re.search(pat, content, re.DOTALL)
            if m:
                price_text = _clean_text(re.sub(r'<[^>]+>', '', m.group(1) if '(' in pat else m.group(0)), 50)
                break

        # Lokacija
        city = ""
        for pat in [
            r'class="[^"]*aditem-main--top--left[^"]*"[^>]*>(.*?)</p>',
            r'class="[^"]*locality[^"]*"[^>]*>(.*?)</',
            r'<span[^>]*>\s*(\d{5}\s+\w+)',
        ]:
            m = re.search(pat, content, re.DOTALL)
            if m:
                raw = re.sub(r'<[^>]+>', ' ', m.group(1))
                city = _clean_text(raw, 100)
                city = re.sub(r'\b(Heute|Gestern|\d{2}\.\d{2}\.\d{4}|\d+\.\d+\.)\b.*', '', city).strip()[:100]
                break

        # Slika
        img_url = ""
        m = re.search(r'<img[^>]+(?:src|data-src)="(https://img\.kleinanzeigen\.de[^"]+)"', content)
        if m:
            img_url = m.group(1)

        # URL
        if ad_href:
            ad_url = f"https://www.kleinanzeigen.de{ad_href}" if ad_href.startswith("/") else ad_href
        elif ad_id:
            ad_url = f"https://www.kleinanzeigen.de/s-anzeige/{ad_id}"
        else:
            continue

        # Godište i km iz naslova
        year_m = re.search(r'\b(20[0-2]\d|199\d)\b', title)
        km_m   = re.search(r'([\d.]+)\s*km', title, re.IGNORECASE)

        price = _parse_price(price_text)
        if not price:
            continue
        if not ad_id:
            continue

        listings.append({
            "id":      ad_id,
            "title":   title,
            "price":   price,
            "city":    city,
            "image":   img_url,
            "url":     ad_url,
            "year":    _parse_int(year_m.group(1)) if year_m else None,
            "mileage": _parse_int(km_m.group(1).replace(".", "")) if km_m else None,
        })

    print(f"[Kleinanzeigen] Ukupno parsiranih: {len(listings)}")
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

        city = _clean_text(item.get("city") or "", 100)

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
                        print(f"[Kleinanzeigen] Status: {resp.status} | Dužina: {resp.content_length}")
                        if resp.status != 200:
                            break

                        html = await resp.text()
                        print(f"[Kleinanzeigen] HTML dužina: {len(html)}")
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
