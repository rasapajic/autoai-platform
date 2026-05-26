import asyncio
import logging
import json
import aiohttp
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class WillhabenScraper(BaseScraper):
    SOURCE_NAME = "willhaben"

    # ✅ ISPRAVLJEN URL — nedostajalo je /gebrauchtwagenmarkt
    BASE_URL = "https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenmarkt"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
        "Referer": "https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenmarkt",
        # ✅ DODAT — willhaben zahteva ovaj header da vrati JSON
        "x-wh-client": "api=v1.24.0",
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

                # Dodaj filtere ako postoje
                if filters.get("make"):
                    params["MAKE"] = filters["make"].upper()
                if filters.get("min_price"):
                    params["PRICE_FROM"] = filters["min_price"]
                if filters.get("max_price"):
                    params["PRICE_TO"] = filters["max_price"]
                if filters.get("min_year"):
                    params["YEAR_FROM"] = filters["min_year"]
                if filters.get("max_year"):
                    params["YEAR_TO"] = filters["max_year"]
                if filters.get("max_km"):
                    params["MILEAGE_TO"] = filters["max_km"]
                if filters.get("fuel_type"):
                    params["FUEL_TYPE"] = filters["fuel_type"].upper()

                logger.info(f"[Willhaben] Stranica {page_num + 1}: offset={offset}")

                try:
                    async with self._session.get(self.BASE_URL, params=params) as resp:
                        logger.info(f"[Willhaben] Status: {resp.status} | Content-Type: {resp.content_type}")

                        if resp.status != 200:
                            logger.warning(f"[Willhaben] Status {resp.status} — prekidam")
                            break

                        text = await resp.text()
                        logger.info(f"[Willhaben] Preview odgovora: {text[:500]}")

                        try:
                            data = json.loads(text)
                        except Exception as je:
                            logger.error(f"[Willhaben] JSON greška: {je}")
                            break

                        adverts = (
                            data.get("advertSummaryList", {}).get("advertSummary", [])
                        )

                        if not adverts:
                            logger.info(f"[Willhaben] Nema oglasa na stranici {page_num + 1} — kraj")
                            break

                        for ad in adverts:
                            parsed = self._parse_ad(ad)
                            if parsed and parsed["external_id"] not in seen_ids:
                                seen_ids.add(parsed["external_id"])
                                all_listings.append(parsed)

                        logger.info(
                            f"[Willhaben] Stranica {page_num + 1}: "
                            f"+{len(adverts)} oglasa | Ukupno: {len(all_listings)}"
                        )

                        await asyncio.sleep(1.2)

                except Exception as e:
                    logger.error(f"[Willhaben] Greška na stranici {page_num + 1}: {e}")
                    break

        logger.info(f"[Willhaben] Završeno — ukupno {len(all_listings)} oglasa")
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

            ad_id    = str(ad.get("id", ""))
            make     = g("MAKE")
            model    = g("MODEL")
            year_str = g("YEAR")
            price_str = g("PRICE_FOR_DISPLAY") or g("PRICE")
            mileage_str = g("MILEAGE")
            fuel     = g("FUEL_TYPE") or ""
            transmission = g("TRANSMISSION_TYPE") or ""
            body     = g("CAR_TYPE") or ""
            power    = g("POWER_KW") or g("ENGINE_POWER")
            color    = g("COLOR") or ""
            city     = g("LOCATION") or g("DISTRICT") or ""
            description = ad.get("description", "") or ""

            year = None
            if year_str:
                try:
                    year = int(str(year_str)[:4])
                except Exception:
                    pass

            # ✅ ISPRAVLJEN format slike
            images = []
            for img in (ad.get("advertImageList", {}).get("advertImage", []) or []):
                ref = img.get("reference")
                if ref:
                    images.append(
                        f"https://cache.willhaben.at/mmo/{ref}?rule=online-_x800"
                    )

            if not ad_id or not make:
                return None

            return {
                "external_id":    f"wh_{ad_id}",
                "source":         self.SOURCE_NAME,
                "make":           make,
                "model":          model,
                "year":           year,
                "price":          self._parse_price(price_str),
                "currency":       "EUR",
                "mileage":        self._parse_int(mileage_str),
                "fuel_type":      self._normalize_fuel(fuel),
                "transmission":   self._normalize_transmission(transmission),
                "body_type":      self._normalize_body(body),
                "engine_power_kw": self._parse_int(power),
                "color":          self._clean_text(color),
                "country":        "AT",
                "city":           self._clean_text(city),
                "description":    self._clean_text(description),
                "images":         images[:6],
                "url":            f"https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagen/{ad_id}",
            }

        except Exception as e:
            logger.warning(f"[Willhaben] Parse greška za oglas: {e}")
            return None

    async def scrape_detail(self, url: str) -> dict:
        return {}
