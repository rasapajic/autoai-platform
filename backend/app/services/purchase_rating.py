from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from app.models import Listing


MIN_COMPARABLES = 5

LABELS = {
    "VERY_GOOD_BUY": "Vrlo dobra kupovina",
    "GOOD_BUY": "Dobra kupovina",
    "FAIR_PRICE": "Fer cena",
    "EXPENSIVE": "Preskupo",
    "ROUGH_ESTIMATE": "Gruba procena",
    "INSUFFICIENT_DATA": "Nema dovoljno podataka",
}


@dataclass
class PurchaseRatingResult:
    rating: str
    label: str
    asking_price: float | None
    estimated_market_value: float | None
    potential_saving: float | None
    comparable_count: int
    median_price: float | None
    p25_price: float | None
    p75_price: float | None
    confidence_percent: int
    market_low: float | None
    market_high: float | None
    comparable_year_range: dict[str, int | None]
    comparable_mileage_range: dict[str, int | None]
    debug: dict[str, Any]
    explanations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rating": self.rating,
            "label": self.label,
            "asking_price": self.asking_price,
            "estimated_market_value": self.estimated_market_value,
            "potential_saving": self.potential_saving,
            "comparable_count": self.comparable_count,
            "median_price": self.median_price,
            "p25_price": self.p25_price,
            "p75_price": self.p75_price,
            "confidence_percent": self.confidence_percent,
            "market_low": self.market_low,
            "market_high": self.market_high,
            "comparable_year_range": self.comparable_year_range,
            "comparable_mileage_range": self.comparable_mileage_range,
            "debug": self.debug,
            "explanations": self.explanations,
        }


def calculate_purchase_rating(db: Session, listing: Listing) -> dict[str, Any]:
    asking_price = _money(listing.price)
    if listing.special_vehicle or asking_price is None:
        return _insufficient(asking_price)

    comparables = _find_comparables(db, listing)
    prices = _trim_price_outliers([_money(item.price) for item in comparables])
    year_range = _range([item.year for item in comparables])
    mileage_range = _range([item.mileage for item in comparables])

    if len(prices) < MIN_COMPARABLES:
        return _insufficient(
            asking_price,
            comparable_count=len(prices),
            year_range=year_range,
            mileage_range=mileage_range,
        )

    median_price = _round_money(median(prices))
    p25_price = _round_money(_percentile(prices, 0.25))
    p75_price = _round_money(_percentile(prices, 0.75))
    estimated = median_price
    market_low = p25_price
    market_high = p75_price
    saving = _round_money(estimated - asking_price)
    saving_pct = saving / estimated if estimated else 0

    if saving_pct >= 0.10:
        rating = "VERY_GOOD_BUY"
    elif saving_pct >= 0.05:
        rating = "GOOD_BUY"
    elif saving_pct > -0.05:
        rating = "FAIR_PRICE"
    else:
        rating = "EXPENSIVE"

    raw_confidence = _confidence_percent(listing, comparables, prices)
    display_rating, display_label = _beta_display_rating(rating, len(prices))
    display_confidence = 0 if display_rating == "INSUFFICIENT_DATA" else raw_confidence

    return PurchaseRatingResult(
        rating=display_rating,
        label=display_label,
        asking_price=_round_money(asking_price),
        estimated_market_value=estimated,
        potential_saving=saving,
        comparable_count=len(prices),
        median_price=median_price,
        p25_price=p25_price,
        p75_price=p75_price,
        confidence_percent=display_confidence,
        market_low=market_low,
        market_high=market_high,
        comparable_year_range=year_range,
        comparable_mileage_range=mileage_range,
        debug={
            "comparable_count": len(prices),
            "median": median_price,
            "p25": p25_price,
            "p75": p75_price,
            "year_range": year_range,
            "mileage_range": mileage_range,
            "raw_rating": rating,
            "raw_label": LABELS[rating],
            "raw_confidence_percent": raw_confidence,
        },
        explanations=_build_explanations(listing, comparables, prices, saving_pct, display_rating),
    ).as_dict()


def _find_comparables(db: Session, listing: Listing) -> list[Listing]:
    query = db.query(Listing).filter(
        Listing.id != listing.id,
        Listing.is_active == True,
        Listing.price.isnot(None),
        Listing.make == listing.make,
    )

    if listing.year:
        query = query.filter(Listing.year.between(listing.year - 3, listing.year + 3))

    if listing.mileage is not None:
        mileage_delta = max(20_000, int(listing.mileage * 0.35))
        query = query.filter(
            Listing.mileage.isnot(None),
            Listing.mileage.between(
                max(0, listing.mileage - mileage_delta),
                listing.mileage + mileage_delta,
            ),
        )

    candidates = [item for item in query.limit(500).all() if not item.special_vehicle and _money(item.price) is not None]

    if listing.model:
        exact_model = [item for item in candidates if _same(item.model, listing.model)]
        if exact_model:
            candidates = exact_model

    if len(candidates) < MIN_COMPARABLES:
        return candidates

    candidates = _prefer_if_enough(candidates, lambda item: _same(item.fuel_type, listing.fuel_type), minimum=MIN_COMPARABLES)
    candidates = _prefer_if_enough(candidates, lambda item: _same(item.country, listing.country), minimum=8)

    return candidates


def _prefer_if_enough(items: list[Listing], predicate, minimum: int) -> list[Listing]:
    if not items:
        return items
    preferred = [item for item in items if predicate(item)]
    return preferred if len(preferred) >= minimum else items


def _trim_price_outliers(prices: list[float | None]) -> list[float]:
    clean = sorted(price for price in prices if price is not None and 100 <= price <= 5_000_000)
    if len(clean) < 10:
        return clean

    trim = max(1, int(len(clean) * 0.10))
    trimmed = clean[trim:-trim]
    return trimmed or clean


def _confidence_percent(listing: Listing, comparables: list[Listing], prices: list[float]) -> int:
    if len(prices) < MIN_COMPARABLES:
        return 0

    count_score = min(25, len(prices) * 2)
    make_score = 10 if listing.make and sum(1 for item in comparables if _same(item.make, listing.make)) >= MIN_COMPARABLES else 0
    exact_model_count = sum(1 for item in comparables if _same(item.model, listing.model))
    model_score = 18 if listing.model and exact_model_count >= MIN_COMPARABLES else -15 if listing.model else 0
    fuel_score = 10 if listing.fuel_type and sum(1 for item in comparables if _same(item.fuel_type, listing.fuel_type)) >= MIN_COMPARABLES else 0
    country_score = 10 if listing.country and sum(1 for item in comparables if _same(item.country, listing.country)) >= 8 else 0
    year_score = 12 if _similar_year_share(listing, comparables) >= 0.70 else 6 if listing.year else 0
    mileage_score = 10 if _similar_mileage_share(listing, comparables) >= 0.70 else 5 if listing.mileage is not None else 0
    spread_score = 5 if _price_spread_is_tight(prices) else 0
    return max(35, min(95, 15 + count_score + make_score + model_score + fuel_score + country_score + year_score + mileage_score + spread_score))


def _beta_display_rating(raw_rating: str, comparable_count: int) -> tuple[str, str]:
    if comparable_count < 50:
        return "INSUFFICIENT_DATA", "Nema dovoljno tržišnih podataka za pouzdanu procenu."
    if comparable_count < 100:
        return "ROUGH_ESTIMATE", LABELS["ROUGH_ESTIMATE"]
    return raw_rating, LABELS[raw_rating]


def _build_explanations(
    listing: Listing,
    comparables: list[Listing],
    prices: list[float],
    saving_pct: float,
    display_rating: str,
) -> list[str]:
    explanations = []
    if display_rating == "INSUFFICIENT_DATA":
        return [
            "Nema dovoljno tržišnih podataka za pouzdanu procenu.",
            f"Pronađeno {len(prices)} sličnih vozila.",
        ]

    percent = abs(round(saving_pct * 100))
    if display_rating == "ROUGH_ESTIMATE":
        explanations.append("Ovo je gruba procena na ograničenom broju tržišnih podataka.")
    elif saving_pct >= 0.05:
        explanations.append(f"Cena je {percent}% ispod tržišnog proseka.")
    elif saving_pct <= -0.05:
        explanations.append(f"Cena je {percent}% iznad tržišnog proseka.")
    else:
        explanations.append("Vozilo je u očekivanom cenovnom rasponu.")

    explanations.append(f"Pronađeno {len(prices)} sličnih vozila.")

    comparable_mileages = [item.mileage for item in comparables if item.mileage is not None]
    if listing.mileage is not None and comparable_mileages:
        avg_mileage = sum(comparable_mileages) / len(comparable_mileages)
        if listing.mileage < avg_mileage * 0.9:
            explanations.append("Kilometraža je niža od proseka.")
        elif listing.mileage > avg_mileage * 1.1:
            explanations.append("Kilometraža je viša od proseka.")

    if _price_spread_is_tight(prices):
        explanations.append("Tržišni raspon je stabilan za ovu grupu vozila.")
    return explanations[:4]


def _similar_year_share(listing: Listing, comparables: list[Listing]) -> float:
    if not listing.year:
        return 0
    with_year = [item for item in comparables if item.year]
    if not with_year:
        return 0
    similar = [item for item in with_year if abs(item.year - listing.year) <= 2]
    return len(similar) / len(with_year)


def _similar_mileage_share(listing: Listing, comparables: list[Listing]) -> float:
    if listing.mileage is None:
        return 0
    with_mileage = [item for item in comparables if item.mileage is not None]
    if not with_mileage:
        return 0
    mileage_delta = max(30_000, int(listing.mileage * 0.3))
    similar = [item for item in with_mileage if abs(item.mileage - listing.mileage) <= mileage_delta]
    return len(similar) / len(with_mileage)


def _price_spread_is_tight(prices: list[float]) -> bool:
    if len(prices) < MIN_COMPARABLES:
        return False
    med = median(prices)
    return med > 0 and ((_percentile(prices, 0.75) - _percentile(prices, 0.25)) / med) <= 0.25


def _insufficient(
    asking_price: float | None,
    comparable_count: int = 0,
    year_range: dict[str, int | None] | None = None,
    mileage_range: dict[str, int | None] | None = None,
) -> dict[str, Any]:
    year_range = year_range or {"min": None, "max": None}
    mileage_range = mileage_range or {"min": None, "max": None}
    return PurchaseRatingResult(
        rating="INSUFFICIENT_DATA",
        label=LABELS["INSUFFICIENT_DATA"],
        asking_price=_round_money(asking_price) if asking_price is not None else None,
        estimated_market_value=None,
        potential_saving=None,
        comparable_count=comparable_count,
        median_price=None,
        p25_price=None,
        p75_price=None,
        confidence_percent=0,
        market_low=None,
        market_high=None,
        comparable_year_range=year_range,
        comparable_mileage_range=mileage_range,
        debug={
            "comparable_count": comparable_count,
            "median": None,
            "p25": None,
            "p75": None,
            "year_range": year_range,
            "mileage_range": mileage_range,
        },
        explanations=["Nema dovoljno sličnih vozila za pouzdanu procenu."],
    ).as_dict()


def _range(values: list[int | None]) -> dict[str, int | None]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {"min": None, "max": None}
    return {"min": min(clean), "max": max(clean)}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _same(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return str(left).strip().lower() == str(right).strip().lower()


def _money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_money(value: float) -> float:
    return float(round(value / 100) * 100)
