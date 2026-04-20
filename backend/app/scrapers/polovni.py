import asyncio
import logging
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class PolvoniScraper(BaseScraper):
    """
    Scraper za Polovniautomobili.com — najveći portal u Srbiji i regionu.
    Pokrivenost: Srbija, BiH, Crna Gora, Hrvatska
    """

    SOURCE_NAME = "polovni"
    BASE_URL = "https://www.polovniautomobili.com"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        params = {
            "page": page,
            "sort": "renewDate",
            "category_id": 1,  # automobili
        }

        if filters.get("make"):
            params["brand"] = filters["make"].lower()
        if filters.get("model"):
            params["model"] = filters["model"].lower()
        if filters.get("min_price"):
            params["price_from"] = filters["min_price"]
        if filters.get("max_price"):
            params["price_to"] = filters["max_price"]
        if filters.get("min_year"):
            params["year_from"] = filters["min_year"]
        if filters.get("max_year"):
            params["year_to"] = filters["max_year"]
        if filters.get("max_km"):
            params["mileage_to"] = filters["max_km"]
        if filters.get("fuel_type"):
            fuel_map = {
                "diesel": "2", "petrol": "1", "electric": "5",
                "hybrid": "6", "lpg": "3",
            }
            params["fuel"] = fuel_map.get(filters["fuel_type"], "")

        query = "&".join(f"{k}={v}" for k, v in params.items() if v != "")
        return f"{self.BASE_URL}/auto-oglasi/pretraga?{query}"

    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list[dict]:
        """Scraping liste oglasa sa Polovniautomobili.com"""
        all_listings = []

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[Polovni] Stranica {page_num}: {url}")

                page = await self.get_page(url, wait_for=".classified-list")
                if not page:
                    break

                listings_data = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('article.classified-item');
                        return Array.from(items).map(item => {

                            const linkEl = item.querySelector('a.ga-title');
                            const titleEl = item.querySelector('h3.classified-title');
                            const priceEl = item.querySelector('.price-box .price');

                            // Detalji (god/km/gorivo)
                            const detailEls = item.querySelectorAll('.classified-details li');
                            const details = Array.from(detailEls).map(d => d.textContent.trim());

                            // Slike
                            const imgEl = item.querySelector('img.classified-photo');

                            // Lokacija
                            const locationEl = item.querySelector('.classified-location');

                            return {
                                url: linkEl ? 'https://www.polovniautomobili.com' + linkEl.getAttribute('href') : '',
                                title: titleEl?.textContent?.trim() || '',
                                price_raw: priceEl?.textContent?.trim() || '',
                                details: details,
                                image: imgEl?.src || imgEl?.getAttribute('data-src') || '',
                                location_raw: locationEl?.textContent?.trim() || '',
                                external_id: linkEl?.getAttribute('href')?.split('/')?.pop() || '',
                            };
                        });
                    }
                """)

                if not listings_data:
                    logger.info(f"[Polovni] Nema više oglasa")
                    await page.close()
                    break

                for raw in listings_data:
                    if raw.get("external_id"):
                        parsed = self._parse_listing(raw)
                        if parsed:
                            all_listings.append(self.normalize(parsed))

                await page.close()
                await asyncio.sleep(2)

                logger.info(f"[Polovni] Skupljeno: {len(all_listings)}")

        return all_listings

    async def scrape_detail(self, url: str) -> dict:
        """Scraping detalja jednog oglasa."""
        async with self:
            page = await self.get_page(url)
            if not page:
                return {}

            data = await page.evaluate("""
                () => {
                    const getText = (selector) =>
                        document.querySelector(selector)?.textContent?.trim();

                    // Sva oprema
                    const featureEls = document.querySelectorAll('.classified-equipment li');
                    const features = Array.from(featureEls).map(f => f.textContent.trim());

                    // Sve slike
                    const imageEls = document.querySelectorAll('.gallery-image img');
                    const images = Array.from(imageEls).map(img => img.src || img.getAttribute('data-src'));

                    // Specifikacije
                    const specEls = document.querySelectorAll('.classified-config tr');
                    const specs = {};
                    specEls.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            specs[cells[0].textContent.trim()] = cells[1].textContent.trim();
                        }
                    });

                    return {
                        description: getText('.classified-content') || '',
                        features: features,
                        images: images.filter(Boolean).slice(0, 20),
                        specs: specs,
                        engine_cc: specs['Kubikaza'] || specs['Zapremina motora'] || '',
                        doors: specs['Broj vrata'] || '',
                        color: specs['Boja'] || '',
                        accident_free: (specs['Šteta'] || '').toLowerCase().includes('nije oštećen'),
                        service_history: (specs['Servisna knjiga'] || '').toLowerCase() !== 'nema',
                    };
                }
            """)

            await page.close()
            return data

    def _parse_listing(self, raw: dict) -> dict | None:
        if not raw.get("url"):
            return None

        title = raw.get("title", "")
        details = raw.get("details", [])

        make, model = self._parse_title(title)

        year = mileage = fuel = transmission = None
        for d in details:
            if len(d) == 4 and d.isdigit():
                year = d
            elif "km" in d.lower():
                mileage = d
            elif any(f in d.lower() for f in ["dizel", "benzin", "elektr", "hibrid", "gas"]):
                fuel = d
            elif any(t in d.lower() for t in ["manual", "automat", "manueln"]):
                transmission = d

        # Cena — Polovni prikazuje u EUR i RSD
        price_raw = raw.get("price_raw", "")
        currency = "EUR" if "€" in price_raw or "EUR" in price_raw else "RSD"

        location = raw.get("location_raw", "")

        return {
            "external_id":  f"pola_{raw['external_id']}",
            "make":         make,
            "model":        model,
            "year":         year,
            "price":        price_raw,
            "currency":     currency,
            "mileage":      mileage,
            "fuel_type":    fuel,
            "transmission": transmission,
            "country":      "RS",
            "city":         location,
            "images":       [raw["image"]] if raw.get("image") else [],
            "url":          raw.get("url", ""),
        }

    def _parse_title(self, title: str) -> tuple[str | None, str | None]:
        if not title:
            return None, None
        parts = title.strip().split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:3])
        return parts[0] if parts else None, None
