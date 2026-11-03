import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core import listing_date_refresh as refresh


def listing(**values):
    return SimpleNamespace(source="willhaben", external_id="wh_123", url=values.get("url", "https://www.willhaben.at/iad/gebrauchtwagen/d/auto/vw-golf-123/"), source_dates=values.get("source_dates"))


def test_visible_last_modified_is_converted_from_vienna_and_never_inferred_from_publish():
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    html = "<p>Zuletzt geändert: 01.11.2026, 13:09 Uhr | willhaben-Code: 123</p>"
    entry = refresh.visible_willhaben_modified(html, now)
    assert entry["value"] == "2026-11-01T12:09:00+00:00"
    assert entry["precision"] == "minute"
    assert refresh.visible_willhaben_modified("Veröffentlicht: 01.11.2026", now) is None
    assert refresh.visible_willhaben_modified(html + " Zuletzt geändert: 02.11.2026, 13:09 Uhr", now) is None


@pytest.mark.parametrize("url", ["http://www.willhaben.at/iad/gebrauchtwagen/d/auto/123", "https://evil.test/iad/gebrauchtwagen/d/auto/123", "https://www.willhaben.at@evil.test/iad/gebrauchtwagen/d/auto/123", "https://www.willhaben.at/iad/gebrauchtwagen/d/auto/456", "https://www.willhaben.at/search/123"])
def test_unrelated_urls_and_listing_ids_are_rejected(url):
    assert refresh.willhaben_detail_url(listing(url=url)) is None


def test_streamed_html_is_read_completely_within_the_bound(monkeypatch):
    class Response:
        status = 200
        headers = {}
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        @property
        def content(self): return self
        async def iter_chunked(self, _size):
            yield b"<html><head></head><body>"
            yield "Zuletzt geändert: 01.11.2025, 13:09 Uhr".encode()
            yield b"</body></html>"
    class Session:
        def __init__(self, **_): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        def get(self, _url, **kwargs):
            assert kwargs["allow_redirects"] is False
            return Response()
    monkeypatch.setattr(refresh.aiohttp, "ClientSession", Session)
    status, modified = asyncio.run(refresh.fetch_willhaben_modified(listing().url))
    assert status == 200 and modified["value"] == "2025-11-01T12:09:00+00:00"


@pytest.fixture
def state(monkeypatch):
    state = SimpleNamespace(pauses={}, fetches=0, committed=False, locked=True)
    class DB:
        def get(self, _model, key):
            return state.pauses.get(key)
        def execute(self, _statement):
            return SimpleNamespace(scalar=lambda: state.locked)
        def refresh(self, _row, **_kwargs):
            pass
        def add(self, pause):
            state.pauses[pause.pause_key] = pause
        def commit(self):
            state.committed = True
        def rollback(self):
            pass
    async def fetch(_url):
        state.fetches += 1
        return state.status, state.modified
    state.status = 200
    state.modified = {"value": "2025-11-01T12:00:00+00:00", "precision": "minute", "semantics": "modified"}
    state.db = DB()
    monkeypatch.setattr(refresh, "get_enabled_source", lambda _: None)
    monkeypatch.setattr(refresh, "fetch_willhaben_modified", fetch)
    return state


def test_cached_observation_is_preserved_and_repeated_views_do_not_refetch(state):
    row = listing(source_dates={"published": {"value": "2025-01-01", "precision": "date"}})
    asyncio.run(refresh.refresh_missing_modified(state.db, row))
    assert row.source_dates["published"]["value"] == "2025-01-01"
    assert row.source_dates["modified"] == state.modified
    assert state.committed
    asyncio.run(refresh.refresh_missing_modified(state.db, row))
    assert state.fetches == 1


def test_existing_source_refusal_prevents_fetch_and_is_never_cleared(state):
    pause = SimpleNamespace(retry_after=datetime.now(timezone.utc) + timedelta(days=1))
    state.pauses["source:willhaben"] = pause
    asyncio.run(refresh.refresh_missing_modified(state.db, listing()))
    assert state.fetches == 0 and state.pauses["source:willhaben"] is pause


def test_a_detail_refusal_is_cached_and_pauses_the_source(state):
    state.status, state.modified = 403, None
    row = listing()
    asyncio.run(refresh.refresh_missing_modified(state.db, row))
    assert "modified" not in row.source_dates
    assert state.pauses["source:willhaben"].retry_after > datetime.now(timezone.utc) + timedelta(hours=23)


def test_expired_cached_modification_is_checked_again(state):
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    row = listing(source_dates={"_detail_checked_at": old, "modified": {"value": "2024-01-01", "observed_at": old}})
    asyncio.run(refresh.refresh_missing_modified(state.db, row))
    assert state.fetches == 1 and row.source_dates["modified"] == state.modified
