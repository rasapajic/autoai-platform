import asyncio
import logging
import re
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.autoscout24.com/lst"
MARKETS = ("A", "D", "NL", "I", "B")
COUNTRY_CODES = {
    "a": "AT",
    "d": "DE",
    "nl": "NL",
    "i": "IT",
    "b": "BE",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

KNOWN_MAKES = [
    "Alfa Romeo", "Aston Martin", "Audi", "BMW", "Bentley", "Bugatti",
    "Citroën", "Citroen", "Dacia", "Ferrari", "Fiat", "Ford", "Honda",
    "Hyundai", "Jaguar", "Jeep", "Kia", "Lamborghini", "Land Rover",
    "Lexus", "Maserati", "Mazda", "Mercedes-Benz", "Mini", "Mitsubishi",
    "Nissan", "Opel", "Peugeot", "Porsche", "Renault", "Rolls-Royce",
    "Seat", "Skoda", "Smart", "Subaru", "Suzuki", "Tesla", "Toyota",
    "Volkswagen", "Volvo",
]


def _parse_int(value) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _parse_price(value) -> float | None:
    price = _parse_int(value)
    if price is None or price < 500 or price > 2_000_000:
        return None
    return float(price)


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


def _normalize_fuel(value: str) -> str | None:
    lowered = value.lower()
    mapping = {
        "diesel": "diesel",
        "gasoline": "petrol",
        "petrol": "petrol",
        "benzin": "petrol",
        "electric": "electric",
        "elektro": "electric",
        "hybrid": "hybrid",
        "lpg": "lpg",
        "cng": "cng",
    }
    for key, normalized in mapping.items():
        if key in lowered:
            return normalized
    return value.strip() or None


def _normalize_transmission(text: str) -> str | None:
    lowered = text.lower()
    if any(word in lowered for word in ("automatic", "automatik", "automat", "dsg", "cvt")):
        return "automatic"
    if any(word in lowered for word in ("manual", "manuell", "schaltgetriebe")):
        return "manual"
    return None


def _parse_location(value: str) -> tuple[str | None, str | None, str | None]:
    value = re.sub(r"\s+", " ", value or "").strip()
    match = re.match(r"^([A-Z]{1,2})-(\d{4,5})\s+(.+)$", value)
    if not match:
        return None, None, None
    raw_country, postal_code, city = match.groups()
    country = COUNTRY_CODES.get(raw_country.lower(), raw_country)
    return country, postal_code, city.strip()


def _parse_card(article) -> dict | None:
    external_id = str(article.get("data-guid") or article.get("id") or "").strip()
    if not external_id:
        return None

    title_node = article.select_one("h2, h3")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    make, model = _extract_make_model(title)

    price_node = article.select_one('[data-testid="regular-price"]')
    price = _parse_price(article.get("data-price") or (price_node.get_text(" ", strip=True) if price_node else None))
    if not price:
        return None

    registration_node = article.select_one('[data-testid="VehicleDetails-calendar"]')
    registration = article.get("data-first-registration") or (
        registration_node.get_text(" ", strip=True) if registration_node else ""
    )
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", registration)
    year = int(year_match.group(1)) if year_match else None

    mileage_node = article.select_one('[data-testid="VehicleDetails-mileage_odometer"]')
    mileage = _parse_int(
        article.get("data-mileage")
        or (mileage_node.get_text(" ", strip=True) if mileage_node else None)
    )

    fuel_node = article.select_one('[data-testid="VehicleDetails-gas_pump"]')
    fuel = _normalize_fuel(fuel_node.get_text(" ", strip=True) if fuel_node else "")

    power_node = article.select_one('[data-testid="VehicleDetails-speedometer"]')
    power_text = power_node.get_text(" ", strip=True) if power_node else ""
    power_match = re.search(r"(\d+)\s*kW", power_text, re.IGNORECASE)
    power_kw = int(power_match.group(1)) if power_match else None

    location_node = article.select_one('[data-testid="dealer-address"]')
    location_text = location_node.get_text(" ", strip=True) if location_node else ""
    country, postal_code, city = _parse_location(location_text)
    if not country:
        country = COUNTRY_CODES.get(str(article.get("data-listing-country") or "").lower())
    if not postal_code:
        postal_code = article.get("data-listing-zip-code") or None

    images = []
    for image in article.select('img[data-testid="list-item-image"], img[src]'):
        src = image.get("src") or image.get("data-src")
        if src and src.startswith("http") and src not in images:
            images.append(src)

    return {
        "external_id": f"as24_{external_id}",
        "source": "autoscout24",
        "make": make,
        "model": model,
        "year": year,
        "price": price,
        "currency": "EUR",
        "mileage": mileage,
        "fuel_type": fuel,
        "transmission": _normalize_transmission(article.get_text(" ", strip=True)),
        "engine_power_kw": power_kw,
        "country": country,
        "city": city,
        "postal_code": postal_code,
        "description": title or None,
        "images": images[:6],
        "url": f"https://www.autoscout24.com/offers/{external_id}",
    }


class AutoScout24Scraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 3) -> list[dict]:
        all_listings: list[dict] = []
        seen_ids: set[str] = set()
        markets = (filters.get("country") or "",)
        if not markets[0]:
            markets = MARKETS

        timeout = aiohttp.ClientTimeout(total=35)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout, trust_env=True) as session:
            for market in markets:
                for page in range(1, max_pages + 1):
                    params = {
                        "atype": "C",
                        "cy": str(market).upper(),
                        "page": page,
                        "sort": "age",
                        "desc": 0,
                        "ustate": "N,U",
                    }
                    if filters.get("min_price"):
                        params["pricefrom"] = filters["min_price"]
                    if filters.get("max_price"):
                        params["priceto"] = filters["max_price"]
                    if filters.get("min_year"):
                        params["fregfrom"] = filters["min_year"]
                    if filters.get("max_year"):
                        params["fregto"] = filters["max_year"]
                    if filters.get("max_km"):
                        params["kmto"] = filters["max_km"]

                    logger.info("[AutoScout24] %s page %s: %s?%s", market, page, BASE_URL, urlencode(params))
                    try:
                        async with session.get(BASE_URL, params=params) as response:
                            if response.status != 200:
                                logger.warning("[AutoScout24] HTTP %s", response.status)
                                break
                            html = await response.text()
                    except Exception as exc:
                        logger.warning("[AutoScout24] %s page %s failed: %s", market, page, exc)
                        break

                    soup = BeautifulSoup(html, "html.parser")
                    cards = soup.select('article[data-testid="list-item"], article[data-guid]')
                    if not cards:
                        break

                    added = 0
                    for card in cards:
                        parsed = _parse_card(card)
                        if parsed and parsed["external_id"] not in seen_ids:
                            seen_ids.add(parsed["external_id"])
                            all_listings.append(parsed)
                            added += 1
                    logger.info("[AutoScout24] %s page %s: +%s", market, page, added)
                    await asyncio.sleep(0.75)

        return all_listings
