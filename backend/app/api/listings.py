from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.db import get_db
from app.core.auth import get_current_user, get_optional_user
from app.models import Listing, PriceHistory, Favorite
from app.api.schemas import ListingDetail, PriceHistoryPoint, MessageResponse

router = APIRouter()


@router.get("/{listing_id}", response_model=ListingDetail)
def get_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
):
    """Detalji jednog oglasa."""
    listing = db.query(Listing).filter(
        Listing.id == listing_id,
        Listing.is_active == True,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Oglas nije pronađen")

    return ListingDetail.model_validate(listing)


@router.get("/{listing_id}/price-history", response_model=list[PriceHistoryPoint])
def get_price_history(
    listing_id: UUID,
    db: Session = Depends(get_db),
):
    """Istorija promene cene za oglas — za grafikon."""
    history = (
        db.query(PriceHistory)
        .filter(PriceHistory.listing_id == listing_id)
        .order_by(PriceHistory.recorded_at.asc())
        .all()
    )
    return [PriceHistoryPoint.model_validate(h) for h in history]


@router.get("/{listing_id}/similar", response_model=list)
def get_similar(
    listing_id: UUID,
    limit: int = 6,
    db: Session = Depends(get_db),
):
    """Slični oglasi — ista marka/model, slična cena i km."""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Oglas nije pronađen")

    similar = (
        db.query(Listing)
        .filter(
            Listing.id != listing_id,
            Listing.is_active == True,
            Listing.make == listing.make,
            Listing.model == listing.model,
        )
        .order_by(
            # Sortiraj po sličnosti cene
            (Listing.price - listing.price if listing.price else 0),
        )
        .limit(limit)
        .all()
    )

    # Ako nema dovoljno — dopuni sa istom markom
    if len(similar) < limit:
        extra = (
            db.query(Listing)
            .filter(
                Listing.id != listing_id,
                Listing.id.notin_([s.id for s in similar]),
                Listing.is_active == True,
                Listing.make == listing.make,
            )
            .limit(limit - len(similar))
            .all()
        )
        similar.extend(extra)

    return [
        {
            "id":           str(s.id),
            "make":         s.make,
            "model":        s.model,
            "year":         s.year,
            "price":        float(s.price) if s.price else None,
            "mileage":      s.mileage,
            "fuel_type":    s.fuel_type,
            "country":      s.country,
            "images":       s.images[:1] if s.images else [],
            "price_rating": s.price_rating,
        }
        for s in similar
    ]


# ── Favoriti ──────────────────────────────────────────────────

@router.post("/{listing_id}/favorite", response_model=MessageResponse)
def add_favorite(
    listing_id: UUID,
    db:   Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """Dodaj oglas u favorite."""
    existing = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.listing_id == listing_id,
    ).first()

    if existing:
        return MessageResponse(message="Već u favoritima")

    fav = Favorite(user_id=user.id, listing_id=listing_id)
    db.add(fav)
    db.commit()
    return MessageResponse(message="Dodato u favorite")


@router.delete("/{listing_id}/favorite", response_model=MessageResponse)
def remove_favorite(
    listing_id: UUID,
    db:   Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """Ukloni iz favorita."""
    db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.listing_id == listing_id,
    ).delete()
    db.commit()
    return MessageResponse(message="Uklonjeno iz favorita")


@router.get("/compare/multi")
def compare_listings(
    ids: str,  # "id1,id2,id3"
    db: Session = Depends(get_db),
):
    """Poređenje do 3 oglasa side-by-side."""
    id_list = [i.strip() for i in ids.split(",")][:3]

    if len(id_list) < 2:
        raise HTTPException(status_code=400, detail="Potrebna su min. 2 oglasa za poređenje")

    listings = db.query(Listing).filter(Listing.id.in_(id_list)).all()

    return [
        {
            "id":             str(l.id),
            "make":           l.make,
            "model":          l.model,
            "year":           l.year,
            "price":          float(l.price) if l.price else None,
            "mileage":        l.mileage,
            "fuel_type":      l.fuel_type,
            "transmission":   l.transmission,
            "engine_power_kw": l.engine_power_kw,
            "body_type":      l.body_type,
            "country":        l.country,
            "price_rating":   l.price_rating,
            "price_estimated": float(l.price_estimated) if l.price_estimated else None,
            "price_delta_pct": float(l.price_delta_pct) if l.price_delta_pct else None,
            "features":       l.features or [],
            "images":         (l.images or [])[:1],
            "url":            l.url,
            "accident_free":  l.accident_free,
            "service_history": l.service_history,
        }
        for l in listings
    ]
