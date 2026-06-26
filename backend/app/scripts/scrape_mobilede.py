import argparse
import asyncio
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "mobile_de"


def main() -> int:
    args = parse_args()
    from app.core.db import SessionLocal
    from app.models import ScraperRun
    from app.scrapers.mobile_de import MobileDeScraper

    limit = max(1, min(args.limit, 20))
    filters = {
        key: value
        for key, value in {
            "make": args.make,
            "model": args.model,
            "country": args.country,
            "max_price": args.max_price,
            "min_year": args.min_year,
            "fuel_type": args.fuel_type,
        }.items()
        if value not in (None, "")
    }

    scraper = MobileDeScraper()
    listings = asyncio.run(scraper.scrape_listings(filters, max_pages=args.max_pages, limit=limit))

    db = SessionLocal()
    run = ScraperRun(portal=SOURCE, status="running")
    db.add(run)
    db.commit()

    try:
        result = upsert_mobilede_listings(db, listings)
        run.listings_found = len(listings)
        run.listings_new = result["created"]
        run.listings_updated = result["updated"]
        run.status = "success"
        run.finished_at = datetime.utcnow()
        db.commit()

        logger.info(
            "Mobile.de scrape done: created=%s updated=%s skipped=%s fetched=%s",
            result["created"],
            result["updated"],
            result["skipped"],
            len(listings),
        )
        print(result)
        return 0
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        logger.exception("Mobile.de scrape failed")
        return 1
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual small-batch Mobile.de scraper")
    parser.add_argument("--limit", type=int, default=20, help="Number of listings to fetch, capped at 20")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum search result pages to visit")
    parser.add_argument("--make", default="", help="Optional make filter")
    parser.add_argument("--model", default="", help="Optional model filter")
    parser.add_argument("--country", default="", help="Accepted for CLI symmetry; Mobile.de MVP searches Germany")
    parser.add_argument("--max-price", type=int, default=None)
    parser.add_argument("--min-year", type=int, default=None)
    parser.add_argument("--fuel-type", default="", choices=["", "petrol", "diesel", "electric", "hybrid", "lpg", "cng"])
    return parser.parse_args()


def upsert_mobilede_listings(db, listings: list[dict[str, Any]]) -> dict[str, int]:
    from app.models import Listing, PriceHistory

    now = datetime.utcnow()
    created = updated = skipped = 0

    for data in listings:
        external_id = data.get("external_id")
        url = data.get("url")
        source = data.get("source")

        if source != SOURCE or not external_id or not url:
            skipped += 1
            continue

        price = _decimal_or_none(data.get("price"))
        existing = (
            db.query(Listing)
            .filter(Listing.source == SOURCE, Listing.external_id == external_id)
            .first()
        )

        if existing:
            old_price = _decimal_or_none(existing.price)
            _apply_listing_data(existing, data, now, price)
            if price is not None and old_price != price:
                db.add(PriceHistory(listing_id=existing.id, price=price, currency=data.get("currency", "EUR")))
            updated += 1
        else:
            listing = Listing(**_listing_create_payload(data, now, price))
            db.add(listing)
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def _apply_listing_data(listing, data: dict[str, Any], now: datetime, price: Decimal | None) -> None:
    for key, value in _listing_update_payload(data, now, price).items():
        setattr(listing, key, value)


def _listing_create_payload(data: dict[str, Any], now: datetime, price: Decimal | None) -> dict[str, Any]:
    payload = _listing_update_payload(data, now, price)
    payload.update({
        "external_id": data["external_id"],
        "source": SOURCE,
        "first_seen_at": now,
    })
    return payload


def _listing_update_payload(data: dict[str, Any], now: datetime, price: Decimal | None) -> dict[str, Any]:
    allowed = {
        "make",
        "model",
        "variant",
        "year",
        "currency",
        "mileage",
        "fuel_type",
        "transmission",
        "engine_power_kw",
        "engine_cc",
        "body_type",
        "color",
        "country",
        "city",
        "description",
        "images",
        "features",
        "url",
        "condition",
        "accident_free",
        "service_history",
    }
    payload = {key: data.get(key) for key in allowed if data.get(key) is not None}
    payload.update({
        "is_active": True,
        "last_seen_at": now,
        "scraped_at": now,
    })
    if price is not None:
        payload["price"] = price
    return payload


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
