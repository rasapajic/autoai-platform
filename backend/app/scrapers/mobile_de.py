import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin

from app.core.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 20
MAX_LIMIT = 20
MAX_RETRIES = 2


class MobileDeScraper(BaseScraper):
    """Small-batch Mobile.de adapter for manual MVP imports."""

    SOURCE_NAME = "mobile_de"
    BASE_URL = "https://suchen.mobile.de"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        params = {
            "dam": "false",
            "isSearchRequest": "true",
            "pageNumber": page,
            "ref": "srp",
            "s": "Car",
            "sb": "rel",
            "vc": "Car",
        }

        if filters.get("make"):
            make_id = self._make_id(filters["make"])
            if make_id:
                params["ms"] = f"{make_id};{filters.get('model_id', '')};;"
        if filters.get("model"):
            params["q"] = " ".join(str(part).strip() for part in [filters.get("make"), filters.get("model")] if part)
        if filters.get("min_price"):
            params["minPrice"] = filters["min_price"]
        if filters.get("max_price"):
            params["maxPrice"] = filters["max_price"]
        if filters.get("min_year"):
            params["minFirstRegistrationDate"] = f"{filters['min_year']}-01-01"
        if filters.get("max_year"):
            params["maxFirstRegistrationDate"] = f"{filters['max_year']}-12-31"
        if filters.get("max_km"):
            params["maxMileage"] = filters["max_km"]
        if filters.get("fuel_type"):
            fuel = self._fuel_code(filters["fuel_type"])
            if fuel:
                params["ft"] = fuel

        return f"{self.BASE_URL}/fahrzeuge/search.html?{urlencode(params)}"

    async def scrape_listings(
        self,
        filters: dict,
        max_pages: int = 2,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        listings: list[dict] = []
        safe_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

        async with self:
            for page_num in range(1, max_pages + 1):
                if len(listings) >= safe_limit:
                    break

                url = self._build_url(filters, page=page_num)
                logger.info("[Mobile.de] Fetch page %s: %s", page_num, url)
                page = await self._get_page_with_retry(url)
                if not page:
                    break

                await self._dismiss_consent_if_present(page)
                await self._log_page_debug(page, page_num)
                raw_items = await self._extract_search_items(page)
                await page.close()

                if not raw_items:
                    logger.info("[Mobile.de] No listings found on page %s", page_num)
                    break

                for raw in raw_items:
                    if len(listings) >= safe_limit:
                        break

                    parsed = self._parse_listing(raw)
                    if parsed:
                        listings.append(self.normalize(parsed))

                logger.info("[Mobile.de] Collected %s/%s listings", len(listings), safe_limit)
                await asyncio.sleep(2)

        return listings

    async def scrape_detail(self, url: str) -> dict:
        async with self:
            page = await self._get_page_with_retry(url)
            if not page:
                return {}

            data = await page.evaluate("""
                () => {
                    const clean = (value) => value?.replace(/\\s+/g, ' ')?.trim() || '';
                    const images = Array.from(document.querySelectorAll('img'))
                        .map(img => img.currentSrc || img.src || img.getAttribute('data-src'))
                        .filter(src => src && !src.includes('logo'))
                        .slice(0, 20);
                    const features = Array.from(document.querySelectorAll('li, [data-testid*="feature"], [data-testid*="equipment"]'))
                        .map(el => clean(el.textContent))
                        .filter(Boolean)
                        .slice(0, 50);
                    const description = clean(document.querySelector('[data-testid*="description"], .seller-notes')?.textContent);
                    return { description, features, images };
                }
            """)

            await page.close()
            return data

    async def _get_page_with_retry(self, url: str):
        for attempt in range(1, MAX_RETRIES + 1):
            page = await self.get_page(url)
            if page:
                return page
            if attempt < MAX_RETRIES:
                delay = 2 * attempt
                logger.warning("[Mobile.de] Retry %s/%s in %ss", attempt, MAX_RETRIES, delay)
                await asyncio.sleep(delay)
        return None

    async def _dismiss_consent_if_present(self, page) -> bool:
        selectors = [
            "#mde-consent-accept-btn",
            "button:has-text('Accept all')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Einverstanden')",
            "button:has-text('Zustimmen')",
        ]
        for selector in selectors:
            try:
                button = page.locator(selector).first
                if await button.count():
                    await button.click(timeout=3000)
                    logger.info("[Mobile.de] Cookie/consent wall appeared: yes, accepted via %s", selector)
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        appeared = await self._consent_wall_present(page)
        logger.info("[Mobile.de] Cookie/consent wall appeared: %s", "yes" if appeared else "no")
        return appeared

    async def _consent_wall_present(self, page) -> bool:
        return await page.evaluate("""
            () => Boolean(
                document.querySelector('[id*="consent"]') ||
                document.querySelector('[class*="consent"]') ||
                document.body?.innerText?.toLowerCase().includes('cookie') ||
                document.body?.innerText?.toLowerCase().includes('datenschutz')
            )
        """)

    async def _log_page_debug(self, page, page_num: int) -> None:
        title = await page.title()
        status = getattr(page, "autoai_status", None)
        final_url = page.url
        counts = await page.evaluate("""
            () => {
                const selectors = [
                    'article',
                    '[data-testid*="result"]',
                    '[data-testid*="listing"]',
                    '[class*="result-item"]',
                    '[class*="ResultItem"]',
                    'a[href*="/fahrzeuge/details.html"]',
                    'a[href*="/auto-inserat/"]'
                ];
                return Object.fromEntries(selectors.map(selector => [selector, document.querySelectorAll(selector).length]));
            }
        """)
        logger.info("[Mobile.de] HTTP status: %s", status)
        logger.info("[Mobile.de] Final URL: %s", final_url)
        logger.info("[Mobile.de] Page title: %s", title)
        logger.info("[Mobile.de] Candidate selector counts: %s", counts)

        if settings.DEBUG:
            await self._write_debug_snapshot(page, page_num)

    async def _write_debug_snapshot(self, page, page_num: int) -> None:
        try:
            debug_dir = Path("/app/debug/mobile_de")
            if not debug_dir.exists():
                debug_dir = Path.cwd() / "debug" / "mobile_de"
            debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = debug_dir / f"mobile_de_page_{page_num}_{stamp}.html"
            path.write_text(await page.content(), encoding="utf-8")
            logger.info("[Mobile.de] Debug HTML snapshot: %s", path)
        except Exception as exc:
            logger.warning("[Mobile.de] Debug HTML snapshot failed: %s", exc)

    async def _extract_search_items(self, page) -> list[dict]:
        return await page.evaluate("""
            () => {
                const clean = (value) => value?.replace(/\\s+/g, ' ')?.trim() || '';
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    return style && style.display !== 'none' && style.visibility !== 'hidden' && el.getClientRects().length > 0;
                };
                const pickText = (root, selectors) => {
                    for (const selector of selectors) {
                        const el = root.querySelector(selector);
                        if (!isVisible(el)) continue;
                        const value = clean(el.textContent);
                        if (value) return value;
                    }
                    return '';
                };
                const pickPrice = (root) => {
                    const selectors = [
                        '[data-testid*="price"]',
                        '[class*="price"]',
                        '[class*="Price"]'
                    ];
                    for (const selector of selectors) {
                        for (const el of Array.from(root.querySelectorAll(selector))) {
                            if (!isVisible(el)) continue;
                            const value = clean(el.textContent || el.getAttribute('aria-label') || el.getAttribute('title'));
                            if (!value || !/[€]|eur/i.test(value)) continue;
                            if (/month|monat|mtl|leasing|finanzierung|rate/i.test(value)) continue;
                            return value;
                        }
                    }
                    const text = clean(root.textContent);
                    return text.match(/(?:€|EUR)\\s*\\d[\\d\\s.,']+|\\d[\\d\\s.,']+\\s*(?:€|EUR)/i)?.[0] || '';
                };
                const pickMileage = (root) => {
                    const text = clean(root.textContent);
                    return text.match(/\\b\\d[\\d\\s.,]{0,12}\\s*km\\b/i)?.[0] || '';
                };
                const pickYear = (root) => {
                    const text = clean(root.textContent);
                    return text.match(/\\b(19|20)\\d{2}\\b/)?.[0] || '';
                };

                let cards = Array.from(document.querySelectorAll('article, [data-testid*="result"], [data-testid*="listing"], [class*="ResultItem"], [class*="result-item"]'))
                    .filter(card => card.querySelector('a[href*="/fahrzeuge/details.html"], a[href*="/auto-inserat/"]'));

                if (!cards.length) {
                    cards = Array.from(document.querySelectorAll('a[href*="/fahrzeuge/details.html"], a[href*="/auto-inserat/"]'))
                        .map(link => link.closest('article, [data-testid], [class*="Card"], [class*="Item"], div'))
                        .filter(Boolean);
                    cards = Array.from(new Set(cards));
                }

                return cards.map(card => {
                    const link = card.querySelector('a[href*="/fahrzeuge/details.html"], a[href*="/auto-inserat/"]');
                    const details = Array.from(card.querySelectorAll('li, span, [data-testid*="detail"], [class*="detail"], [class*="Attribute"]'))
                        .filter(isVisible)
                        .map(el => clean(el.textContent))
                        .filter(Boolean)
                        .slice(0, 30);
                    const images = Array.from(card.querySelectorAll('img'))
                        .map(img => img.currentSrc || img.src || img.getAttribute('data-src'))
                        .filter(src => src && !src.includes('logo'))
                        .slice(0, 10);
                    const title = pickText(card, [
                        'h2',
                        'h3',
                        '[data-testid*="title"]',
                        '[class*="title"]',
                        '[class*="Title"]'
                    ]) || clean(link?.textContent || link?.getAttribute('aria-label'));

                    return {
                        external_id: card.getAttribute('data-ad-id') || card.getAttribute('data-listing-id') || '',
                        title,
                        url: link?.href || '',
                        price_raw: pickPrice(card),
                        mileage_raw: pickMileage(card),
                        year_raw: pickYear(card),
                        details,
                        images,
                        location_raw: pickText(card, ['[data-testid*="seller"]', '[class*="seller"]', '[class*="Seller"]']),
                    };
                });
            }
        """)

    def _parse_listing(self, raw: dict) -> dict | None:
        url = urljoin(self.BASE_URL, raw.get("url") or "")
        external_id = self._external_id(raw, url)
        if not external_id or not url:
            return None

        title = raw.get("title", "")
        make, model = self._parse_title(title)
        raw_price = raw.get("price_raw")
        raw_mileage = raw.get("mileage_raw") or self._find_detail(raw.get("details", []), r"\b\d[\d\s.,]{0,12}\s*km\b")
        price = self._parse_price_eur(raw_price)
        mileage = self._parse_mileage(raw_mileage)
        year = self._parse_year(raw.get("year_raw")) or self._parse_year_from_details(raw.get("details", []))
        fuel = self._parse_fuel(raw.get("details", []))

        logger.info("[Mobile.de] Price raw=%r parsed=%s", raw_price, price)
        logger.info("[Mobile.de] Mileage raw=%r parsed=%s", raw_mileage, mileage)

        return {
            "external_id": external_id,
            "make": make,
            "model": model,
            "variant": title or None,
            "year": year,
            "price": price,
            "mileage": mileage,
            "fuel_type": fuel,
            "country": "DE",
            "city": self._parse_city(raw.get("location_raw", "")),
            "images": raw.get("images", []),
            "url": url,
            "condition": "used",
        }

    def _external_id(self, raw: dict, url: str) -> str | None:
        candidate = str(raw.get("external_id") or "").strip()
        if not candidate:
            match = re.search(r"(?:id=|/)(\d{6,})(?:[/?#.]|$)", url)
            candidate = match.group(1) if match else ""
        candidate = re.sub(r"[^a-zA-Z0-9_-]", "", candidate)
        return f"mob_{candidate}" if candidate else None

    def _parse_title(self, title: str) -> tuple[str | None, str | None]:
        known_makes = [
            "Mercedes-Benz", "Volkswagen", "Alfa Romeo", "Land Rover",
            "BMW", "Audi", "Ford", "Toyota", "Honda", "Renault", "Peugeot",
            "Opel", "Skoda", "Seat", "Kia", "Hyundai", "Mazda", "Volvo",
            "Porsche", "Fiat", "Citroen", "Citroën", "Dacia", "Nissan",
            "Mitsubishi", "Tesla",
        ]
        lowered = title.lower()
        for make in known_makes:
            if lowered.startswith(make.lower()) or f" {make.lower()} " in f" {lowered} ":
                rest = re.sub(re.escape(make), "", title, count=1, flags=re.I).strip()
                words = rest.split()
                model = " ".join(words[:2]).strip() if words else None
                return make, model
        words = title.split()
        return (words[0], words[1] if len(words) > 1 else None) if words else (None, None)

    def _parse_price_eur(self, value: str | None) -> int | None:
        if not value:
            return None
        match = re.search(r"(\d[\d\s.,']*)", str(value))
        if not match:
            return None
        digits = re.sub(r"\D", "", match.group(1))
        if not digits:
            return None
        price = int(digits)
        if price < 100 or price > 5_000_000:
            logger.warning("[Mobile.de] Ignoring invalid price raw=%r parsed=%s", value, price)
            return None
        return price

    def _parse_mileage(self, value: str | None) -> int | None:
        if not value:
            return None
        match = re.search(r"\b(\d[\d\s.,]{0,12})\s*km\b", str(value), re.I)
        if not match:
            return None
        digits = re.sub(r"\D", "", match.group(1))
        if not digits:
            return None
        mileage = int(digits)
        if mileage < 0 or mileage > 2_000_000:
            logger.warning("[Mobile.de] Ignoring invalid mileage raw=%r parsed=%s", value, mileage)
            return None
        return mileage

    def _parse_year(self, value: str | None) -> int | None:
        if not value:
            return None
        match = re.search(r"\b(19|20)\d{2}\b", str(value))
        return int(match.group(0)) if match else None

    def _parse_year_from_details(self, details: list[str]) -> int | None:
        for detail in details:
            year = self._parse_year(detail)
            if year:
                return year
        return None

    def _parse_fuel(self, details: list[str]) -> str | None:
        for detail in details:
            lowered = detail.lower()
            if any(word in lowered for word in ["diesel", "benzin", "petrol", "gasoline", "elektro", "electric", "hybrid", "lpg", "cng"]):
                return detail
        return None

    def _parse_city(self, location: str) -> str | None:
        if not location:
            return None
        cleaned = re.sub(r"\s+", " ", location).strip()
        return cleaned[:100] if cleaned else None

    def _find_detail(self, details: list[str], pattern: str) -> str | None:
        for detail in details:
            if re.search(pattern, detail, re.I):
                return detail
        return None

    def _make_id(self, make: str) -> str:
        make_ids = {
            "AUDI": "1900",
            "BMW": "3500",
            "CITROEN": "5900",
            "CITROËN": "5900",
            "DACIA": "6600",
            "FIAT": "8800",
            "FORD": "9000",
            "HONDA": "11000",
            "HYUNDAI": "11600",
            "KIA": "13200",
            "MAZDA": "16800",
            "MERCEDES": "17200",
            "MERCEDES-BENZ": "17200",
            "NISSAN": "18700",
            "OPEL": "19000",
            "PEUGEOT": "19300",
            "PORSCHE": "20100",
            "RENAULT": "20700",
            "SEAT": "22500",
            "SKODA": "22900",
            "TESLA": "135",
            "TOYOTA": "24100",
            "VOLKSWAGEN": "25200",
            "VW": "25200",
            "VOLVO": "25100",
        }
        return make_ids.get(str(make).strip().upper(), "")

    def _fuel_code(self, fuel_type: str) -> str:
        fuel_codes = {
            "diesel": "DIESEL",
            "petrol": "PETROL",
            "electric": "ELECTRICITY",
            "hybrid": "HYBRID",
            "lpg": "LPG",
            "cng": "CNG",
        }
        return fuel_codes.get(str(fuel_type).strip().lower(), "")
