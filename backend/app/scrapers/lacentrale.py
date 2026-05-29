import asyncio
import re
import aiohttp

SEARCH_URL = "https://recherche.lacentrale.fr/v3/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Origin": "https://www.lacentrale.fr",
    "Referer": "https://www.lacentrale.fr/listing?families=AUTO",
    "X-Client-Source": "classified:lcpab:recherche-react",
    "x-api-key": "2vHD2GjDJ07RpNvbGYpJG7s6bQNwRNkI9SEkgQnR",
}


class LaCentraleScraper:
    async def scrape_listings(self, filters: dict, max_pages: int = 10) -> list:

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            params = {
                "families": "AUTO",
                "pageSize": 10,
                "page":     1,
            }

            try:
                async with session.get(
                    SEARCH_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    text = await resp.text()
                    raise Exception(f"STATUS={resp.status} BODY={text[:600]}")

            except Exception as e:
                print(f"[LaCentrale DEBUG] {e}")
                raise

        return []
