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


def test_prepare_batch_normalizes_numeric_vehicle_codes_from_title():
    rows, skipped = _prepare_source_batch(SOURCE_REGISTRY["willhaben"], [{
        "external_id": "wh_123", "url": "https://example.test/123", "price": 12000,
        "make": "1036", "model": "10004", "description": "Volkswagen Golf 1.6 TDI",
    }], datetime.now(timezone.utc))
    assert skipped == 0
    assert rows[0]["make"] == "Volkswagen"
    assert rows[0]["model"] == "Golf"


def test_prepare_batch_rejects_non_finite_or_boolean_prices():
    rows, skipped = _prepare_source_batch(SOURCE_REGISTRY["willhaben"], [
        {"external_id": f"wh_{i}", "url": "https://example.test/123", "price": price}
        for i, price in enumerate([float("inf"), float("nan"), True, 12000])
    ], datetime.now(timezone.utc))
    assert skipped == 3
    assert len(rows) == 1
    assert rows[0]["price"] == 12000


def test_willhaben_prefers_readable_source_labels_over_taxonomy_ids():
    from app.scrapers.willhaben import _parse_ad

    row = _parse_ad({"id": "123", "attributes": {"attribute": [
        {"name": "CAR_MODEL/MAKE", "values": ["1036"]},
        {"name": "CAR_MODEL/MAKE_RESOLVED", "values": ["Volkswagen"]},
        {"name": "CAR_MODEL/MODEL", "values": ["10004"]},
        {"name": "CAR_MODEL/MODEL_RESOLVED", "values": ["Golf"]},
        {"name": "PRICE", "values": ["12000"]},
    ]}})
    assert row["make"] == "Volkswagen"
    assert row["model"] == "Golf"


def test_identity_diagnostics_are_bounded_and_exclude_resolved_rows(monkeypatch):
    import app.api.m01_listings as recovery
    rows = [{"external_id": f"wh_{i}", "url": f"https://example.test/{i}", "price": 10000,
             "make": "1036", "description": "Unrecognized " + "x" * 300} for i in range(10)]
    rows.append({"external_id": "wh_known", "url": "https://example.test/known", "price": 10000, "make": "VW"})

    class Scraper:
        async def scrape_listings(self, *_args, **_kwargs):
            return rows

    monkeypatch.setattr(recovery, "_load_scraper", lambda _source: Scraper())
    batch, report = asyncio.run(recovery._fetch_source_batch(SOURCE_REGISTRY["willhaben"], 1, datetime.now(timezone.utc)))
    assert len(batch) == 11
    assert report["unresolved_make"] == 10
    assert len(report["identity_samples"]) == 5
    assert all(len(sample["headline"]) <= 140 and sample["raw_make"] == "1036" for sample in report["identity_samples"])
    assert "wh_known" not in {sample["external_id"] for sample in report["identity_samples"]}


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



def test_stage_rejects_external_id_collision_across_sources(monkeypatch):
    sources = [
        SOURCE_REGISTRY["willhaben"],
        SOURCE_REGISTRY["autoscout24"],
    ]

    async def colliding_fetch(source, _max_pages, now):
        return (
            [{
                "external_id": "shared-id",
                "source": source.storage_source,
                "url": f"https://example.test/{source.key}",
                "price": 10000,
                "is_active": True,
                "first_seen_at": now,
                "last_seen_at": now,
                "scraped_at": now,
            }],
            {"found": 1, "accepted": 1, "skipped": 0},
        )

    monkeypatch.setattr(recovery, "_require_all_historical_sources", lambda: sources)
    monkeypatch.setattr(recovery, "_fetch_source_batch", colliding_fetch)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(recovery._stage_all_sources(1))

    assert exc_info.value.status_code == 502
    assert "duplicate_external_id_across_sources:shared-id" in exc_info.value.detail


def test_scheduled_refresh_does_not_open_database_when_staging_fails(monkeypatch):
    async def failed_stage(_max_pages):
        raise HTTPException(status_code=502, detail="source_returned_no_valid_listings")

    def database_must_not_open():
        raise AssertionError("database opened before every source was validated")

    monkeypatch.setattr(recovery, "_stage_all_sources", failed_stage)
    monkeypatch.setattr(recovery, "SessionLocal", database_must_not_open)
    monkeypatch.setattr(recovery.settings, "AUTOAI_ADMIN_SECRET", "test-secret")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            recovery.scheduled_refresh_all_sources(
                confirm=recovery.SCHEDULED_REFRESH_CONFIRMATION,
                max_pages=1,
                x_autoai_admin_secret="test-secret",
            )
        )

    assert exc_info.value.status_code == 502


def test_scheduled_refresh_updates_in_place_and_never_deletes(monkeypatch):
    now = datetime.now(timezone.utc)
    preserved_first_seen = datetime(2025, 1, 1, tzinfo=timezone.utc)

    class ExistingListing:
        external_id = "wh_existing"
        source = "willhaben"
        first_seen_at = preserved_first_seen
        url = "https://example.test/old"
        is_active = False
        price_rating = "great"

    existing = ExistingListing()
    existing.source_dates = {"published": {"value": "2025-01-01", "precision": "date"}}
    staged = {
        "willhaben": [{
            "external_id": "wh_existing",
            "source_dates": {"modified": {"value": "2025-02-01", "precision": "date"}},
            "source": "willhaben",
            "url": "https://example.test/current",
            "price": 12500,
            "is_active": True,
            "first_seen_at": now,
            "last_seen_at": now,
            "scraped_at": now,
        }],
        "autoscout24": [{
            "external_id": "as24_new",
            "source": "autoscout24",
            "url": "https://example.test/new",
            "price": 17500,
            "is_active": True,
            "first_seen_at": now,
            "last_seen_at": now,
            "scraped_at": now,
        }],
    }

    class ListingQuery:
        def __init__(self):
            self.first_results = [existing, None]
            self.bulk_values = None

        def filter(self, *_conditions):
            return self

        def update(self, values, synchronize_session=False):
            assert synchronize_session is False
            self.bulk_values = values
            return 5

        def all(self):
            return [existing]

    class CountQuery:
        def __init__(self, values):
            self.values = values

        def filter(self, *_conditions):
            return self

        def scalar(self):
            return self.values.pop(0)

    class FakeSession:
        def __init__(self):
            self.listing_query = ListingQuery()
            self.count_query = CountQuery([5, 7, 4])
            self.added = []
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def query(self, value):
            if value is recovery.Listing:
                return self.listing_query
            return self.count_query

        def add(self, row):
            self.added.append(row)

        def flush(self):
            return None

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    fake_db = FakeSession()
    monkeypatch.setattr(recovery, "SessionLocal", lambda: fake_db)

    result = recovery._apply_scheduled_catalog_refresh(staged)

    assert fake_db.listing_query.bulk_values is None
    assert existing.url == "https://example.test/current"
    assert existing.is_active is True
    assert existing.first_seen_at == preserved_first_seen
    assert existing.source_dates["published"]["value"] == "2025-01-01"
    assert existing.source_dates["modified"]["value"] == "2025-02-01"
    assert existing.price_rating is None
    assert [row.external_id for row in fake_db.added] == ["as24_new"]
    assert result == {
        "active_before": 5,
        "new": 1,
        "updated": 1,
        "active_after": 7,
        "inactive_after": 4,
        "deactivated": 0,
        "coverage": "partial_sample",
    }
    assert fake_db.committed is True
    assert fake_db.rolled_back is False
    assert fake_db.closed is True


def test_large_partial_batch_uses_one_existing_listing_lookup(monkeypatch):
    size = 10000

    class CountQuery:
        def filter(self, *_):
            return self

        def scalar(self):
            return counts.pop(0)

    class ExistingQuery:
        def filter(self, *_):
            return self

        def all(self):
            return []

        def first(self):
            raise AssertionError("per-row listing lookups do not scale")

        def update(self, *_args, **_kwargs):
            raise AssertionError("a partial sample cannot deactivate unseen rows")

    class Session:
        existing_lookups = 0
        added = 0

        def query(self, value):
            if value is recovery.Listing:
                self.existing_lookups += 1
                return ExistingQuery()
            return CountQuery()

        def add(self, _row):
            self.added += 1

        def flush(self):
            pass

        def commit(self):
            pass

        def close(self):
            pass

        def rollback(self):
            raise AssertionError("unexpected rollback")

    counts = [5000, 15000, 0]
    session = Session()
    monkeypatch.setattr(recovery, "SessionLocal", lambda: session)
    result = recovery._apply_scheduled_catalog_refresh({"willhaben": [
        {"external_id": f"wh_{i}", "source": "willhaben", "url": f"https://example.test/{i}", "price": 12000}
        for i in range(size)
    ]})

    assert session.existing_lookups == 1
    assert session.added == size
    assert result["new"] == size
    assert result["active_after"] == 15000
    assert result["deactivated"] == 0
