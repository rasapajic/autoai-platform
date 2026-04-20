import asyncio
import logging
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AutoScout24Scraper(BaseScraper):
    """
    Scraper za AutoScout24 — najveći auto portal u Evropi.
    Pokrivenost: Nemačka, Austrija, Italija, Belgija, Holandija i dr.
    """

    SOURCE_NAME = "autoscout24"
    BASE_URL = "https://www.autoscout24.com"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        """Gradi URL za pretragu na osnovu filtera."""
        params = {
            "atype": "C",  # samo automobili
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
        if filters.get("fuel_type"):
            fuel_map = {
                "petrol": "B", "diesel": "D", "electric": "E",
                "hybrid": "M", "lpg": "L", "cng": "C",
            }
            params["fuel"] = fuel_map.get(filters["fuel_type"], "")
        if filters.get("country"):
            params["countrycode"] = filters["country"].upper()

        query = "&".join(f"{k}={v}" for k, v in params.items() if v != "")
        return f"{self.BASE_URL}/lst?{query}"

    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list[dict]:
        """Scraping liste oglasa sa više stranica."""
        all_listings = []

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[AutoScout24] Stranica {page_num}: {url}")

                page = await self.get_page(url, wait_for="article.cldt-summary-full-item")
                if not page:
                    break

                # Izvuci sve oglase sa stranice
                listings_data = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('article.cldt-summary-full-item');
                        return Array.from(items).map(item => {
                            // Izvuci ID
                            const id = item.getAttribute('data-guid') ||
                                       item.getAttribute('id') || '';

                            // Naziv i link
                            const titleEl = item.querySelector('h2');
                            const linkEl = item.querySelector('a.cldt-summary-full-item-main');

                            // Cena
                            const priceEl = item.querySelector('[data-type="price_block"] .cldt-price');

                            // Kilometraža i godina
                            const details = item.querySelectorAll('.cldt-summary-attributes-item');
                            const detailTexts = Array.from(details).map(d => d.textContent.trim());

                            // Slike
                            const images = Array.from(item.querySelectorAll('img[src*="autoscout24"]'))
                                .map(img => img.src)
                                .filter(src => src && !src.includes('logo'));

                            // Lokacija
                            const locationEl = item.querySelector('.cldt-summary-seller-contact-country');

                            return {
                                external_id: id,
                                title: titleEl?.textContent?.trim() || '',
                                url: linkEl?.href || '',
                                price_raw: priceEl?.textContent?.trim() || '',
                                details: detailTexts,
                                images: images.slice(0, 10),
                                location_raw: locationEl?.textContent?.trim() || '',
                            };
                        });
                    }
                """)

                if not listings_data:
                    logger.info(f"[AutoScout24] Nema više oglasa na stranici {page_num}")
                    await page.close()
                    break

                # Parsiraj svaki oglas
                for raw in listings_data:
                    parsed = self._parse_listing(raw)
                    if parsed:
                        all_listings.append(self.normalize(parsed))

                await page.close()

                # Pauza između stranica (anti-bot)
                await asyncio.sleep(2)

                logger.info(f"[AutoScout24] Skupljeno ukupno: {len(all_listings)}")

        return all_listings

    async def scrape_detail(self, url: str) -> dict:
        """Scraping detalja jednog oglasa — kompletne informacije."""
        async with self:
            page = await self.get_page(url)
            if not page:
                return {}

            data = await page.evaluate("""
                () => {
                    const getText = (selector) =>
                        document.querySelector(selector)?.textContent?.trim();

                    // Oprema/features
                    const featureEls = document.querySelectorAll('.sc-expandable-element li');
                    const features = Array.from(featureEls).map(f => f.textContent.trim());

                    // Sve slike
                    const imageEls = document.querySelectorAll('.image-gallery-image img');
                    const images = Array.from(imageEls).map(img => img.src);

                    // Tehničke specifikacije
                    const specEls = document.querySelectorAll('[data-item-key]');
                    const specs = {};
                    specEls.forEach(el => {
                        const key = el.getAttribute('data-item-key');
                        specs[key] = el.textContent.trim();
                    });

                    return {
                        description: getText('.cldt-stage-description') || '',
                        features: features,
                        images: images.filter(i => i && !i.includes('logo')).slice(0, 20),
                        specs: specs,
                        vin: getText('[data-item-key="vin"]') || '',
                    };
                }
            """)

            await page.close()
            return data

    def _parse_listing(self, raw: dict) -> dict | None:
        """Parsira sirove podatke iz AutoScout24 formata."""
        if not raw.get("external_id") or not raw.get("url"):
            return None

        title = raw.get("title", "")
        details = raw.get("details", [])

        # Izvuci make/model iz naslova (npr. "BMW 5 Series 530d")
        make, model = self._parse_title(title)

        # Parsiranje detalja (km, godina, gorivo, menjač...)
        mileage = year = fuel = transmission = power = None
        for detail in details:
            if "km" in detail.lower():
                mileage = detail
            elif any(c.isdigit() for c in detail) and len(detail) == 4:
                year = detail
            elif any(fuel in detail.lower() for fuel in ["diesel", "petrol", "benzin", "electric", "hybrid"]):
                fuel = detail
            elif any(t in detail.lower() for t in ["automatic", "manual", "automat"]):
                transmission = detail
            elif "kw" in detail.lower() or "ps" in detail.lower() or "hp" in detail.lower():
                power = detail

        # Lokacija
        location = raw.get("location_raw", "")
        country, city = self._parse_location(location)

        return {
            "external_id":   f"as24_{raw['external_id']}",
            "make":          make,
            "model":         model,
            "year":          year,
            "price":         raw.get("price_raw"),
            "mileage":       mileage,
            "fuel_type":     fuel,
            "transmission":  transmission,
            "engine_power_kw": self._parse_power_kw(power),
            "country":       country,
            "city":          city,
            "images":        raw.get("images", []),
            "url":           raw.get("url", ""),
        }

    def _parse_title(self, title: str) -> tuple[str | None, str | None]:
        """Izvuci marku i model iz naslova oglasa."""
        KNOWN_MAKES = [
            "BMW", "Mercedes-Benz", "Volkswagen", "Audi", "Ford", "Toyota",
            "Honda", "Renault", "Peugeot", "Opel", "Skoda", "Seat", "Kia",
            "Hyundai", "Mazda", "Volvo", "Porsche", "Ferrari", "Lamborghini",
            "Fiat", "Alfa Romeo", "Citroën", "Dacia", "Nissan", "Mitsubishi",
        ]
        for make in KNOWN_MAKES:
            if make.lower() in title.lower():
                rest = title.lower().replace(make.lower(), "").strip()
                words = rest.split()
                model = " ".join(words[:2]).title() if words else None
                return make, model
        return None, None

    def _parse_location(self, location: str) -> tuple[str | None, str | None]:
        """Izvuci grad i zemlju iz location stringa."""
        if not location:
            return None, None
        parts = location.split(",")
        if len(parts) >= 2:
            return parts[-1].strip(), parts[0].strip()
        return None, location.strip()

    def _parse_power_kw(self, power_str: str | None) -> int | None:
        if not power_str:
            return None
        import re
        # Traži KW broj
        kw_match = re.search(r'(\d+)\s*kw', power_str.lower())
        if kw_match:
            return int(kw_match.group(1))
        # Konvertuj PS u KW
        ps_match = re.search(r'(\d+)\s*(ps|hp)', power_str.lower())
        if ps_match:
            ps = int(ps_match.group(1))
            return round(ps * 0.7355)
        return None
