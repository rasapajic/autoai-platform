import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from app.core.config import settings
from app.scrapers.base import BaseScraper
from app.services.location_parser import parse_city

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 20
MAX_LIMIT = 20
MAX_RETRIES = 2


class WillhabenScraper(BaseScraper):
    """Small-batch willhaben adapter for manual Austrian used-car imports."""

    SOURCE_NAME = "willhaben"
    BASE_URL = "https://www.willhaben.at"
    SEARCH_PATH = "/iad/gebrauchtwagen/auto/gebrauchtwagenboerse"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        query_text = " ".join(str(part).strip() for part in [filters.get("make"), filters.get("model")] if part)
        params = {
            "isNavigation": "true",
            "page": page,
        }

        if query_text:
            params["keyword"] = query_text
        if filters.get("min_price"):
            params["PRICE_FROM"] = filters["min_price"]
        if filters.get("max_price"):
            params["PRICE_TO"] = filters["max_price"]
        if filters.get("min_year"):
            params["YEAR_MODEL_FROM"] = filters["min_year"]
        if filters.get("max_year"):
            params["YEAR_MODEL_TO"] = filters["max_year"]
        if filters.get("max_km"):
            params["MILEAGE_TO"] = filters["max_km"]

        return f"{self.BASE_URL}{self.SEARCH_PATH}?{urlencode(params)}"

    async def scrape_listings(
        self,
        filters: dict,
        max_pages: int = 2,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        listings: list[dict] = []
        seen_external_ids: set[str] = set()
        seen_fingerprints: set[str] = set()
        safe_limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

        async with self:
            for page_num in range(1, max_pages + 1):
                if len(listings) >= safe_limit:
                    break

                url = self._build_url(filters, page=page_num)
                logger.info("[willhaben] Fetch page %s: %s", page_num, url)
                page = await self._get_page_with_retry(url)
                if not page:
                    break

                await self._dismiss_consent_if_present(page)
                await self._log_page_debug(page, page_num)
                raw_items = await self._extract_search_items(page)
                await page.close()

                if not raw_items:
                    logger.info("[willhaben] No listings found on page %s", page_num)
                    break

                for raw in raw_items:
                    if len(listings) >= safe_limit:
                        break

                    parsed = self._parse_listing(raw)
                    if parsed:
                        external_id = parsed.get("external_id")
                        if external_id in seen_external_ids:
                            logger.info("[willhaben] Duplicate external_id skipped: %s", external_id)
                            continue
                        fingerprint = self._listing_fingerprint(parsed)
                        if fingerprint and fingerprint in seen_fingerprints:
                            logger.info("[willhaben] Duplicate fingerprint skipped: %s", fingerprint)
                            continue
                        seen_external_ids.add(external_id)
                        if fingerprint:
                            seen_fingerprints.add(fingerprint)
                        listings.append(self.normalize(parsed))

                logger.info("[willhaben] Collected %s/%s listings", len(listings), safe_limit)
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
                        .filter(src => src && !src.includes('logo') && !src.startsWith('data:'))
                        .slice(0, 20);
                    const features = Array.from(document.querySelectorAll('li, [data-testid*="attribute"], [data-testid*="detail"]'))
                        .map(el => clean(el.textContent))
                        .filter(Boolean)
                        .slice(0, 50);
                    const description = clean(document.querySelector('[data-testid*="description"], [class*="description"]')?.textContent);
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
                logger.warning("[willhaben] Retry %s/%s in %ss", attempt, MAX_RETRIES, delay)
                await asyncio.sleep(delay)
        return None

    async def _dismiss_consent_if_present(self, page) -> bool:
        selectors = [
            "#didomi-notice-agree-button",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Akzeptieren')",
            "button:has-text('Zustimmen')",
            "button:has-text('Accept all')",
        ]
        for selector in selectors:
            try:
                button = page.locator(selector).first
                if await button.count():
                    await button.click(timeout=3000)
                    logger.info("[willhaben] Cookie/consent wall appeared: yes, accepted via %s", selector)
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        appeared = await self._consent_wall_present(page)
        logger.info("[willhaben] Cookie/consent wall appeared: %s", "yes" if appeared else "no")
        return appeared

    async def _consent_wall_present(self, page) -> bool:
        return await page.evaluate("""
            () => Boolean(
                document.querySelector('#didomi-notice') ||
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
                    '[data-testid*="search-result"]',
                    '[data-testid*="result"]',
                    '[data-testid*="ad"]',
                    '[class*="SearchResult"]',
                    'a[href*="/iad/gebrauchtwagen/d/auto/"]',
                    'a[href*="/iad/gebrauchtwagen/"]'
                ];
                return Object.fromEntries(selectors.map(selector => [selector, document.querySelectorAll(selector).length]));
            }
        """)
        logger.info("[willhaben] HTTP status: %s", status)
        logger.info("[willhaben] Final URL: %s", final_url)
        logger.info("[willhaben] Page title: %s", title)
        logger.info("[willhaben] Candidate selector counts: %s", counts)

        if settings.DEBUG:
            await self._write_debug_snapshot(page, page_num)

    async def _write_debug_snapshot(self, page, page_num: int) -> None:
        try:
            debug_dir = Path("/app/debug/willhaben")
            if not debug_dir.exists():
                debug_dir = Path.cwd() / "debug" / "willhaben"
            debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = debug_dir / f"willhaben_page_{page_num}_{stamp}.html"
            path.write_text(await page.content(), encoding="utf-8")
            logger.info("[willhaben] Debug HTML snapshot: %s", path)
        except Exception as exc:
            logger.warning("[willhaben] Debug HTML snapshot failed: %s", exc)

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
                const titleFromUrl = (url) => {
                    try {
                        const path = new URL(url, location.href).pathname;
                        const last = path.split('/').filter(Boolean).pop() || '';
                        return clean(last
                            .replace(/-\\d{6,}.*$/, '')
                            .replace(/[-_]+/g, ' ')
                            .replace(/\\b\\w/g, c => c.toUpperCase()));
                    } catch (_) {
                        return '';
                    }
                };
                const canonicalUrl = (url) => {
                    try {
                        const parsed = new URL(url, location.href);
                        parsed.hash = '';
                        parsed.search = '';
                        return parsed.href.replace(/\\/$/, '');
                    } catch (_) {
                        return String(url || '').split('#')[0].split('?')[0].replace(/\\/$/, '');
                    }
                };
                const idFromUrl = (url) => {
                    const value = String(url || '');
                    return value.match(/(?:-|\\/)(\\d{6,})(?:[\\/?#.]|$)/)?.[1]
                        || value.match(/[?&](?:id|adId|objectId)=(\\d{6,})/)?.[1]
                        || value.match(/(\\d{6,})/)?.[1]
                        || '';
                };
                const bestCardForLink = (link) => {
                    let node = link;
                    for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
                        const text = clean(node.textContent);
                        const listingLinks = Array.from(node.querySelectorAll('a[href*="/iad/gebrauchtwagen/d/auto/"], a[href*="/iad/gebrauchtwagen/"]'))
                            .map(a => a.href)
                            .filter(Boolean);
                        const uniqueLinks = Array.from(new Set(listingLinks));
                        const looksLikeCard = node.matches?.('article, [data-testid*="search-result"], [data-testid*="result"], [data-testid*="ad"], [class*="Card"], [class*="Item"], [class*="SearchResult"], li, div');
                        if (looksLikeCard && uniqueLinks.length === 1 && uniqueLinks[0] === link.href && text.length >= 20 && text.length <= 1200) {
                            return { card: node, scoped: true };
                        }
                        if (uniqueLinks.length > 1) break;
                    }
                    return { card: link, scoped: false };
                };
                const toItem = (card, linkArg = null, scoped = true) => {
                    const link = linkArg || card.querySelector('a[href*="/iad/gebrauchtwagen/d/auto/"], a[href*="/iad/gebrauchtwagen/"]');
                    const url = canonicalUrl(link?.href || '');
                    const rawText = scoped ? clean(card.textContent) : '';
                    const details = scoped ? Array.from(card.querySelectorAll('li, span, [data-testid*="attribute"], [data-testid*="detail"], [class*="Attribute"]'))
                        .filter(isVisible)
                        .map(el => clean(el.textContent))
                        .filter(Boolean)
                        .slice(0, 30) : [];
                    const images = scoped ? Array.from(card.querySelectorAll('img'))
                        .map(img => img.currentSrc || img.src || img.getAttribute('data-src'))
                        .filter(src => src && !src.includes('logo') && !src.startsWith('data:'))
                        .slice(0, 10) : [];
                    const title = (scoped ? pickText(card, [
                        'h2',
                        'h3',
                        '[data-testid*="title"]',
                        '[class*="title"]',
                        '[class*="Title"]'
                    ]) : '') || clean(link?.textContent || link?.getAttribute('aria-label') || link?.getAttribute('title')) || titleFromUrl(link?.href || '');

                    return {
                        external_id: idFromUrl(url) || card.getAttribute('data-adid') || card.getAttribute('data-id') || '',
                        title,
                        url,
                        price_raw: scoped ? pickPrice(card) : '',
                        mileage_raw: scoped ? pickMileage(card) : '',
                        year_raw: scoped ? pickYear(card) : '',
                        details,
                        images,
                        raw_text: rawText,
                        location_raw: scoped ? pickText(card, [
                            '[data-testid*="location"]',
                            '[class*="location"]',
                            '[class*="Location"]'
                        ]) : '',
                    };
                };

                let cards = Array.from(document.querySelectorAll('article, [data-testid*="search-result"], [data-testid*="result"], [class*="SearchResult"]'))
                    .filter(card => {
                        const links = Array.from(card.querySelectorAll('a[href*="/iad/gebrauchtwagen/d/auto/"], a[href*="/iad/gebrauchtwagen/"]'))
                            .map(a => a.href);
                        return new Set(links).size === 1;
                    });

                const cardItems = cards.map(card => toItem(card)).filter(item => item.url);
                const linkItems = Array.from(document.querySelectorAll('a[href*="/iad/gebrauchtwagen/d/auto/"], a[href*="/iad/gebrauchtwagen/"]'))
                    .filter(isVisible)
                    .map(link => {
                        const candidate = bestCardForLink(link);
                        return toItem(candidate.card, link, candidate.scoped);
                    })
                    .filter(item => item.url);
                const seenIds = new Set();
                const domItems = [...cardItems, ...linkItems].filter(item => {
                    const dedupeKey = item.external_id || item.url;
                    if (seenIds.has(dedupeKey)) return false;
                    seenIds.add(dedupeKey);
                    return true;
                });
                if (domItems.length) return domItems;

                const scriptItems = [];
                for (const script of Array.from(document.querySelectorAll('script'))) {
                    const text = script.textContent || '';
                    if (!text.includes('/iad/gebrauchtwagen/') || !text.includes('price')) continue;
                    try {
                        const jsonText = text.trim().replace(/^window\\.__.*?=\\s*/, '').replace(/;$/, '');
                        const parsed = JSON.parse(jsonText);
                        const seen = new Set();
                        const walk = (node) => {
                            if (!node || typeof node !== 'object') return;
                            const url = node.url || node.seoUrl || node.href || node.adUrl;
                            const title = node.name || node.title || node.heading;
                            if (typeof url === 'string' && url.includes('/iad/gebrauchtwagen/') && title && !seen.has(url)) {
                                seen.add(url);
                                scriptItems.push({
                                    external_id: String(node.id || node.adId || node.uuid || ''),
                                    title: String(title || ''),
                                    url,
                                    price_raw: String(node.price || node.priceForDisplay || node.displayPrice || ''),
                                    mileage_raw: String(node.mileage || node.mileageForDisplay || ''),
                                    year_raw: String(node.year || node.firstRegistration || ''),
                                    details: [],
                                    images: Array.isArray(node.images) ? node.images.map(img => img.url || img.src || img).filter(Boolean).slice(0, 10) : [],
                                    location_raw: String(node.location || node.address || ''),
                                });
                            }
                            for (const value of Object.values(node)) {
                                if (Array.isArray(value)) value.slice(0, 100).forEach(walk);
                                else if (value && typeof value === 'object') walk(value);
                            }
                        };
                        walk(parsed);
                    } catch (_) {}
                }
                return scriptItems;
            }
        """)

    def _parse_listing(self, raw: dict) -> dict | None:
        url = self._canonical_url(urljoin(self.BASE_URL, raw.get("url") or ""))
        external_id = self._external_id(raw, url)
        if not external_id or not url:
            logger.info("[willhaben] Candidate skipped url=%r external_id=%r", url, external_id)
            return None

        raw_text = raw.get("raw_text") or " ".join(raw.get("details", []))
        title = self._clean_title(raw.get("title")) or self._title_from_text(raw_text) or self._title_from_url(url)
        if not title:
            logger.info("[willhaben] Candidate skipped url=%r reason=missing title raw_text=%r", url, raw_text[:300])
            return None

        make, model = self._parse_title(title)
        raw_price = raw.get("price_raw")
        raw_mileage = (
            raw.get("mileage_raw")
            or self._find_detail(raw.get("details", []), r"\b\d[\d\s.,]{0,12}\s*km\b")
            or self._find_match(raw_text, r"\b\d[\d\s.,]{0,12}\s*km\b")
        )
        raw_price = raw_price or self._find_match(raw_text, r"(?:€|EUR)\s*\d[\d\s.,']+|\d[\d\s.,']+\s*(?:€|EUR)")
        price = self._parse_price_eur(raw_price)
        mileage = self._parse_mileage(raw_mileage)
        year = self._parse_year(raw.get("year_raw")) or self._parse_year_from_details(raw.get("details", [])) or self._parse_year(raw_text)
        fuel = self._parse_fuel(raw.get("details", []))
        transmission = self._parse_transmission(raw.get("details", []))

        logger.info("[willhaben] Candidate URL: %s", url)
        logger.info("[willhaben] Candidate raw text: %r", raw_text[:500])
        logger.info("[willhaben] Parsed title: %r", title)
        logger.info("[willhaben] Price raw=%r parsed=%s", raw_price, price)
        logger.info("[willhaben] Mileage raw=%r parsed=%s", raw_mileage, mileage)

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
            "country": "AT",
            "city": self._parse_city(raw.get("location_raw", ""), raw.get("details", [])),
            "images": raw.get("images", []),
            "url": url,
            "condition": "used",
        }

    def _external_id(self, raw: dict, url: str) -> str | None:
        match = (
            re.search(r"(?:-|/)(\d{6,})(?:[/?#.]|$)", url)
            or re.search(r"[?&](?:id|adId|objectId)=(\d{6,})", url)
            or re.search(r"(\d{6,})", url)
        )
        candidate = match.group(1) if match else str(raw.get("external_id") or "").strip()
        candidate = re.sub(r"[^a-zA-Z0-9_-]", "", candidate)
        return f"wh_{candidate}" if candidate else None

    def _canonical_url(self, url: str) -> str:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))

    def _clean_title(self, value: str | None) -> str | None:
        if not value:
            return None
        title = re.sub(r"\s+", " ", str(value)).strip()
        title = re.sub(r"\b(€|EUR)\s*\d[\d\s.,']+.*$", "", title).strip()
        return title[:120] if title else None

    def _title_from_text(self, value: str | None) -> str | None:
        if not value:
            return None
        text = re.sub(r"\s+", " ", str(value)).strip()
        if not text:
            return None
        text = re.split(r"(?:€|EUR)\s*\d|\d[\d\s.,']+\s*(?:€|EUR)|\b\d[\d\s.,]{0,12}\s*km\b", text, maxsplit=1, flags=re.I)[0]
        return self._clean_title(text)

    def _title_from_url(self, url: str) -> str | None:
        path = url.split("?", 1)[0].rstrip("/")
        slug = path.rsplit("/", 1)[-1]
        slug = re.sub(r"-\d{6,}.*$", "", slug)
        slug = re.sub(r"[-_]+", " ", slug).strip()
        if not slug:
            return None
        return " ".join(word.capitalize() for word in slug.split())[:120]

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
            logger.warning("[willhaben] Ignoring invalid price raw=%r parsed=%s", value, price)
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
            logger.warning("[willhaben] Ignoring invalid mileage raw=%r parsed=%s", value, mileage)
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

    def _parse_transmission(self, details: list[str]) -> str | None:
        for detail in details:
            lowered = detail.lower()
            if any(word in lowered for word in ["automatik", "automatic", "schaltgetriebe", "manuell", "manual"]):
                return detail
        return None

    def _parse_city(self, location: str, details: list[str]) -> str | None:
        candidates = [location, *details]
        for candidate in candidates:
            cleaned = re.sub(r"\s+", " ", str(candidate or "")).strip()
            if not cleaned:
                continue
            city = parse_city(cleaned, "AT")
            if city:
                return city
            if re.search(r"\b(österreich|austria|wien|graz|linz|salzburg|innsbruck|klagenfurt|st\.?\s*pölten)\b", cleaned, re.I):
                return cleaned[:100]
        return None

    def _find_detail(self, details: list[str], pattern: str) -> str | None:
        for detail in details:
            if re.search(pattern, detail, re.I):
                return detail
        return None

    def _find_match(self, value: str | None, pattern: str) -> str | None:
        if not value:
            return None
        match = re.search(pattern, str(value), re.I)
        return match.group(0) if match else None

    def _listing_fingerprint(self, data: dict) -> str | None:
        images = data.get("images") or []
        first_image = str(images[0]) if images else ""
        title = re.sub(r"\W+", "", str(data.get("variant") or "").lower())
        price = str(data.get("price") or "")
        mileage = str(data.get("mileage") or "")
        if not first_image or not title or not price:
            return None
        return "|".join([title, first_image, price, mileage])
