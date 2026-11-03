"""Additive, repeatable listing metadata migration for existing installations."""
from sqlalchemy import text


def migrate_listing_metadata(connection):
    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    connection.execute(text("""
        ALTER TABLE listings
            ADD COLUMN IF NOT EXISTS contact_type VARCHAR(20) DEFAULT 'unknown',
            ADD COLUMN IF NOT EXISTS contact_url TEXT,
            ADD COLUMN IF NOT EXISTS source_dates JSONB
    """))
