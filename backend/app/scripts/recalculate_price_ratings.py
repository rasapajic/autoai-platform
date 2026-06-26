import argparse
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.db import SessionLocal
from app.models import Listing
from app.services.purchase_rating import calculate_purchase_rating

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        query = db.query(Listing).filter(Listing.is_active == True)
        if args.source:
            query = query.filter(Listing.source == args.source)

        listings = query.order_by(Listing.scraped_at.desc().nullslast()).all()
        report = {
            "source": args.source or "all",
            "checked": len(listings),
            "updated": 0,
            "skipped_insufficient_data": 0,
            "skipped_special": 0,
            "skipped_no_price": 0,
        }

        for listing in listings:
            if listing.special_vehicle:
                report["skipped_special"] += 1
                _clear_market_rating(listing)
                continue

            if listing.price is None:
                report["skipped_no_price"] += 1
                _clear_market_rating(listing)
                continue

            valuation = calculate_purchase_rating(db, listing)
            rating = _price_rating_from_purchase_rating(valuation)
            if not rating:
                report["skipped_insufficient_data"] += 1
                _clear_market_rating(listing)
                continue

            listing.price_rating = rating
            listing.price_estimated = _decimal_or_none(valuation.get("estimated_market_value"))
            listing.price_delta_pct = _delta_pct(valuation)
            report["updated"] += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        report["dry_run"] = args.dry_run
        print(json.dumps(report, indent=2))
        return 0
    except Exception:
        db.rollback()
        logger.exception("Price rating recalculation failed")
        return 1
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recalculate market price_rating values from comparable listings")
    parser.add_argument("--source", default="", help="Optional source filter, e.g. autoscout24 or willhaben")
    parser.add_argument("--dry-run", action="store_true", help="Calculate report without committing changes")
    return parser.parse_args()


def _price_rating_from_purchase_rating(valuation: dict[str, Any]) -> str | None:
    rating = valuation.get("rating")
    if rating == "VERY_GOOD_BUY":
        return "great"
    if rating == "GOOD_BUY":
        return "good"
    if rating == "FAIR_PRICE":
        return "fair"
    if rating == "EXPENSIVE":
        estimated = valuation.get("estimated_market_value")
        saving = valuation.get("potential_saving")
        if not estimated or saving is None:
            return "high"
        overpay_pct = abs(float(saving)) / float(estimated)
        return "overpriced" if overpay_pct >= 0.15 else "high"
    return None


def _delta_pct(valuation: dict[str, Any]) -> Decimal | None:
    asking = valuation.get("asking_price")
    estimated = valuation.get("estimated_market_value")
    if not asking or not estimated:
        return None
    delta = ((float(asking) - float(estimated)) / float(estimated)) * 100
    return Decimal(str(round(delta, 2)))


def _clear_market_rating(listing: Listing) -> None:
    listing.price_rating = None
    listing.price_estimated = None
    listing.price_delta_pct = None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
