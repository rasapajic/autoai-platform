"""A bounded cohort query on a single listing view, without stored valuations."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.models import Listing
from app.core.recommendation import (
    FRESH_DAYS, MAX_CANDIDATES, IDENTITY_FIELDS, missing_fields, number, fresh, damage_reported, recommend_offer,
)


def candidate_statement(listing, now):
    fields = ("id", "source", "external_id", "url", "is_active", "currency", "price", "year",
              "mileage", "engine_power_kw", "variant", "engine_cc", "condition", "accident_free",
              "last_seen_at", *IDENTITY_FIELDS)
    km, power = number(listing.mileage), number(listing.engine_power_kw)
    filters = [Listing.id != listing.id, Listing.is_active.is_(True), Listing.price > 0,
               func.lower(Listing.currency) == "eur", Listing.last_seen_at >= now-timedelta(days=FRESH_DAYS),
               Listing.last_seen_at <= now+timedelta(minutes=5), Listing.year.between(listing.year-1, min(now.year, listing.year+1)),
               Listing.mileage.between(max(0, km-max(5000, km*.2)), km+max(5000, km*.2)),
               Listing.engine_power_kw.between(power-max(2, power*.05), power+max(2, power*.05))]
    filters.extend(func.lower(func.trim(getattr(Listing, k))) == str(getattr(listing, k)).strip().lower() for k in IDENTITY_FIELDS)
    for key in ("variant", "engine_cc", "condition", "accident_free"):
        current = getattr(listing, key, None)
        if current is not None and str(current).strip():
            column = getattr(Listing, key)
            filters.append(func.lower(func.trim(column)) == str(current).strip().lower() if key in {"variant", "condition"} else column == current)
    return select(*(getattr(Listing, k) for k in fields)).where(*filters).order_by(Listing.last_seen_at.desc(), Listing.id).limit(MAX_CANDIDATES)


def listing_recommendation(db, listing):
    now = datetime.now(timezone.utc)
    if (missing_fields(listing, now) or not fresh(listing.last_seen_at, now)
        or number(listing.price) is None or number(listing.price) <= 0 or str(listing.currency or "").lower() != "eur"
        or damage_reported(listing) or listing.service_history is False):
        return recommend_offer(listing, now=now)
    try:
        # A separate savepoint keeps an optional comparison failure from poisoning the read.
        with db.begin_nested():
            rows = db.execute(candidate_statement(listing, now)).mappings().all()
        return recommend_offer(listing, rows, now)
    except Exception:
        return recommend_offer(listing, now=now, comparison_error=True)
