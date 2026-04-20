import anthropic
import json
import logging
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class ImportCalcRequest(BaseModel):
    price_eur:      float           # cena auta
    year:           int             # godina
    engine_cc:      Optional[int]   # kubikaza
    fuel_type:      Optional[str]   # diesel/petrol/electric
    from_country:   str             # "DE", "AT", "FR"...
    to_country:     str = "RS"      # uvoz u Srbiju (default)


class ImportCalcResponse(BaseModel):
    price_eur:          float
    customs_duty_eur:   float
    vat_eur:            float
    excise_tax_eur:     float
    transport_est_eur:  float
    registration_est_eur: float
    total_cost_eur:     float
    total_cost_rsd:     float
    breakdown:          list[dict]
    notes:              list[str]


# Carinski propisi po zemlji odredišta
IMPORT_RULES = {
    "RS": {
        "name": "Srbija",
        "currency": "RSD",
        "eur_rate": 117.0,
        "customs_rate": 0.0,       # Srbija ima CEFTA/sporazume - 0% za EU auta
        "vat_rate": 0.20,          # PDV 20%
        "excise_base_rate": 0.10,  # akciza base
        "registration_est": 300,   # EUR procena
        "transport_from": {
            "DE": 500, "AT": 350, "FR": 700,
            "IT": 600, "NL": 650, "BE": 650,
            "PL": 400, "CZ": 350, "SK": 300,
            "HU": 250, "HR": 150, "SI": 200,
        },
        "notes": [
            "Carina 0% za vozila uvezena iz EU (CEFTA/SAA sporazum)",
            "PDV 20% se plaća na cenu + carina + akciza",
            "Akciza zavisi od kubikaze i starosti vozila",
            "Obavezna homologacija ako vozilo nije već EU-homologovano",
        ]
    },
    "HR": {
        "name": "Hrvatska",
        "currency": "EUR",
        "eur_rate": 1.0,
        "customs_rate": 0.0,
        "vat_rate": 0.25,
        "excise_base_rate": 0.05,
        "registration_est": 400,
        "transport_from": {"DE": 400, "AT": 200, "FR": 600},
        "notes": ["EU zemlja — nema carine unutar EU"],
    },
}


def calculate_import_cost(req: ImportCalcRequest) -> ImportCalcResponse:
    """
    Izračunava ukupne troškove uvoza vozila.
    Koristi AI za kompleksne poreske kalkulacije i aktuelne propise.
    """
    rules = IMPORT_RULES.get(req.to_country, IMPORT_RULES["RS"])

    # ── Osnovna kalkulacija ───────────────────────────────────
    customs = req.price_eur * rules["customs_rate"]
    base_for_vat = req.price_eur + customs

    # Akciza — zavisi od kubikaze i starosti
    excise = _calculate_excise_rs(req) if req.to_country == "RS" else 0

    vat = (base_for_vat + excise) * rules["vat_rate"]
    transport = rules["transport_from"].get(req.from_country, 600)
    registration = rules["registration_est"]

    total_eur = req.price_eur + customs + excise + vat + transport + registration
    total_rsd = total_eur * rules["eur_rate"]

    breakdown = [
        {"stavka": "Cena vozila",      "eur": req.price_eur,  "procenat": ""},
        {"stavka": "Carina",           "eur": customs,        "procenat": f"{rules['customs_rate']*100:.0f}%"},
        {"stavka": "Akciza",           "eur": excise,         "procenat": ""},
        {"stavka": "PDV",              "eur": vat,            "procenat": f"{rules['vat_rate']*100:.0f}%"},
        {"stavka": "Transport (proc.)", "eur": transport,     "procenat": ""},
        {"stavka": "Registracija (proc.)", "eur": registration, "procenat": ""},
        {"stavka": "UKUPNO",           "eur": total_eur,      "procenat": f"+{((total_eur/req.price_eur)-1)*100:.0f}%"},
    ]

    return ImportCalcResponse(
        price_eur=req.price_eur,
        customs_duty_eur=round(customs, 2),
        vat_eur=round(vat, 2),
        excise_tax_eur=round(excise, 2),
        transport_est_eur=round(transport, 2),
        registration_est_eur=round(registration, 2),
        total_cost_eur=round(total_eur, 2),
        total_cost_rsd=round(total_rsd, 2),
        breakdown=breakdown,
        notes=rules["notes"],
    )


def _calculate_excise_rs(req: ImportCalcRequest) -> float:
    """
    Akciza u Srbiji — zavisi od kubikaze, goriva i starosti.
    Ovo su aproksimativne vrednosti, zakoni se menjaju!
    """
    from datetime import datetime
    age = datetime.now().year - req.year

    cc = req.engine_cc or 1600

    # Električna vozila — nema akcize
    if req.fuel_type == "electric":
        return 0.0

    # Osnovna stopa po kubikazi (EUR)
    if cc <= 1400:
        base = 0
    elif cc <= 2000:
        base = req.price_eur * 0.03
    elif cc <= 3000:
        base = req.price_eur * 0.05
    else:
        base = req.price_eur * 0.07

    # Starija vozila plaćaju više
    if age > 10:
        base *= 1.5
    elif age > 5:
        base *= 1.2

    return round(base, 2)


async def ai_import_advisor(
    vehicle_description: str,
    from_country: str,
    to_country: str = "RS",
) -> str:
    """
    AI savetnik za uvoz — odgovara na specifična pitanja o uvozu
    koristeći aktuelne propise.
    """
    prompt = f"""Korisnik pita o uvozu vozila iz {from_country} u {to_country}.

Vozilo: {vehicle_description}

Odgovori kratko i praktično na srpskom jeziku:
1. Koji dokumenti su potrebni
2. Koji su koraci uvoza
3. Na šta treba paziti
4. Procena ukupnih troškova pored cene vozila

Budi konkretan i praktičan. Max 200 reči."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
