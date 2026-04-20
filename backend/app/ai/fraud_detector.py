import anthropic
import json
import re
import logging
from dataclasses import dataclass

from app.core.config import settings
from app.models import Listing

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


@dataclass
class FraudScore:
    score:       int          # 0-100 (100 = sigurno prevara)
    risk_level:  str          # "low", "medium", "high", "critical"
    red_flags:   list[str]    # konkretni razlozi
    safe_signals: list[str]   # pozitivni znaci


def check_listing_fraud(listing: Listing) -> FraudScore:
    """
    Kombinovana provera oglasa — brza heuristika + AI za sumnjive slučajeve.
    Brza heuristika ne troši API, AI samo za sumnjive.
    """
    flags = []
    safe = []

    # ── Brza heuristika (bez API-ja) ─────────────────────────

    # 1. Cena previše niska
    if listing.price and listing.price_estimated:
        ratio = float(listing.price) / float(listing.price_estimated)
        if ratio < 0.4:
            flags.append(f"Cena je {int((1-ratio)*100)}% ispod tržišne vrednosti")
        elif ratio < 0.65:
            flags.append("Cena je značajno ispod tržišne vrednosti")
        else:
            safe.append("Cena je u realnom opsegu")

    # 2. Sumnjivi telefoni/linkovi u opisu
    if listing.description:
        desc = listing.description.lower()
        if re.search(r'whatsapp|telegram|viber', desc):
            flags.append("Kontakt samo preko messaging aplikacija")
        if re.search(r'western union|moneygram|bitcoin|crypto', desc):
            flags.append("Sumnjiv način plaćanja")
        if re.search(r'http[s]?://', desc):
            flags.append("Sumnjivi linkovi u opisu")
        if re.search(r'military|deployed|abroad|africa|nigeria', desc):
            flags.append("Klasična 'vojnik u inostranstvu' prevara")

    # 3. Premalo slika
    if listing.images:
        if len(listing.images) < 2:
            flags.append("Premalo fotografija vozila")
        elif len(listing.images) >= 5:
            safe.append("Dobar broj fotografija")

    # 4. Staro vozilo, nerealno niska km
    if listing.year and listing.mileage:
        age = 2025 - listing.year
        if age > 5 and listing.mileage < 10000:
            flags.append(f"Neobično niska kilometraža za {age}-godišnje vozilo")

    # 5. Nema URL
    if not listing.url or "example.com" in listing.url:
        flags.append("Neispravan ili nedostaje link na oglas")
    else:
        safe.append("Oglas ima verifikovan link")

    # ── Izračunaj score ───────────────────────────────────────
    score = min(len(flags) * 20, 100)

    if score == 0:
        risk_level = "low"
    elif score <= 20:
        risk_level = "low"
    elif score <= 40:
        risk_level = "medium"
    elif score <= 60:
        risk_level = "high"
    else:
        risk_level = "critical"

    # AI analiza samo za visoko sumnjive oglase (štedi API pozive)
    if score >= 40 and listing.description and len(listing.description) > 50:
        ai_flags = _ai_fraud_check(listing)
        flags.extend(ai_flags)
        score = min(score + len(ai_flags) * 15, 100)

        if score >= 60:
            risk_level = "high"
        if score >= 80:
            risk_level = "critical"

    return FraudScore(
        score=score,
        risk_level=risk_level,
        red_flags=flags,
        safe_signals=safe,
    )


def _ai_fraud_check(listing: Listing) -> list[str]:
    """AI proverava opis oglasa na znakove prevare."""
    try:
        prompt = f"""Analiziraj ovaj oglas polovnog automobila i pronađi znakove prevare.

Vozilo: {listing.make} {listing.model} {listing.year}, {listing.price} EUR
Opis: {listing.description[:500]}

Odgovori SAMO validnim JSON nizom stringova — lista konkretnih red flag-ova na srpskom.
Ako nema sumnjivog, vrati prazan niz [].

Primer: ["Prodavac insistira na plaćanju unapred", "Priča je neverovatna"]"""

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        response = message.content[0].text.strip()

        # Parsiranje JSON liste
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())

    except Exception as e:
        logger.warning(f"AI fraud check greška: {e}")

    return []


def get_risk_badge(risk_level: str) -> dict:
    """Vraća boju i tekst za UI badge."""
    badges = {
        "low":      {"color": "#22c55e", "text": "✅ Izgleda OK",      "emoji": "✅"},
        "medium":   {"color": "#f59e0b", "text": "⚠️ Provjeri detalje", "emoji": "⚠️"},
        "high":     {"color": "#ef4444", "text": "🚨 Sumnjivo",         "emoji": "🚨"},
        "critical": {"color": "#7f1d1d", "text": "🔴 Visoki rizik",     "emoji": "🔴"},
    }
    return badges.get(risk_level, badges["medium"])
