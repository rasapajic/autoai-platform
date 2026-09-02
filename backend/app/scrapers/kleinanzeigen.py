import asyncio
import re

import aiohttp
from bs4 import BeautifulSoup

BASE_URL = "https://www.kleinanzeigen.de/s-autos"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Referer": "https://www.kleinanzeigen.de/",
}

KNOWN_MAKES = [
    "Alfa Romeo", "Audi", "BMW", "BYD", "Citroën", "Citroen", "Cupra",
    "Dacia", "Fiat", "Ford", "Honda", "Hyundai", "Jaguar", "Jeep", "Kia",
    "Land Rover", "Lexus", "Mazda", "Mercedes-Benz", "Mercedes", "Mini",
    "Mitsubishi", "Nissan", "Opel", "Peugeot", "Polestar", "Porsche",
    "Renault", "Seat", "Skoda", "Smart", "Subaru", "Suzuki", "Tesla",
    "Toyota", "Volkswagen", "Volvo", "VW", "Xpeng",
]


def _parse_int(value) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _parse_price(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d[\d.]*)(?:,(\d{1,2}))?\s*€", value)
    if not match:
        return None
    euros = match.group(1).replace(".", "")
    cents = (match.group(2) or "0").ljust(2, "0")
    price = float(f"{euros}.{cents}")
    return price if 500 <= price <= 500_000 else None


def _extract_make_model(title: str) -> tuple[str | None, str | None]:
    for make in sorted(KNOWN_MAKES, key=len, reverse=True):
        if title.lower().startswith(make.lower()):
            rest = title[len(make):].strip().split()
            return make, " ".join(rest[:2]) or None
    words = title.split()
    return (
        words[0] if words else None,
        " ".join(words[1:3]) if len(words) > 1 else None,
    )


def _extract_location(article) -> tuple[str | None, str | None]:
    for text_node in article.stripped_strings:
        cleaned = re.sub(r"\s+", " ", text_node).strip()
        match = re.fullmatch(r"(\d{5})\s+(.{2,80})", cleaned)
        if match:
            return match.group(1), match.group(2).strip()
    return None, None


def _parse_article(article) -> dict | None:
    item_id = str(article.get("data-adid") or "").strip()
    href = str(article.get("data-href") or "").strip()
    if not item_id or "-216-" not in href:
        return None

    title_node = article.select_one("h3, h2")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    text = re.sub(r"\s+", " ", article.get_text(" ", strip=True))
    price = _parse_price(text)
    if not price:
        return None

    make, model = _extract_make_model(title)
    year_match = re.search(r"\bEZ\s+\d{1,2}/(19\d{2}|20\d{2})\b", text, re.IGNORECASE)
    if not year_match:
        year_match = re.search(r"\b(19[7-9]\d|20[0-2]\d)\b", title)
    year = int(year_match.group(1)) if year_match else None

    mileage_match = re.search(r"([\d.]+)\s*km\b", text, re.IGNORECASE)
    mileage = _parse_int(mileage_match.group(1)) if mileage_match else None
    postal_code, city = _extract_location(article)

    images = []
    for image in article.select("img"):
        src = image.get("src") or image.get("data-src")
        if src and src.startswith("http") and src not in images:
            images.append(re.sub(r"\$_\w+\.AUTO", "$_57.AUTO", src))

    url = href if href.startswith("http") else f"https://www.kleinanzeigen.de{href}"
    return {
        "external_id": f"ka_{item_id}",
        "source": "kleinanzeigen",
        "make": make,
        "model": model,
        "year": year,
        "price": price,
        "currency": "EUR",
        "mileage": mileage,
        "country": "DE",
        "city": city,
        "postal_code": postal_code,
        "description": text[:1000] or title or None,
        "images": images[:6],
        "url": url,
    }


def _parse_listings_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []
    for article in soup.select("article[data-adid][data-href]"):
        parsed = _parse_article(article)
        if parsed:
            listings.append(parsed)
    return listings


class KleinanzeigenScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list[dict]:
        all_listings: list[dict] = []
        seen_ids: set[str] = set()
        timeout = aiohttp.ClientTimeout(total=35)

        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout, trust_env=True) as session:
            for page in range(1, max_pages + 1):
                url = f"{BASE_URL}/c216" if page == 1 else f"{BASE_URL}/seite:{page}/c216"
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            break
                        html = await response.text(encoding="utf-8", errors="replace")
                except Exception:
                    break

                items = _parse_listings_from_html(html)
                if not items:
                    break
                for item in items:
                    if item["external_id"] not in seen_ids:
                        seen_ids.add(item["external_id"])
                        all_listings.append(item)
                await asyncio.sleep(0.75)

        return all_listings
