import argparse
import json
import logging
import re
from typing import Any

from sqlalchemy import case, func, or_

from app.core.db import SessionLocal
from app.models import Listing
from app.services.location_parser import parse_city, parse_city_from_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SOURCES = ["autoscout24", "willhaben", "demo_seed"]


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        sources = [args.source] if args.source else DEFAULT_SOURCES
        before = {source: audit_source(db, source) for source in sources}
        updated = 0

        if args.source in ("autoscout24", "willhaben"):
            updated = backfill_source(db, args.source, args.dry_run)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        after = {source: audit_source(db, source) for source in sources}
        report = {
            "dry_run": args.dry_run,
            "source": args.source or "all",
            "updated": updated,
            "before": before,
            "after": after,
        }
        print(json.dumps(report, indent=2, default=str))
        return 0
    except Exception:
        db.rollback()
        logger.exception("City backfill failed")
        return 1
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and backfill listing city fields")
    parser.add_argument("--source", default="", choices=["", "autoscout24", "willhaben", "demo_seed"])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def audit_source(db, source: str) -> dict[str, Any]:
    total = db.query(func.count(Listing.id)).filter(Listing.source == source).scalar() or 0
    with_city = (
        db.query(func.count(Listing.id))
        .filter(Listing.source == source, Listing.city.isnot(None), func.trim(Listing.city) != "")
        .scalar()
        or 0
    )
    by_country_rows = (
        db.query(
            Listing.country,
            func.count(Listing.id),
            func.sum(
                case(
                    (Listing.city.isnot(None) & (func.trim(Listing.city) != ""), 1),
                    else_=0,
                )
            ),
        )
        .filter(Listing.source == source)
        .group_by(Listing.country)
        .order_by(func.count(Listing.id).desc())
        .all()
    )
    return {
        "total_listings": total,
        "listings_with_city": with_city,
        "listings_without_city": total - with_city,
        "by_country": [
            {
                "country": country,
                "total": count,
                "with_city": int(city_count or 0),
                "without_city": count - int(city_count or 0),
            }
            for country, count, city_count in by_country_rows
        ],
    }


def backfill_source(db, source: str, dry_run: bool) -> int:
    listings = (
        db.query(Listing)
        .filter(
            Listing.source == source,
            or_(Listing.city.is_(None), func.trim(Listing.city) == ""),
        )
        .all()
    )
    updated = 0
    for listing in listings:
        city = infer_city(listing)
        if not city:
            continue
        updated += 1
        if not dry_run:
            listing.city = city
            if not listing.postal_code:
                listing.postal_code = infer_postal_code(listing)
    return updated


def infer_city(listing: Listing) -> str | None:
    country = listing.country
    candidates = [
        listing.description,
        " ".join(str(feature) for feature in (listing.features or [])) if isinstance(listing.features, list) else listing.features,
    ]
    for candidate in candidates:
        city = parse_city(candidate, country)
        if city:
            return city
    return parse_city_from_url(listing.url, country)


def infer_postal_code(listing: Listing) -> str | None:
    text = " ".join(str(value or "") for value in [listing.description, listing.variant, listing.url])
    match = re.search(r"\b\d{4,5}\b", text)
    return match.group(0) if match else None


if __name__ == "__main__":
    raise SystemExit(main())
