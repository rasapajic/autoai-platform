import argparse
import json
import logging
from typing import Any

from sqlalchemy import func, or_

from app.core.db import SessionLocal
from app.models import Listing

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


COUNTRY_ALIASES = {
    "D": "DE",
    "DE": "DE",
    "GERMANY": "DE",
    "DEUTSCHLAND": "DE",
    "A": "AT",
    "AT": "AT",
    "AUSTRIA": "AT",
    "OSTERREICH": "AT",
    "B": "BE",
    "BE": "BE",
    "BELGIUM": "BE",
    "BELGIQUE": "BE",
    "BELGIE": "BE",
    "NL": "NL",
    "NETHERLANDS": "NL",
    "NEDERLAND": "NL",
    "F": "FR",
    "FR": "FR",
    "FRANCE": "FR",
    "I": "IT",
    "IT": "IT",
    "ITALY": "IT",
    "ITALIA": "IT",
}


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        before = grouped_counts(db)
        top_records = top_autoscout24_records(db)
        normalized = normalize_existing_country_values(db, dry_run=args.dry_run)
        missing = fill_missing_country(db, args.missing_country, dry_run=args.dry_run)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        after = grouped_counts(db)
        report = {
            "dry_run": args.dry_run,
            "before": before,
            "top_20_autoscout24": top_records,
            "normalized_existing_country_values": normalized,
            "missing_country_set_to": args.missing_country,
            "missing_country_updated": missing,
            "after": after,
        }
        print(json.dumps(report, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        logger.exception("AutoScout24 country backfill failed")
        return 1
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and backfill AutoScout24 country values")
    parser.add_argument(
        "--missing-country",
        default="DE",
        choices=["DE", "AT", "BE", "NL", "FR", "IT"],
        help="Country assigned to existing AutoScout24 rows with NULL/empty country",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without committing them")
    return parser.parse_args()


def grouped_counts(db) -> list[dict[str, Any]]:
    rows = (
        db.query(Listing.source, Listing.country, func.count(Listing.id))
        .group_by(Listing.source, Listing.country)
        .order_by(Listing.source.asc(), Listing.country.asc().nullsfirst())
        .all()
    )
    return [
        {
            "source": source,
            "country": country,
            "count": count,
        }
        for source, country, count in rows
    ]


def top_autoscout24_records(db) -> list[dict[str, Any]]:
    rows = (
        db.query(Listing.id, Listing.make, Listing.model, Listing.country, Listing.city)
        .filter(Listing.source == "autoscout24")
        .order_by(Listing.scraped_at.desc().nullslast(), Listing.id.asc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": str(id_),
            "make": make,
            "model": model,
            "country": country,
            "city": city,
        }
        for id_, make, model, country, city in rows
    ]


def normalize_existing_country_values(db, dry_run: bool) -> int:
    updated = 0
    rows = (
        db.query(Listing)
        .filter(Listing.source == "autoscout24", Listing.country.isnot(None), func.trim(Listing.country) != "")
        .all()
    )
    for listing in rows:
        normalized = normalize_country(listing.country)
        if normalized and normalized != listing.country:
            updated += 1
            if not dry_run:
                listing.country = normalized
    return updated


def fill_missing_country(db, country: str, dry_run: bool) -> int:
    query = db.query(Listing).filter(
        Listing.source == "autoscout24",
        or_(Listing.country.is_(None), func.trim(Listing.country) == ""),
    )
    rows = query.all()
    if not dry_run:
        for listing in rows:
            listing.country = country
    return len(rows)


def normalize_country(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().upper().replace("\u00d6", "O")
    return COUNTRY_ALIASES.get(normalized, normalized)


if __name__ == "__main__":
    raise SystemExit(main())
