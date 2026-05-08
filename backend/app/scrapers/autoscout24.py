import asyncio
import logging
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


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
        if filters.get("make"):
            params["mmvmk0"] = filters["make"]
        if filters.get("model"):
            params["mmvmd0"] = filters["model"]
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
        query = "&".join(f"{k}={v}" for k, v in params.items() if v != "")
        return f"{self.BASE_URL}/lst?{query}"

    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list[dict]:
        all_listings = []

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[AutoScout24] Stranica {page_num}: {url}")

                page = await self.get_page(url, wait_for=None)
                if not page:
                    break

                listings_data = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('article.cldt-summary-full-item');
                        return Array.from(items).map(item => {
                            const id = item.getAttribute('data-guid') || '';

                            const linkEl = item.querySelector('a[href*="/offers/"]') ||
                                           item.querySelector('a[href*="autoscout24"]') ||
                                           item.querySelector('h2 a') ||
                                           item.querySelector('a');

                            const titleEl = item.querySelector('h2');

                            const priceEl = item.querySelector('[data-type="price_block"] .cldt-price') ||
                                            item.querySelector('.cldt-price') ||
                                            item.querySelector('[class*="price"]');

                            const detailEls = item.querySelectorAll('.cldt-summary-attributes-item');
                            const detailTexts = Array.from(detailEls).map(d => d.textContent.trim()).filter(t => t);

                            const images = Array.from(item.querySelectorAll('img'))
                                .map(img => img.src).filter(s => s && s.startsWith('http'));

                            const locationEl = item.querySelector('.cldt-summary-seller-contact-country') ||
                                               item.querySelector('[class*="country"]') ||
                                               item.querySelector('[class*="location"]');

                            const href = linkEl?.href || (id ? 'https://www.autoscout24.com/offers/' + id : '');

                            return {
                                external_id: id,
                                title: titleEl?.textContent?.trim() || '',
                                url: href,
                                price_raw: priceEl?.textContent?.trim() || '',
                                details: detailTexts,
                                images: images.slice(0, 10),
                                location_raw: locationEl?.textContent?.trim() || '',
                            };
                        });
                    }
                """)

                if not listings_data:
                    logger.info(f"[AutoScout24] Nema oglasa na stranici {page_num}")
                    await page.close()
                    if page_num == 1:
                        break
                    continue

                for raw in listings_data:
                    parsed = self._parse_listing(raw)
                    if parsed:
                        all_listings.append(self.normalize(parsed))

                await page.close()
                await asyncio.sleep(2)
                logger.info(f"[AutoScout24] Skupljeno ukupno: {len(all_listings)}")

        return all_listings

    async def scrape_detail(self, url: str) -> dict:
        async with self:
            page = await self.get_page(url)
            if not page:
                return {}
            await page.close()
            return {}

    def _parse_listing(self, raw: dict) -> dict | None:
        if not raw.get("external_id") or not raw.get("url"):
            return None
        title = raw.get("title", "")
        details = raw.get("details", [])
        make, model = self._parse_title(title)
        mileage = year = fuel = transmission = power = None
        for detail in details:
            if "km" in detail.lower():
                mileage = detail
            elif any(c.isdigit() for c in detail) and len(detail) == 4:
                year = detail
            elif any(f in detail.lower() for f in ["diesel","petrol","benzin","electric","hybrid"]):
                fuel = detail
            elif any(t in detail.lower() for t in ["automatic","manual","automat"]):
                transmission = detail
            elif "kw" in detail.lower() or "ps" in detail.lower():
                power = detail
        location = raw.get("location_raw", "")
        country, city = self._parse_location(location)
        return {
            "external_id":     f"as24_{raw['external_id']}",
            "make":            make,
            "model":           model,
            "year":            year,
            "price":           raw.get("price_raw"),
            "mileage":         mileage,
            "fuel_type":       fuel,
            "transmission":    transmission,
            "engine_power_kw": self._parse_power_kw(power),
            "country":         country,
            "city":            city,
            "images":          raw.get("images", []),
            "url":             raw.get("url", ""),
        }

    def _parse_title(self, title: str) -> tuple:
        KNOWN_MAKES = [
            "BMW", "Mercedes-Benz", "Volkswagen", "Audi", "Ford", "Toyota",
            "Honda", "Renault", "Peugeot", "Opel", "Skoda", "Seat", "Kia",
            "Hyundai", "Mazda", "Volvo", "Porsche", "Fiat", "Alfa Romeo",
            "Citroën", "Dacia", "Nissan", "Mitsubishi",
        ]
        for make in KNOWN_MAKES:
            if make.lower() in title.lower():
                rest = title.lower().replace(make.lower(), "").strip()
                words = rest.split()
                model = " ".join(words[:2]).title() if words else None
                return make, model
        return None, None

    def _parse_location(self, location: str) -> tuple:
        if not location:
            return None, None
        parts = location.split(",")
        if len(parts) >= 2:
            return parts[-1].strip(), parts[0].strip()
        return None, location.strip()

    def _parse_power_kw(self, power_str) -> int | None:
        if not power_str:
            return None
        import re
        kw_match = re.search(r'(\d+)\s*kw', power_str.lower())
        if kw_match:
            return int(kw_match.group(1))
        ps_match = re.search(r'(\d+)\s*(ps|hp)', power_str.lower())
        if ps_match:
            return round(int(ps_match.group(1)) * 0.7355)
        return None
