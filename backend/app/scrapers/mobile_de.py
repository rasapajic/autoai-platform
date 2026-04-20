import asyncio
import logging
import json
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class MobileDeScraper(BaseScraper):
    """
    Scraper za Mobile.de — lider na nemačkom tržištu.
    Koristi JSON-LD structured data za lakše parsiranje.
    """

    SOURCE_NAME = "mobile_de"
    BASE_URL = "https://suchen.mobile.de"

    def _build_url(self, filters: dict, page: int = 1) -> str:
        params = {
            "isSearchRequest": "true",
            "pageNumber": page,
            "sortOption.sortBy": "creationTime",
            "sortOption.sortOrder": "DESCENDING",
        }

        if filters.get("make"):
            params["makeModelVariant1.makeId"] = self._get_make_id(filters["make"])
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
            fuel_map = {
                "diesel": "DIESEL", "petrol": "PETROL",
                "electric": "ELECTRICITY", "hybrid": "HYBRID_PETROL",
            }
            params["fuels"] = fuel_map.get(filters["fuel_type"], "")

        query = "&".join(f"{k}={v}" for k, v in params.items() if v != "")
        return f"{self.BASE_URL}/fahrzeuge/pkw?{query}"

    async def scrape_listings(self, filters: dict, max_pages: int = 5) -> list[dict]:
        """Scraping Mobile.de — koristi structured data (brže i pouzdanije)."""
        all_listings = []

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[Mobile.de] Stranica {page_num}: {url}")

                page = await self.get_page(url, wait_for=".cBox-body--resultitem")
                if not page:
                    break

                # Mobile.de ima JSON-LD structured data — zlatni rudnik!
                listings_data = await page.evaluate("""
                    () => {
                        // Probaj JSON-LD prvo (najlakše parsirati)
                        const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
                        const structured = [];
                        jsonLdScripts.forEach(script => {
                            try {
                                const data = JSON.parse(script.textContent);
                                if (data['@type'] === 'ItemList') {
                                    data.itemListElement?.forEach(item => {
                                        structured.push(item.item || item);
                                    });
                                }
                            } catch(e) {}
                        });

                        if (structured.length > 0) return { type: 'structured', data: structured };

                        // Fallback — DOM scraping
                        const items = document.querySelectorAll('.cBox-body--resultitem');
                        const dom = Array.from(items).map(item => {
                            const titleEl = item.querySelector('.g-col-8 h2 a, .headline-block a');
                            const priceEl = item.querySelector('.price-block .price-div');
                            const attribs = Array.from(
                                item.querySelectorAll('.rbt-attr-item')
                            ).map(a => a.textContent.trim());

                            return {
                                url: titleEl?.href || '',
                                title: titleEl?.textContent?.trim() || '',
                                price: priceEl?.textContent?.trim() || '',
                                attributes: attribs,
                                external_id: titleEl?.href?.match(/\\/(\d+)\\.html/)?.[1] || '',
                            };
                        });
                        return { type: 'dom', data: dom };
                    }
                """)

                if not listings_data or not listings_data.get("data"):
                    await page.close()
                    break

                data_type = listings_data["type"]
                for raw in listings_data["data"]:
                    if data_type == "structured":
                        parsed = self._parse_structured(raw)
                    else:
                        parsed = self._parse_dom(raw)

                    if parsed:
                        all_listings.append(self.normalize(parsed))

                await page.close()
                await asyncio.sleep(2.5)
                logger.info(f"[Mobile.de] Skupljeno: {len(all_listings)}")

        return all_listings

    async def scrape_detail(self, url: str) -> dict:
        async with self:
            page = await self.get_page(url)
            if not page:
                return {}

            data = await page.evaluate("""
                () => {
                    // JSON-LD sa detalja
                    const jsonLd = document.querySelector('script[type="application/ld+json"]');
                    let structured = {};
                    if (jsonLd) {
                        try { structured = JSON.parse(jsonLd.textContent); } catch(e) {}
                    }

                    // Oprema
                    const features = Array.from(
                        document.querySelectorAll('.rbt-features li, .features-list li')
                    ).map(f => f.textContent.trim());

                    // Slike
                    const images = Array.from(
                        document.querySelectorAll('.gallery-item img, .rbt-gallery img')
                    ).map(img => img.src || img.getAttribute('data-src'))
                     .filter(Boolean);

                    const description = document.querySelector(
                        '.seller-notes, .description-block'
                    )?.textContent?.trim() || '';

                    return { structured, features, images: images.slice(0, 20), description };
                }
            """)

            await page.close()
            return data

    def _parse_structured(self, item: dict) -> dict | None:
        """Parsiranje JSON-LD structured data."""
        url = item.get("url", "")
        if not url:
            return None

        external_id = url.split("/")[-1].replace(".html", "")
        vehicle = item.get("vehicleEngine", {}) or {}
        offer = item.get("offers", {}) or {}

        return {
            "external_id":      f"mob_{external_id}",
            "make":             item.get("brand", {}).get("name"),
            "model":            item.get("model"),
            "year":             item.get("modelDate"),
            "price":            offer.get("price"),
            "currency":         offer.get("priceCurrency", "EUR"),
            "mileage":          item.get("mileageFromOdometer", {}).get("value"),
            "fuel_type":        item.get("fuelType"),
            "transmission":     item.get("vehicleTransmission"),
            "engine_power_kw":  vehicle.get("enginePower"),
            "body_type":        item.get("bodyType"),
            "color":            item.get("color"),
            "country":          "DE",
            "images":           [item.get("image")] if item.get("image") else [],
            "url":              url,
        }

    def _parse_dom(self, raw: dict) -> dict | None:
        """Fallback DOM parsiranje."""
        if not raw.get("url"):
            return None

        attrs = raw.get("attributes", [])
        year = mileage = fuel = transmission = None
        for a in attrs:
            if len(a) == 4 and a.isdigit():
                year = a
            elif "km" in a.lower():
                mileage = a
            elif any(f in a.lower() for f in ["diesel", "petrol", "elektro", "hybrid"]):
                fuel = a

        title = raw.get("title", "")
        parts = title.split()
        make = parts[0] if parts else None
        model = " ".join(parts[1:3]) if len(parts) > 1 else None

        return {
            "external_id":  f"mob_{raw.get('external_id', '')}",
            "make":         make,
            "model":        model,
            "year":         year,
            "price":        raw.get("price"),
            "mileage":      mileage,
            "fuel_type":    fuel,
            "transmission": transmission,
            "country":      "DE",
            "url":          raw.get("url", ""),
        }

    def _get_make_id(self, make: str) -> str:
        """Mobile.de koristi numeričke ID-eve za marke."""
        make_ids = {
            "BMW": "3500", "Mercedes-Benz": "17200", "Volkswagen": "25200",
            "Audi": "1900", "Ford": "9000", "Toyota": "24100",
            "Renault": "21200", "Peugeot": "19600", "Opel": "19000",
            "Skoda": "22900", "Seat": "22200", "Kia": "13600",
            "Hyundai": "11400", "Mazda": "16200", "Volvo": "25100",
        }
        return make_ids.get(make, "")
