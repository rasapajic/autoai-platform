"""Explainable, read-only triage of one offer; never a vehicle inspection."""
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import median
from itertools import islice
from urllib.parse import urlsplit

FRESH_DAYS = 7
MAX_CANDIDATES = 200
MIN_SAMPLE = 10
IDENTITY_FIELDS = ("make", "model", "fuel_type", "transmission", "body_type", "country")
FIELD_LABELS = {
    "make": "marka", "model": "model", "year": "godište", "mileage": "kilometraža",
    "fuel_type": "gorivo", "transmission": "menjač", "engine_power_kw": "snaga",
    "body_type": "karoserija", "country": "država",
}


def value(row, key):
    return row.get(key) if hasattr(row, "get") else getattr(row, key, None)


def number(raw):
    if raw is None or isinstance(raw, bool):
        return None
    try:
        result = float(raw)
        return result if isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def label(raw):
    return str(raw if raw is not None else "").strip().casefold()


def damage_reported(listing):
    return value(listing, "accident_free") is False or label(value(listing, "condition")) in {
        "damaged", "accident", "accident_damaged", "unfallwagen", "beschädigt", "ostecen", "oštećen",
    }


def fresh(raw, now):
    try:
        date = raw if isinstance(raw, datetime) else datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return bool(date.tzinfo and now - timedelta(days=FRESH_DAYS) <= date <= now + timedelta(minutes=5))
    except (ValueError, TypeError, AttributeError):
        return False


def missing_fields(listing, now):
    missing = [FIELD_LABELS[k] for k in IDENTITY_FIELDS if label(value(listing, k)) in {"", "unknown", "nepoznato"}]
    year, mileage, power = (number(value(listing, k)) for k in ("year", "mileage", "engine_power_kw"))
    for key, valid in (("year", year is not None and year.is_integer() and 1950 <= year <= now.year),
                       ("mileage", mileage is not None and 0 <= mileage <= 999999),
                       ("engine_power_kw", power is not None and 0 < power <= 2000)):
        if not valid:
            missing.append(FIELD_LABELS[key])
    return missing


def comparison_unavailable(reason):
    return {"available": False, "sample_size": 0, "reference_price": None, "delta_pct": None,
            "reason": reason, "freshness_days": FRESH_DAYS}


def url_identity(raw):
    try:
        parsed = urlsplit(str(raw or ""))
        return (parsed.hostname, parsed.path.rstrip("/")) if parsed.hostname else None
    except ValueError:
        return None


def vehicle_signature(row):
    return tuple(number(value(row, k)) for k in ("year", "mileage", "engine_power_kw", "price")) + (label(value(row, "variant")), number(value(row, "engine_cc")))


def compare_offer(listing, candidates, now):
    missing = missing_fields(listing, now)
    if missing:
        return comparison_unavailable("Za poređenje nedostaju pouzdani osnovni podaci: " + ", ".join(missing) + ".")
    price = number(value(listing, "price"))
    if price is None or price <= 0 or label(value(listing, "currency")) != "eur":
        return comparison_unavailable("Za poređenje je potrebna važeća cena u evrima.")
    if not fresh(value(listing, "last_seen_at"), now):
        return comparison_unavailable("Ovaj oglas nije preuzet u poslednjih 7 dana; prvo proveri dostupnost i cenu na izvornom sajtu.")
    prices, signatures, urls, identities = [], {vehicle_signature(listing)}, set(), set()
    if url_identity(value(listing, "url")):
        urls.add(url_identity(value(listing, "url")))
    base_year, base_km, base_power = (number(value(listing, k)) for k in ("year", "mileage", "engine_power_kw"))
    km_window = max(5000, base_km * .20)
    for row in islice(candidates, MAX_CANDIDATES):
        if value(row, "id") == value(listing, "id") or value(row, "is_active") is not True:
            continue
        if not fresh(value(row, "last_seen_at"), now) or label(value(row, "currency")) != "eur":
            continue
        if any(label(value(row, k)) != label(value(listing, k)) for k in IDENTITY_FIELDS):
            continue
        year, km, power, candidate_price = (number(value(row, k)) for k in ("year", "mileage", "engine_power_kw", "price"))
        if (year is None or not year.is_integer() or not 1950 <= year <= now.year or abs(year-base_year) > 1
            or km is None or km < 0 or abs(km-base_km) > km_window
            or power is None or abs(power-base_power) > max(2, base_power * .05)
            or candidate_price is None or candidate_price <= 0):
            continue
        # A known trim, displacement, condition or damage history cannot silently change.
        if any(value(listing, k) is not None and label(value(listing, k)) != ""
               and label(value(row, k)) != label(value(listing, k))
               for k in ("variant", "engine_cc", "condition", "accident_free")):
            continue
        url = url_identity(value(row, "url"))
        identity = (value(row, "source"), value(row, "external_id"))
        signature = vehicle_signature(row)
        # Conservative suppression of repeated observations; not a VIN identity claim.
        if signature in signatures or url and url in urls or identity[1] and identity in identities:
            continue
        signatures.add(signature)
        if url:
            urls.add(url)
        if identity[1]:
            identities.add(identity)
        prices.append(candidate_price)
    count = len(prices)
    result = comparison_unavailable(f"Pronađeno je {count} dovoljno sličnih, skoro preuzetih oglasa; potrebno je najmanje {MIN_SAMPLE} za okvirno poređenje cene.")
    result["sample_size"] = count
    if count < MIN_SAMPLE:
        return result
    ordered = sorted(prices)
    reference = median(ordered)
    spread = (ordered[int(count*.75)] - ordered[int(count*.25)]) / reference * 100
    if spread > 25:
        result["reason"] = f"Cene {count} sličnih oglasa su previše rasute za pouzdano poređenje (srednji raspon {spread:.0f}%)."
        return result
    return {"available": True, "sample_size": count, "reference_price": round(reference, 2),
            "delta_pct": round((price/reference-1)*100, 1), "freshness_days": FRESH_DAYS,
            "reason": "Ista marka, model, država, gorivo, menjač i karoserija; godište ±1, kilometraža ±20% (najmanje ±5.000 km), snaga ±5% (najmanje ±2 kW). Poznata verzija, zapremina, stanje i istorija štete moraju da odgovaraju."}


def recommend_offer(listing, candidates=(), now=None, comparison_error=False):
    now = now or datetime.now(timezone.utc)
    comparison = comparison_unavailable("Poređenje cene trenutno nije dostupno. Pokušaj ponovo kasnije.") if comparison_error else compare_offer(listing, candidates, now)
    cautions = ["Podaci potiču iz oglasa; stanje vozila, servisna istorija i uslovi uvoza zahtevaju posebnu proveru."]
    if value(listing, "service_history") is not True:
        cautions.append("Nema potvrđene servisne dokumentacije.")
    if value(listing, "accident_free") is not True:
        cautions.append("Istorija oštećenja nije potvrđena.")
    if not label(value(listing, "variant")):
        cautions.append("Verzija i oprema nisu dovoljno opisane za potpuno poređenje.")
    if comparison["available"]:
        cautions.append("Porede se tražene EU cene, bez troška uvoza. Mogući duplikati bez VIN-a nisu potpuno isključeni.")
    result = {"status": "verify", "title": "Prvo proveri podatke", "reason": comparison["reason"],
              "next_step": "Zatraži VIN, servisne račune i podatke o oštećenjima; proveri aktuelnu cenu na izvornom sajtu.",
              "confidence": "insufficient", "cautions": cautions, "comparison": comparison}
    if damage_reported(listing):
        result.update(title="Prvo proveri istoriju oštećenja", reason="U podacima oglasa navedena su oštećenja ili istorija udesa. Povoljna cena sama po sebi nije dovoljan razlog za kupovinu.",
                      next_step="Zatraži fotografije pre popravke, račune i nezavisan pregled pre odluke.")
        return result
    if value(listing, "service_history") is False:
        result.update(title="Prvo proveri održavanje", reason="U oglasu nije navedena servisna istorija. Bez dokaza o održavanju ne preporučujemo odluku o kupovini.",
                      next_step="Zatraži servisne račune i pregled ključnih sklopova kod nezavisnog servisera.")
        return result
    if not comparison["available"]:
        return result
    delta, count, reference = comparison["delta_pct"], comparison["sample_size"], comparison["reference_price"]
    relation = "ispod" if delta < 0 else "iznad"
    formatted_reference = f"{reference:,.0f}".replace(",", ".")
    price_reason = f"Tražena cena je {abs(delta):.1f}% {relation} medijane {count} sličnih oglasa ({formatted_reference} €)."
    result.update(confidence="limited", reason=price_reason)
    if delta < -20:
        result.update(title="Proveri razlog niske cene", next_step="Pre kontakta o uplati proveri VIN, oštećenja, dokumentaciju i prodavca; niska cena nije dokaz povoljne kupovine.")
    elif delta > 20:
        result.update(status="avoid", title="Preskoči po ovoj ceni", next_step="Traži obrazloženje razlike i uporedi opremu; razmotri druge ponude ili znatno nižu cenu.")
    elif delta > 5:
        result.update(status="negotiate", title="Pregovaraj o ceni", next_step="Uporedi opremu i dokumentaciju, pa koristi tržišno poređenje kao osnov za nižu ponudu.")
    else:
        result.update(status="consider", title="Vredi kontaktirati prodavca", next_step="Cena opravdava dalju proveru: zatraži VIN i dokumentaciju, zatim zakaži nezavisan pregled pre kupovine.")
    return result
