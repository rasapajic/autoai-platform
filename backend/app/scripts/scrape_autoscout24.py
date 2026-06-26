import argparse
import asyncio
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    args = parse_args()
    from app.core.db import SessionLocal
    from app.models import ScraperRun
    from app.scrapers.autoscout24 import AutoScout24Scraper

    limit = max(1, min(args.limit, 50))
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

    scraper = AutoScout24Scraper()
    listings = asyncio.run(scraper.scrape_listings(filters, max_pages=args.max_pages, limit=limit))

    db = SessionLocal()
    run = ScraperRun(portal="autoscout24", status="running")
    db.add(run)
    db.commit()

    try:
        result = upsert_autoscout24_listings(db, listings)
        run.listings_found = len(listings)
        run.listings_new = result["created"]
        run.listings_updated = result["updated"]
        run.status = "success"
        run.finished_at = datetime.utcnow()
        db.commit()

        logger.info(
            "AutoScout24 scrape done: created=%s updated=%s skipped=%s fetched=%s",
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
        logger.exception("AutoScout24 scrape failed")
        return 1
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual small-batch AutoScout24 scraper")
    parser.add_argument("--limit", type=int, default=20, help="Number of listings to fetch, capped at 50")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum search result pages to visit")
    parser.add_argument("--make", default="", help="Optional make filter")
    parser.add_argument("--model", default="", help="Optional model filter")
    parser.add_argument(
        "--country",
        default="",
        choices=["", "DE", "AT", "BE", "NL", "FR", "IT"],
        help="Optional AutoScout24 country code: DE, AT, BE, NL, FR or IT",
    )
    parser.add_argument("--max-price", type=int, default=None)
    parser.add_argument("--min-year", type=int, default=None)
    parser.add_argument("--fuel-type", default="", choices=["", "petrol", "diesel", "electric", "hybrid", "lpg", "cng"])
    return parser.parse_args()


def upsert_autoscout24_listings(db, listings: list[dict[str, Any]]) -> dict[str, int]:
    from app.models import Listing, PriceHistory

    now = datetime.utcnow()
    created = updated = skipped = 0

    for data in listings:
        external_id = data.get("external_id")
        url = data.get("url")
        source = data.get("source")

        if source != "autoscout24" or not external_id or not url:
            skipped += 1
            continue

        price = _decimal_or_none(data.get("price"))
        existing = (
            db.query(Listing)
            .filter(Listing.source == "autoscout24", Listing.external_id == external_id)
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
        "source": "autoscout24",
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
    if "country" in payload:
        payload["country"] = _normalize_country(payload["country"])
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


def _normalize_country(value: Any) -> str | None:
    if value in (None, ""):
        return None

    normalized = str(value).strip().upper().replace("\u00d6", "O")
    mapping = {
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
    return mapping.get(normalized, normalized)


if __name__ == "__main__":
    raise SystemExit(main())
