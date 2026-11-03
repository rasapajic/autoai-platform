import os

import pytest
from sqlalchemy import create_engine, text

from app.core.listing_schema import migrate_listing_metadata


@pytest.fixture
def connection():
    url = os.getenv("AUTOAI_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL test service is not configured")
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("CREATE TEMP TABLE listings (id INTEGER PRIMARY KEY, price INTEGER)"))
        conn.execute(text("INSERT INTO listings VALUES (1, 12000)"))
        conn.commit()
        yield conn
    engine.dispose()


def test_additive_migration_is_repeatable_and_preserves_existing_rows(connection):
    migrate_listing_metadata(connection)
    migrate_listing_metadata(connection)
    connection.commit()
    assert connection.execute(text("SELECT price, source_dates FROM listings WHERE id=1")).one() == (12000, None)
    connection.execute(text('''UPDATE listings SET source_dates='{"published":{"value":"2026-11-01","precision":"date"}}'::jsonb WHERE id=1'''))
    connection.commit()
    migrate_listing_metadata(connection)
    connection.commit()
    assert connection.execute(text("SELECT source_dates->'published'->>'value' FROM listings WHERE id=1")).scalar() == "2026-11-01"


def test_migration_rolls_back_transactionally(connection):
    migrate_listing_metadata(connection)
    connection.rollback()
    assert connection.execute(text("SELECT count(*) FROM pg_attribute WHERE attrelid='listings'::regclass AND attname='source_dates' AND NOT attisdropped")).scalar() == 0
    assert connection.execute(text("SELECT price FROM listings WHERE id=1")).scalar() == 12000
