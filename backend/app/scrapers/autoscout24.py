import asyncio
import logging
import re
from urllib.parse import urlencode
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "diesel": "diesel", "dizel": "diesel",
    "petrol": "petrol", "benzin": "petrol", "gasoline": "petrol",
    "electric": "electric", "elektro": "electric", "elektrisch": "electric",
    "hybrid": "hybrid", "plug-in": "hybrid",
    "lpg": "lpg", "autogas": "lpg",
    "cng": "cng", "erdgas": "cng",
}

TRANSMISSION_MAP = {
    "automatic": "automatic", "automat": "automatic", "automatik": "automatic",
    "dsg": "automatic", "cvt": "automatic", "tiptronic": "automatic",
    "manual": "manual", "manuell": "manual", "schaltgetriebe": "manual",
}

KNOWN_MAKES = [
    "Alfa Romeo", "Aston Martin", "Audi", "BMW", "Bentley", "Bugatti",
    "Citroën", "Citroen", "Dacia", "Ferrari", "Fiat", "Ford",
    "Honda", "Hyundai", "Jaguar", "Jeep", "Kia", "Lamborghini",
    "Land Rover", "Lexus", "Maserati", "Mazda", "Mercedes-Benz",
    "Mini", "Mitsubishi", "Nissan", "Opel", "Peugeot", "Porsche",
    "Renault", "Rolls-Royce", "Seat", "Skoda", "Smart", "Subaru",
    "Suzuki", "Tesla", "Toyota", "Volkswagen", "Volvo",
]


class AutoScout24Scraper(BaseScraper):
    SOURCE_NAME = "autoscout24"
    BASE_URL = "https://www.autoscout24.com"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        params = {
            "atype": "C",
            "page": page,
            "sort": "age",
            "desc": 0,
        }
        mapping = {
            "make": "mmvmk0", "model": "mmvmd0",
            "min_price": "pricefrom", "max_price": "priceto",
            "min_year": "fregfrom", "max_year": "fregto",
            "max_km": "kmto",
        }
        fuel_map = {
            "petrol": "B", "diesel": "D", "electric": "E",
            "hybrid": "M", "lpg": "L", "cng": "C",
        }
        for key, param in mapping.items():
            if filters.get(key):
                params[param] = filters[key]
        if filters.get("fuel_type"):
            code = fuel_map.get(filters["fuel_type"])
            if code:
                params["fuel"] = code
        if filters.get("country"):
            params["countrycode"] = filters["country"].upper()
        return f"{self.BASE_URL}/lst?{urlencode(params)}"

    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list[dict]:
        all_listings = []
        seen_ids = set()

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[AutoScout24] Stranica {page_num}: {url}")

                page = None
                for attempt in range(3):
                    try:
                        page = await self.get_page(url, wait_for=None)
                        if page:
                            break
                    except Exception as e:
                        logger.warning(f"[AutoScout24] Pokušaj {attempt+1} neuspešan: {e}")
                        await asyncio.sleep(2 ** attempt)

                if not page:
                    logger.warning(f"[AutoScout24] Preskačem stranicu {page_num}")
                    continue

                try:
                    raw_items = await page.evaluate(self._listing_js())
                except Exception as e:
                    logger.error(f"[AutoScout24] JS evaluate greška: {e}")
                    await page.close()
                    continue

                if not raw_items:
                    logger.info(f"[AutoScout24] Nema oglasa — završavam")
                    await page.close()
                    break

                page_saved = 0
                for raw in raw_items:
                    try:
                        parsed = self._parse_listing(raw)
                        if not parsed:
                            continue
                        if parsed["external_id"] in seen_ids:
                            continue
                        seen_ids.add(parsed["external_id"])
                        all_listings.append(parsed)
                        page_saved += 1
                    except Exception as e:
                        logger.warning(f"[AutoScout24] Parse greška: {e}")

                logger.info(f"[AutoScout24] Str {page_num}: +{page_saved} | Ukupno: {len(all_listings)}")
                await page.close()
                await asyncio.sleep(2)

        return all_listings

    async def scrape_detail(self, url: str) -> dict:
        async with self:
            page = await self.get_page(url, wait_for=None)
            if not page:
                return {}
            try:
                data = await page.evaluate("""
                    () => {
                        const getText = sel => document.querySelector(sel)?.textContent?.trim() || null;
                        const getAll  = sel => Array.from(document.querySelectorAll(sel))
                                                    .map(e => e.textContent.trim()).filter(Boolean);
                        const specs = {};
                        document.querySelectorAll('[data-item-key]').forEach(el => {
                            specs[el.getAttribute('data-item-key')] = el.textContent.trim();
                        });
                        const images = Array.from(document.querySelectorAll(
                            '.image-gallery-image img, [class*="gallery"] img'
                        )).map(i => i.src || i.getAttribute('data-src')).filter(Boolean);
                        const features = getAll('.sc-expandable-element li, [class*="equipment"] li');
                        return {
                            description:        getText('.cldt-stage-description, [class*="description"]'),
                            seller_name:        getText('.cldt-stage-vendor-info-name, [class*="seller-name"]'),
                            seller_type:        getText('[class*="dealer-type"], [class*="seller-type"]'),
                            vin:                specs['vin'] || null,
                            fuel_consumption:   specs['fuel-consumption'] || null,
                            co2:                specs['co2-emission'] || null,
                            doors:              specs['doors'] || null,
                            seats:              specs['seats'] || null,
                            drivetrain:         specs['drivetrain'] || null,
                            first_registration: specs['first-registration'] || null,
                            accident_free:      (specs['accident'] || '').toLowerCase().includes('unfall') ? false : null,
                            features:           features,
                            images:             images.slice(0, 20),
                        };
                    }
                """)
                return data or {}
            except Exception as e:
                logger.error(f"[AutoScout24] Detail greška {url}: {e}")
                return {}
            finally:
                await page.close()

    def _listing_js(self) -> str:
        return """
        () => {
            const cleanPrice = (text) => {
                if (!text) return '';
                // Ukloni superscript Unicode karaktere (footnote markeri)
                let clean = text.replace(/[\u00B9\u00B2\u00B3\u2070-\u2079]+/g, '');
                // Ukloni izolovane cifre na kraju (npr. "18.999 1" -> "18.999")
                clean = clean.replace(/\\s+\\d+\\s*$/, '');
                return clean.trim();
            };

            const containers = [
                ...document.querySelectorAll('article.cldt-summary-full-item'),
                ...document.querySelectorAll('article[data-guid]'),
                ...document.querySelectorAll('[data-testid="listing-item"]'),
            ];
            const seen = new Set();
            const items = containers.filter(el => {
                const id = el.getAttribute('data-guid') || el.id;
                if (!id || seen.has(id)) return false;
                seen.add(id);
                return true;
            });
            return items.map(item => {
                const id = item.getAttribute('data-guid') || item.getAttribute('id') || '';
                const titleEl = item.querySelector('h2, h3, [class*="title"]');
                const title = titleEl?.textContent?.trim() || '';
                const linkEl = item.querySelector('a[href*="/offers/"]')
                            || item.querySelector('a[href*="autoscout24"]')
                            || item.querySelector('h2 a, h3 a')
                            || item.querySelector('a');
                const url = linkEl?.href
                         || (id ? 'https://www.autoscout24.com/offers/' + id : '');
                const priceEl = item.querySelector('.cldt-price, [data-type="price_block"] .cldt-price, [class*="price"]');
                const price_raw = cleanPrice(priceEl?.textContent || '');
                const detailEls = item.querySelectorAll(
                    '.cldt-summary-attributes-item, [class*="attribute"], [class*="detail"] li'
                );
                const details = Array.from(detailEls).map(d => d.textContent.trim()).filter(Boolean);
                const images = Array.from(item.querySelectorAll('img'))
                    .map(img => img.src || img.getAttribute('data-src'))
                    .filter(s => s && s.startsWith('http') && !s.includes('logo'));
                const locEl = item.querySelector(
                    '.cldt-summary-seller-contact-country, [class*="country"], [class*="location"], [class*="city"]'
                );
                const location_raw = locEl?.textContent?.trim() || '';
                return { id, title, url, price_raw, details, images: images.slice(0, 10), location_raw };
            });
        }
        """

    def _parse_listing(self, raw: dict) -> dict | None:
        ext_id = raw.get("id", "").strip()
        url = raw.get("url", "").strip()
        if "?" in url:
            url = url.split("?")[0]
        if not ext_id or not url:
            return None

        title = raw.get("title", "").strip()
        make, model = self._parse_title(title)
        details = raw.get("details", [])

        price_raw = raw.get("price_raw", "")
        price_eur = self._parse_price_eur(price_raw)
        logger.debug(f"[AutoScout24] price_raw='{price_raw}' → {price_eur}")

        mileage_raw = year = fuel_type = transmission = power_str = None
        for d in details:
            if not d:
                continue
            if "km" in d.lower() and any(c.isdigit() for c in d):
                mileage_raw = mileage_raw or d
            elif self._extract_year(d):
                year = year or self._extract_year(d)
            elif any(k in d.lower() for k in FUEL_MAP):
                fuel_type = fuel_type or self._normalize_fuel(d)
            elif any(k in d.lower() for k in TRANSMISSION_MAP):
                transmission = transmission or self._normalize_transmission(d)
            elif re.search(r'\d+\s*(kw|ps|hp)', d.lower()):
                power_str = power_str or d

        location_raw = raw.get("location_raw", "")
        country, city = self._parse_location(location_raw)

        return {
            "external_id":     f"as24_{ext_id}",
            "source":          self.SOURCE_NAME,
            "title":           title,
            "make":            make,
            "model":           model,
            "year":            year,
            "price_raw":       price_raw or None,
            "price":           price_eur,
            "currency":        "EUR",
            "mileage_raw":     mileage_raw,
            "mileage":         self._parse_mileage_km(mileage_raw),
            "fuel_type":       fuel_type,
            "transmission":    transmission,
            "engine_power_kw": self._parse_power_kw(power_str),
            "country":         country or "DE",
            "city":            city,
            "images":          raw.get("images", []),
            "url":             url,
        }

    def _parse_title(self, title: str) -> tuple:
        if not title:
            return None, None
        for make in sorted(KNOWN_MAKES, key=len, reverse=True):
            if make.lower() in title.lower():
                rest = re.sub(re.escape(make), "", title, flags=re.IGNORECASE).strip()
                words = rest.split()
                model = " ".join(words[:2]) if words else None
                return make, model or None
        words = title.split()
        return (words[0] if words else None), (" ".join(words[1:3]) if len(words) > 1 else None)

    def _parse_price_eur(self, raw: str) -> int | None:
        if not raw:
            return None
        # Izvuci prvi broj sa separatorima
        m = re.search(r'\d[\d.,]+\d', raw)
        if m:
            num = m.group(0).replace('.', '').replace(',', '')
            try:
                val = int(num)
                # Realna cena automobila: max 2 miliona EUR
                return val if val <= 2000000 else None
            except ValueError:
                pass
        digits = re.sub(r'[^\d]', '', raw)
        return int(digits[:6]) if digits else None

    def _parse_mileage_km(self, raw: str) -> int | None:
        if not raw:
            return None
        m = re.search(r'\d[\d.,]+\d', raw)
        if m:
            num = m.group(0).replace('.', '').replace(',', '')
            try:
                return int(num)
            except ValueError:
                pass
        digits = re.sub(r'[^\d]', '', raw)
        return int(digits[:7]) if digits else None

    def _extract_year(self, text: str) -> int | None:
        m = re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', text)
        return int(m.group(1)) if m else None

    def _normalize_fuel(self, val: str) -> str | None:
        v = val.lower()
        for k, norm in FUEL_MAP.items():
            if k in v:
                return norm
        return None

    def _normalize_transmission(self, val: str) -> str | None:
        v = val.lower()
        for k, norm in TRANSMISSION_MAP.items():
            if k in v:
                return norm
        return None

    def _parse_power_kw(self, raw: str) -> int | None:
        if not raw:
            return None
        kw = re.search(r'(\d+)\s*kw', raw.lower())
        if kw:
            return int(kw.group(1))
        ps = re.search(r'(\d+)\s*(ps|hp)', raw.lower())
        if ps:
            return round(int(ps.group(1)) * 0.7355)
        return None

    def _parse_location(self, raw: str) -> tuple:
        if not raw:
            return "DE", None
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) >= 2:
            return parts[-1], parts[0]
        return "DE", parts[0]
