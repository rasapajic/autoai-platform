import asyncio
import logging
import random
import re
from urllib.parse import urlencode
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

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

BODY_MAP = {
    "limousine": "sedan", "sedan": "sedan",
    "suv": "suv", "geländewagen": "suv", "crossover": "suv",
    "kombi": "kombi", "estate": "kombi", "touring": "kombi",
    "hatchback": "hatchback", "schrägheck": "hatchback",
    "coupe": "coupe", "coupé": "coupe",
    "cabrio": "cabrio", "kabriolet": "cabrio", "roadster": "cabrio",
    "van": "van", "minivan": "van", "kleinbus": "van",
    "pickup": "pickup",
}

KNOWN_MAKES = [
    "Alfa Romeo","Aston Martin","Audi","BMW","Bentley","Bugatti",
    "Citroën","Citroen","Dacia","Ferrari","Fiat","Ford",
    "Honda","Hyundai","Jaguar","Jeep","Kia","Lamborghini",
    "Land Rover","Lexus","Maserati","Mazda","Mercedes-Benz",
    "Mini","Mitsubishi","Nissan","Opel","Peugeot","Porsche",
    "Renault","Rolls-Royce","Seat","Skoda","Smart","Subaru",
    "Suzuki","Tesla","Toyota","Volkswagen","Volvo",
]


class AutoScout24Scraper:
    SOURCE_NAME = "autoscout24"
    BASE_URL    = "https://www.autoscout24.com"

    def __init__(self):
        self._playwright = None
        self.browser = None
        self.context = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]
        )
        self.context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",
            timezone_id="Europe/Berlin",
            extra_http_headers={
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            }
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            window.chrome = { runtime: {} };
        """)
        return self

    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_page(self, url: str, wait_for: str = None):
        page = await self.context.new_page()
        await asyncio.sleep(random.uniform(1.5, 3.5))
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)
        except Exception as e:
            logger.warning(f"Greška pri otvaranju {url}: {e}")
            await page.close()
            return None
        return page

    def _build_url(self, filters: dict, page: int = 1) -> str:
        params = {"atype": "C", "page": page, "sort": "age", "desc": 0, "fregfrom": 2008, "pricefrom": 3000}
        mapping = {
            "make": "mmvmk0", "model": "mmvmd0",
            "min_price": "pricefrom", "max_price": "priceto",
            "min_year": "fregfrom", "max_year": "fregto",
            "max_km": "kmto",
        }
        fuel_map = {"petrol": "B", "diesel": "D", "electric": "E", "hybrid": "M", "lpg": "L", "cng": "C"}
        for key, param in mapping.items():
            if filters.get(key):
                params[param] = filters[key]
        if filters.get("fuel_type"):
            code = fuel_map.get(filters["fuel_type"])
            if code:
                params["fuel"] = code
        if filters.get("country"):
            params["cy"] = filters["country"].upper()
        return f"{self.BASE_URL}/lst?{urlencode(params)}"

    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        all_listings = []
        seen_ids = set()
        filter_fuel = filters.get("fuel_type")

        async with self:
            for page_num in range(1, max_pages + 1):
                url = self._build_url(filters, page=page_num)
                logger.info(f"[AutoScout24] Stranica {page_num}: {url}")
                page = None
                for attempt in range(3):
                    try:
                        page = await self.get_page(url, wait_for=None)
                        if page: break
                    except Exception as e:
                        logger.warning(f"[AutoScout24] Pokušaj {attempt+1}: {e}")
                        await asyncio.sleep(2 ** attempt)
                if not page:
                    continue

                for selector in [
                    'article[data-guid]',
                    '[data-testid="regular-list-item"]',
                    '[data-testid="result-list-item"]',
                    'article.cldt-summary-full-item',
                ]:
                    try:
                        await page.wait_for_selector(selector, timeout=8000)
                        logger.info(f"[AutoScout24] Selector pronađen: {selector}")
                        break
                    except Exception:
                        continue

                await asyncio.sleep(2)

                try:
                    raw_items = await page.evaluate(self._listing_js())
                except Exception as e:
                    logger.error(f"[AutoScout24] JS greška: {e}")
                    await page.close()
                    continue

                if not raw_items:
                    await page.close()
                    break

                page_saved = 0
                for raw in raw_items:
                    try:
                        parsed = self._parse_listing(raw, filter_fuel=filter_fuel)
                        if not parsed or parsed["external_id"] in seen_ids:
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
        return {}

    def _listing_js(self) -> str:
        return r"""
        () => {
            const getCleanPrice = (el) => {
                if (!el) return '';
                const clone = el.cloneNode(true);
                clone.querySelectorAll('sup,sub,[class*="footnote"],[class*="superscript"]').forEach(e=>e.remove());
                let text = clone.textContent.trim();
                text = text.replace(/[\u00B9\u00B2\u00B3\u2070-\u2079]/g,'');
                text = text.replace(/\s+\d\s*$/,'').trim();
                return text;
            };
            const containers = [
                ...document.querySelectorAll('article.cldt-summary-full-item'),
                ...document.querySelectorAll('article[data-guid]'),
                ...document.querySelectorAll('[data-testid="regular-list-item"]'),
                ...document.querySelectorAll('[data-testid="result-list-item"]'),
            ];
            const seen = new Set();
            const items = containers.filter(el => {
                const id = el.getAttribute('data-guid') || el.id;
                if (!id || seen.has(id)) return false;
                seen.add(id); return true;
            });
            return items.map((item, idx) => {
                const id = item.getAttribute('data-guid') || item.getAttribute('id') || '';
                const titleEl = item.querySelector('h2,h3,[class*="title"]');
                const title = titleEl?.textContent?.trim() || '';
                const offerLink = item.querySelector('a[href*="/offers/"]');
                const url = offerLink?.href || (id ? 'https://www.autoscout24.com/offers/'+id : '');
                const priceEl = item.querySelector('.cldt-price,[data-type="price_block"] .cldt-price,[class*="price"]');
                const price_raw = getCleanPrice(priceEl);
                const fullText = item.textContent || '';
                const innerText = item.innerText || '';
                let year_text = '';
                const regMatch1 = fullText.match(/\b(0[1-9]|1[0-2])[\/\.](19[5-9]\d|20[0-3]\d)\b/)
                               || innerText.match(/\b(0[1-9]|1[0-2])[\/\.](19[5-9]\d|20[0-3]\d)\b/);
                if (regMatch1) year_text = regMatch1[2];
                if (!year_text) {
                    const m = fullText.match(/\b(20[0-2]\d|19[5-9]\d)\b/);
                    if (m) year_text = m[1];
                }
                let km_text = '';
                const kmMatches = [...fullText.matchAll(/([\d.,]+)\s*km/gi)];
                for (const m of kmMatches) {
                    const raw = m[1];
                    if ((raw.match(/\./g)||[]).length > 1) continue;
                    const val = parseInt(raw.replace(/\./g,'').replace(/,/g,''));
                    if (val >= 1 && val <= 999999) { km_text = raw+' km'; break; }
                }
                const fuelPairs = [
                    ['Electric','electric'],['Elektro','electric'],['Hybrid','hybrid'],
                    ['Diesel','diesel'],['Benzin','petrol'],['Petrol','petrol'],
                    ['LPG','lpg'],['CNG','cng'],
                ];
                let fuel_text = '';
                for (const [kw,norm] of fuelPairs) {
                    if (fullText.includes(kw)) { fuel_text=norm; break; }
                }
                const transKws = ['Automatik','Automatic','Schaltgetriebe','Manual','DSG'];
                let trans_text = '';
                for (const kw of transKws) { if (fullText.includes(kw)) { trans_text=kw; break; } }
                const powerMatch = fullText.match(/(\d+)\s*kW/);
                const power_text = powerMatch ? powerMatch[1]+' kW' : '';
                const bodyKws = ['Limousine','SUV','Kombi','Hatchback','Coupe','Coupé','Cabrio','Van','Pickup'];
                let body_text = '';
                for (const kw of bodyKws) { if (fullText.includes(kw)) { body_text=kw; break; } }
                const details = [year_text,km_text,fuel_text,trans_text,power_text,body_text].filter(Boolean);
                const images = Array.from(item.querySelectorAll('img'))
                    .map(img=>img.src||img.getAttribute('data-src'))
                    .filter(s=>s&&s.startsWith('http')&&!s.includes('logo'));
                const locEl = item.querySelector('.cldt-summary-seller-contact-country,[class*="country"],[class*="location"]');
                return { id, title, url, price_raw, details, images: images.slice(0,10), location_raw: locEl?.textContent?.trim()||'' };
            });
        }
        """

    def _parse_listing(self, raw: dict, filter_fuel=None) -> dict | None:
        ext_id = raw.get("id", "").strip()
        url = raw.get("url", "").strip()
        if "?" in url: url = url.split("?")[0]
        if not ext_id or not url: return None

        title = raw.get("title", "").strip()
        make, model = self._parse_title(title)
        details = raw.get("details", [])
        price_raw = raw.get("price_raw", "")
        price_eur = self._parse_price_eur(price_raw)

        if price_eur and price_eur < 3000:
            return None

        mileage_raw = year = fuel_type = transmission = power_str = body_type = None

        for d in details:
            if not d: continue
            dl = d.lower()
            if dl in ("diesel", "petrol", "electric", "hybrid", "lpg", "cng"):
                fuel_type = fuel_type or d
            elif "km" in dl and any(c.isdigit() for c in d):
                mileage_raw = mileage_raw or d
            elif self._extract_year(d):
                year = year or self._extract_year(d)
            elif any(k in dl for k in TRANSMISSION_MAP):
                transmission = transmission or self._normalize_transmission(d)
            elif re.search(r'\d+\s*(kw|ps|hp)', dl):
                power_str = power_str or d
            elif any(k in dl for k in BODY_MAP):
                body_type = body_type or self._normalize_body(d)

        if year and year < 2005:
            return None
        if not fuel_type and filter_fuel:
            fuel_type = filter_fuel

        country, city = self._parse_location(raw.get("location_raw", ""))

        return {
            "external_id":     f"as24_{ext_id}",
            "source":          self.SOURCE_NAME,
            "title":           title,
            "make":            make,
            "model":           model,
            "year":            year,
            "price":           price_eur,
            "currency":        "EUR",
            "mileage":         self._parse_mileage_km(mileage_raw),
            "fuel_type":       fuel_type,
            "transmission":    transmission,
            "engine_power_kw": self._parse_power_kw(power_str),
            "body_type":       body_type,
            "country":         country,
            "city":            city,
            "images":          raw.get("images", []),
            "url":             url,
        }

    def _parse_title(self, title: str) -> tuple:
        if not title: return None, None
        for make in sorted(KNOWN_MAKES, key=len, reverse=True):
            if make.lower() in title.lower():
                rest = re.sub(re.escape(make), "", title, flags=re.IGNORECASE).strip()
                words = rest.split()
                return make, (" ".join(words[:2]) if words else None)
        words = title.split()
        return (words[0] if words else None), (" ".join(words[1:3]) if len(words) > 1 else None)

    def _parse_price_eur(self, raw: str) -> int | None:
        if not raw: return None
        m = re.search(r'\d[\d.,]+\d', raw)
        if m:
            num = m.group(0).replace('.', '').replace(',', '')
            try:
                val = int(num)
                return val if val <= 2_000_000 else None
            except ValueError: pass
        digits = re.sub(r'[^\d]', '', raw)
        return int(digits[:6]) if digits else None

    def _parse_mileage_km(self, raw: str) -> int | None:
        if not raw: return None
        m = re.search(r'\d[\d.,]+\d|\d+', raw)
        if m:
            num = m.group(0).replace('.', '').replace(',', '')
            try:
                val = int(num)
                return val if 1 <= val <= 999_999 else None
            except ValueError: pass
        return None

    def _extract_year(self, text: str) -> int | None:
        m = re.search(r'\b(0[1-9]|1[0-2])[\/\.](19[5-9]\d|20[0-3]\d)\b', text)
        if m: return int(m.group(2))
        m = re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', text)
        return int(m.group(1)) if m else None

    def _normalize_transmission(self, val: str) -> str | None:
        v = val.lower()
        for k, norm in TRANSMISSION_MAP.items():
            if k in v: return norm
        return None

    def _normalize_body(self, val: str) -> str | None:
        v = val.lower()
        for k, norm in BODY_MAP.items():
            if k in v: return norm
        return None

    def _parse_power_kw(self, raw: str) -> int | None:
        if not raw: return None
        kw = re.search(r'(\d+)\s*kw', raw.lower())
        if kw: return int(kw.group(1))
        ps = re.search(r'(\d+)\s*(ps|hp)', raw.lower())
        if ps: return round(int(ps.group(1)) * 0.7355)
        return None

    def _parse_location(self, raw: str) -> tuple:
        if not raw: return None, None
        raw = raw.split('\n')[0].strip()
        m = re.match(r'^([A-Z]{2})-\d+\s+(.+)', raw)
        if m:
            return m.group(1), m.group(2).split(' - ')[0].strip()
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) >= 2:
            country = parts[-1].strip()
            city = parts[0].split(' - ')[0].strip()
            if len(country) <= 3:
                return country, city
            return None, parts[0]
        return None, raw
