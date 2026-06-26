import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from app.core.config import settings
from app.scrapers.base import BaseScraper
from app.services.location_parser import parse_city

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 20
MAX_LIMIT = 50
MAX_RETRIES = 2


class AutoScout24Scraper(BaseScraper):
    """Small-batch AutoScout24 adapter for manual MVP imports."""

    SOURCE_NAME = "autoscout24"
    BASE_URL = "https://www.autoscout24.com"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        path = "/lst"
        if filters.get("make"):
            path += f"/{self._slug(filters['make'])}"
            if filters.get("model"):
                path += f"/{self._slug(filters['model'])}"

        params = {
            "atype": "C",
            "page": page,
            "sort": "age",
            "desc": "0",
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
        if filters.get("country"):
            params["cy"] = self._country_code(filters["country"])
        if filters.get("fuel_type"):
            fuel_map = {
                "petrol": "B",
                "diesel": "D",
                "electric": "E",
                "hybrid": "M",
                "lpg": "L",
                "cng": "C",
            }
            params["fuel"] = fuel_map.get(filters["fuel_type"], "")

        query = "&".join(f"{k}={v}" for k, v in params.items() if v not in ("", None))
        return f"{self.BASE_URL}{path}?{query}"

    async def scrape_listings(
        self,
        filters: dict,
        max_pages: int = 2,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        listings: list[dict] = []
        safe_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
        search_country = self._country_iso(filters.get("country")) if filters.get("country") else None

        async with self:
            for page_num in range(1, max_pages + 1):
                if len(listings) >= safe_limit:
                    break

                url = self._build_url(filters, page=page_num)
                logger.info("[AutoScout24] Fetch page %s: %s", page_num, url)
                page = await self._get_page_with_retry(url)
                if not page:
                    break

                await self._dismiss_consent_if_present(page)
                await self._log_page_debug(page, page_num)
                raw_items = await self._extract_search_items(page)
                await page.close()

                if not raw_items:
                    logger.info("[AutoScout24] No listings found on page %s", page_num)
                    break

                for raw in raw_items:
                    if len(listings) >= safe_limit:
                        break

                    raw["search_country"] = search_country
                    parsed = self._parse_listing(raw)
                    if parsed:
                        listings.append(self.normalize(parsed))

                logger.info("[AutoScout24] Collected %s/%s listings", len(listings), safe_limit)
                await asyncio.sleep(2)

        return listings

    def _slug(self, value: str) -> str:
        slug = str(value).strip().lower()
        aliases = {
            "mercedes benz": "mercedes-benz",
            "vw": "volkswagen",
        }
        slug = aliases.get(slug, slug)
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        return quote(slug.strip("-"))

    def _country_code(self, value: str) -> str:
        mapping = {
            "DE": "D",
            "GERMANY": "D",
            "DEUTSCHLAND": "D",
            "AT": "A",
            "AUSTRIA": "A",
            "ÖSTERREICH": "A",
            "OSTERREICH": "A",
            "NL": "NL",
            "NETHERLANDS": "NL",
            "NEDERLAND": "NL",
            "BE": "B",
            "BELGIUM": "B",
            "BELGIQUE": "B",
            "BELGIE": "B",
            "IT": "I",
            "ITALY": "I",
            "ITALIA": "I",
            "FR": "F",
            "FRANCE": "F",
        }
        return mapping.get(str(value).strip().upper(), str(value).strip().upper())

    def _country_iso(self, value: str | None) -> str | None:
        if not value:
            return None
        mapping = {
            "D": "DE",
            "DE": "DE",
            "GERMANY": "DE",
            "DEUTSCHLAND": "DE",
            "A": "AT",
            "AT": "AT",
            "AUSTRIA": "AT",
            "ÖSTERREICH": "AT",
            "OSTERREICH": "AT",
            "B": "BE",
            "BE": "BE",
            "BELGIUM": "BE",
            "BELGIQUE": "BE",
            "BELGIE": "BE",
            "NL": "NL",
            "NETHERLANDS": "NL",
            "NEDERLAND": "NL",
            "F": "FR",
            "FR": "FR",
            "FRANCE": "FR",
            "I": "IT",
            "IT": "IT",
            "ITALY": "IT",
            "ITALIA": "IT",
        }
        return mapping.get(str(value).strip().upper())

    async def scrape_detail(self, url: str) -> dict:
        async with self:
            page = await self._get_page_with_retry(url)
            if not page:
                return {}

            data = await page.evaluate("""
                () => {
                    const clean = (value) => value?.replace(/\\s+/g, ' ')?.trim() || '';
                    const text = (selector) => clean(document.querySelector(selector)?.textContent);
                    const features = Array.from(document.querySelectorAll('li, [data-testid*="equipment"]'))
                        .map(el => clean(el.textContent))
                        .filter(Boolean)
                        .slice(0, 50);
                    const images = Array.from(document.querySelectorAll('img'))
                        .map(img => img.currentSrc || img.src)
                        .filter(src => src && !src.includes('logo'))
                        .slice(0, 20);

                    return {
                        description: text('[data-testid="description"], .cldt-stage-description'),
                        features,
                        images,
                    };
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
                logger.warning("[AutoScout24] Retry %s/%s in %ss", attempt, MAX_RETRIES, delay)
                await asyncio.sleep(delay)
        return None

    async def _dismiss_consent_if_present(self, page) -> bool:
        selectors = [
            "#onetrust-accept-btn-handler",
            "button:has-text('Accept all')",
            "button:has-text('Accept All')",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('I agree')",
        ]
        for selector in selectors:
            try:
                button = page.locator(selector).first
                if await button.count():
                    await button.click(timeout=3000)
                    logger.info("[AutoScout24] Cookie/consent wall appeared: yes, accepted via %s", selector)
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        appeared = await self._consent_wall_present(page)
        logger.info("[AutoScout24] Cookie/consent wall appeared: %s", "yes" if appeared else "no")
        return appeared

    async def _consent_wall_present(self, page) -> bool:
        return await page.evaluate("""
            () => Boolean(
                document.querySelector('#onetrust-banner-sdk') ||
                document.querySelector('[id*="sp_message"]') ||
                document.body?.innerText?.toLowerCase().includes('privacy settings') ||
                document.body?.innerText?.toLowerCase().includes('cookie')
            )
        """)

    async def _log_page_debug(self, page, page_num: int) -> None:
        title = await page.title()
        status = getattr(page, "autoai_status", None)
        final_url = page.url
        counts = await page.evaluate("""
            () => {
                const selectors = [
                    'article.cldt-summary-full-item',
                    'article[data-testid="list-item"]',
                    'div[data-testid="list-item"]',
                    '[data-testid="list-item"]',
                    '[data-testid*="vehicle-card"]',
                    '[class*="VehicleCard"]',
                    'article',
                    'a[href*="/offers/"]',
                    'a[href*="/angebote/"]'
                ];
                return Object.fromEntries(selectors.map(selector => [selector, document.querySelectorAll(selector).length]));
            }
        """)
        logger.info("[AutoScout24] HTTP status: %s", status)
        logger.info("[AutoScout24] Final URL: %s", final_url)
        logger.info("[AutoScout24] Page title: %s", title)
        logger.info("[AutoScout24] Candidate selector counts: %s", counts)

        if settings.DEBUG:
            await self._write_debug_snapshot(page, page_num)

    async def _write_debug_snapshot(self, page, page_num: int) -> None:
        try:
            debug_dir = Path("/app/debug/autoscout24")
            if not debug_dir.exists():
                debug_dir = Path.cwd() / "debug" / "autoscout24"
            debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = debug_dir / f"autoscout24_page_{page_num}_{stamp}.html"
            path.write_text(await page.content(), encoding="utf-8")
            logger.info("[AutoScout24] Debug HTML snapshot: %s", path)
        except Exception as exc:
            logger.warning("[AutoScout24] Debug HTML snapshot failed: %s", exc)

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
                        const value = clean(el?.textContent);
                        if (value) return value;
                    }
                    return '';
                };
                const pickMileage = (root) => {
                    const selectors = [
                        '[data-testid*="mileage"]',
                        '[data-testid*="Mileage"]',
                        '[class*="mileage"]',
                        '[class*="Mileage"]',
                        '.cldt-summary-attributes-item'
                    ];
                    const candidates = [];
                    for (const selector of selectors) {
                        for (const el of Array.from(root.querySelectorAll(selector))) {
                            if (!isVisible(el)) continue;
                            const value = clean(el.textContent);
                            if (/\\b\\d[\\d\\s.,]{0,12}\\s*km\\b/i.test(value)) {
                                candidates.push(value);
                            }
                        }
                    }
                    return candidates[0] || '';
                };
                const pickPrice = (root) => {
                    const selectors = [
                        '[data-testid="regular-price"]',
                        '[data-testid="price-label"]',
                        '[data-type="price_block"] .cldt-price',
                        '[class*="Price"]'
                    ];
                    for (const selector of selectors) {
                        for (const el of Array.from(root.querySelectorAll(selector))) {
                            if (!isVisible(el)) continue;
                            const clone = el.cloneNode(true);
                            clone.querySelectorAll('sup, [aria-hidden="true"]').forEach(node => node.remove());
                            const directText = Array.from(el.childNodes)
                                .filter(node => node.nodeType === Node.TEXT_NODE)
                                .map(node => node.textContent)
                                .join('');
                            const value = clean(directText || clone.textContent || el.getAttribute('aria-label') || el.getAttribute('title'));
                            if (!value || !/[€]|eur/i.test(value)) continue;
                            if (/month|monat|mtl|leasing|finanzierung|rate/i.test(value)) continue;
                            return value;
                        }
                    }
                    return '';
                };

                const cardSelectors = [
                    'article.cldt-summary-full-item',
                    'article[data-testid="list-item"]',
                    'div[data-testid="list-item"]',
                    '[data-testid="list-item"]',
                    '[data-testid*="list-item"]',
                    '[data-testid*="vehicle-card"]',
                    '[class*="ListItem"]',
                    '[class*="VehicleCard"]',
                    'article'
                ];

                let cards = [];
                for (const selector of cardSelectors) {
                    cards = Array.from(document.querySelectorAll(selector))
                        .filter(card => card.querySelector('a[href*="/offers/"], a[href*="/angebote/"]'));
                    if (cards.length) break;
                }

                if (!cards.length) {
                    cards = Array.from(document.querySelectorAll('a[href*="/offers/"], a[href*="/angebote/"]'))
                        .map(link => link.closest('article, [data-testid], [class*="Card"], [class*="Item"], div'))
                        .filter(Boolean);
                    cards = Array.from(new Set(cards));
                }

                return cards.map(card => {
                    const link = card.querySelector('a[href*="/offers/"], a[href*="/angebote/"]');
                    const details = Array.from(card.querySelectorAll(
                        '.cldt-summary-attributes-item, [data-testid="VehicleDetails"] span, li, [class*="VehicleDetail"]'
                    ))
                        .filter(isVisible)
                        .map(el => clean(el.textContent))
                        .filter(Boolean);

                    const images = Array.from(card.querySelectorAll('img'))
                        .map(img => img.currentSrc || img.src)
                        .filter(src => src && !src.includes('logo'))
                        .slice(0, 10);

                    return {
                        external_id: card.getAttribute('data-guid') || card.getAttribute('data-id') || card.id || '',
                        title: pickText(card, ['h2', '[data-testid="title"]', '[data-testid="list-item-title"]']) || clean(link?.getAttribute('aria-label')),
                        url: link?.href || '',
                        price_raw: pickPrice(card),
                        mileage_raw: pickMileage(card),
                        details,
                        images,
                        location_raw: pickText(card, [
                            '.cldt-summary-seller-contact-country',
                            '[data-testid="sellerinfo"]',
                            '[class*="SellerInfo"]'
                        ]),
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
        price = self._parse_price_eur(raw_price)
        raw_mileage = raw.get("mileage_raw") or self._find_mileage_text(raw.get("details", []))
        mileage = self._parse_mileage(raw_mileage)
        year = fuel = transmission = power = body_type = None
        logger.info("[AutoScout24] Price raw=%r parsed=%s", raw_price, price)
        logger.info("[AutoScout24] Mileage raw=%r parsed=%s", raw_mileage, mileage)

        for detail in raw.get("details", []):
            lowered = detail.lower()
            if re.search(r"\\b(19|20)\\d{2}\\b", detail):
                year = re.search(r"\\b(19|20)\\d{2}\\b", detail).group(0)
            elif any(word in lowered for word in ["diesel", "petrol", "benzin", "electric", "hybrid", "lpg", "cng"]):
                fuel = detail
            elif any(word in lowered for word in ["automatic", "manual", "automat", "schaltgetriebe"]):
                transmission = detail
            elif "kw" in lowered or "ps" in lowered or "hp" in lowered:
                power = detail
            elif any(word in lowered for word in ["suv", "limousine", "estate", "kombi", "coupe", "cabrio", "van"]):
                body_type = detail

        country, city = self._parse_location(raw.get("location_raw", ""))
        country = country or raw.get("search_country")

        return {
            "external_id": external_id,
            "make": make,
            "model": model,
            "variant": title or None,
            "year": year,
            "price": price,
            "mileage": mileage,
            "fuel_type": fuel,
            "transmission": transmission,
            "engine_power_kw": self._parse_power_kw(power),
            "body_type": body_type,
            "country": country,
            "city": city,
            "images": raw.get("images", []),
            "url": url,
            "condition": "used",
        }

    def _parse_price_eur(self, value: str | None) -> int | None:
        if not value:
            return None

        text = str(value)
        match = re.search(r"(\d[\d\s.,']*)", text)
        if not match:
            return None

        number = match.group(1).strip()
        number = self._strip_price_footnote(number)

        if "," in number and "." in number:
            last_comma = number.rfind(",")
            last_dot = number.rfind(".")
            decimal_separator = "," if last_comma > last_dot else "."
            thousands_separator = "." if decimal_separator == "," else ","
            normalized = number.replace(thousands_separator, "")
            if re.search(rf"\{decimal_separator}\d{{1,2}}$", normalized):
                normalized = normalized.rsplit(decimal_separator, 1)[0]
            digits = re.sub(r"\D", "", normalized)
        elif "," in number or "." in number:
            separator = "," if "," in number else "."
            parts = number.split(separator)
            if len(parts[-1]) == 3:
                digits = "".join(parts)
            elif len(parts) == 2 and len(parts[-1]) == 2 and len(parts[0]) == 1:
                digits = parts[0] + parts[-1] + "00"
            elif len(parts) == 2 and len(parts[-1]) == 2 and len(parts[0]) == 2:
                digits = parts[0] + parts[-1] + "0"
            elif len(parts) == 2 and len(parts[-1]) <= 2:
                digits = parts[0]
            else:
                digits = "".join(parts)
            digits = re.sub(r"\D", "", digits)
        else:
            digits = re.sub(r"\D", "", number)

        if not digits:
            return None

        price = int(digits)
        if price < 100 or price > 5_000_000:
            logger.warning("[AutoScout24] Ignoring invalid price raw=%r parsed=%s", value, price)
            return None

        return price

    def _strip_price_footnote(self, number: str) -> str:
        normalized = number.replace(" ", "").replace("'", "")
        if re.match(r"^\d{1,3}([.,])\d{4}$", normalized):
            return normalized[:-1]
        if re.match(r"^\d{1,3}([.,])\d{3}([.,])\d{4}$", normalized):
            return normalized[:-1]
        return number

    def _find_mileage_text(self, details: list[str]) -> str | None:
        first_candidate = None
        for detail in details:
            if re.search(r"\b\d[\d\s.,]{0,12}\s*km\b", detail, re.I):
                first_candidate = first_candidate or detail
                if self._parse_mileage(detail) is not None:
                    return detail
        return first_candidate

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
            logger.warning("[AutoScout24] Ignoring invalid mileage raw=%r parsed=%s", value, mileage)
            return None

        return mileage

    def _external_id(self, raw: dict, url: str) -> str | None:
        candidate = str(raw.get("external_id") or "").strip()
        if not candidate:
            match = re.search(r"([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})", url, re.I)
            candidate = match.group(1) if match else ""

        candidate = re.sub(r"[^a-zA-Z0-9_-]", "", candidate)
        return f"as24_{candidate}" if candidate else None

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

    def _parse_location(self, location: str) -> tuple[str | None, str | None]:
        if not location:
            return None, None

        parts = [part.strip() for part in re.split(r"[,|]", location) if part.strip()]
        lowered = location.lower()
        country_map = {
            "germany": "DE",
            "deutschland": "DE",
            "austria": "AT",
            "österreich": "AT",
            "osterreich": "AT",
            "belgium": "BE",
            "belgique": "BE",
            "belgie": "BE",
            "belgien": "BE",
            "netherlands": "NL",
            "nederland": "NL",
            "france": "FR",
            "frankreich": "FR",
            "italy": "IT",
            "italia": "IT",
            "italien": "IT",
        }
        country = next((code for label, code in country_map.items() if label in lowered), None)
        city = parse_city(location, country)
        if not city and parts:
            city = parse_city(parts[0], country)
        return country, city

    def _parse_power_kw(self, power_str: str | None) -> int | None:
        if not power_str:
            return None
        kw_match = re.search(r"(\\d+)\\s*kw", power_str.lower())
        if kw_match:
            return int(kw_match.group(1))
        ps_match = re.search(r"(\\d+)\\s*(ps|hp)", power_str.lower())
        if ps_match:
            return round(int(ps_match.group(1)) * 0.7355)
        return None
