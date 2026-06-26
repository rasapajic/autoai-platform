from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_

from app.core.db import get_db
from app.models import Listing
from app.api.schemas import SearchFilters, SearchResponse, ListingCard

router = APIRouter()

PRICE_RATINGS = ["great", "good", "fair", "high", "overpriced"]

SOURCE_ALIASES = {
    "autoscout24": "autoscout24",
    "autoscout": "autoscout24",
    "willhaben": "willhaben",
    "mobile_de": "mobile_de",
    "mobile.de": "mobile_de",
    "mobilede": "mobile_de",
    "demo_seed": "demo_seed",
    "demo": "demo_seed",
}


def normalize_source(source: str | None) -> str | None:
    if not source:
        return None
    return SOURCE_ALIASES.get(source.strip().lower())


def apply_search_filters(q, filters: SearchFilters, include_price_rating: bool = True):
    if filters.make:
        q = q.filter(Listing.make.ilike(f"%{filters.make}%"))
    if filters.model:
        q = q.filter(Listing.model.ilike(f"%{filters.model}%"))
    if filters.min_price is not None:
        q = q.filter(Listing.price >= filters.min_price)
    if filters.max_price is not None:
        q = q.filter(Listing.price <= filters.max_price)
    if filters.min_year is not None:
        q = q.filter(Listing.year >= filters.min_year)
    if filters.max_year is not None:
        q = q.filter(Listing.year <= filters.max_year)
    if filters.min_km is not None:
        q = q.filter(Listing.mileage >= filters.min_km)
    if filters.max_km is not None:
        q = q.filter(Listing.mileage <= filters.max_km)
    if filters.fuel_type:
        q = q.filter(Listing.fuel_type == filters.fuel_type)
    if filters.transmission:
        q = q.filter(Listing.transmission == filters.transmission)
    if filters.body_type:
        q = q.filter(Listing.body_type == filters.body_type)
    if filters.country:
        q = q.filter(Listing.country.ilike(f"%{filters.country}%"))
    if include_price_rating and filters.price_rating:
        q = q.filter(Listing.price_rating == filters.price_rating)

    normalized_source = normalize_source(filters.source)
    if filters.source:
        if normalized_source:
            q = q.filter(func.lower(Listing.source) == normalized_source)
        else:
            q = q.filter(Listing.source == "__unknown_source__")

    if filters.query:
        term = f"%{filters.query}%"
        q = q.filter(or_(
            Listing.make.ilike(term),
            Listing.model.ilike(term),
            Listing.description.ilike(term),
        ))
    return q


def get_price_rating_counts(db: Session, filters: SearchFilters) -> dict[str, int]:
    q = apply_search_filters(
        db.query(Listing.price_rating, func.count(Listing.id)).filter(Listing.is_active == True),
        filters,
        include_price_rating=False,
    )
    rows = (
        q.filter(Listing.price_rating.in_(PRICE_RATINGS))
        .group_by(Listing.price_rating)
        .all()
    )
    counts = {rating: 0 for rating in PRICE_RATINGS}
    counts.update({rating: count for rating, count in rows})
    return counts


@router.get("/", response_model=SearchResponse)
def search(filters: SearchFilters = Depends(), db: Session = Depends(get_db)):
    q = apply_search_filters(
        db.query(Listing).filter(Listing.is_active == True),
        filters,
        include_price_rating=True,
    )
    normalized_source = normalize_source(filters.source)
    price_rating_counts = get_price_rating_counts(db, filters)

    source_priority = case(
        (Listing.source == "autoscout24", 0),
        (Listing.source == "willhaben", 1),
        (Listing.source == "mobile_de", 2),
        (Listing.source == "demo_seed", 9),
        else_=5,
    )
    default_sort = (source_priority, Listing.scraped_at.desc())
    sort_options = {
        "date": default_sort,
        "price_asc": Listing.price.asc(),
        "price_desc": Listing.price.desc(),
        "best_deal": Listing.price_delta_pct.asc(),
        "year_desc": Listing.year.desc(),
        "km_asc": Listing.mileage.asc(),
    }
    sort_order = sort_options.get(filters.sort_by, default_sort)
    if isinstance(sort_order, tuple):
        q = q.order_by(*sort_order)
    else:
        q = q.order_by(sort_order)

    total = q.count()
    results = q.offset((filters.page - 1) * filters.limit).limit(filters.limit).all()
    pages = (total + filters.limit - 1) // filters.limit

    filters_applied = filters.model_dump(exclude_none=True)
    if normalized_source:
        filters_applied["source"] = normalized_source

    return SearchResponse(
        total=total,
        page=filters.page,
        pages=pages,
        results=[ListingCard.model_validate(r) for r in results],
        filters_applied=filters_applied,
        price_rating_counts=price_rating_counts,
    )


@router.get("/stats")
def search_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Listing.id)).filter(Listing.is_active == True).scalar()

    portals = dict(
        db.query(Listing.source, func.count(Listing.id))
        .filter(Listing.is_active == True)
        .group_by(Listing.source)
        .all()
    )

    top_makes = [
        {"make": make, "count": count}
        for make, count in
        db.query(Listing.make, func.count(Listing.id))
        .filter(Listing.is_active == True, Listing.make != None)
        .group_by(Listing.make)
        .order_by(func.count(Listing.id).desc())
        .limit(10)
        .all()
    ]

    avg_price = db.query(func.avg(Listing.price)).filter(
        Listing.is_active == True,
        Listing.currency == "EUR",
        Listing.price > 0,
    ).scalar()

    return {
        "total_listings": total,
        "active_listings": total,
        "portals": portals,
        "top_makes": top_makes,
        "avg_price_eur": round(float(avg_price), 2) if avg_price else None,
    }


@router.get("/makes")
def get_makes(db: Session = Depends(get_db)):
    makes = (
        db.query(Listing.make, func.count(Listing.id).label("count"))
        .filter(Listing.is_active == True, Listing.make != None)
        .group_by(Listing.make)
        .order_by(func.count(Listing.id).desc())
        .limit(100)
        .all()
    )
    return [{"make": m, "count": c} for m, c in makes]


@router.get("/models")
def get_models(make: str, db: Session = Depends(get_db)):
    models = (
        db.query(Listing.model, func.count(Listing.id).label("count"))
        .filter(
            Listing.is_active == True,
            Listing.make.ilike(f"%{make}%"),
            Listing.model != None,
        )
        .group_by(Listing.model)
        .order_by(func.count(Listing.id).desc())
        .limit(50)
        .all()
    )
    return [{"model": m, "count": c} for m, c in models]
