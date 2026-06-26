from collections import Counter
import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Listing, ScraperRun

router = APIRouter()

TRACKED_SOURCES = ["autoscout24", "willhaben", "mobile_de"]


@router.get("/coverage")
def coverage_stats(db: Session = Depends(get_db)):
    total_listings = db.query(func.count(Listing.id)).scalar() or 0
    active_listings = db.query(func.count(Listing.id)).filter(Listing.is_active == True).scalar() or 0

    by_source = _count_group(db, Listing.source)
    by_country = _count_group(db, Listing.country)
    by_make = _count_group(db, Listing.make)
    by_model = _top_models(db)

    listings_with_price = _count_where(db, Listing.price.isnot(None))
    listings_with_mileage = _count_where(db, Listing.mileage.isnot(None))
    listings_with_year = _count_where(db, Listing.year.isnot(None))

    active_all = db.query(Listing).filter(Listing.is_active == True).all()
    special_vehicle_count = sum(1 for listing in active_all if listing.special_vehicle)

    active_priced = (
        db.query(Listing)
        .filter(Listing.is_active == True, Listing.price.isnot(None), Listing.make.isnot(None))
        .all()
    )
    non_special = [listing for listing in active_priced if not listing.special_vehicle]

    model_counts = _model_comparable_counts(non_special)
    readiness = {
        "models_with_50_plus_comparables": sum(1 for count in model_counts.values() if count >= 50),
        "models_with_100_plus_comparables": sum(1 for count in model_counts.values() if count >= 100),
        "models_with_300_plus_comparables": sum(1 for count in model_counts.values() if count >= 300),
    }

    return {
        "total_listings": total_listings,
        "active_listings": active_listings,
        "by_source": by_source,
        "by_country": by_country,
        "by_make": by_make,
        "by_model": by_model,
        "listings_with_price": listings_with_price,
        "listings_with_mileage": listings_with_mileage,
        "listings_with_year": listings_with_year,
        "special_vehicle_count": special_vehicle_count,
        "valuation_readiness": readiness,
        "source_coverage": {source: by_source.get(source, 0) for source in TRACKED_SOURCES},
        "last_expansion_run": _last_expansion_run(db),
    }


def _count_group(db: Session, column) -> dict[str, int]:
    rows = (
        db.query(column, func.count(Listing.id))
        .filter(Listing.is_active == True, column.isnot(None))
        .group_by(column)
        .order_by(func.count(Listing.id).desc())
        .all()
    )
    return {str(key): count for key, count in rows if key not in (None, "")}


def _top_models(db: Session) -> list[dict]:
    rows = (
        db.query(Listing.make, Listing.model, func.count(Listing.id))
        .filter(Listing.is_active == True, Listing.make.isnot(None), Listing.model.isnot(None))
        .group_by(Listing.make, Listing.model)
        .order_by(func.count(Listing.id).desc())
        .limit(20)
        .all()
    )
    return [
        {"make": make, "model": model, "count": count}
        for make, model, count in rows
    ]


def _count_where(db: Session, condition) -> int:
    return db.query(func.count(Listing.id)).filter(Listing.is_active == True, condition).scalar() or 0


def _model_comparable_counts(listings: list[Listing]) -> dict[tuple[str, str], int]:
    counts = Counter()
    for listing in listings:
        model_key = (str(listing.make or "").strip().lower(), str(listing.model or "").strip().lower())
        if all(model_key):
            counts[model_key] += 1
    return dict(counts)


def _last_expansion_run(db: Session) -> dict:
    last_run = (
        db.query(ScraperRun)
        .filter(ScraperRun.portal == "marketplace_expansion")
        .order_by(ScraperRun.started_at.desc())
        .first()
    )
    last_success = (
        db.query(ScraperRun)
        .filter(ScraperRun.portal == "marketplace_expansion", ScraperRun.status.in_(["success", "partial"]))
        .order_by(ScraperRun.started_at.desc())
        .first()
    )

    if not last_run:
        return {
            "last_run_at": None,
            "last_status": None,
            "last_success_at": None,
            "last_duration_seconds": None,
            "last_created_count": 0,
            "last_updated_count": 0,
            "last_skipped_count": 0,
            "last_active_listings_delta": 0,
        }

    metadata = _run_metadata(last_run)
    return {
        "last_run_at": last_run.started_at,
        "last_status": last_run.status,
        "last_success_at": last_success.finished_at if last_success else None,
        "last_duration_seconds": _duration_seconds(last_run),
        "last_created_count": last_run.listings_new or 0,
        "last_updated_count": last_run.listings_updated or 0,
        "last_skipped_count": metadata.get("skipped", 0),
        "last_active_listings_delta": metadata.get("active_listings_delta", 0),
    }


def _run_metadata(run: ScraperRun) -> dict:
    if not run.error_message:
        return {}
    try:
        data = json.loads(run.error_message)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _duration_seconds(run: ScraperRun) -> int | None:
    if not run.started_at or not run.finished_at:
        return None
    started_at = run.started_at.replace(tzinfo=None)
    finished_at = run.finished_at.replace(tzinfo=None)
    return max(0, int((finished_at - started_at).total_seconds()))
