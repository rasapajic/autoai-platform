import asyncio
import re
import aiohttp

SEARCH_URL = "https://www.tutti.ch/api/v10/ads"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "de-CH,de;q=0.9",
    "Origin": "https://www.tutti.ch",
    "Referer": "https://www.tutti.ch/de/q/fahrzeuge/occasionen/autos",
}


class TuttiScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            params = {
                "category_id": 10,
                "sub_category_id": 11,
                "page":     1,
                "page_size": 10,
            }
            try:
                async with session.get(
                    SEARCH_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    text = await resp.text()
                    raise Exception(f"STATUS={resp.status} CT={resp.content_type} BODY={text[:800]}")
            except Exception as e:
                print(f"[Tutti DEBUG] {e}")
                raise
        return []
