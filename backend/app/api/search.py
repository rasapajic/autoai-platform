from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.db import get_db
from app.models import Listing
from app.api.schemas import SearchFilters, SearchResponse, ListingCard

router = APIRouter()

FUEL_MAP = {
    "dizel":      ["diesel", "dizel"],
    "diesel":     ["diesel", "dizel"],
    "benzin":     ["petrol", "benzin", "gasoline"],
    "petrol":     ["petrol", "benzin", "gasoline"],
    "električni": ["electric", "elektro", "električni"],
    "electric":   ["electric", "elektro", "električni"],
    "hibrid":     ["hybrid", "hibrid"],
    "hybrid":     ["hybrid", "hibrid"],
    "plin":       ["lpg", "autogas", "plin"],
    "lpg":        ["lpg", "autogas", "plin"],
    "cng":        ["cng", "erdgas"],
}

BODY_KEYWORDS = {
    "cabrio":    ["Cabrio", "Cabriolet", "Convertible", "Roadster", "Kabriolet", "Spider", "Spyder", "Targa"],
    "suv":       ["SUV", "Geländewagen", "Crossover", "Allroad", "Offroad", "4x4"],
    "kombi":     ["Kombi", "Estate", "Touring", "Avant", "Variant", "SW", "Break", "Sportourer"],
    "hatchback": ["Hatchback", "Schrägheck"],
    "coupe":     ["Coupe", "Coupé", "Fastback"],
    "sedan":     ["Limousine", "Berlina", "Saloon"],
    "van":       ["Van", "Minivan", "MPV", "Kleinbus", "Multivan", "Sharan", "Galaxy"],
    "pickup":    ["Pickup", "Pick-up", "Amarok", "Ranger", "Navara", "Hilux"],
}

@router.get("/", response_model=SearchResponse)
def search(filters: SearchFilters = Depends(), db: Session = Depends(get_db)):
    q = db.query(Listing).filter(
        Listing.is_active == True,
        Listing.price != None,
        Listing.price > 0,
    )

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
        variants = FUEL_MAP.get(filters.fuel_type.lower(), [filters.fuel_type.lower()])
        q = q.filter(or_(*[Listing.fuel_type.ilike(v) for v in variants]))

    if filters.transmission:
        q = q.filter(Listing.transmission == filters.transmission)

    if filters.body_type:
        keywords = BODY_KEYWORDS.get(filters.body_type.lower(), [])
        body_conditions = [Listing.body_type == filters.body_type]
        for kw in keywords:
            body_conditions.append(Listing.make.ilike(f"%{kw}%"))
            body_conditions.append(Listing.model.ilike(f"%{kw}%"))
        q = q.filter(or_(*body_conditions))

    if filters.country:
        q = q.filter(Listing.country.ilike(f"%{filters.country}%"))

    if filters.price_rating:
        q = q.filter(Listing.price_rating == filters.price_rating)

    if filters.source:
        q = q.filter(Listing.source == filters.source)

    if filters.query:
        term = f"%{filters.query}%"
        q = q.filter(or_(
            Listing.make.ilike(term),
            Listing.model.ilike(term),
            Listing.description.ilike(term),
        ))

    sort_options = {
        "date":       Listing.scraped_at.desc(),
        "price_asc":  Listing.price.asc(),
        "price_desc": Listing.price.desc(),
        "best_deal":  Listing.price_delta_pct.asc(),
        "year_desc":  Listing.year.desc(),
        "km_asc":     Listing.mileage.asc(),
    }
    q = q.order_by(sort_options.get(filters.sort_by, Listing.scraped_at.desc()))

    total   = q.count()
    results = q.offset((filters.page - 1) * filters.limit).limit(filters.limit).all()
    pages   = (total + filters.limit - 1) // filters.limit

    return SearchResponse(
        total=total,
        page=filters.page,
        pages=pages,
        results=[ListingCard.model_validate(r) for r in results],
        filters_applied=filters.model_dump(exclude_none=True),
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
        "total_listings":  total,
        "active_listings": total,
        "portals":         portals,
        "top_makes":       top_makes,
        "avg_price_eur":   round(float(avg_price), 2) if avg_price else None,
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
