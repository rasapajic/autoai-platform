import asyncio
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)

# Lista user-agenta da izgledamo kao pravi browser
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
    """
    Osnovna klasa za sve scrapere.
    Svaki portal nasljeđuje ovu klasu i implementira
    svoje metode za parsiranje.
    """

    SOURCE_NAME: str = "unknown"
    BASE_URL: str = ""

    def __init__(self):
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def __aenter__(self):
        """Pokretanje browser-a."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        self.context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",  # izgledamo kao da smo iz Nemačke
            timezone_id="Europe/Berlin",
        )
        # Sakrij da smo bot
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return self

    async def __aexit__(self, *args):
        """Gašenje browser-a."""
        if self.browser:
            await self.browser.close()
        await self._playwright.stop()

    async def get_page(self, url: str, wait_for: str = None):
        """Otvori stranicu i čekaj da se učita."""
        page = await self.context.new_page()

        # Random delay da ne izgledamo kao bot
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

    @abstractmethod
    async def scrape_listings(self, filters: dict) -> list[dict]:
        """Glavna metoda — svaki portal implementira svoju."""
        pass

    @abstractmethod
    async def scrape_detail(self, url: str) -> dict:
        """Scraping detalja jednog oglasa."""
        pass

    def normalize(self, raw: dict) -> dict:
        """
        Normalizuje podatke u standardni format.
        Svaki portal vraća podatke drugačije,
        ovo ih sve svodi na isti format.
        """
        return {
            "external_id":    raw.get("external_id", ""),
            "source":         self.SOURCE_NAME,
            "make":           self._clean_text(raw.get("make")),
            "model":          self._clean_text(raw.get("model")),
            "variant":        self._clean_text(raw.get("variant")),
            "year":           self._parse_int(raw.get("year")),
            "price":          self._parse_price(raw.get("price")),
            "currency":       raw.get("currency", "EUR"),
            "mileage":        self._parse_int(raw.get("mileage")),
            "fuel_type":      self._normalize_fuel(raw.get("fuel_type")),
            "transmission":   self._normalize_transmission(raw.get("transmission")),
            "engine_power_kw": self._parse_int(raw.get("engine_power_kw")),
            "engine_cc":      self._parse_int(raw.get("engine_cc")),
            "body_type":      self._normalize_body(raw.get("body_type")),
            "color":          self._clean_text(raw.get("color")),
            "country":        raw.get("country", ""),
            "city":           self._clean_text(raw.get("city")),
            "description":    self._clean_text(raw.get("description")),
            "images":         raw.get("images", []),
            "features":       raw.get("features", []),
            "url":            raw.get("url", ""),
            "condition":      raw.get("condition", "used"),
            "accident_free":  raw.get("accident_free"),
            "service_history": raw.get("service_history"),
            "scraped_at":     datetime.utcnow().isoformat(),
        }

    # ── Helper metode ─────────────────────────────────────────

    def _clean_text(self, val) -> str | None:
        if not val:
            return None
        return str(val).strip()

    def _parse_int(self, val) -> int | None:
        if val is None:
            return None
        try:
            cleaned = str(val).replace(".", "").replace(",", "").replace(" ", "")
            cleaned = ''.join(filter(str.isdigit, cleaned))
            return int(cleaned) if cleaned else None
        except Exception:
            return None

    def _parse_price(self, val) -> float | None:
        if val is None:
            return None
        try:
            cleaned = str(val).replace(".", "").replace(",", ".").replace(" ", "").replace("€", "").replace("EUR", "")
            cleaned = ''.join(c for c in cleaned if c.isdigit() or c == '.')
            return float(cleaned) if cleaned else None
        except Exception:
            return None

    def _normalize_fuel(self, val) -> str | None:
        if not val:
            return None
        val = val.lower().strip()
        mapping = {
            "diesel": "diesel", "dizel": "diesel", "tdi": "diesel",
            "petrol": "petrol", "benzin": "petrol", "gasoline": "petrol", "benzine": "petrol",
            "electric": "electric", "elektro": "electric", "bev": "electric",
            "hybrid": "hybrid", "phev": "hybrid", "mhev": "hybrid",
            "lpg": "lpg", "cng": "cng", "autogas": "lpg",
        }
        for key, normalized in mapping.items():
            if key in val:
                return normalized
        return val

    def _normalize_transmission(self, val) -> str | None:
        if not val:
            return None
        val = val.lower().strip()
        if any(w in val for w in ["automatic", "automat", "automatik", "dsg", "cvt", "tiptronic"]):
            return "automatic"
        if any(w in val for w in ["manual", "manuell", "schaltgetriebe", "6-speed"]):
            return "manual"
        return val

    def _normalize_body(self, val) -> str | None:
        if not val:
            return None
        val = val.lower().strip()
        mapping = {
            "sedan": "sedan", "limousine": "sedan", "limuzina": "sedan",
            "suv": "suv", "geländewagen": "suv", "crossover": "suv",
            "hatchback": "hatchback", "schrägheck": "hatchback",
            "kombi": "kombi", "estate": "kombi", "touring": "kombi", "wagon": "kombi",
            "coupe": "coupe", "coupé": "coupe",
            "cabrio": "cabrio", "convertible": "cabrio", "kabriolet": "cabrio",
            "van": "van", "minivan": "van", "mpv": "van",
            "pickup": "pickup",
        }
        for key, normalized in mapping.items():
            if key in val:
                return normalized
        return val
