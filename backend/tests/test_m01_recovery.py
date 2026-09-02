import asyncio
from datetime import datetime, timezone
from importlib import import_module

import pytest
from fastapi import HTTPException

import app.api.m01_listings as recovery
from app.api.m01_listings import _prepare_source_batch
from app.core.source_policy import SOURCE_REGISTRY


EXPECTED_SOURCES = {
    "willhaben": ("willhaben", "AT"),
    "autoscout24": ("autoscout24", None),
    "marktplaats": ("marktplaats", "NL"),
    "2dehands": ("2dehands", "BE"),
    "kleinanzeigen": ("kleinanzeigen", "DE"),
}


def test_registry_matches_sources_that_populated_the_legacy_database():
    assert {
        key: (source.storage_source, source.default_country)
        for key, source in SOURCE_REGISTRY.items()
    } == EXPECTED_SOURCES


def test_every_recovery_adapter_imports_and_exposes_its_scraper_class():
    for source in SOURCE_REGISTRY.values():
        module = import_module(source.module)
        scraper_class = getattr(module, source.class_name)
        assert callable(scraper_class)


def test_prepare_batch_rejects_invalid_rows_and_deduplicates_external_ids():
    source = SOURCE_REGISTRY["willhaben"]
    now = datetime.now(timezone.utc)
    rows, skipped = _prepare_source_batch(
        source,
        [
            {"external_id": "wh_1", "url": "https://example.test/1", "price": 12000},
            {"external_id": "wh_1", "url": "https://example.test/1-new", "price": 11900},
            {"external_id": "", "url": "https://example.test/2", "price": 9000},
            {"external_id": "wh_3", "url": "not-a-url", "price": 9000},
            {"external_id": "wh_4", "url": "https://example.test/4", "price": 0},
        ],
        now,
    )

    assert skipped == 4
    assert len(rows) == 1
    assert rows[0]["external_id"] == "wh_1"
    assert rows[0]["url"] == "https://example.test/1-new"
    assert rows[0]["price"] == 11900
    assert rows[0]["source"] == "willhaben"
    assert rows[0]["country"] == "AT"
    assert rows[0]["first_seen_at"] == now
    assert rows[0]["last_seen_at"] == now


def test_prepare_batch_preserves_multimarket_country():
    source = SOURCE_REGISTRY["autoscout24"]
    now = datetime.now(timezone.utc)
    rows, skipped = _prepare_source_batch(
        source,
        [{
            "external_id": "as24_1",
            "url": "https://example.test/as24/1",
            "price": 22000,
            "country": "IT",
        }],
        now,
    )

    assert skipped == 0
    assert rows[0]["country"] == "IT"


def test_refresh_does_not_open_database_when_a_source_probe_fails(monkeypatch):
    async def failed_stage(_max_pages):
        raise HTTPException(status_code=502, detail="source_returned_no_valid_listings")

    def database_must_not_open():
        raise AssertionError("database opened before every source was validated")

    monkeypatch.setattr(recovery, "_stage_all_sources", failed_stage)
    monkeypatch.setattr(recovery, "SessionLocal", database_must_not_open)
    monkeypatch.setattr(recovery.settings, "AUTOAI_ADMIN_SECRET", "test-secret")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            recovery.refresh_all_sources(
                confirm=recovery.REFRESH_CONFIRMATION,
                max_pages=1,
                x_autoai_admin_secret="test-secret",
            )
        )

    assert exc_info.value.status_code == 502


def test_refresh_rolls_back_if_fresh_rows_cannot_be_inserted(monkeypatch):
    fresh_row = {
        "external_id": "wh_fresh",
        "source": "willhaben",
        "price": 10000,
        "url": "https://example.test/fresh",
    }

    async def successful_stage(_max_pages):
        return {"willhaben": [fresh_row]}, {"checked_at": "now", "by_source": {}}

    class FakeQuery:
        def scalar(self):
            return 10

        def delete(self, synchronize_session=False):
            assert synchronize_session is False
            return 10

    class FakeSession:
        rolled_back = False
        closed = False

        def query(self, _value):
            return FakeQuery()

        def add_all(self, rows):
            list(rows)

        def flush(self):
            raise RuntimeError("insert failed")

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    fake_db = FakeSession()
    monkeypatch.setattr(recovery, "_stage_all_sources", successful_stage)
    monkeypatch.setattr(recovery, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(recovery.settings, "AUTOAI_ADMIN_SECRET", "test-secret")

    with pytest.raises(RuntimeError, match="insert failed"):
        asyncio.run(
            recovery.refresh_all_sources(
                confirm=recovery.REFRESH_CONFIRMATION,
                max_pages=1,
                x_autoai_admin_secret="test-secret",
            )
        )

    assert fake_db.rolled_back is True
    assert fake_db.closed is True
