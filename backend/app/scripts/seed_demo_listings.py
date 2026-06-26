from datetime import datetime, timedelta
from decimal import Decimal

from app.core.db import SessionLocal
from app.models import Listing, PriceHistory


SOURCE = "demo_seed"

COUNTRIES = [
    ("DE", "Munich"),
    ("DE", "Berlin"),
    ("DE", "Hamburg"),
    ("AT", "Vienna"),
    ("AT", "Graz"),
    ("AT", "Linz"),
    ("RS", "Belgrade"),
    ("RS", "Novi Sad"),
]

VEHICLES = [
    ("BMW", "3 Series", "320d", "diesel", "sedan", "automatic", 140, 1995),
    ("BMW", "5 Series", "530d xDrive", "diesel", "sedan", "automatic", 195, 2993),
    ("Volkswagen", "Golf", "1.5 TSI", "petrol", "hatchback", "manual", 110, 1498),
    ("Volkswagen", "Passat", "2.0 TDI", "diesel", "kombi", "automatic", 147, 1968),
    ("Audi", "A4", "40 TDI", "diesel", "sedan", "automatic", 150, 1968),
    ("Audi", "Q5", "45 TFSI quattro", "petrol", "suv", "automatic", 195, 1984),
    ("Mercedes-Benz", "C-Class", "C 220 d", "diesel", "sedan", "automatic", 147, 1993),
    ("Mercedes-Benz", "E-Class", "E 300 e", "hybrid", "sedan", "automatic", 235, 1999),
    ("Toyota", "Corolla", "1.8 Hybrid", "hybrid", "sedan", "automatic", 90, 1798),
    ("Toyota", "RAV4", "2.5 Hybrid", "hybrid", "suv", "automatic", 160, 2487),
    ("Tesla", "Model 3", "Long Range", "electric", "sedan", "automatic", 366, 0),
    ("Tesla", "Model Y", "Performance", "electric", "suv", "automatic", 393, 0),
]

FEATURES = [
    "Navigation",
    "Adaptive cruise control",
    "Parking sensors",
    "Heated seats",
    "LED headlights",
    "Bluetooth",
    "Backup camera",
    "Lane assist",
]


def estimate_market_price(base_price: int, year: int, mileage: int, fuel_type: str) -> int:
    age = max(datetime.utcnow().year - year, 0)
    fuel_adjustment = {
        "diesel": 800,
        "petrol": 0,
        "hybrid": 1800,
        "electric": 4500,
    }.get(fuel_type, 0)
    estimated = base_price + fuel_adjustment - age * 1100 - int(mileage / 10000) * 350
    return max(round(estimated / 100) * 100, 4500)


def price_rating(delta_pct: float) -> str:
    if delta_pct < -15:
        return "great"
    if delta_pct < -5:
        return "good"
    if delta_pct < 5:
        return "fair"
    if delta_pct < 15:
        return "high"
    return "overpriced"


def build_listing(index: int, vehicle: tuple, country: tuple) -> dict:
    make, model, variant, fuel_type, body_type, transmission, power_kw, engine_cc = vehicle
    country_code, city = country
    year = 2016 + (index % 9)
    mileage = 12000 + ((index * 13750) % 210000)

    base_prices = {
        "BMW": 36000,
        "Volkswagen": 26000,
        "Audi": 39000,
        "Mercedes-Benz": 43000,
        "Toyota": 29000,
        "Tesla": 48000,
    }
    estimated = estimate_market_price(base_prices[make], year, mileage, fuel_type)
    delta_options = [-18, -9, -2, 4, 11, 19]
    delta_pct = delta_options[index % len(delta_options)]
    price = int(round((estimated * (1 + delta_pct / 100)) / 100) * 100)

    return {
        "external_id": f"DEMO-{index:03d}",
        "source": SOURCE,
        "make": make,
        "model": model,
        "variant": variant,
        "year": year,
        "price": Decimal(price),
        "currency": "EUR",
        "price_negotiable": index % 4 == 0,
        "mileage": mileage,
        "fuel_type": fuel_type,
        "transmission": transmission,
        "engine_cc": engine_cc,
        "engine_power_kw": power_kw,
        "body_type": body_type,
        "color": ["black", "white", "silver", "blue", "gray", "red"][index % 6],
        "doors": 5 if body_type in ("suv", "hatchback", "kombi") else 4,
        "seats": 5,
        "country": country_code,
        "city": city,
        "condition": "used",
        "owners_count": 1 + (index % 3),
        "service_history": index % 5 != 0,
        "accident_free": index % 7 != 0,
        "description": (
            "DEMO DATA - realistic local MVP test listing. "
            f"{year} {make} {model} {variant}, {fuel_type}, {city}."
        ),
        "images": [],
        "features": FEATURES[: 3 + (index % 5)],
        "url": f"https://example.com/demo-listings/{index:03d}",
        "is_active": True,
        "price_estimated": Decimal(estimated),
        "price_delta_pct": Decimal(str(delta_pct)),
        "price_rating": price_rating(delta_pct),
    }


def seed_demo_listings() -> dict:
    db = SessionLocal()
    created = 0
    updated = 0

    try:
        index = 1
        for country in COUNTRIES:
            for vehicle in VEHICLES:
                data = build_listing(index, vehicle, country)
                listing = db.query(Listing).filter(
                    Listing.external_id == data["external_id"]
                ).first()

                if listing:
                    for key, value in data.items():
                        setattr(listing, key, value)
                    listing.last_seen_at = datetime.utcnow()
                    updated += 1
                else:
                    listing = Listing(**data)
                    db.add(listing)
                    db.flush()
                    created += 1

                db.query(PriceHistory).filter(
                    PriceHistory.listing_id == listing.id
                ).delete()
                db.add(PriceHistory(
                    listing_id=listing.id,
                    price=Decimal(int(float(data["price"]) * 1.04)),
                    currency="EUR",
                    recorded_at=datetime.utcnow() - timedelta(days=21),
                ))
                db.add(PriceHistory(
                    listing_id=listing.id,
                    price=data["price"],
                    currency="EUR",
                    recorded_at=datetime.utcnow(),
                ))

                index += 1

        db.commit()
        total = db.query(Listing).filter(Listing.source == SOURCE).count()
        return {"created": created, "updated": updated, "total_demo_listings": total}
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_demo_listings()
    print(
        "Demo listings seeded: "
        f"created={result['created']}, "
        f"updated={result['updated']}, "
        f"total={result['total_demo_listings']}"
    )
