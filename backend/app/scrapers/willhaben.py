import asyncio
import logging
import json
import aiohttp
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class WillhabenScraper(BaseScraper):
    SOURCE_NAME = "willhaben"
    BASE_URL = "https://www.willhaben.at/iad/gebrauchtwagen/auto"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
        "Referer": "https://www.willhaben.at/",
    }

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(headers=self.HEADERS)
        return self

    async def __aexit__(self, *args):
        await self._session.close()

    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list[dict]:
        all_listings = []
        seen_ids = set()
        rows = 25

        async with self:
            for page_num in range(max_pages):
                offset = page_num * rows
                params = {
                    "sfId": "",
                    "rows": rows,
                    "isNavigation": "false",
                    "pagingOffset": offset,
                    "sort": 1,
                }
                logger.info(f"[Willhaben] Stranica {page_num + 1}: offset={offset}")

                try:
                    async with self._session.get(self.BASE_URL, params=params) as resp:
                        if resp.status != 200:
                            logger.warning(f"[Willhaben] Status {resp.status}")
                            break

                        text = await resp.text()
                        logger.info(f"[Willhaben] Preview: {text[:300]}")

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            logger.error(f"[Willhaben] JSON greška: {je} | CT: {resp.content_type}")
                            break

                        adverts = data.get("advertSummaryList", {}).get("advertSummary", [])

                        if not adverts:
                            logger.info(f"[Willhaben] Nema oglasa na str {page_num + 1}")
                            break

                        for ad in adverts:
                            parsed = self._parse_ad(ad)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        logger.info(f"[Willhaben] Str {page_num + 1}: +{len(adverts)} | Ukupno: {len(all_listings)}")
                        await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(f"[Willhaben] Greška na str {page_num + 1}: {e}")
                    break

        return all_listings

    def _get_attr(self, attributes: list, name: str):
        for attr in attributes:
            if attr.get("name") == name:
                vals = attr.get("values", [])
                return vals[0] if vals else None
        return None

    def _parse_ad(self, ad: dict) -> dict | None:
        try:
            attrs = ad.get("attributes", {}).get("attribute", [])

            def g(name):
                return self._get_attr(attrs, name)

            ad_id = str(ad.get("id", ""))
            make = g("MAKE")
            model = g("MODEL")
            year_str = g("YEAR")
            price_str = g("PRICE_FOR_DISPLAY") or g("PRICE")
            mileage_str = g("MILEAGE")
            fuel = g("FUEL_TYPE") or ""
            transmission = g("TRANSMISSION_TYPE") or ""
            body = g("CAR_TYPE") or ""

            year = None
            if year_str:
                try:
                    year = int(str(year_str)[:4])
                except Exception:
                    pass

            images = []
            for img in (ad.get("advertImageList", {}).get("advertImage", []) or []):
                ref = img.get("reference")
                if ref:
                    images.append(f"https://cache.willhaben.at/mmo/{ref}")

            return {
                "external_id": f"wh_{ad_id}",
                "source":      self.SOURCE_NAME,
                "make":        make,
                "model":       model,
                "year":        year,
                "price":       self._parse_price(price_str),
                "currency":    "EUR",
                "mileage":     self._parse_int(mileage_str),
                "fuel_type":   self._normalize_fuel(fuel),
                "transmission": self._normalize_transmission(transmission),
                "body_type":   self._normalize_body(body),
                "country":     "AT",
                "images":      images[:5],
                "url":         f"https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagen/{ad_id}",
            }
        except Exception as e:
            logger.warning(f"[Willhaben] Parse greška: {e}")
            return None

    async def scrape_detail(self, url: str) -> dict:
        return {}
