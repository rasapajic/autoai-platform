"""
AutoAI Valuation Engine
Weighted median pricing with confidence scoring.
Replaces the raw SQL PERCENTILE_CONT approach.
"""

import psycopg2
import os
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValuationResult:
    market_value: Optional[float]
    range_low: Optional[float]
    range_high: Optional[float]
    confidence: int  # 0-100
    sample_size: int
    valid_comparables: int
    explanation: str
    warning: Optional[str]
    decision_trace: dict


def _mileage_similarity(base_km: int, comp_km: int) -> float:
    if base_km <= 0 or comp_km <= 0:
        return 0.7  # nepoznato — neutralna težina
    diff = abs(base_km - comp_km) / base_km
    if diff <= 0.10:
        return 1.0
    if diff <= 0.20:
        return 0.9
    if diff <= 0.30:
        return 0.75
    if diff <= 0.50:
        return 0.55
    return 0.3


def _year_similarity(base_year: int, comp_year: int) -> float:
    diff = abs(base_year - comp_year)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.9
    if diff == 2:
        return 0.75
    return 0.5


def _country_similarity(base_country: str, comp_country: str) -> float:
    if not base_country or not comp_country:
        return 0.8
    if base_country.upper() == comp_country.upper():
        return 1.0
    # Isti jezički/ekonomski blok
    dach = {'DE', 'AT', 'CH'}
    benelux = {'NL', 'BE', 'LU'}
    nordic = {'SE', 'NO', 'DK', 'FI'}
    eastern = {'PL', 'CZ', 'SK', 'HU', 'RO', 'RS'}
    for group in [dach, benelux, nordic, eastern]:
        if base_country.upper() in group and comp_country.upper() in group:
            return 0.85
    return 0.65


def _body_similarity(base_body: str, comp_body: str) -> float:
    if not base_body or not comp_body:
        return 0.85
    if base_body.lower() == comp_body.lower():
        return 1.0
    # Slični tipovi karoserije
    similar = [
        {'limousine', 'sedan', 'berlina', 'saloon'},
        {'kombi', 'estate', 'touring', 'avant', 'variant'},
        {'suv', 'crossover', 'geländewagen'},
        {'hatchback', 'schrägheck'},
    ]
    for group in similar:
        if base_body.lower() in group and comp_body.lower() in group:
            return 0.9
    return 0.6


def _age_weight(age_days: int) -> float:
    """Stari oglasi dobijaju manju, ali ne nultu težinu."""
    return max(0.5, 1.0 - age_days / 180.0)


def _iqr_bounds(prices: list[float]) -> tuple[float, float]:
    """Ukloni outliere pomoću IQR metode."""
    sorted_p = sorted(prices)
    n = len(sorted_p)
    q1 = sorted_p[int(n * 0.25)]
    q3 = sorted_p[int(n * 0.75)]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return lower, upper


def _weighted_median(values_weights: list[tuple[float, float]]) -> float:
    """Izračunaj weighted median."""
    if not values_weights:
        return 0.0
    sorted_vw = sorted(values_weights, key=lambda x: x[0])
    total_weight = sum(w for _, w in sorted_vw)
    cumulative = 0.0
    for value, weight in sorted_vw:
        cumulative += weight
        if cumulative >= total_weight / 2:
            return value
    return sorted_vw[-1][0]


def _confidence_score(
    sample_size: int,
    valid_count: int,
    price_spread_pct: float,
    has_body: bool,
    has_fuel: bool,
    has_mileage: bool,
) -> int:
    # Sample score (0-100)
    if sample_size >= 100:
        sample_score = 100
    elif sample_size >= 50:
        sample_score = 80
    elif sample_size >= 20:
        sample_score = 60
    elif sample_size >= 10:
        sample_score = 40
    else:
        sample_score = 20

    # Spread score — uži spread = viši confidence
    if price_spread_pct <= 15:
        spread_score = 100
    elif price_spread_pct <= 25:
        spread_score = 75
    elif price_spread_pct <= 40:
        spread_score = 50
    else:
        spread_score = 25

    # Comparator quality — koliko filtera imamo
    comp_quality = 50
    if has_body:
        comp_quality += 20
    if has_fuel:
        comp_quality += 15
    if has_mileage:
        comp_quality += 15

    # Metadata quality — valid / total ratio
    if sample_size > 0:
        meta_quality = min(100, int((valid_count / sample_size) * 100))
    else:
        meta_quality = 0

    confidence = int(
        sample_score * 0.35 +
        spread_score * 0.25 +
        comp_quality * 0.25 +
        meta_quality * 0.15
    )
    return max(0, min(100, confidence))


def estimate_price(
    conn,
    listing_id: str,
    make: str,
    model: str,
    year: int,
    mileage: int,
    fuel_type: str,
    body_type: str,
    country: str,
    current_price: float,
) -> ValuationResult:
    """
    Glavni entry point — procijeni tržišnu vrijednost oglasa.
    """
    NO_ESTIMATE = ValuationResult(
        market_value=None, range_low=None, range_high=None,
        confidence=0, sample_size=0, valid_comparables=0,
        explanation="Nedovoljno uporedivih oglasa.",
        warning="NO_ESTIMATE",
        decision_trace={}
    )

    if not make or not model or not year:
        return NO_ESTIMATE

    cur = conn.cursor()

    # 1. Dohvati kandidate — širi upit, filtriranje radimo u Pythonu
    cur.execute("""
        SELECT
            id, price, year, mileage, fuel_type, body_type, country,
            EXTRACT(DAY FROM NOW() - scraped_at)::int AS age_days
        FROM listings
        WHERE
            is_active = TRUE
            AND LOWER(make) = LOWER(%s)
            AND LOWER(model) = LOWER(%s)
            AND price IS NOT NULL
            AND price > 500
            AND price < 500000
            AND year IS NOT NULL
            AND ABS(year - %s) <= 3
            AND id != %s::uuid
        LIMIT 500
    """, (make, model, year, listing_id))

    rows = cur.fetchall()
    cur.close()

    initial_count = len(rows)

    if initial_count == 0:
        return NO_ESTIMATE

    # 2. Inicijalni IQR filter na sirovim cijenama
    raw_prices = [float(r[1]) for r in rows]
    iqr_low, iqr_high = _iqr_bounds(raw_prices)
    rows = [r for r in rows if iqr_low <= float(r[1]) <= iqr_high]
    after_iqr = len(rows)

    # 3. Izračunaj težine i filtriraj slabe kandidate
    weighted_items = []
    rejected = 0

    for row in rows:
        _, price, comp_year, comp_km, comp_fuel, comp_body, comp_country, age_days = row
        price = float(price)
        comp_year = int(comp_year) if comp_year else year
        comp_km = int(comp_km) if comp_km else 0
        age_days = int(age_days) if age_days else 0

        w_year    = _year_similarity(year, comp_year)
        w_km      = _mileage_similarity(mileage or 0, comp_km)
        w_country = _country_similarity(country or '', comp_country or '')
        w_body    = _body_similarity(body_type or '', comp_body or '')
        w_age     = _age_weight(age_days)

        weight = w_year * w_km * w_country * w_body * w_age

        # Odbaci ako je težina previše niska
        if weight < 0.15:
            rejected += 1
            continue

        weighted_items.append((price, weight))

    valid_count = len(weighted_items)

    if valid_count < 10:
        return ValuationResult(
            market_value=None, range_low=None, range_high=None,
            confidence=0, sample_size=initial_count, valid_comparables=valid_count,
            explanation=f"Samo {valid_count} uporedivih oglasa — premalo za procenu.",
            warning="LOW_SAMPLE",
            decision_trace={
                "initial_sql": initial_count,
                "after_iqr": after_iqr,
                "rejected_low_weight": rejected,
                "valid": valid_count,
            }
        )

    # 4. Weighted median
    market_value = _weighted_median(weighted_items)

    # 5. Range — p25 i p75 od weighted skupa
    sorted_prices = sorted([p for p, _ in weighted_items])
    n = len(sorted_prices)
    range_low  = sorted_prices[int(n * 0.25)]
    range_high = sorted_prices[int(n * 0.75)]

    # 6. Spread
    spread_pct = ((range_high - range_low) / market_value * 100) if market_value > 0 else 100

    # 7. Confidence
    confidence = _confidence_score(
        sample_size=initial_count,
        valid_count=valid_count,
        price_spread_pct=spread_pct,
        has_body=bool(body_type),
        has_fuel=bool(fuel_type),
        has_mileage=bool(mileage),
    )

    # 8. Zaštita — ako SQL procjena odlazi >35% od weighted mediane, ignoriši je
    deviation_from_current = abs(current_price - market_value) / market_value * 100 if market_value > 0 else 0

    warning = None
    if valid_count < 20:
        warning = "Low confidence — mali uzorak"
    elif spread_pct > 25:
        warning = "Širok raspon cijena na tržištu"

    # 9. Price rating
    delta_pct = ((current_price - market_value) / market_value * 100) if market_value > 0 else 0
    if delta_pct < -10:
        rating_label = "great"
    elif delta_pct < -3:
        rating_label = "good"
    elif delta_pct <= 5:
        rating_label = "fair"
    elif delta_pct <= 15:
        rating_label = "high"
    else:
        rating_label = "overpriced"

    # Ako confidence < 50 i devijacija > 35% — ne prikazuj procenu
    if confidence < 50 and deviation_from_current > 35:
        warning = "Procena nije pouzdana — ignoriši"
        return ValuationResult(
            market_value=None, range_low=None, range_high=None,
            confidence=confidence, sample_size=initial_count,
            valid_comparables=valid_count,
            explanation="Nedovoljno pouzdani podaci za procenu.",
            warning=warning,
            decision_trace={
                "initial_sql": initial_count,
                "after_iqr": after_iqr,
                "rejected_low_weight": rejected,
                "valid": valid_count,
                "weighted_median": round(market_value, 0),
                "deviation_from_listing_pct": round(deviation_from_current, 1),
                "confidence": confidence,
                "ignored": True,
            }
        )

    explanation = (
        f"Procena bazirana na {valid_count} uporedivih oglasa "
        f"(od {initial_count} kandidata). "
        f"Delta: {delta_pct:+.1f}% od tržišne vrednosti."
    )

    return ValuationResult(
        market_value=round(market_value, 0),
        range_low=round(range_low, 0),
        range_high=round(range_high, 0),
        confidence=confidence,
        sample_size=initial_count,
        valid_comparables=valid_count,
        explanation=explanation,
        warning=warning,
        decision_trace={
            "initial_sql": initial_count,
            "after_iqr": after_iqr,
            "rejected_low_weight": rejected,
            "valid": valid_count,
            "weighted_median": round(market_value, 0),
            "range": f"{round(range_low,0)}–{round(range_high,0)}",
            "spread_pct": round(spread_pct, 1),
            "delta_pct": round(delta_pct, 1),
            "price_rating": rating_label,
            "confidence": confidence,
            "deviation_from_listing_pct": round(deviation_from_current, 1),
        }
    )


def run_price_estimation(database_url: str):
    """
    Pokreni procenu za sve aktivne oglase koji imaju cenu.
    Zamenjuje stari SQL PERCENTILE_CONT pristup.
    """
    print("\n=== PRICE ESTIMATION (Valuation Engine) ===")
    conn = get_conn(database_url)
    cur = conn.cursor()

    # Dohvati sve oglase koje treba procijeniti
    cur.execute("""
        SELECT id, make, model, year, mileage, fuel_type, body_type, country, price
        FROM listings
        WHERE is_active = TRUE
          AND price IS NOT NULL
          AND price > 0
          AND make IS NOT NULL
          AND model IS NOT NULL
        ORDER BY scraped_at DESC
        LIMIT 5000
    """)
    listings = cur.fetchall()
    cur.close()

    print(f"  Oglasi za procenu: {len(listings)}")

    updated = 0
    skipped = 0
    errors = 0

    for row in listings:
        lid, make, model, year, mileage, fuel_type, body_type, country, price = row
        try:
            result = estimate_price(
                conn=conn,
                listing_id=str(lid),
                make=make or '',
                model=model or '',
                year=int(year) if year else 0,
                mileage=int(mileage) if mileage else 0,
                fuel_type=fuel_type or '',
                body_type=body_type or '',
                country=country or '',
                current_price=float(price),
            )

            if result.market_value is None:
                skipped += 1
                continue

            delta_pct = result.decision_trace.get('delta_pct', 0)
            price_rating = result.decision_trace.get('price_rating')

            cur2 = conn.cursor()
            cur2.execute("""
                UPDATE listings SET
                    price_estimated = %s,
                    price_delta_pct = %s,
                    price_rating = %s
                WHERE id = %s
            """, (
                result.market_value,
                round(delta_pct, 1),
                price_rating,
                str(lid),
            ))
            conn.commit()
            cur2.close()
            updated += 1

        except Exception as e:
            errors += 1
            conn.rollback()
            if errors <= 5:
                print(f"  Greška za {make} {model}: {e}")

    conn.close()
    print(f"  Ažurirano: {updated} | Preskočeno: {skipped} | Greške: {errors}")
    return updated


def get_conn(database_url: str):
    return psycopg2.connect(database_url)
