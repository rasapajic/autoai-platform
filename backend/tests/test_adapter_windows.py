import asyncio
import importlib
import json
import re

import pytest


ADAPTERS = [
    ("willhaben", "WillhabenScraper"), ("autoscout24", "AutoScout24Scraper"),
    ("marktplaats", "MarktplaatsScraper"), ("tweedehands", "TweedehandsScraper"),
    ("kleinanzeigen", "KleinanzeigenScraper"),
]


def configure_adapter(monkeypatch, name, fail_page=None):
    module = importlib.import_module(f"app.scrapers.{name}")
    requested = []

    class Response:
        def __init__(self, page):
            self.page = page
            self.status = 403 if page == fail_page else 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def text(self, **_kwargs):
            if name in {"marktplaats", "tweedehands"}:
                return json.dumps({"listings": [{"id": f"{self.page}_{i}"} for i in range(30)], "totalResultCount": 100000})
            return str(self.page)

    class Session:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        def get(self, url, params=None, **_kwargs):
            params = params or {}
            page = params.get("page") or (params["offset"] // 30 + 1 if "offset" in params else None)
            if page is None:
                match = re.search(r"seite:(\d+)", url)
                page = int(match.group(1)) if match else 1
            requested.append(page)
            return Response(page)

    async def no_wait(*_):
        pass

    monkeypatch.setattr(module.aiohttp, "ClientSession", Session)
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    if name == "willhaben":
        monkeypatch.setattr(module, "_extract_next_data", lambda html: {"page": int(html)})
        monkeypatch.setattr(module, "_extract_listings_from_next_data", lambda data: [{"id": f"{data['page']}_{i}"} for i in range(30)])
        monkeypatch.setattr(module, "_parse_ad", lambda data: {"external_id": data["id"]})
    elif name == "autoscout24":
        class Soup:
            def __init__(self, html, _parser):
                self.page = int(html)

            def select(self, _selector):
                return [{"id": f"{self.page}_{i}"} for i in range(30)]
        monkeypatch.setattr(module, "BeautifulSoup", Soup)
        monkeypatch.setattr(module, "_parse_card", lambda card: {"external_id": card["id"]})
    elif name == "kleinanzeigen":
        monkeypatch.setattr(module, "_parse_listings_from_html", lambda html: [{"external_id": f"{html}_{i}"} for i in range(30)])
    else:
        monkeypatch.setattr(module, "_parse_listing", lambda item: {"external_id": item["id"]})
    return module, requested


@pytest.mark.parametrize("name,class_name", ADAPTERS)
def test_adapter_requests_the_saved_window_instead_of_restarting(monkeypatch, name, class_name):
    module, requested = configure_adapter(monkeypatch, name)
    rows = asyncio.run(getattr(module, class_name)().scrape_listings({
        "start_page": 4, "strict_window": True, "country": "D", "category": "limousine",
    }, max_pages=3))
    assert requested == [4, 5, 6]
    assert len(rows) == 90


@pytest.mark.parametrize("name,class_name", ADAPTERS)
def test_failed_page_is_not_reported_as_a_complete_window(monkeypatch, name, class_name):
    module, requested = configure_adapter(monkeypatch, name, fail_page=5)
    with pytest.raises(RuntimeError, match="source_http_403"):
        asyncio.run(getattr(module, class_name)().scrape_listings({
            "start_page": 4, "strict_window": True, "country": "D", "category": "limousine",
        }, max_pages=3))
    assert requested == [4, 5]
