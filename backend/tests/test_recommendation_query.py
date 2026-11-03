import os
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text, MetaData, Table, insert, select
from sqlalchemy.orm import Session

from app.core import recommendation_query as query
from app.api.schemas import ListingRecommendation


@pytest.fixture
def catalog():
    url = os.getenv("AUTOAI_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL test service is not configured")
    engine = create_engine(url)
    with engine.connect() as connection:
        connection.execute(text("""CREATE TEMP TABLE listings (
            id UUID PRIMARY KEY, source TEXT, external_id TEXT, url TEXT, is_active BOOLEAN,
            currency TEXT, price NUMERIC, year INTEGER, mileage INTEGER, engine_power_kw INTEGER,
            variant TEXT, engine_cc INTEGER, condition TEXT, accident_free BOOLEAN,
            last_seen_at TIMESTAMPTZ, make TEXT, model TEXT, fuel_type TEXT, transmission TEXT,
            body_type TEXT, country TEXT
        )"""))
        table = Table("listings", MetaData(), autoload_with=connection)
        now = datetime.now(timezone.utc)
        base = dict(id=uuid4(), source="willhaben", external_id="target", url="https://example.test/target",
                    is_active=True, currency="EUR", price=18000, year=2023, mileage=60000,
                    engine_power_kw=110, variant="1.5 TSI", engine_cc=1498, condition="used", accident_free=True,
                    last_seen_at=now, make="Volkswagen", model="Tiguan", fuel_type="petrol",
                    transmission="automatic", body_type="suv", country="DE")
        rows = [{**base, "id":uuid4(), "external_id":f"comp-{i}", "url":f"https://example.test/{i}", "price":20000, "mileage":55001+i*200} for i in range(10)]
        bad = [{"country":"AT"}, {"fuel_type":"diesel"}, {"engine_power_kw":200},
               {"model":"Tiguan Allspace"}, {"variant":"2.0 TSI"}, {"engine_cc":1998},
               {"last_seen_at":now-timedelta(days=8)}, {"is_active":False}, {"currency":"CHF"},
               {"mileage":100000}, {"body_type":"estate"}, {"year":2010}, {"accident_free":None}]
        rows += [{**rows[0], **changes, "id":uuid4(), "external_id":f"bad-{i}", "url":f"https://bad.test/{i}"} for i,changes in enumerate(bad)]
        connection.execute(insert(table), [base, *rows])
        connection.commit()
        with Session(bind=connection) as session:
            yield session, SimpleNamespace(**base, service_history=True), table
    engine.dispose()


def test_bounded_read_only_query_and_response_schema_use_only_matching_observations(catalog):
    db, listing, table = catalog
    result = query.listing_recommendation(db, listing)
    assert result["status"] == "consider"
    assert result["comparison"]["sample_size"] == 10
    assert result["comparison"]["delta_pct"] == -10
    validated = ListingRecommendation.model_validate(result)
    assert validated.comparison.reference_price == 20000
    statement = str(query.candidate_statement(listing, datetime.now(timezone.utc)))
    assert "LIMIT" in statement and "images" not in statement and "description" not in statement
    assert db.execute(select(table.c.price).where(table.c.id == listing.id)).scalar() == 18000


def test_optional_query_failure_rolls_back_its_savepoint_without_breaking_the_listing_read(catalog, monkeypatch):
    db, listing, _table = catalog
    monkeypatch.setattr(query, "candidate_statement", lambda *_: text("SELECT nonexistent_recommendation_column FROM listings"))
    result = query.listing_recommendation(db, listing)
    assert result["status"] == "verify" and not result["comparison"]["available"]
    assert "trenutno nije dostupno" in result["reason"]
    assert db.execute(text("SELECT 1")).scalar() == 1


def test_incomplete_offer_does_not_query_or_trust_old_price_estimates():
    listing = SimpleNamespace(make="Volkswagen", model="Tiguan", year=None, mileage=None,
                              fuel_type=None, transmission=None, body_type=None, country=None,
                              engine_power_kw=None, price_estimated=30000, price=20000)
    result = query.listing_recommendation(object(), listing)
    assert result["status"] == "verify"
    assert "godište" in result["reason"]
