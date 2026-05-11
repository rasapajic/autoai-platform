import asyncio
import logging
import re
from urllib.parse import urlencode
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class MobileDeScraper(BaseScraper):
    SOURCE_NAME = "mobile_de"
    BASE_URL = "https://suchen.mobile.de"

    FUEL_MAP = {
        "diesel": "diesel", "benzin": "petrol", "petrol": "petrol",
        "elektro": "electric", "electric": "electric",
        "hybrid": "hybrid", "autogas": "lpg", "lpg": "lpg",
        "erdgas": "cng", "cng": "cng",
    }

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
        return f"{self.BASE_URL}/fahrzeuge/pkw?{urlencode(params)}"

    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list[dict]:
        all_listings = []
        seen_ids = set()

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[Mobile.de] Stranica {page_num}: {url}")

                # Ne cekaj specific selektor
                page = await self.get_page(url, wait_for=None)
                if not page:
                    logger.warning(f"[Mobile.de] Nije ucitana stranica {page_num}")
                    break

                try:
                    # Debug: pokazi sta stranica sadrzi
                    debug = await page.evaluate("""
                        () => ({
                            title: document.title,
                            s1: document.querySelectorAll('.cBox-body--resultitem').length,
                            s2: document.querySelectorAll('[data-testid="result-list-item"]').length,
                            s3: document.querySelectorAll('article').length,
                            s4: document.querySelectorAll('[class*="result"]').length,
                            s5: document.querySelectorAll('[class*="listing"]').length,
                            s6: document.querySelectorAll('[class*="vehicle"]').length,
                            s7: document.querySelectorAll('ul.result-list li').length,
                            s8: document.querySelectorAll('[data-ad-id]').length,
                        })
                    """)
                    logger.info(f"[Mobile.de] DEBUG str{page_num}: {debug}")

                    # Probaj JSON-LD structured data
                    raw_items = await page.evaluate("""
                        () => {
                            // Pokusaj JSON-LD
                            const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
                            const structured = [];
                            jsonLdScripts.forEach(script => {
                                try {
                                    const data = JSON.parse(script.textContent);
                                    if (data['@type'] === 'ItemList') {
                                        (data.itemListElement || []).forEach(item => {
                                            structured.push(item.item || item);
                                        });
                                    } else if (data['@type'] === 'Car' || data['@type'] === 'Vehicle') {
                                        structured.push(data);
                                    }
                                } catch(e) {}
                            });
                            if (structured.length > 0) return { type: 'jsonld', data: structured };

                            // DOM fallback - pokusaj razlicite selektore
                            const selectors = [
                                '.cBox-body--resultitem',
                                '[data-testid="result-list-item"]',
                                'article[data-ad-id]',
                                '[data-ad-id]',
                                '.result-list-item',
                                '[class*="resultitem"]',
                                '[class*="result-item"]',
                            ];
                            for (const sel of selectors) {
                                const items = document.querySelectorAll(sel);
                                if (items.length > 0) {
                                    const data = Array.from(items).map(item => {
                                        const titleEl = item.querySelector('h2, h3, [class*="title"]');
                                        const priceEl = item.querySelector('[class*="price"]');
                                        const linkEl = item.querySelector('a[href*="fahrzeuge"]') || item.querySelector('a');
                                        const imgEl = item.querySelector('img');
                                        const attrs = Array.from(item.querySelectorAll(
                                            '[class*="attribute"], [class*="detail"], li'
                                        )).map(a => a.textContent.trim()).filter(Boolean);
                                        const href = linkEl?.href || '';
                                        return {
                                            url: href,
                                            title: titleEl?.textContent?.trim() || '',
                                            price: priceEl?.textContent?.trim() || '',
                                            attributes: attrs,
                                            image: imgEl?.src || imgEl?.getAttribute('data-src') || '',
                                            external_id: href.match(/\/(\d+)\.html/)?.[1] || href.split('/').pop() || '',
                                        };
                                    }).filter(i => i.url);
                                    if (data.length > 0) return { type: 'dom', selector: sel, data };
                                }
                            }
                            return { type: 'none', data: [] };
                        }
                    """)

                    logger.info(f"[Mobile.de] Tip: {raw_items.get('type')} | Broj: {len(raw_items.get('data', []))}")

                    if not raw_items or not raw_items.get('data'):
                        logger.info(f"[Mobile.de] Nema podataka na str {page_num}")
                        await page.close()
                        if page_num == 1:
                            break
                        continue

                    page_saved = 0
                    data_type = raw_items['type']
                    for raw in raw_items['data']:
                        try:
                            if data_type == 'jsonld':
                                parsed = self._parse_jsonld(raw)
                            else:
                                parsed = self._parse_dom(raw)
                            if not parsed:
                                continue
                            if parsed['external_id'] in seen_ids:
                                continue
                            seen_ids.add(parsed['external_id'])
                            all_listings.append(parsed)
                            page_saved += 1
                        except Exception as e:
                            logger.warning(f"[Mobile.de] Parse greška: {e}")

                    logger.info(f"[Mobile.de] Str {page_num}: +{page_saved} | Ukupno: {len(all_listings)}")

                except Exception as e:
                    logger.error(f"[Mobile.de] Greška str {page_num}: {e}")
                finally:
                    await page.close()

                await asyncio.sleep(2.5)

        return all_listings

    async def scrape_detail(self, url: str) -> dict:
        async with self:
            page = await self.get_page(url, wait_for=None)
            if not page:
                return {}
            try:
                data = await page.evaluate("""
                    () => {
                        const jsonLd = document.querySelector('script[type="application/ld+json"]');
                        let structured = {};
                        if (jsonLd) {
                            try { structured = JSON.parse(jsonLd.textContent); } catch(e) {}
                        }
                        const features = Array.from(
                            document.querySelectorAll('[class*="feature"] li, [class*="equipment"] li')
                        ).map(f => f.textContent.trim()).filter(Boolean);
                        const images = Array.from(
                            document.querySelectorAll('img[src*="img.classistatic"], img[src*="mobile"]')
                        ).map(img => img.src).filter(Boolean);
                        return { structured, features, images: images.slice(0, 20) };
                    }
                """)
                return data or {}
            except Exception as e:
                logger.error(f"[Mobile.de] Detail greška: {e}")
                return {}
            finally:
                await page.close()

    def _parse_jsonld(self, item: dict) -> dict | None:
        url = item.get("url", "")
        if not url:
            return None
        external_id = f"mob_{url.split('/')[-1].replace('.html', '')}"
        offer = item.get("offers", {}) or {}
        return {
            "external_id":     external_id,
            "source":          self.SOURCE_NAME,
            "make":            item.get("brand", {}).get("name") if isinstance(item.get("brand"), dict) else item.get("brand"),
            "model":           item.get("model"),
            "year":            self._parse_int(item.get("modelDate")),
            "price":           self._parse_price(offer.get("price")),
            "currency":        offer.get("priceCurrency", "EUR"),
            "mileage":         self._parse_int(item.get("mileageFromOdometer", {}).get("value") if isinstance(item.get("mileageFromOdometer"), dict) else None),
            "fuel_type":       self._normalize_fuel(item.get("fuelType", "")),
            "transmission":    item.get("vehicleTransmission"),
            "body_type":       item.get("bodyType"),
            "color":           item.get("color"),
            "country":         "DE",
            "images":          [item["image"]] if item.get("image") else [],
            "url":             url,
        }

    def _parse_dom(self, raw: dict) -> dict | None:
        if not raw.get("url"):
            return None
        attrs = raw.get("attributes", [])
        year = mileage = fuel_type = transmission = None
        for a in attrs:
            if re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', a):
                m = re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', a)
                year = year or int(m.group(1))
            elif "km" in a.lower() and any(c.isdigit() for c in a):
                mileage = mileage or a
            elif any(f in a.lower() for f in ["diesel", "benzin", "elektro", "hybrid", "autogas"]):
                fuel_type = fuel_type or self._normalize_fuel(a)
        title = raw.get("title", "")
        parts = title.split()
        make = parts[0] if parts else None
        model = " ".join(parts[1:3]) if len(parts) > 1 else None
        return {
            "external_id":  f"mob_{raw.get('external_id', '')}",
            "source":       self.SOURCE_NAME,
            "make":         make,
            "model":        model,
            "year":         year,
            "price":        self._parse_price(raw.get("price", "")),
            "currency":     "EUR",
            "mileage":      self._parse_mileage(mileage),
            "fuel_type":    fuel_type,
            "transmission": transmission,
            "country":      "DE",
            "images":       [raw["image"]] if raw.get("image") else [],
            "url":          raw.get("url", ""),
