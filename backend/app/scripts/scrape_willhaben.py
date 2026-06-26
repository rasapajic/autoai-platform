import argparse
import asyncio
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit, urlunsplit

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "willhaben"


def main() -> int:
    args = parse_args()
    from app.core.db import SessionLocal
    from app.models import ScraperRun
    from app.scrapers.willhaben import WillhabenScraper

    limit = max(1, min(args.limit, 20))
    filters = {
        key: value
        for key, value in {
            "make": args.make,
            "model": args.model,
            "country": "AT",
            "max_price": args.max_price,
            "min_year": args.min_year,
            "fuel_type": args.fuel_type,
        }.items()
        if value not in (None, "")
    }

    scraper = WillhabenScraper()
    listings = asyncio.run(scraper.scrape_listings(filters, max_pages=args.max_pages, limit=limit))

    db = SessionLocal()
    run = ScraperRun(portal=SOURCE, status="running")
    db.add(run)
    db.commit()

    try:
        cleanup = cleanup_existing_willhaben_duplicates(db)
        duplicate_report = build_duplicate_detection_report(db, listings)
        log_duplicate_detection_report(duplicate_report)
        result = upsert_willhaben_listings(db, listings)
        run.listings_found = len(listings)
        run.listings_new = result["created"]
        run.listings_updated = result["updated"]
        run.status = "success"
        run.finished_at = datetime.utcnow()
        db.commit()

        logger.info(
            "willhaben scrape done: created=%s updated=%s skipped=%s fetched=%s",
            result["created"],
            result["updated"],
            result["skipped"],
            len(listings),
        )
        print({**result, "cleanup": cleanup, "duplicates": duplicate_report})
        return 0
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        logger.exception("willhaben scrape failed")
        return 1
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual small-batch willhaben scraper")
    parser.add_argument("--limit", type=int, default=20, help="Number of listings to fetch, capped at 20")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum search result pages to visit")
    parser.add_argument("--make", default="", help="Optional make filter, e.g. BMW")
    parser.add_argument("--model", default="", help="Optional model filter")
    parser.add_argument("--max-price", type=int, default=None)
    parser.add_argument("--min-year", type=int, default=None)
    parser.add_argument("--fuel-type", default="", choices=["", "petrol", "diesel", "electric", "hybrid", "lpg", "cng"])
    return parser.parse_args()


def upsert_willhaben_listings(db, listings: list[dict[str, Any]]) -> dict[str, int]:
    from app.models import Listing, PriceHistory
    from sqlalchemy import or_

    now = datetime.utcnow()
    created = updated = skipped = 0

    for data in listings:
        external_id = data.get("external_id")
        url = canonical_url(data.get("url"))
        source = data.get("source")
        data["url"] = url

        if source != SOURCE or not external_id or not url:
            skipped += 1
            continue

        price = _decimal_or_none(data.get("price"))
        fingerprint = listing_fingerprint(data)
        existing = find_existing_willhaben_listing(db, Listing, external_id, url, fingerprint)

        if existing:
            old_price = _decimal_or_none(existing.price)
            existing.external_id = external_id
            _apply_listing_data(existing, data, now, price)
            deactivate_duplicate_rows(db, Listing, or_, existing.id, external_id, url, fingerprint)
            if price is not None and old_price != price:
                db.add(PriceHistory(listing_id=existing.id, price=price, currency=data.get("currency", "EUR")))
            updated += 1
        else:
            listing = Listing(**_listing_create_payload(data, now, price))
            db.add(listing)
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def deactivate_duplicate_rows(db, Listing, or_, keep_id, external_id: str, url: str, fingerprint: str | None = None) -> int:
    candidates = (
        db.query(Listing)
        .filter(
            Listing.source == SOURCE,
            Listing.id != keep_id,
            Listing.is_active == True,
            or_(Listing.external_id == external_id, Listing.url == url),
        )
        .all()
    )
    if fingerprint:
        fingerprint_matches = (
            db.query(Listing)
            .filter(Listing.source == SOURCE, Listing.id != keep_id, Listing.is_active == True)
            .all()
        )
        candidates.extend(
            row for row in fingerprint_matches
            if listing_fingerprint({
                "variant": row.variant,
                "price": row.price,
                "mileage": row.mileage,
                "images": row.images or [],
            }) == fingerprint
        )

    duplicates = list({duplicate.id: duplicate for duplicate in candidates}.values())
    for duplicate in duplicates:
        duplicate.is_active = False
    if duplicates:
        logger.warning(
            "willhaben deactivated duplicate rows for external_id=%s url=%s count=%s",
            external_id,
            url,
            len(duplicates),
        )
    return len(duplicates)


def find_existing_willhaben_listing(db, Listing, external_id: str, url: str, fingerprint: str | None = None):
    existing = (
        db.query(Listing)
        .filter(Listing.source == SOURCE, Listing.external_id == external_id)
        .first()
    )
    if existing:
        return existing

    existing = (
        db.query(Listing)
        .filter(Listing.source == SOURCE, Listing.url == url)
        .order_by(Listing.scraped_at.desc())
        .first()
    )
    if existing or not fingerprint:
        return existing

    candidates = (
        db.query(Listing)
        .filter(Listing.source == SOURCE, Listing.is_active == True)
        .order_by(Listing.scraped_at.desc())
        .all()
    )
    for candidate in candidates:
        candidate_fingerprint = listing_fingerprint({
            "variant": candidate.variant,
            "price": candidate.price,
            "mileage": candidate.mileage,
            "images": candidate.images or [],
        })
        if candidate_fingerprint == fingerprint:
            return candidate

    return None


def build_duplicate_detection_report(db, listings: list[dict[str, Any]]) -> dict[str, Any]:
    from app.models import Listing

    incoming = {
        "same_url": duplicate_groups(listings, lambda item: canonical_url(item.get("url"))),
        "same_external_id": duplicate_groups(listings, lambda item: item.get("external_id")),
        "same_image": duplicate_groups(listings, first_image),
        "same_fingerprint": duplicate_groups(listings, listing_fingerprint),
    }

    existing_rows = (
        db.query(Listing.external_id, Listing.url, Listing.images, Listing.variant, Listing.price, Listing.mileage)
        .filter(Listing.source == SOURCE, Listing.is_active == True)
        .all()
    )
    existing = [
        {
            "external_id": external_id,
            "url": url,
            "images": images or [],
            "variant": variant,
            "price": price,
            "mileage": mileage,
        }
        for external_id, url, images, variant, price, mileage in existing_rows
    ]

    return {
        "incoming": incoming,
        "existing_active": {
            "same_url": duplicate_groups(existing, lambda item: canonical_url(item.get("url"))),
            "same_external_id": duplicate_groups(existing, lambda item: item.get("external_id")),
            "same_image": duplicate_groups(existing, first_image),
            "same_fingerprint": duplicate_groups(existing, listing_fingerprint),
        },
    }


def cleanup_existing_willhaben_duplicates(db) -> dict[str, int]:
    from app.models import Listing

    rows = (
        db.query(Listing)
        .filter(Listing.source == SOURCE, Listing.is_active == True)
        .order_by(Listing.scraped_at.desc())
        .all()
    )
    deactivated_ids = set()

    for key_fn in (
        lambda row: row.external_id,
        lambda row: canonical_url(row.url),
        lambda row: listing_fingerprint({
            "variant": row.variant,
            "price": row.price,
            "mileage": row.mileage,
            "images": row.images or [],
        }),
    ):
        groups: dict[str, list[Any]] = {}
        for row in rows:
            key = key_fn(row)
            if key:
                groups.setdefault(str(key), []).append(row)

        for key, group in groups.items():
            active_group = [row for row in group if row.id not in deactivated_ids]
            if len(active_group) < 2:
                continue
            keep = active_group[0]
            for duplicate in active_group[1:]:
                duplicate.is_active = False
                deactivated_ids.add(duplicate.id)
            logger.warning(
                "willhaben cleanup deactivated duplicates key=%s keep=%s count=%s",
                key,
                keep.id,
                len(active_group) - 1,
            )

    if deactivated_ids:
        db.commit()
    return {"deactivated": len(deactivated_ids)}


def duplicate_groups(items: list[dict[str, Any]], key_fn) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = key_fn(item)
        if not key:
            continue
        groups.setdefault(str(key), []).append(item)

    report = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        report.append({
            "key": key,
            "count": len(group),
            "external_ids": [item.get("external_id") for item in group],
            "urls": [item.get("url") for item in group],
        })
    return report


def first_image(item: dict[str, Any]) -> str | None:
    images = item.get("images") or []
    if not images:
        return None
    return str(images[0])


def listing_fingerprint(item: dict[str, Any]) -> str | None:
    image = first_image(item)
    title = normalize_fingerprint_text(item.get("variant") or item.get("title"))
    price = normalize_price_for_fingerprint(item.get("price"))
    mileage = str(item.get("mileage") or "")
    if not image or not title or not price:
        return None
    return "|".join([title, image, price, mileage])


def normalize_fingerprint_text(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def normalize_price_for_fingerprint(value: Any) -> str:
    price = _decimal_or_none(value)
    if price is None:
        return ""
    return str(int(price))


def log_duplicate_detection_report(report: dict[str, Any]) -> None:
    for scope, values in report.items():
        for kind, groups in values.items():
            if groups:
                logger.warning("willhaben duplicate report %s.%s=%s", scope, kind, groups)
            else:
                logger.info("willhaben duplicate report %s.%s=none", scope, kind)


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


def canonical_url(url: Any) -> str:
    if not url:
        return ""
    parsed = urlsplit(str(url))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


if __name__ == "__main__":
    raise SystemExit(main())
